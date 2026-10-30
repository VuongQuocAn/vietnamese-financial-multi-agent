"""D-01 offline projections, fixed retrieval cases and analytical readiness; no results."""

import argparse
import json
import time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from run_d01_coverage import digest, load
from validate_m3_metrics import examples
from vietnamese_financial_multi_agent.accounting.automated_extraction import run_automated_pdf
from vietnamese_financial_multi_agent.accounting.quality import (
    assess_evidence_for_task,
    evidence_from_automated_records,
)
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DocumentEvidenceRepository,
    EvidenceQuery,
    EvidenceRetrieval,
    MetricRequest,
    RetrievalReference,
    build_graph,
    build_metric,
    evidence_from_persisted_result,
    facts_from_persisted_result,
    trace_metric_lineage,
    validate_graph,
)

ROLES = {
    "b02.net_revenue": "revenue",
    "b02.gross_profit": "gross_profit",
    "b01.total_assets": "assets",
    "b01.total_liabilities": "liabilities",
}


def persist(repository, record):
    try:
        return repository.put(record)
    except PermissionError as error:
        if getattr(error, "winerror", None) != 5:
            raise
        # Observed Windows transient replace lock; one bounded local retry only.
        time.sleep(0.25)
        return repository.put(record)


def fixed_queries():
    # Declared before loading outputs; filing labels are query inputs, not inferred periods.
    rows = []
    for year in range(2021, 2026):
        for item, period in (
            ("b01.total_assets", f"{year}-12-31"),
            ("b02.net_revenue", str(year)),
            ("b03.operating_cash_flow", str(year)),
            ("b02.gross_profit", str(year)),
        ):
            rows.append(dict(filing=year, item=item, period=period, operation="find_facts"))
    rows.extend(
        [
            dict(item="b02.net_revenue", period="2024", operation="find_facts"),
            dict(item="b02.net_revenue", operation="find_facts"),
            dict(filing=2025, item="b02.net_revenue", period="2024", operation="find_facts"),
            dict(filing=2023, item="b01.total_assets", operation="find_facts"),
            dict(filing=2024, item="b01.short_term_liabilities", operation="find_facts"),
            dict(
                filing=2025,
                item="b02.net_revenue",
                period="2025",
                snapshot="absent",
                operation="find_facts",
            ),
            dict(filing=2021, item="b02.net_revenue", period="2021", operation="get_sources"),
            dict(
                filing=2024, item="b03.operating_cash_flow", period="2024", operation="get_sources"
            ),
            dict(
                filing=2021, item="b02.net_revenue", period="2021", operation="different_snapshots"
            ),
        ]
    )
    return [dict(id=f"Q{i:02}", **row) for i, row in enumerate(rows, 1)]


