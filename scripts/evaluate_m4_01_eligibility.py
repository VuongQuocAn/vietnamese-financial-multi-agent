"""Offline M4-01 acceptance trên accepted persisted BBS snapshots; zero Gateway."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_d01_coverage import compare_observations, fixed_queries
from evaluate_d04_closure import save
from evaluate_d06_validation import SNAPSHOT, qa09, selected_facts
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DerivedMetric,
    DocumentEvidenceRepository,
    EvidenceGraph,
    EvidenceQuery,
    EvidenceRetrieval,
    ExecutionCompatibilityApproval,
    FinancialOperand,
    OperandRequirement,
    OperationCompatibilitySpec,
    RetrievalReference,
    SnapshotCatalog,
    SnapshotDescriptor,
    assess_execution_compatibility,
    build_graph,
    evaluate_source_validations,
    evidence_from_persisted_result,
    facts_from_persisted_result,
    trace_metric_lineage,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import (
    AccountingBasisReview,
    SourceReview,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)


def manifest(root):
    paths = set(load(root / "artifacts/evidence/D-06-review/hashes-before.json"))
    for folder in ("D-06-final", "D-06-review"):
        paths.update(
            p.relative_to(root).as_posix()
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    return {p: digest(root / p) for p in sorted(paths)}


def inputs(root):
    base = root / "artifacts/evidence/D-01/evaluation"
    d04 = root / "artifacts/evidence/D-04-review"
    descriptors = [SnapshotDescriptor(**d) for d in load(d04 / "snapshots.json")]
    facts, evidence, scopes = [], [], {}
    for row in load(base.parent / "inventory.json"):
        assert digest(root / row["pdf"]) == row["sha256"]
        result = load(base / str(row["year"]) / "normalized-result.json")
        scope = dict(document_id=result["document_id"], snapshot_id=result["attempt_id"])
        facts.extend(
            CanonicalFactRepository(base / str(row["year"]) / "canonical").list_by_document(**scope)
        )
        evidence.extend(evidence_from_persisted_result(result))
        scopes[row["year"]] = scope
    target = next(d for d in descriptors if d.parent_snapshot_id)
    recovered = CanonicalFactRepository(d04 / "canonical").list_by_document(
        target.document_id, target.snapshot_id
    )
    recovered_evidence = DocumentEvidenceRepository(d04 / "document-evidence").list_by_document(
        target.document_id, target.snapshot_id
    )
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m))
        for path in (base / "metrics.json", d04 / "metrics.json")
        for m in load(path)
    ]
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for path in (
            root / "artifacts/evidence/D-02/source-reviews.json",
            root / "artifacts/evidence/D-02/recovery-source-reviews.json",
            d04 / "source-reviews.json",
        )
        for r in load(path)
    ]
    bases = [
        AccountingBasisReview(**b)
        for path in (
            root / "artifacts/evidence/D-02/accounting-basis-reviews.json",
            d04 / "accounting-basis-reviews.json",
        )
        for b in load(path)
    ]
    # Exact persisted render references, including freshly verified D-04 reuse.
    inventory = load(base.parent / "inventory.json")
    for record in [*reviews, *bases]:
        reference = record.review_reference.split(":")[0]
        assert (root / "artifacts/evidence" / reference).is_file()
        if reference.endswith(".json"):
            year = next(
                r["year"]
                for r in inventory
                if "sha256:" + r["sha256"] == record.observation.document_id
            )
            reference = f"D-02/{year}-{record.pdf_page}.png"
        assert digest(root / "artifacts/evidence" / reference) == record.review_image_sha256
        if record.verification_reference:
            assert (
                root / "artifacts/evidence" / record.verification_reference.split("#")[0]
            ).is_file()
    return (
        dict(
            descriptors=descriptors,
            facts=facts + recovered,
            evidence=evidence + recovered_evidence,
            metrics=metrics,
            source_reviews=reviews,
            accounting_bases=bases,
        ),
        scopes,
        target,
    )


def regression_queries(root, data, scopes, target):
    facts = [
        f
        for f in data["facts"]
        if f.document_id != target.document_id or f.snapshot_id == target.snapshot_id
    ]
    evidence = [
        e
        for e in data["evidence"]
        if e.document_id != target.document_id or e.snapshot_id == target.snapshot_id
    ]
    scopes = {**scopes, 2022: dict(document_id=target.document_id, snapshot_id=target.snapshot_id)}
    api = EvidenceRetrieval(
        facts,
        evidence,
        coverage=[
            CanonicalCoverage(
                **s,
                canonical_extraction="available",
                missing_canonical_items=["b01.short_term_liabilities"],
                inventory_reference="D-01/inventory",
            )
            for s in scopes.values()
        ],
    )
    queries = load(root / "artifacts/evidence/D-02-final/retrieval.json")
    assert [q["case"] for q in queries] == fixed_queries()
    for q in queries:
        case = q["case"]
        scope = dict(scopes[case["filing"]]) if "filing" in case else {}
        if "snapshot" in case:
            scope["snapshot_id"] = case["snapshot"]
        query = EvidenceQuery(**scope, canonical_item_id=case["item"], period=case.get("period"))
        if case["operation"] == "different_snapshots":
            legacy = facts_from_persisted_result(
                load(root / "artifacts/evidence/D-01/2021/result.json")
            )
            result = EvidenceRetrieval([*facts, *legacy]).find_facts(
                query.model_copy(update={"snapshot_id": None})
            )
        else:
            result = api.find_facts(query)
        assert result.model_dump(mode="json") == q["result"], case["id"]
        if case["operation"] == "get_sources":
            assert [
                api.get_sources(
                    RetrievalReference(kind="fact", observation=m.record.observation_identity())
                ).model_dump(mode="json")
                for m in result.matches
            ] == q["sources"]
    return facts, queries


def d06_regression(root):
    folder = root / "artifacts/evidence/D-06-final"
    facts = selected_facts(root, "artifacts/evidence/D-06-final", SNAPSHOT)
    old_qa09 = load(root / "artifacts/evidence/D-06-review/qa-after.json")["qa09"]
    current_qa09 = qa09(facts[2024], SNAPSHOT)
    assert current_qa09 == old_qa09
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(folder / "source-reviews.json")
    ]
    descriptors = [SnapshotDescriptor(**d) for d in load(folder / "snapshots.json")]
    validations = []
    for year, rows in facts.items():
        descriptor = next(
            d
            for d in descriptors
            if d.document_id == rows[0].document_id and d.snapshot_id == SNAPSHOT
        )
        for period in (f"{year}-12-31", f"{year}-01-01", str(year), str(year - 1)):
            checks = evaluate_source_validations(
                descriptor, rows, period=period, source_reviews=reviews
            )
            validations.extend(
                dict(filing=year, **c.model_dump(mode="json"))
                for c in checks
                if c.rule_id.startswith("b01") == ("-" in period)
            )
    assert validations == load(root / "artifacts/evidence/D-06-review/validation.json")
    qa15 = [
        v
        for v in validations
        if v["filing"] == 2023
        and v["period"] == "2023-12-31"
        and v["rule_id"] in {"b01.balance_identity", "b01.assets_liabilities_equity"}
    ]
    assert len(qa15) == 2 and all(
        v["status"] == "consistent" and v["residual"] == "0" for v in qa15
    )
    return dict(
        qa09=current_qa09,
        qa15=qa15,
        validation_count=len(validations),
        statuses=dict(Counter(v["status"] for v in validations)),
    )


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=True)
    hashes = manifest(root)
    print(f"Pinned {len(hashes)} protected input hashes", flush=True)
    save(output / "hashes-before.json", hashes)
    data, scopes, target = inputs(root)
    print("Loaded original15 and D-04 recovery3 metrics with exact reviews", flush=True)
    graph = build_graph(data["facts"], data["evidence"], data["metrics"])
    assert graph == EvidenceGraph.model_validate_json(
        (root / "artifacts/evidence/D-04-review/graph.json").read_text(encoding="utf-8")
    )
    data["graph"] = graph
    historical = load(root / "configs/d02-analytical-policies.json")
    assert historical["formula_execution_approvals"] == []
    baseline = SnapshotCatalog(
        **data,
        approval=PreparationApproval(**historical["preparation_approval"]),
        formula_policies=[PreparedFormulaPolicy(**p) for p in historical["formula_policies"]],
    )
    before = [
        baseline.select(d.document_id, d.snapshot_id).candidates[0].model_dump(mode="json")
        for d in data["descriptors"]
    ]
    assert before == load(root / "artifacts/evidence/D-04-review/catalog.json")
    assert sum(e["preparation_ready_metrics"] for e in before) == 18
    assert not sum(e["calculation_eligible_metrics"] for e in before)
    lineages = [
        trace_metric_lineage(
            m, graph, data["facts"], data["evidence"], expected_formula=m.definition
        ).model_dump(mode="json")
        for m in data["metrics"][:15]
    ]
    assert lineages == load(root / "artifacts/evidence/D-01/evaluation/lineages.json")
    assert [
        baseline.reviewed_lineage(target, m.metric_id).model_dump(mode="json")
        for m in data["metrics"][15:]
    ] == load(root / "artifacts/evidence/D-04-review/lineages.json")
    save(output / "before.json", before)
    execution = load(root / "configs/m4-execution-policies.json")
    approval = ExecutionCompatibilityApproval(**execution["execution_approval"])
    catalog = SnapshotCatalog(
        **data,
        approval=baseline.approval,
        execution_approval=approval,
        formula_policies=[PreparedFormulaPolicy(**p) for p in execution["formula_policies"]],
        formula_approvals=[
            FormulaExecutionApproval(**a) for a in execution["formula_execution_approvals"]
        ],
    )
    index = {f.observation_identity(): f for f in data["facts"]}
    closures = {}
    for descriptor in data["descriptors"]:
        selection = catalog.select(descriptor.document_id, descriptor.snapshot_id)
        assert selection.status == "selected"
        closures.update((c.metric_id, c) for c in selection.candidates[0].metrics)
    rows = []
    for metric in data["metrics"]:
        descriptor = next(
            d
            for d in data["descriptors"]
            if (d.document_id, d.snapshot_id)
            == (metric.request.document_id, metric.request.snapshot_id)
        )
        closure = closures[metric.metric_id]
        assert closure.readiness["global_compatibility"] == metric.compatibility.model_dump(
            mode="json"
        )
        assert metric.compatibility.status == "undetermined" and metric.result is None
        lineage = catalog.reviewed_lineage(descriptor, metric.metric_id)
        rows.append(
            dict(
                filing=next(
                    y for y, s in scopes.items() if s["document_id"] == descriptor.document_id
                ),
                formula=metric.definition.name,
                group="recovery" if descriptor.parent_snapshot_id else "baseline",
                snapshot=descriptor.model_dump(mode="json"),
                metric_id=metric.metric_id,
                operands=[
                    dict(
                        role=o.role,
                        observation=o.observation.model_dump(),
                        source_review=catalog.api.get_source_review(o.observation).model_dump(
                            mode="json"
                        ),
                        fact=index[o.observation].model_dump(mode="json"),
                        source_fact_node_id=o.source_fact_node_id,
                    )
                    for o in metric.operands
                ],
                accounting_basis=[
                    b.model_dump(mode="json")
                    for b in data["accounting_bases"]
                    if (b.document_id, b.snapshot_id)
                    == (descriptor.document_id, descriptor.snapshot_id)
                ],
                closure=closure.model_dump(mode="json"),
                reviewed_lineage=lineage.model_dump(mode="json"),
                computed=False,
            )
        )
    save(output / "metrics.json", rows)
    print("Assessed18 selected metric snapshots; checking29 queries/36 pairs/D-06", flush=True)
    effective, queries = regression_queries(root, data, scopes, target)
    save(output / "retrieval.json", queries)
    pairs = compare_observations(effective)
    assert pairs == load(root / "artifacts/evidence/D-02/cross-year-after-recovery.json")
    cross = []
    for pair in pairs:
        selected = [
            index[next(i for i in index if i.model_dump() == identity)]
            for identity in pair["observations"]
        ]
        spec = OperationCompatibilitySpec(
            operation_id="cross_document_comparison",
            rule_reference="M4-01/cross-document-negative-control",
            operands=[
                OperandRequirement(
                    role=role,
                    canonical_item_id=f.canonical_item_id,
                    semantic_role=f.semantic_role or "unknown",
                    statement_type=f.context.statement_type,
                )
                for role, f in zip(("left", "right"), selected, strict=True)
            ],
            period_relation="same",
            document_relation="any",
        )
        result = assess_execution_compatibility(
            spec,
            [
                FinancialOperand(role=role, fact=f)
                for role, f in zip(("left", "right"), selected, strict=True)
            ],
            data["source_reviews"],
            data["accounting_bases"],
            approval=approval,
        )
        assert (
            pair["status"] == "undetermined"
            and result.approved_execution_compatibility.status != "compatible"
        )
        cross.append(dict(baseline=pair, execution=result.model_dump(mode="json")))
    save(output / "cross-document.json", cross)
    save(output / "d06-regression.json", d06_regression(root))
    assert all(
        catalog.api.get_fact(f.observation_identity()).matches[0].record == f for f in data["facts"]
    )
    after_hashes = manifest(root)
    assert hashes == after_hashes, "protected_input_changed"
    save(output / "hashes-after.json", after_hashes)
    summary = dict(
        baseline_preparation_ready=15,
        recovery_preparation_ready=3,
        eligible_before=0,
        baseline_eligible_after=sum(
            r["closure"]["calculation_eligible"] for r in rows if r["group"] == "baseline"
        ),
        recovery_eligible_after=sum(
            r["closure"]["calculation_eligible"] for r in rows if r["group"] == "recovery"
        ),
        by_formula={
            name: {
                group: sum(
                    r["closure"]["calculation_eligible"]
                    for r in rows
                    if r["formula"] == name and r["group"] == group
                )
                for group in ("baseline", "recovery")
            }
            for name in ("gross_margin", "debt_to_assets", "revenue_yoy")
        },
        global_compatibility=dict(
            Counter(r["closure"]["readiness"]["global_compatibility"]["status"] for r in rows)
        ),
        computed_metrics=0,
        regression_queries=len(queries),
        cross_document_pairs=len(cross),
        cross_document_approved=0,
        exact_fact_lookups=len(data["facts"]),
        baseline_lineages_exact=15,
        recovery_lineages_exact=3,
        d06_validation_exact=True,
        protected_input_hashes=len(hashes),
        input_hashes_unchanged=True,
        formula_registry_sha256=digest(root / "configs/m4-execution-policies.json"),
        gateway_calls=0,
        financial_fact_verified=False,
        numeric_calculation_pass=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    assert summary["baseline_eligible_after"] == 15 and summary["recovery_eligible_after"] == 3, (
        "Inspect metrics.json blockers; do not relax policy"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M4-01"))
    args = parser.parse_args()
    evaluate(Path.cwd().resolve(), args.output.resolve())
