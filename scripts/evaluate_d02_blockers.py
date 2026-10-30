"""D-02 fixed real-artifact comparison; controlled review inputs required, no auto-gold."""

import argparse
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from evaluate_d01_coverage import ROLES, compare_observations, fixed_queries, persist
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.accounting.automated_extraction import run_automated_pdf
from vietnamese_financial_multi_agent.accounting.quality import (
    assess_evidence_for_task,
    evidence_from_automated_records,
)
from vietnamese_financial_multi_agent.api.metadata_service import compose_metadata_service
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DerivedMetric,
    EvidenceQuery,
    EvidenceRetrieval,
    FinancialOperand,
    RetrievalReference,
    build_graph,
    evidence_from_persisted_result,
    facts_from_persisted_result,
    trace_metric_lineage,
    validate_graph,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
    assess_analytical_readiness,
    source_review_status,
)


def save(path, value):
    value = json.loads(json.dumps(value))
    if path.exists():
        if load(path) != value:
            raise ValueError(f"output_changed_use_new_directory:{path.name}")
    else:
        atomic_json(path, value)


def pointer(payload, selector):
    value = payload
    for part in selector.strip("/").split("/"):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def bind_review(fact, reading, record):
    """Bind separately transcribed visual reading to exact extraction selectors.

    A matching raw number alone is insufficient: label/header selectors must also
    exist in the same source association, and row/column positions must be unique.
    Caller resolves PDF/render hash before invoking this function.
    """
    payload = record["response"]["output"]["payload"]
    selectors = [s.reference.source_pointer for s in fact.sources if s.reference]

    def select(text, kind):
        matches = [
            s
            for s in selectors
            if s and f"/{kind}/" in s and pointer(payload, s).get("text") == text
        ]
        if len(matches) != 1:
            raise ValueError("ambiguous_or_missing_review_selector")
        return matches[0]

    value = select(reading["raw_value"], "cells")
    label = select(reading["raw_label"], "cells")
    header = select(reading["raw_header"], "headers")
    value_cell, label_cell, header_cell = [pointer(payload, s) for s in (value, label, header)]
    table_paths = {s.split("/cells/")[0].split("/headers/")[0] for s in (value, label, header)}
    if (
        len(table_paths) != 1
        or value == label
        or None
        in (value_cell["row"], label_cell["row"], value_cell["column"], header_cell["column"])
        or value_cell["row"] != label_cell["row"]
        or value_cell["column"] != header_cell["column"]
        or any(c["reading"] != "observed" for c in (value_cell, label_cell, header_cell))
    ):
        raise ValueError("review_row_column_mismatch")
    table = pointer(payload, next(iter(table_paths)))
    for cell in (value_cell, label_cell, header_cell):
        if (
            sum(
                c["row"] == cell["row"] and c["column"] == cell["column"]
                for c in table["cells"] + table["headers"]
            )
            != 1
        ):
            raise ValueError("ambiguous_review_position")
    review = SourceReview(
        **reading,
        sources=fact.sources,
        value_selector=value,
        label_selector=label,
        header_selector=header,
    )
    if source_review_status(fact, [review]) != "value_row_verified":
        raise ValueError("review_fact_mismatch")
    return review


