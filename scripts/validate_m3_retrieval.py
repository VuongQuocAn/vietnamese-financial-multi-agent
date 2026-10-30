"""M3-07 deterministic persisted retrieval evaluation; zero extraction/API calls."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DerivedMetric,
    DocumentEvidenceRepository,
    EvidenceGraph,
    EvidenceQuery,
    EvidenceRetrieval,
    RetrievalReference,
    RetrievalResult,
    build_graph,
    facts_from_persisted_result,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    baseline_path = root / "artifacts/evidence/M3-06/review-final/report.json"
    baseline = load(baseline_path)
    hashes, source_aliases = {}, {}
    for name, expected in baseline["source_hashes"].items():
        path = root / name
        if not path.is_file() and path.suffix == ".pdf":
            candidates = [p for p in path.parent.glob("*.pdf") if digest(p) == expected]
            assert len(candidates) == 1, "Missing/ambiguous inventory PDF content"
            path = candidates[0]
            source_aliases[name] = path.relative_to(root).as_posix()
        assert digest(path) == expected, "M3-06 inputs changed; review inventory first"
        hashes[path.relative_to(root).as_posix()] = expected
    hashes[baseline_path.relative_to(root).as_posix()] = digest(baseline_path)
    metrics_path = root / "artifacts/evidence/M3-05/review-final/metrics.json"
    metrics = TypeAdapter(list[DerivedMetric]).validate_json(
        metrics_path.read_text(encoding="utf-8")
    )
    hashes[metrics_path.relative_to(root).as_posix()] = digest(metrics_path)
    facts, evidence, repos, docs, scopes = [], [], [], [], {}
    for family in ("storage", "fresh-storage"):
        source = list((root / f"artifacts/w07/{family}").rglob("result.json"))
        assert len(source) == 1
        payload = load(source[0])
        scopes[family] = dict(document_id=payload["document_id"], snapshot_id=payload["attempt_id"])
        repo = CanonicalFactRepository(root / f"artifacts/evidence/M3-04/final/{family}")
        document_repo = DocumentEvidenceRepository(
            root / f"artifacts/evidence/M3-03-real-validation/final/w07-{family}"
        )
        selected = repo.list_by_document(**scopes[family])
        assert sorted(f.model_dump_json() for f in selected) == sorted(
            f.model_dump_json() for f in facts_from_persisted_result(payload)
        )
        facts.extend(selected)
        evidence.extend(document_repo.list_by_document(**scopes[family]))
        repos.append(repo)
        docs.append(document_repo)
    coverage = []
    historical = {}
    for row in baseline["inventory"]:
        if row["year"] < 2025:
            assert row["financial_extraction"] == "not_found" and not row["canonical_catalogs"]
            # Explicit content identity for inventory-only PDF; never inferred company/period.
            historical[row["year"]] = "pdf-sha256:" + row["sha256"]
            coverage.append(
                CanonicalCoverage(
                    document_id=historical[row["year"]],
                    canonical_extraction="missing",
                    inventory_reference="M3-06:review-final:inventory",
                )
            )
    for scope in scopes.values():
        assert not any(f.canonical_item_id == "b01.total_liabilities" for f in facts)
        coverage.append(
            CanonicalCoverage(
                **scope,
                canonical_extraction="available",
                missing_canonical_items=["b01.total_liabilities"],
                inventory_reference="M3-06:liabilities-mapping-gap",
            )
        )
    graph = build_graph(facts, evidence, metrics)
    api = EvidenceRetrieval(facts, evidence, metrics, graph=graph, coverage=coverage)

    def query(family, item, period):
        return EvidenceQuery(**scopes[family], canonical_item_id=item, period=period)

    fresh = "fresh-storage"
    revenue = next(
        f
        for f in facts
        if f.document_id == scopes[fresh]["document_id"]
        and f.snapshot_id == scopes[fresh]["snapshot_id"]
        and f.canonical_item_id == "b02.net_revenue"
        and f.context.period == "2025"
    )
    storage_revenue = next(
        f
        for f in facts
        if f.document_id == scopes["storage"]["document_id"]
        and f.snapshot_id == scopes["storage"]["snapshot_id"]
        and f.canonical_item_id == "b02.net_revenue"
        and f.context.period == "2025"
    )
    text = next(e for e in evidence if e.kind == "text")
    table = next(e for e in evidence if e.kind == "table")
    metric = next(
        m
        for m in metrics
        if m.request.document_id == scopes[fresh]["document_id"]
        and m.request.snapshot_id == scopes[fresh]["snapshot_id"]
        and m.definition.name == "gross_margin"
    )
    # Fixed query categories and expectations declared BEFORE execution; no selecting PASS rows.
    cases = [
        ("Q01", "find_facts", query(fresh, "b01.total_assets", "2025-12-31"), "found", 1),
        ("Q02", "find_facts", query(fresh, "b02.net_revenue", "2025"), "found", 1),
        ("Q03", "find_facts", query(fresh, "b02.gross_profit", "2025"), "found", 1),
        ("Q04", "find_facts", query(fresh, "b01.cash_equivalents", "2025-12-31"), "found", 1),
        (
            "Q05",
            "find_facts",
            EvidenceQuery(**scopes[fresh], canonical_item_id="b02.net_revenue"),
            "ambiguous",
            2,
        ),
        (
            "Q06",
            "find_facts",
            EvidenceQuery(**scopes[fresh], canonical_item_id="b01.total_assets"),
            "ambiguous",
            2,
        ),
        (
            "Q07",
            "find_facts",
            EvidenceQuery(canonical_item_id="b02.net_revenue", period="2025"),
            "ambiguous",
            2,
        ),
        ("Q08", "get_fact", storage_revenue.observation_identity(), "found", 1),
        (
            "Q09",
            "get_sources",
            RetrievalReference(kind="fact", observation=revenue.observation_identity()),
            "found",
            1,
        ),
        ("Q10", "get_evidence", text.evidence_identity(), "found", 1),
        ("Q11", "get_evidence", table.evidence_identity(), "found", 1),
        ("Q12", "get_metric", metric.metric_id, "found", 1),
        ("Q13", "get_lineage", metric.metric_id, "found", 1),
        (
            "Q14",
            "find_facts",
            query(fresh, "b01.total_liabilities", "2025-12-31"),
            "unavailable",
            0,
        ),
        (
            "Q15",
            "find_facts",
            EvidenceQuery(
                document_id=historical[2022], canonical_item_id="b02.net_revenue", period="2022"
            ),
            "unavailable",
            0,
        ),
        (
            "Q16",
            "get_fact",
            revenue.observation_identity().model_copy(update={"local_id": "nonexistent"}),
            "not_found",
            0,
        ),
        ("Q17", "find_facts", query(fresh, "b02.net_revenue", "2023"), "not_found", 0),
        ("Q18", "get_fact", revenue.observation_identity(), "found", 1),
    ]
    rows = []
    for qid, method, argument, expected, count in cases:
        result = getattr(api, method)(argument)
        passed = result.status == expected and len(result.matches) == count
        if qid == "Q08":
            passed &= result.matches[0].display_status == "blocked"
        if qid == "Q13":
            passed &= result.matches[0].record.completeness == "complete"
            passed &= result.matches[0].record.compatibility.status == "undetermined"
        reasons = {
            "Q14": "canonical_mapping_missing",
            "Q15": "canonical_extraction_missing",
            "Q16": "no_matching_fact",
            "Q17": "missing_period",
        }
        if qid in reasons:
            passed &= reasons[qid] in result.reasons
        if qid == "Q18":
            passed &= all(c.provenance_level == "page" for c in result.matches[0].citations)
            passed &= any(
                "source_reference_uncertain" in c.limitations for c in result.matches[0].citations
            )
        rows.append(
            dict(
                query_id=qid,
                method=method,
                filters=argument.model_dump(mode="json")
                if hasattr(argument, "model_dump")
                else argument,
                expected_status=expected,
                expected_matches=count,
                passed=passed,
                actual=result.model_dump(mode="json"),
                limitations=["retrieval_consistency_only", "not_pdf_factual_verification"],
            )
        )

    exact = [api.get_fact(f.observation_identity()) for f in facts]
    assert all(
        r.status == "found" and r.matches[0].record == f for r, f in zip(exact, facts, strict=True)
    )
    assert all(RetrievalResult.model_validate_json(r.model_dump_json()) == r for r in exact)
    atomic_json(output / "graph.json", graph.model_dump(mode="json"))
    restarted = EvidenceRetrieval.from_repositories(
        [CanonicalFactRepository(r.root) for r in repos],
        [DocumentEvidenceRepository(r.root) for r in docs],
        [s["document_id"] for s in scopes.values()],
        metrics=TypeAdapter(list[DerivedMetric]).validate_json(
            metrics_path.read_text(encoding="utf-8")
        ),
        graph=EvidenceGraph.model_validate_json(
            (output / "graph.json").read_text(encoding="utf-8")
        ),
        coverage=coverage,
    )
    for _, method, argument, _, _ in cases:
        assert (
            getattr(api, method)(argument).model_dump_json()
            == getattr(restarted, method)(argument).model_dump_json()
        )
    assert all(
        api.get_fact(f.observation_identity()).model_dump_json()
        == restarted.get_fact(f.observation_identity()).model_dump_json()
        for f in facts
    )
    questions = []
    question_specs = [
        ("Tổng tài sản cuối kỳ 2025", [("b01.total_assets", "2025-12-31")]),
        ("Doanh thu thuần 2025", [("b02.net_revenue", "2025")]),
        ("Lợi nhuận gộp 2025", [("b02.gross_profit", "2025")]),
        ("Tiền và tương đương tiền cuối kỳ", [("b01.cash_equivalents", "2025-12-31")]),
        (
            "Doanh thu 2024 và 2025 trong filing 2025",
            [("b02.net_revenue", "2024"), ("b02.net_revenue", "2025")],
        ),
        (
            "Tổng tài sản đầu và cuối kỳ",
            [("b01.total_assets", "2025-01-01"), ("b01.total_assets", "2025-12-31")],
        ),
    ]
    for family in scopes:
        for question, selectors in question_specs:
            results = [api.find_facts(query(family, item, period)) for item, period in selectors]
            complete = all(
                r.status == "found"
                and r.matches[0].display_status == "display_with_caveat"
                and r.matches[0].citations
                for r in results
            )
            questions.append(
                dict(
                    question=question,
                    scope=family,
                    answer_data_status="complete_with_caveat"
                    if complete
                    else "partial_quality_blocked",
                    results=[r.model_dump(mode="json") for r in results],
                )
            )
    for qid in ("Q14", "Q15"):
        questions.append(
            dict(
                question=qid,
                answer_data_status="canonical_unavailable",
                results=[next(r["actual"] for r in rows if r["query_id"] == qid)],
            )
        )
    assert all(digest(root / p) == sha for p, sha in hashes.items())
    summary = dict(
        total_facts=len(facts),
        exact_statuses=dict(Counter(r.status for r in exact)),
        display=dict(Counter(m.display_status for r in exact for m in r.matches)),
        source_page_coverage=sum(
            bool(r.matches[0].citations) and all(c.pdf_page for c in r.matches[0].citations)
            for r in exact
        ),
        pages=sorted({c.pdf_page for r in exact for c in r.matches[0].citations}),
        document_evidence=len(evidence),
        metrics=len(metrics),
        query_count=len(rows),
        query_passed=sum(r["passed"] for r in rows),
        query_statuses=dict(Counter(r["actual"]["status"] for r in rows)),
        questions=dict(Counter(q["answer_data_status"] for q in questions)),
        original_quality_preserved=all(
            r.matches[0].record.quality_context == f.quality_context
            for r, f in zip(exact, facts, strict=True)
        ),
        json_roundtrip=True,
        restart_exact=True,
        snapshot_isolation=True,
        unchanged_files=len(hashes),
        gemini_calls=0,
        ocr_calls=0,
        extraction_calls=0,
        financial_fact_verified=False,
        external_pdf_accuracy="not_evaluated",
    )
    atomic_json(
        output / "report.json",
        dict(
            summary=summary,
            queries=rows,
            questions=questions,
            source_hashes=hashes,
            source_aliases=source_aliases,
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert all(r["passed"] for r in rows), "Query expectations failed; retain failures in report"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(Path.cwd(), args.output)
