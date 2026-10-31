"""D-02 approved preparation: read-only 15/36/29 evaluation, no extraction/Gemini."""

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from evaluate_d01_coverage import ROLES, compare_observations, fixed_queries
from evaluate_d02_blockers import save
from run_d01_coverage import digest, load
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
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
    assess_analytical_readiness,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)


def signing_date_overlay(record, review, snapshot):
    """Source-backed metadata riêng; không sửa context/financial period/extraction."""
    match = re.search(r"ngày (\d+) tháng (\d+) năm (\d+)", review["source_quote"])
    if not match or date(*map(int, reversed(match.groups()))).isoformat() != review["signing_date"]:
        raise ValueError("signing_date_quote_mismatch")
    if (
        review["field"] != "signing_date"
        or review["snapshot_id"] != snapshot
        or review["document_id"] != record["source"]["page"]["source_ref"]
        or review["pdf_page"] != record["source"]["page"]["page"]
        or record["response"]["output"]["payload"]["context"][review["context_index"]]
        != review["original_text"]
        or review["method"] != "controlled_original_pdf_visual_read"
    ):
        raise ValueError("signing_date_source_mismatch")
    return dict(**review, usable_for="signing_date_only", financial_period_override=False)


def evaluate(root, output):
    previous = root / "artifacts/evidence/D-02"
    baseline = root / "artifacts/evidence/D-01/evaluation"
    output.mkdir(parents=True, exist_ok=True)
    hashes = load(output / "hashes-before.json")
    assert all(digest(root / p) == h for p, h in hashes.items()), "input_changed"
    registry = load(root / "configs/d02-analytical-policies.json")
    approval = PreparationApproval(**registry["preparation_approval"])
    policies = {p["formula_id"]: PreparedFormulaPolicy(**p) for p in registry["formula_policies"]}
    formula_approvals = [
        FormulaExecutionApproval(**a) for a in registry["formula_execution_approvals"]
    ]
    # JSON validation preserves exact nested financial models (no Decimal floats).
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(previous / "source-reviews.json")
    ]
    bases = [AccountingBasisReview(**b) for b in load(previous / "accounting-basis-reviews.json")]
    for r in reviews:
        assert r.pdf_sha256 == r.observation.document_id.removeprefix("sha256:")
    for b in bases:
        assert digest(root / "artifacts/evidence" / b.review_reference) == b.review_image_sha256
    facts, evidence, scopes = [], [], {}
    for y in range(2021, 2026):
        result = load(baseline / str(y) / "normalized-result.json")
        scope = dict(document_id=result["document_id"], snapshot_id=result["attempt_id"])
        scopes[y] = scope
        facts.extend(
            CanonicalFactRepository(baseline / str(y) / "canonical").list_by_document(**scope)
        )
        evidence.extend(evidence_from_persisted_result(result))
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m)) for m in load(baseline / "metrics.json")
    ]
    old_readiness = load(previous / "metrics-readiness.json")
    assert [r["metric_id"] for r in old_readiness] == [m.metric_id for m in metrics]
    index = {f.observation_identity(): f for f in facts}
    rows = []
    for metric in metrics:
        operands = [
            FinancialOperand(role=o.role, fact=index[o.observation]) for o in metric.operands
        ]
        result = assess_analytical_readiness(
            metric.definition.compatibility,
            operands,
            reviews,
            bases,
            approval=approval,
            formula_policy=policies[metric.definition.name],
            formula_approvals=formula_approvals,
        )
        assert result["global_compatibility"] == metric.compatibility.model_dump(mode="json")
        rows.append(
            dict(
                metric_id=metric.metric_id,
                name=metric.definition.name,
                operand_references=[o.model_dump(mode="json") for o in metric.operands],
                **result,
            )
        )
    save(output / "metrics-readiness.json", rows)
    graph = build_graph(facts, evidence, metrics)
    lineages = [
        trace_metric_lineage(m, graph, facts, evidence, expected_formula=m.definition).model_dump(
            mode="json"
        )
        for m in metrics
    ]
    assert lineages == load(baseline / "lineages.json")
    recovered_result = load(previous / "recovery-2022/normalized-result.json")
    recovered = facts_from_persisted_result(
        recovered_result, company_id=recovered_result["metadata_binding"]["company_id"]
    )
    for f in recovered:
        f.semantic_role = ROLES.get(f.canonical_item_id)
    after = [f for f in facts if f.document_id != recovered_result["document_id"]] + recovered
    pairs = compare_observations(after)
    assert pairs == load(previous / "cross-year-after-recovery.json")
    save(output / "cross-year.json", pairs)
    evidence = [
        e for e in evidence if e.document_id != recovered_result["document_id"]
    ] + evidence_from_persisted_result(recovered_result)
    scopes[2022]["snapshot_id"] = recovered_result["attempt_id"]
    coverage = [
        CanonicalCoverage(
            **s,
            canonical_extraction="available",
            missing_canonical_items=["b01.short_term_liabilities"],
            inventory_reference="D-01/inventory",
        )
        for s in scopes.values()
    ]
    api = EvidenceRetrieval(after, evidence, coverage=coverage)
    assert all(api.get_fact(f.observation_identity()).matches[0].record == f for f in after)
    queries = load(previous / "retrieval.json")
    assert [q["case"] for q in queries] == fixed_queries()
    retrieval = []
    for before in queries:
        case = before["case"]
        scope = dict(scopes[case["filing"]]) if "filing" in case else {}
        if "snapshot" in case:
            scope["snapshot_id"] = case["snapshot"]
        query = EvidenceQuery(**scope, canonical_item_id=case["item"], period=case.get("period"))
        if case["operation"] == "different_snapshots":
            legacy = facts_from_persisted_result(load(baseline.parent / "2021/result.json"))
            result = EvidenceRetrieval([*after, *legacy]).find_facts(
                query.model_copy(update={"snapshot_id": None})
            )
        else:
            result = api.find_facts(query)
        assert result.model_dump(mode="json") == before["result"], case["id"]
        sources = (
            [
                api.get_sources(
                    RetrievalReference(kind="fact", observation=m.record.observation_identity())
                ).model_dump(mode="json")
                for m in result.matches
            ]
            if case["operation"] == "get_sources"
            else []
        )
        assert sources == before["sources"], case["id"]
        retrieval.append(
            dict(
                case=case,
                category=before["after"],
                result=result.model_dump(mode="json"),
                sources=sources,
            )
        )
    save(output / "retrieval.json", retrieval)
    review = load(output / "signing-date-review.json")
    inventory = next(r for r in load(baseline.parent / "inventory.json") if r["year"] == 2022)
    assert digest(root / inventory["pdf"]) == review["document_id"].removeprefix("sha256:")
    assert digest(previous / "2022-8.png") == review["review_image_sha256"]
    record_path = previous / "recovery-2022/extraction-8.json"
    assert digest(record_path) == review["extraction_sha256"]
    save(
        output / "signing-date-overlay.json",
        signing_date_overlay(load(record_path), review, recovered_result["attempt_id"]),
    )
    assert all(digest(root / p) == h for p, h in hashes.items()), "input_changed"
    summary = dict(
        metrics=len(rows),
        complete_bindings=sum(m.structural_readiness == "complete" for m in metrics),
        approved_preparation_ready_before=sum(
            r.get("preparation_ready", False)
            and r["policy_status"] == "approved_analytical_preparation"
            for r in old_readiness
        ),
        approved_preparation_ready_after=sum(r["preparation_ready"] for r in rows),
        global_compatibility=dict(Counter(r["global_compatibility"]["status"] for r in rows)),
        approved_profile_compatibility=dict(
            Counter(r["approved_profile_compatibility"]["status"] for r in rows)
        ),
        calculation_eligible=sum(r["calculation_eligible"] for r in rows),
        formula_preflight_clear=sum(not r["formula_policy"]["blockers"] for r in rows),
        formula_execution_status=dict(Counter(r["formula_policy"]["status"] for r in rows)),
        cross_year=dict(count=len(pairs), statuses=dict(Counter(p["status"] for p in pairs))),
        retrieval=dict(Counter(q["category"] for q in retrieval)),
        exact_retrieval=len(after),
        original_lineages_exact=True,
        signing_date_overlay_usable=True,
        gemini_calls=0,
        tokens=0,
        source_hash_count=len(hashes),
        source_hashes_unchanged=True,
        policy_registry_sha256=digest(root / "configs/d02-analytical-policies.json"),
    )
    # Baseline had no approved profile/approval record: candidate true is not readiness.
    assert all(r["policy_status"] == "experimental_pending_tech_lead" for r in old_readiness)
    save(output / "summary.json", summary)
    print(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/D-02-final"))
    args = parser.parse_args()
    evaluate(Path.cwd(), args.output.resolve())