def recover(root, output, live=False):
    folder = output / "recovery-2022"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "extraction-8.json"
    row = next(
        r for r in load(root / "artifacts/evidence/D-01/inventory.json") if r["year"] == 2022
    )
    pdf = root / row["pdf"]
    if digest(pdf) != row["sha256"]:
        raise ValueError("recovery_pdf_changed")
    service = pool = None
    options = {}
    if not path.exists():
        if not live:
            raise ValueError("targeted_recovery_missing_use_recover_live_once")
        service, pool, options = compose_metadata_service(SimpleNamespace(root=folder))
        if service is None:
            raise ValueError("existing_gateway_configuration_unavailable")
    try:
        record = run_automated_pdf(
            pdf,
            symbol="BBS",
            year="2022",
            pages=[8],
            cached_records={8: load(path)} if path.exists() else None,
            service=service,
            credential_ref=options.get("credential_ref", ""),
        )[0]
        if service is not None:
            save(path, record)
            save(folder / "usage.json", service.last_attempts)
    finally:
        if pool is not None:
            pool.close()
    old = load(root / "artifacts/evidence/D-01/evaluation/2022/normalized-result.json")
    result = dict(old)
    result["attempt_id"] = "D-02/recovery-2022-v1"
    result["parent_snapshot_id"] = old["attempt_id"]
    result["records"] = [record if r["source"]["page"]["page"] == 8 else r for r in old["records"]]
    result["quality"] = assess_evidence_for_task(
        evidence_from_automated_records(result["records"])
    ).model_dump(mode="json")
    save(folder / "normalized-result.json", result)
    facts = facts_from_persisted_result(result, company_id=result["metadata_binding"]["company_id"])
    repo = CanonicalFactRepository(folder / "canonical")
    for f in facts:
        f.semantic_role = ROLES.get(f.canonical_item_id)
        persist(repo, f)
    assert sorted(f.model_dump_json() for f in facts) == sorted(
        f.model_dump_json()
        for f in repo.list_by_document(result["document_id"], result["attempt_id"])
    )
    return result, facts