def project(root, output, row, binding, payload, suffix=""):
    """Revalidate source-bound cached records with the current small mapping catalog.

    New M2 projection/snapshot, never edit old facts or remove their issues. Company
    binding is from controlled original-PDF registration reading, not a name match.
    Scope remains unknown unless the normal context resolver has explicit evidence.
    """
    if binding["document_id"] != "sha256:" + row["sha256"]:
        raise ValueError("metadata_document_mismatch")
    if binding["verification"] != "controlled_original_pdf_visual_read":
        raise ValueError("metadata_source_not_verified")
    if not (1 <= binding["pdf_page"] <= row["pages"] and binding["source_quote"].strip()):
        raise ValueError("metadata_source_missing")
    if binding["company_id"] != "vn-business-registration:" + binding["registration_code"]:
        raise ValueError("registration_identity_mismatch")
    pdf = root / row["pdf"]
    if digest(pdf) != row["sha256"]:
        raise ValueError("pdf_changed")
    records = []
    for record in payload["records"]:
        identity = record["source"]["page"]
        if identity["source_ref"] != binding["document_id"]:
            raise ValueError("record_pdf_mismatch")
        page = identity["page"]
        records.extend(
            run_automated_pdf(
                pdf,
                symbol=identity["symbol"],
                year=identity["year"],
                pages=[page],
                cached_records={page: record},
            )
        )
    excluded = [
        r["source"]["page"]["page"]
        for r in records
        if (r.get("response") or {}).get("output", {}).get("payload", {}).get("statement_type")
        not in {"B01", "B02", "B03"}
    ]
    records = [r for r in records if r["source"]["page"]["page"] not in excluded]
    quality = assess_evidence_for_task(evidence_from_automated_records(records))
    snapshot = "D-01/normalized-v2" + suffix
    result = dict(
        document_id=binding["document_id"],
        attempt_id=snapshot,
        records=records,
        quality=quality.model_dump(mode="json"),
        parent_document_id=payload["document_id"],
        parent_snapshot_id=payload["attempt_id"],
        metadata_binding=binding,
        mapping_version="D-01/catalog-v1",
        excluded_non_primary_pages=excluded,
    )
    folder = output / (str(row["year"]) + suffix.replace("/", "-"))
    folder.mkdir(parents=True, exist_ok=True)
    existing = folder / "normalized-result.json"
    if existing.exists() and load(existing) != result:
        raise ValueError("projection_changed_use_new_output_snapshot")
    atomic_json(folder / "normalized-result.json", result)
    facts = facts_from_persisted_result(result, company_id=binding["company_id"])
    before = {f.local_observation_id: f for f in facts_from_persisted_result(payload)}
    repo = CanonicalFactRepository(folder / "canonical")
    stored = {
        f.observation_identity(): f for f in repo.list_by_document(result["document_id"], snapshot)
    }
    for f in facts:
        original = before[f.local_observation_id]
        if f.value != original.value or f.raw_header != original.raw_header:
            raise ValueError("projection_changed_source_value")
        for field in (
            "period",
            "period_type",
            "currency",
            "scale",
            "reporting_scope",
            "raw_item_label",
        ):
            if getattr(f.context, field) != getattr(original.context, field):
                raise ValueError("projection_changed_source_context")
        f.semantic_role = ROLES.get(f.canonical_item_id)
        f.source_metadata["d01_binding"] = binding
        f.source_metadata["parent_snapshot"] = payload["attempt_id"]
        if stored.get(f.observation_identity()) != f:
            persist(repo, f)
    persisted = repo.list_by_document(result["document_id"], snapshot)
    assert sorted(f.model_dump_json() for f in facts) == sorted(
        f.model_dump_json() for f in persisted
    )
    evidence = evidence_from_persisted_result(result)
    doc_repo = DocumentEvidenceRepository(folder / "document-evidence")
    for e in evidence:
        persist(doc_repo, e)
    return facts, evidence, result


def metrics_for(year, result, facts, evidence):
    metrics, lineages = [], []
    for definition, periods in examples():

        def period(p):
            return str(year if p[:4] == "2025" else year - 1) + p[4:]

        definition = definition.model_copy(deep=True)
        for pair in definition.compatibility.period_pairs:
            pair.left, pair.right = period(pair.left), period(pair.right)
        metric = build_metric(
            definition,
            MetricRequest(
                document_id=result["document_id"],
                snapshot_id=result["attempt_id"],
                operand_periods={role: period(p) for role, p in periods.items()},
            ),
            facts,
        )
        metrics.append(metric)
    graph = build_graph(facts, evidence, metrics)
    for metric in metrics:
        lineages.append(
            trace_metric_lineage(metric, graph, facts, evidence, expected_formula=metric.definition)
        )
    return metrics, lineages


