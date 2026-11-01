"""BBS-specific bounded evaluation; runtime không phụ thuộc paths/years trong file này.

--prepare: hash inputs và render original PDF. Đọc ảnh trước --evaluate; evaluator
chỉ bind controlled readings đã đối chiếu, không gọi Gemini/OCR/extraction.
"""

import argparse
import json
from pathlib import Path

import pypdfium2 as pdfium
from evaluate_d01_coverage import ROLES, compare_observations, fixed_queries
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DerivedMetric,
    DocumentEvidenceRepository,
    EvidenceGraph,
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
    PreparationApproval,
    PreparedFormulaPolicy,
)
from vietnamese_financial_multi_agent.evidence.snapshots import (
    SnapshotCatalog,
    SnapshotDescriptor,
    rebuild_snapshot_metrics,
)
from vietnamese_financial_multi_agent.evidence.source_reviews import bind_source_review


def save(path, value):
    if path.exists():
        if load(path) != value:
            raise ValueError("Use a new output directory; existing output differs")
        return
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def manifest(root):
    paths = set(load(root / "artifacts/evidence/D-03-final-audit/hashes-before.json"))
    for folder in ("D-03-final-audit", "D-02"):
        paths.update(
            p.relative_to(root).as_posix()
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    return {p: digest(root / p) for p in sorted(paths)}


def prepare(root, output):
    if output.exists():
        raise ValueError("Use a NEW ignored output directory")
    output.mkdir(parents=True)
    save(output / "hashes-before.json", manifest(root))
    row = next(
        r for r in load(root / "artifacts/evidence/D-01/inventory.json") if r["year"] == 2022
    )
    assert digest(root / row["pdf"]) == row["sha256"]
    pdf = pdfium.PdfDocument(root / row["pdf"])
    renders = []
    try:
        for number in (5, 6, 7, 9):
            page = pdf[number - 1]
            bitmap = page.render(scale=1.5)
            try:
                bitmap.to_pil().save(output / f"source-{number}.png")
            finally:
                bitmap.close()
                page.close()
            renders.append(
                dict(
                    document_id="sha256:" + row["sha256"],
                    pdf_sha256=row["sha256"],
                    pdf_page=number,
                    image_sha256=digest(output / f"source-{number}.png"),
                    reference=f"source-{number}.png",
                    method="original_pdf_render",
                )
            )
    finally:
        pdf.close()
    save(output / "renders.json", renders)
    print(
        json.dumps(
            dict(
                prepared=True,
                input_hashes=len(load(output / "hashes-before.json")),
                source_pages=[r["pdf_page"] for r in renders],
            )
        )
    )


def evaluate(root, output):
    before_hashes = load(output / "hashes-before.json")
    assert before_hashes == manifest(root), "input_changed"
    base, previous = root / "artifacts/evidence/D-01/evaluation", root / "artifacts/evidence/D-02"
    inventory = load(base.parent / "inventory.json")
    registry = load(root / "configs/d02-analytical-policies.json")
    approval = PreparationApproval(**registry["preparation_approval"])
    policies = [PreparedFormulaPolicy(**p) for p in registry["formula_policies"]]
    assert not registry["formula_execution_approvals"]
    reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(previous / "source-reviews.json")
    ]
    existing_recovery_reviews = [
        SourceReview.model_validate_json(json.dumps(r))
        for r in load(previous / "recovery-source-reviews.json")
    ]
    bases = [AccountingBasisReview(**b) for b in load(previous / "accounting-basis-reviews.json")]
    facts, evidence, descriptors, scopes, results = [], [], [], {}, {}
    for row in inventory:
        assert digest(root / row["pdf"]) == row["sha256"]
        result = load(base / str(row["year"]) / "normalized-result.json")
        results[row["year"]] = result
        scope = dict(document_id=result["document_id"], snapshot_id=result["attempt_id"])
        scopes[row["year"]] = scope
        descriptors.append(
            SnapshotDescriptor(**scope, pdf_sha256=row["sha256"], origin="normalized_projection")
        )
        facts.extend(
            CanonicalFactRepository(base / str(row["year"]) / "canonical").list_by_document(**scope)
        )
        evidence.extend(evidence_from_persisted_result(result))
    metrics = [
        DerivedMetric.model_validate_json(json.dumps(m)) for m in load(base / "metrics.json")
    ]
    recovered_result = load(previous / "recovery-2022/normalized-result.json")
    recovered = facts_from_persisted_result(
        recovered_result, company_id=recovered_result["metadata_binding"]["company_id"]
    )
    for fact in recovered:
        fact.semantic_role = ROLES.get(fact.canonical_item_id)
    recovered_evidence = evidence_from_persisted_result(recovered_result)
    original_descriptor = next(
        d for d in descriptors if d.document_id == recovered_result["document_id"]
    )
    target = SnapshotDescriptor(
        document_id=recovered_result["document_id"],
        snapshot_id=recovered_result["attempt_id"],
        pdf_sha256=original_descriptor.pdf_sha256,
        parent_snapshot_id=original_descriptor.snapshot_id,
        origin="recovery",
    )
    descriptors.append(target)
    original_metrics = [m for m in metrics if m.request.document_id == target.document_id]
    old_index = {f.observation_identity(): f for f in facts}
    recovery_only = EvidenceRetrieval(recovered, recovered_evidence, source_reviews=reviews)
    before = []
    for metric in original_metrics:
        # Explicitly requested target view; old references remain old and fail resolution.
        count = sum(
            recovery_only.get_fact(o.observation).status == "found" for o in metric.operands
        )
        closure = SnapshotCatalog(
            descriptors,
            recovered,
            recovered_evidence,
            metrics,
            source_reviews=reviews,
            accounting_bases=bases,
        ).assess_metric(target, metric)
        before.append(
            dict(
                metric_id=metric.metric_id,
                selected_snapshot=target.snapshot_id,
                old_operand_references=[o.observation.model_dump() for o in metric.operands],
                resolved=count,
                preparation_ready=closure.preparation_ready,
                closure=closure.model_dump(mode="json"),
            )
        )
    save(output / "before.json", before)
    new_metrics = rebuild_snapshot_metrics(
        [(m.definition, m.request.operand_periods) for m in original_metrics], target, recovered
    )
    renders = {r["pdf_page"]: r for r in load(output / "renders.json")}
    for render in renders.values():
        assert render["pdf_sha256"] == target.pdf_sha256
        assert digest(output / render["reference"]) == render["image_sha256"]
    # Reuse evidence only after fresh visual inspection of original PDF pages 5/6/7/9.
    # Exact equivalence below includes identities, payload selectors, value/unit/scale,
    # context and quality; not just equality of numeric values.
    recovery_index = {f.observation_identity(): f for f in recovered}
    verifications, new_reviews = [], []
    records = {r["source"]["page"]["page"]: r for r in recovered_result["records"]}
    unique_refs = sorted(
        {o.observation for m in new_metrics for o in m.operands}, key=lambda i: i.model_dump_json()
    )
    for identity in unique_refs:
        fact = recovery_index[identity]
        parent_id = identity.model_copy(update={"snapshot_id": original_descriptor.snapshot_id})
        original = old_index[parent_id]
        old_review = next(r for r in reviews if r.observation == parent_id)

        def comparable(f):
            value = f.model_dump(mode="json")
            value.pop("snapshot_id")
            value.pop("source_metadata")
            for source in value["sources"]:
                source.pop("snapshot_id")
            return value

        assert comparable(original) == comparable(fact), "source_equivalence_not_established"
        assert all(original.source_metadata.get(k) == v for k, v in fact.source_metadata.items())
        page = old_review.pdf_page
        reference = (
            output.relative_to(root / "artifacts/evidence").as_posix()
            + "/verification-records.json#"
            + str(len(verifications))
        )
        reading = old_review.model_dump(
            exclude={"sources", "value_selector", "label_selector", "header_selector"}
        )
        reading.update(
            observation=identity,
            reused_from=parent_id,
            verification_reference=reference,
            review_reference=output.relative_to(root / "artifacts/evidence").as_posix()
            + f"/source-{page}.png",
            review_image_sha256=renders[page]["image_sha256"],
        )
        review = bind_source_review(fact, reading, records[page]["response"]["output"]["payload"])
        verifications.append(
            dict(
                observation=identity.model_dump(),
                parent=parent_id.model_dump(),
                pdf_sha256=target.pdf_sha256,
                pdf_page=page,
                render=renders[page],
                verification_reference=reference,
                method="controlled_original_pdf_visual_read",
                parent_only_metadata=sorted(
                    set(original.source_metadata) - set(fact.source_metadata)
                ),
                checks=dict(
                    canonical_item=True,
                    periods=True,
                    unit_scale=True,
                    raw_normalized_value=True,
                    exact_source_selectors=True,
                    source_row_header=True,
                    quality_preserved=True,
                ),
                source_selectors=[
                    review.value_selector,
                    review.label_selector,
                    review.header_selector,
                ],
            )
        )
        new_reviews.append(review)
    old_basis = next(b for b in bases if b.document_id == target.document_id)
    new_basis = old_basis.model_copy(deep=True)
    new_basis.snapshot_id = target.snapshot_id
    new_basis.reused_from_snapshot = original_descriptor.snapshot_id
    new_basis.verification_reference = (
        output.relative_to(root / "artifacts/evidence").as_posix() + "/basis-verification.json"
    )
    new_basis.review_reference = (
        output.relative_to(root / "artifacts/evidence").as_posix()
        + f"/source-{old_basis.pdf_page}.png"
    )
    new_basis.review_image_sha256 = renders[old_basis.pdf_page]["image_sha256"]
    save(
        output / "basis-verification.json",
        dict(
            document_id=target.document_id,
            snapshot_id=target.snapshot_id,
            parent_snapshot_id=original_descriptor.snapshot_id,
            pdf_sha256=target.pdf_sha256,
            source_quote=new_basis.source_quote,
            render=renders[old_basis.pdf_page],
            method="controlled_original_pdf_visual_read",
            same_source_document=True,
            basis_quote_rechecked=True,
            statement_types=new_basis.statement_types,
        ),
    )
    save(output / "verification-records.json", verifications)
    save(output / "source-reviews.json", [r.model_dump(mode="json") for r in new_reviews])
    save(output / "accounting-basis-reviews.json", [new_basis.model_dump(mode="json")])
    save(output / "metrics.json", [m.model_dump(mode="json") for m in new_metrics])
    save(output / "snapshots.json", [d.model_dump(mode="json") for d in descriptors])
    all_facts, all_evidence = [*facts, *recovered], [*evidence, *recovered_evidence]
    all_metrics, all_reviews, all_bases = (
        [*metrics, *new_metrics],
        [*reviews, *existing_recovery_reviews, *new_reviews],
        [*bases, new_basis],
    )
    graph = build_graph(all_facts, all_evidence, all_metrics)
    catalog = SnapshotCatalog(
        descriptors,
        all_facts,
        all_evidence,
        all_metrics,
        graph=graph,
        source_reviews=all_reviews,
        accounting_bases=all_bases,
        approval=approval,
        formula_policies=policies,
    )
    entries = [catalog.select(d.document_id, d.snapshot_id).candidates[0] for d in descriptors]
    save(output / "catalog.json", [e.model_dump(mode="json") for e in entries])
    save(output / "graph.json", graph.model_dump(mode="json"))
    overlays = [catalog.reviewed_lineage(target, m.metric_id) for m in new_metrics]
    save(output / "lineages.json", [o.model_dump(mode="json") for o in overlays])
    # Persist projection via existing repositories; no alternate storage schema/engine.
    for fact in recovered:
        CanonicalFactRepository(output / "canonical").put(fact)
    for record in recovered_evidence:
        DocumentEvidenceRepository(output / "document-evidence").put(record)
    restarted_facts = CanonicalFactRepository(output / "canonical").list_by_document(
        target.document_id, target.snapshot_id
    )
    assert restarted_facts == recovered
    restart_metrics = [
        DerivedMetric.model_validate_json(json.dumps(m)) for m in load(output / "metrics.json")
    ]
    assert restart_metrics == new_metrics
    restarted = SnapshotCatalog(
        [SnapshotDescriptor(**d) for d in load(output / "snapshots.json")],
        [*facts, *restarted_facts],
        [
            *evidence,
            *DocumentEvidenceRepository(output / "document-evidence").list_by_document(
                target.document_id, target.snapshot_id
            ),
        ],
        [*metrics, *restart_metrics],
        graph=EvidenceGraph.model_validate_json(
            (output / "graph.json").read_text(encoding="utf-8")
        ),
        source_reviews=[
            *reviews,
            *existing_recovery_reviews,
            *[
                SourceReview.model_validate_json(json.dumps(r))
                for r in load(output / "source-reviews.json")
            ],
        ],
        accounting_bases=[
            *bases,
            *[AccountingBasisReview(**b) for b in load(output / "accounting-basis-reviews.json")],
        ],
        approval=approval,
        formula_policies=policies,
    )
    assert restarted.select(target.document_id, target.snapshot_id) == catalog.select(
        target.document_id, target.snapshot_id
    )
    assert [restarted.reviewed_lineage(target, m.metric_id) for m in restart_metrics] == overlays
    assert all(
        catalog.api.get_source_review(r.observation).matches[0].status == "value_row_verified"
        for r in all_reviews
    )
    # Baseline 15 readiness and lineage remain exact to accepted persisted evidence.
    baseline_rows = load(root / "artifacts/evidence/D-02-final/metrics-readiness.json")
    for metric, old in zip(metrics, baseline_rows, strict=True):
        operands = [
            FinancialOperand(role=o.role, fact=old_index[o.observation]) for o in metric.operands
        ]
        readiness = assess_analytical_readiness(
            metric.definition.compatibility,
            operands,
            reviews,
            bases,
            approval=approval,
            formula_policy=next(p for p in policies if p.formula_id == metric.definition.name),
        )
        for key, value in readiness.items():
            assert value == old[key], (metric.metric_id, key)
    baseline_lineages = [
        trace_metric_lineage(
            m, graph, all_facts, all_evidence, expected_formula=m.definition
        ).model_dump(mode="json")
        for m in metrics
    ]
    assert baseline_lineages == load(base / "lineages.json")
    effective = [f for f in facts if f.document_id != target.document_id] + recovered
    assert compare_observations(effective) == load(previous / "cross-year-after-recovery.json")
    # Keep the exact accepted 29 query cases and results for regression.
    effective_evidence = [
        e for e in evidence if e.document_id != target.document_id
    ] + recovered_evidence
    scopes[2022]["snapshot_id"] = target.snapshot_id
    api = EvidenceRetrieval(
        effective,
        effective_evidence,
        coverage=[
            CanonicalCoverage(
                **scope,
                canonical_extraction="available",
                missing_canonical_items=["b01.short_term_liabilities"],
                inventory_reference="D-01/inventory",
            )
            for scope in scopes.values()
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
            legacy = facts_from_persisted_result(load(base.parent / "2021/result.json"))
            result = EvidenceRetrieval([*effective, *legacy]).find_facts(
                query.model_copy(update={"snapshot_id": None})
            )
        else:
            result = api.find_facts(query)
        assert result.model_dump(mode="json") == q["result"], case["id"]
        if case["operation"] == "get_sources":
            sources = [
                api.get_sources(
                    RetrievalReference(kind="fact", observation=m.record.observation_identity())
                ).model_dump(mode="json")
                for m in result.matches
            ]
            assert sources == q["sources"]
    assert all(
        catalog.api.get_fact(f.observation_identity()).matches[0].record == f for f in all_facts
    )
    recovery_entry = next(e for e in entries if e.descriptor == target)
    original_entry = next(e for e in entries if e.descriptor == original_descriptor)
    summary = dict(
        baseline_metrics=len(metrics),
        baseline_preparation_ready=sum(
            c.preparation_ready for e in entries if e.descriptor != target for c in e.metrics
        ),
        original_preparation_ready=original_entry.preparation_ready_metrics,
        recovery_before_preparation_ready=sum(r["preparation_ready"] for r in before),
        recovery_before_resolved=sum(r["resolved"] for r in before),
        recovery_preparation_ready=recovery_entry.preparation_ready_metrics,
        recovery_metrics=len(new_metrics),
        recovery_closed=sum(c.status == "closed" for c in recovery_entry.metrics),
        recovery_resolved=sum(c.resolved_operands for c in recovery_entry.metrics),
        recovery_operand_occurrences=sum(c.operand_count for c in recovery_entry.metrics),
        new_source_reviews=len(new_reviews),
        existing_recovery_reviews=len(existing_recovery_reviews),
        verified_review_bindings=len(all_reviews),
        persisted_restart_exact=True,
        new_basis_reviews=len([new_basis]),
        baseline_lineages_exact=len(baseline_lineages),
        exact_fact_lookups=len(all_facts),
        regression_queries=len(queries),
        cross_year_pairs=len(compare_observations(effective)),
        calculation_eligible=sum(c.calculation_eligible for e in entries for c in e.metrics),
        snapshot_selection=catalog.select(target.document_id).status,
        input_hashes=len(before_hashes),
        input_hashes_unchanged=before_hashes == manifest(root),
        gateway_calls=0,
        financial_accuracy_scope="controlled selected BBS operand rows; not full-PDF or independent human gold",
    )
    assert summary["input_hashes_unchanged"]
    assert summary["baseline_preparation_ready"] == len(metrics)
    assert summary["recovery_preparation_ready"] == len(new_metrics)
    assert summary["recovery_resolved"] == summary["recovery_operand_occurrences"]
    assert not summary["calculation_eligible"]
    save(output / "hashes-after.json", manifest(root))
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under configured artifacts/evidence")
    (prepare if args.prepare else evaluate)(root, output)