def evaluate(root, output, *, recover_live=False):
    baseline = root / "artifacts/evidence/D-01/evaluation"
    hashes = load(output / "hashes-before.json")
    if any(digest(root / p) != h for p, h in hashes.items()):
        raise ValueError("baseline_input_changed")
    facts, evidence, records = [], [], {}
    inventory = load(baseline.parent / "inventory.json")
    scopes, by_year = {}, {}
    for row in inventory:
        year = row["year"]
        if digest(root / row["pdf"]) != row["sha256"]:
            raise ValueError("pdf_changed")
        result = load(baseline / str(year) / "normalized-result.json")
        fs = CanonicalFactRepository(baseline / str(year) / "canonical").list_by_document(
            result["document_id"], result["attempt_id"]
        )
        facts.extend(fs)
        by_year[year] = fs
        scopes[year] = dict(document_id=result["document_id"], snapshot_id=result["attempt_id"])
        evidence.extend(evidence_from_persisted_result(result))
        # Re-render only selected primary pages to validate actual cached image binding.
        checked = run_automated_pdf(
            root / row["pdf"],
            symbol=result["records"][0]["source"]["page"]["symbol"],
            year=result["records"][0]["source"]["page"]["year"],
            pages=[r["source"]["page"]["page"] for r in result["records"]],
            cached_records={r["source"]["page"]["page"]: r for r in result["records"]},
        )
        for r in checked:
            records[(result["document_id"], r["source"]["page"]["page"])] = r
    index = {f.observation_identity(): f for f in facts}
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m)) for m in load(baseline / "metrics.json")
    ]
    reviews = []
    for reading in load(output / "review-inputs.json"):
        f = next(
            f for f in facts if f.observation_identity().model_dump() == reading["observation"]
        )
        year = next(y for y, scope in scopes.items() if scope["document_id"] == f.document_id)
        if digest(output / f"{year}-{reading['pdf_page']}.png") != reading["review_image_sha256"]:
            raise ValueError("review_render_changed")
        reviews.append(bind_review(f, reading, records[(f.document_id, reading["pdf_page"])]))
    save(output / "source-reviews.json", [r.model_dump(mode="json") for r in reviews])
    save(
        output / "metric-source-links.json",
        [
            dict(
                metric_id=m.metric_id,
                operands=[
                    dict(
                        role=o.role,
                        observation=o.observation.model_dump(),
                        review_references=[
                            r.review_reference for r in reviews if r.observation == o.observation
                        ],
                    )
                    for o in m.operands
                ],
            )
            for m in metrics
        ],
    )
    bases = [AccountingBasisReview(**b) for b in load(output / "accounting-basis-reviews.json")]
    for b in bases:
        if digest(root / "artifacts/evidence" / b.review_reference) != b.review_image_sha256:
            raise ValueError("basis_render_changed")
    readiness = []
    for m in metrics:
        operands = [FinancialOperand(role=o.role, fact=index[o.observation]) for o in m.operands]
        assessment = assess_analytical_readiness(
            m.definition.compatibility, operands, reviews, bases
        )
        assert assessment["approved_compatibility"] == m.compatibility.model_dump(mode="json")
        readiness.append(dict(metric_id=m.metric_id, name=m.definition.name, **assessment))
    save(output / "metrics-readiness.json", readiness)
    original_graph = build_graph(facts, evidence, metrics)
    original_lineages = [
        trace_metric_lineage(
            m, original_graph, facts, evidence, expected_formula=m.definition
        ).model_dump(mode="json")
        for m in metrics
    ]
    assert original_lineages == load(baseline / "lineages.json")
    comparisons = compare_observations(facts)
    assert comparisons == load(baseline / "cross-year.json")
    save(output / "cross-year.json", comparisons)
    recovery_result, recovered = recover(root, output, live=recover_live)
    recovery_record = load(output / "recovery-2022/extraction-8.json")
    recovery_reviews = []
    for reading in load(output / "recovery-review-inputs.json"):
        f = next(
            f for f in recovered if f.observation_identity().model_dump() == reading["observation"]
        )
        if digest(output / "2022-8.png") != reading["review_image_sha256"]:
            raise ValueError("recovery_review_render_changed")
        recovery_reviews.append(bind_review(f, reading, recovery_record))
    save(
        output / "recovery-source-reviews.json",
        [r.model_dump(mode="json") for r in recovery_reviews],
    )
    after_facts = [f for y, fs in by_year.items() if y != 2022 for f in fs] + recovered
    after_comparisons = compare_observations(after_facts)

    def pair_key(pair):
        return (
            pair["item"],
            pair["period"],
            tuple(sorted(o["document_id"] for o in pair["observations"])),
        )

    assert {pair_key(c) for c in after_comparisons} == {pair_key(c) for c in comparisons}
    save(output / "cross-year-after-recovery.json", after_comparisons)
    after_evidence = [e for e in evidence if e.document_id != scopes[2022]["document_id"]]
    after_evidence.extend(evidence_from_persisted_result(recovery_result))
    scopes[2022]["snapshot_id"] = recovery_result["attempt_id"]
    coverage = [
        CanonicalCoverage(
            **scope,
            canonical_extraction="available",
            missing_canonical_items=["b01.short_term_liabilities"],
            inventory_reference="D-01/inventory",
        )
        for scope in scopes.values()
    ]
    graph = build_graph(after_facts, after_evidence)
    structural = validate_graph(graph, after_facts, after_evidence)
    assert not structural.orphan_nodes
    assert all(a.status == "valid" for a in structural.nodes + structural.edges + structural.inputs)
    api = EvidenceRetrieval(after_facts, after_evidence, graph=graph, coverage=coverage)
    for f in after_facts:
        assert api.get_fact(f.observation_identity()).matches[0].record == f
    retrieval = []
    before_queries = load(baseline / "retrieval.json")
    assert [q["case"] for q in before_queries] == fixed_queries()
    for case, before in zip(fixed_queries(), before_queries, strict=True):
        options = dict(scopes[case["filing"]]) if "filing" in case else {}
        if "snapshot" in case:
            options["snapshot_id"] = case["snapshot"]
        query = EvidenceQuery(**options, canonical_item_id=case["item"], period=case.get("period"))
        if case["operation"] == "different_snapshots":
            original = facts_from_persisted_result(load(baseline.parent / "2021/result.json"))
            result = EvidenceRetrieval([*after_facts, *original]).find_facts(
                query.model_copy(update={"snapshot_id": None})
            )
        else:
            result = api.find_facts(query)
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
        if case["id"] != "Q07":
            assert category == before["category"], case["id"]
            assert [m.record.value for m in result.matches] == [
                type(result.matches[0].record.value).model_validate_json(
                    json.dumps(m["record"]["value"])
                )
                for m in before["result"]["matches"]
            ]
        citations = (
            [
                api.get_sources(
                    RetrievalReference(kind="fact", observation=m.record.observation_identity())
                ).model_dump(mode="json")
                for m in result.matches
            ]
            if case["operation"] == "get_sources"
            else []
        )
        retrieval.append(
            dict(
                case=case,
                before=before["category"],
                after=category,
                result=result.model_dump(mode="json"),
                sources=citations,
            )
        )
    save(output / "retrieval.json", retrieval)
    old_b03 = [f for f in by_year[2022] if f.context.statement_type == "B03"]
    new_b03 = [f for f in recovered if f.context.statement_type == "B03"]

    def row_key(f):
        return f.source_item_code, f.context.raw_item_label, f.context.period

    old_values = {row_key(f): f for f in old_b03}
    changes = [
        dict(
            key=row_key(f),
            before=old_values[row_key(f)].value.model_dump(mode="json"),
            after=f.value.model_dump(mode="json"),
        )
        for f in new_b03
        if row_key(f) in old_values and f.value != old_values[row_key(f)].value
    ]
    save(
        output / "recovery-comparison.json",
        dict(
            old_snapshot="D-01/normalized-v2",
            new_snapshot=recovery_result["attempt_id"],
            before_count=len(old_b03),
            after_count=len(new_b03),
            before_quality=dict(Counter(q.decision for f in old_b03 for q in f.quality_context)),
            after_quality=dict(Counter(q.decision for f in new_b03 for q in f.quality_context)),
            changed_values=changes,
            matched_rows=sum(row_key(f) in old_values for f in new_b03),
            original_attempt_preserved=True,
            value_row_verified=len(recovery_reviews),
            before_table_layout=[
                (t["rows"], t["columns"])
                for t in records[(recovery_result["document_id"], 8)]["response"]["output"][
                    "payload"
                ]["tables"]
            ],
            after_table_layout=[
                (t["rows"], t["columns"])
                for t in recovery_record["response"]["output"]["payload"]["tables"]
            ],
            before_context=records[(recovery_result["document_id"], 8)]["response"]["output"][
                "payload"
            ]["context"],
            after_context=recovery_record["response"]["output"]["payload"]["context"],
        ),
    )
    unchanged = all(digest(root / p) == h for p, h in hashes.items())
    assert unchanged
    save(
        output / "summary.json",
        dict(
            original_facts=len(facts),
            after_recovery_facts=len(after_facts),
            metrics=len(metrics),
            complete_bindings=sum(m.structural_readiness == "complete" for m in metrics),
            reviewed_unique_operands=len(reviews),
            reviewed_operand_occurrences=sum(
                s == "value_row_verified" for r in readiness for s in r["source_status"].values()
            ),
            candidate_compatibility=dict(Counter(r["candidate_compatibility"] for r in readiness)),
            approved_compatibility=dict(Counter(m.compatibility.status for m in metrics)),
            calculation_eligible=0,
            formula_policy="reference_example",
            basis_reviews=len(bases),
            cross_year=dict(
                pairs=len(after_comparisons),
                status=dict(Counter(c["status"] for c in after_comparisons)),
            ),
            retrieval=dict(Counter(r["after"] for r in retrieval)),
            lineage_exact=True,
            exact_retrieval=len(after_facts),
            source_hashes_unchanged=unchanged,
            source_hash_count=len(hashes),
        ),
    )
    print(load(output / "summary.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-02"))
    parser.add_argument("--recover-live", action="store_true")
    args = parser.parse_args()
    evaluate(Path.cwd(), args.output.resolve(), recover_live=args.recover_live)