def compare_observations(facts):
    groups = defaultdict(list)
    for f in facts:
        if f.canonical_item_id and f.context.period:
            groups[(f.canonical_item_id, f.context.period)].append(f)
    comparisons = []
    for (item, period), observations in sorted(groups.items()):
        for left, right in combinations(observations, 2):
            if left.document_id == right.document_id:
                continue
            reasons = []
            for field in ("company_id",):
                a, b = getattr(left, field), getattr(right, field)
                if not a or not b or a != b:
                    reasons.append(field)
            for field in ("reporting_scope", "period_type", "currency", "scale"):
                a, b = getattr(left.context, field), getattr(right.context, field)
                if a is None or b is None or a != b:
                    reasons.append(field)
            if not left.value.unit or left.value.unit != right.value.unit:
                reasons.append("unit")
            a, b = left.value.normalized_value, right.value.normalized_value
            if a is None or b is None:
                reasons.append("numeric_value")
            comparisons.append(
                dict(
                    item=item,
                    period=period,
                    observations=[f.observation_identity().model_dump() for f in (left, right)],
                    values=[str(a), str(b)],
                    numeric_equal=None if a is None or b is None else a == b,
                    status="undetermined" if reasons else "consistent" if a == b else "different",
                    reasons=reasons,
                )
            )
    return comparisons


def spot_checks(facts_by_year, references):
    results = []
    for ref in references:
        candidates = [
            f
            for f in facts_by_year[ref["filing"]]
            if f.source_item_code == ref["code"]
            and f.context.statement_type == ref["statement"]
            and f.context.period == ref["period"]
            and any(
                s.reference and s.reference.anchor.page.page == ref["pdf_page"] for s in f.sources
            )
        ]
        status = "uncertain"
        label_status = "uncertain"
        if len(candidates) == 1:
            f = candidates[0]
            from vietnamese_financial_multi_agent.accounting.automated_extraction import (
                parse_vietnamese_number,
            )

            status = (
                "correct"
                if (
                    f.value.raw_value == ref["raw_value"]
                    and f.value.normalized_value == parse_vietnamese_number(ref["raw_value"])
                )
                else "incorrect"
            )
            label_status = (
                "correct"
                if " ".join((f.context.raw_item_label or "").split()) == ref["raw_label"]
                else "incorrect"
            )
        results.append(
            dict(
                reference=ref,
                status=status,
                label_status=label_status,
                observations=[f.model_dump(mode="json") for f in candidates],
            )
        )
    return results


def evaluate(root, inputs, output, *, resume=False):
    output.mkdir(parents=True, exist_ok=resume)
    cases = fixed_queries()
    if cases != load(inputs / "fixed-queries-before-evaluation.json"):
        raise ValueError("query_sample_changed")
    atomic_json(output / "fixed-queries.json", cases)
    inventory = load(inputs / "inventory.json")
    bindings = {b["document_id"]: b for b in load(inputs / "metadata-bindings.json")}
    all_facts, all_evidence, all_metrics, all_lineages = [], [], [], []
    coverage, scopes, rows, relationships, discovery_rows = [], {}, [], [], []
    facts_by_year = {}
    for row in inventory:
        year = row["year"]
        payload = load(inputs / str(year) / "result.json")
        extracted = {r["source"]["page"]["page"]: r for r in payload["records"]}
        discovered = payload.get("inventory", [])
        for page in discovered:
            kind = page["statement_type"]
            status = "discovery"
            number = page.get("page", page.get("pdf_page"))
            if not kind and number in extracted:
                record = extracted[number]
                if "invalid_extraction_response" not in record["extraction"]["issues"]:
                    kind = record["response"]["output"]["payload"]["statement_type"]
                    status = "extraction_reconciliation"
            discovery_rows.append(
                dict(
                    year=year,
                    document_id="sha256:" + row["sha256"],
                    pdf_page=number,
                    statement_type=kind,
                    status=status,
                    discovery_issue=page.get("uncertainty"),
                    source_reference=f"{year}/discovery-{number}.json"
                    if year != 2025
                    else "2025/result.json:inventory",
                )
            )
        binding = bindings["sha256:" + row["sha256"]]
        facts, evidence, result = project(root, output, row, binding, payload)
        facts_by_year[year] = facts
        metrics, lineages = metrics_for(year, result, facts, evidence)
        all_facts.extend(facts)
        all_evidence.extend(evidence)
        all_metrics.extend(metrics)
        all_lineages.extend(lineages)
        scopes[year] = dict(document_id=result["document_id"], snapshot_id=result["attempt_id"])
        coverage.append(
            CanonicalCoverage(
                **scopes[year],
                canonical_extraction="available",
                missing_canonical_items=["b01.short_term_liabilities"]
                if any(f.source_item_code == "310" and not f.canonical_item_id for f in facts)
                else [],
                inventory_reference="D-01/inventory",
            )
        )
        rows.append(
            dict(
                year=year,
                facts=len(facts),
                mapped=sum(bool(f.canonical_item_id) for f in facts),
                numeric=sum(f.value.normalized_value is not None for f in facts),
                items=dict(Counter(f.canonical_item_id for f in facts if f.canonical_item_id)),
                quality=dict(Counter(q.decision for f in facts for q in f.quality_context)),
                periods=dict(Counter(f.context.period for f in facts)),
                company_bound=sum(bool(f.company_id) for f in facts),
                scope_bound=sum(bool(f.context.reporting_scope) for f in facts),
                statements=dict(Counter(f.context.statement_type for f in facts)),
                extracted_pages=len(payload["records"]),
                primary_extracted_pages=len(result["records"]),
                excluded_non_primary_pages=result["excluded_non_primary_pages"],
                discovery_pages=len(discovered),
            )
        )
        for item in ("b01.total_assets", "b01.total_liabilities", "b01.total_equity"):
            matches = [
                f
                for f in facts
                if f.canonical_item_id == item and f.context.period == f"{year}-12-31"
            ]
            relationships.append(
                dict(
                    year=year,
                    item=item,
                    count=len(matches),
                    numeric_available=sum(f.value.normalized_value is not None for f in matches),
                )
            )
    graph = build_graph(all_facts, all_evidence, all_metrics)
    atomic_json(output / "discovery-coverage.json", discovery_rows)
    structural = validate_graph(graph, all_facts, all_evidence, all_metrics)
    atomic_json(output / "graph.json", graph.model_dump(mode="json"))
    atomic_json(output / "graph-validation.json", structural.model_dump(mode="json"))
    api = EvidenceRetrieval(all_facts, all_evidence, all_metrics, graph=graph, coverage=coverage)
    for fact in all_facts:
        exact = api.get_fact(fact.observation_identity())
        if len(exact.matches) != 1 or exact.matches[0].record != fact:
            raise ValueError("exact_retrieval_mismatch")
    query_results = []
    for case in cases:
        options = dict(scopes[case["filing"]]) if "filing" in case else {}
        if "snapshot" in case:
            options["snapshot_id"] = case["snapshot"]
        query = EvidenceQuery(**options, canonical_item_id=case["item"], period=case.get("period"))
        result = api.find_facts(query)
        if case["operation"] == "different_snapshots":
            baseline = facts_from_persisted_result(load(inputs / "2021/result.json"))
            snapshot_api = EvidenceRetrieval([*all_facts, *baseline])
            query = query.model_copy(update={"snapshot_id": None})
            result = snapshot_api.find_facts(query)
        blocked = sum(m.display_status == "blocked" for m in result.matches)
        category = (
            "missing_mapping"
            if "canonical_mapping_missing" in result.reasons
            else "missing_canonical_extraction"
            if "canonical_extraction_missing" in result.reasons
            else "ambiguous"
            if result.status in {"ambiguous", "conflicted"}
            else "source_limitations"
            if not result.matches
            else "quality_blocked"
            if blocked == len(result.matches)
            else "answer_data_partial"
            if blocked
            else "answer_data_available"
        )
        source_results = []
        if case["operation"] == "get_sources":
            for match in result.matches:
                source_results.append(
                    api.get_sources(
                        RetrievalReference(
                            kind="fact", observation=match.record.observation_identity()
                        )
                    ).model_dump(mode="json")
                )
        query_results.append(
            dict(
                case=case,
                query=query.model_dump(mode="json"),
                result=result.model_dump(mode="json"),
                sources=source_results,
                category=category,
            )
        )
    atomic_json(output / "retrieval.json", query_results)
    atomic_json(output / "metrics.json", [m.model_dump(mode="json") for m in all_metrics])
    atomic_json(output / "lineages.json", [m.model_dump(mode="json") for m in all_lineages])
    comparisons = compare_observations(all_facts)
    atomic_json(output / "cross-year.json", comparisons)
    checks = spot_checks(facts_by_year, load(inputs / "spot-reference.json"))
    atomic_json(output / "spot-checks.json", checks)
    atomic_json(
        output / "revenue-trend-data.json",
        [
            dict(
                filing=year,
                observations=[
                    f.model_dump(mode="json")
                    for f in facts_by_year[year]
                    if f.canonical_item_id == "b02.net_revenue" and f.context.period == str(year)
                ],
            )
            for year in range(2021, 2026)
        ],
    )
    # Match both accepted 2025 attempts for a same-six before/after comparison.
    legacy_path = next((root / "artifacts/w07/storage").rglob("result.json"))
    row = inventory[-1]
    facts, evidence, result = project(
        root,
        output,
        row,
        bindings["sha256:" + row["sha256"]],
        load(legacy_path),
        suffix="/legacy-storage",
    )
    legacy_metrics, _ = metrics_for(2025, result, facts, evidence)
    matched = [
        m for m in all_metrics if m.request.document_id == scopes[2025]["document_id"]
    ] + legacy_metrics
    atomic_json(output / "matched-six-metrics.json", [m.model_dump(mode="json") for m in matched])
    summary = dict(
        coverage=rows,
        canonical_facts=len(all_facts),
        exact_retrieval=len(all_facts),
        repository_restart_exact=True,
        raw_value_context_preserved=True,
        mapping=dict(
            mapped=sum(bool(f.canonical_item_id) for f in all_facts),
            unmapped=sum(not f.canonical_item_id for f in all_facts),
        ),
        metrics=dict(
            binding=dict(Counter(m.structural_readiness for m in all_metrics)),
            compatibility=dict(Counter(m.compatibility.status for m in all_metrics)),
            reasons=dict(
                Counter(
                    code for m in all_metrics for code in {r.code for r in m.compatibility.reasons}
                )
            ),
        ),
        matched_six=dict(
            structural=dict(Counter(m.structural_readiness for m in matched)),
            compatibility=dict(Counter(m.compatibility.status for m in matched)),
        ),
        cross_year=dict(
            pairs=len(comparisons),
            statuses=dict(Counter(c["status"] for c in comparisons)),
            numeric_equal=dict(Counter(str(c["numeric_equal"]) for c in comparisons)),
        ),
        retrieval=dict(
            queries=len(cases),
            statuses=dict(Counter(q["result"]["status"] for q in query_results)),
            categories=dict(Counter(q["category"] for q in query_results)),
        ),
        graph=dict(
            nodes=len(graph.nodes),
            edges=len(graph.edges),
            statuses=dict(
                Counter(
                    a.status for a in [*structural.nodes, *structural.edges, *structural.inputs]
                )
            ),
            orphans=len(structural.orphan_nodes),
        ),
        spot_checks=dict(Counter(c["status"] for c in checks)),
        label_spot_checks=dict(Counter(c["label_status"] for c in checks)),
        relationships=relationships,
        formula_execution="not_implemented",
        financial_accuracy="separate_spot_checks_only",
    )
    atomic_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path("artifacts/evidence/D-01"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.output.resolve().is_relative_to(root / "artifacts"):
        parser.error("output must stay in ignored artifacts storage")
    evaluate(root, args.inputs, args.output, resume=args.resume)
