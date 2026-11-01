"""Generic contract controls; synthetic PASS không chứng minh chất lượng PDF thật."""

import pytest
from vietnamese_financial_multi_agent.evidence import (
    EvidenceGraph,
    FormulaDefinition,
    TableEvidence,
    build_graph,
)
from vietnamese_financial_multi_agent.evidence.snapshots import (
    SnapshotCatalog,
    SnapshotDescriptor,
    rebuild_snapshot_metrics,
)
from vietnamese_financial_multi_agent.evidence.source_reviews import bind_source_review

from .test_d02_readiness import preparation_approval, sample


def fixture():
    descriptors, facts, evidence, metrics, reviews, bases = [], [], [], [], [], []
    for doc, salt in enumerate(("a", "d")):
        for attempt, parent in (
            ("original", None),
            ("fix-one", "original"),
            ("fix-two", "fix-one"),
            ("alternative", "original"),
        ):
            spec, operands, old_reviews, old_bases = sample()
            descriptor = SnapshotDescriptor(
                document_id="sha256:" + salt * 64,
                pdf_sha256=salt * 64,
                snapshot_id=attempt,
                parent_snapshot_id=parent,
                origin="original_extraction" if parent is None else "recovery",
            )
            descriptors.append(descriptor)
            roles = ("opening", "closing") if doc else ("numerator", "denominator")
            selected = []
            for i, (o, r) in enumerate(zip(operands, old_reviews, strict=True)):
                f = o.fact
                f.document_id, f.snapshot_id = descriptor.document_id, attempt
                f.local_observation_id = f"observation-{doc}-{i}"
                spec.operands[i].role = roles[i]
                # Independent document source refs/page/selector prefixes.
                for source in f.sources:
                    source.document_id, source.snapshot_id = descriptor.document_id, attempt
                    source.reference.anchor.page.source_ref = descriptor.document_id
                    source.reference.anchor.page.page = 7 + doc
                    source.reference.source_pointer = source.reference.source_pointer.replace(
                        "/tables/0/", f"/tables/{doc + i}/"
                    )
                selected.append(f)
                reading = r.model_dump(
                    exclude={"sources", "value_selector", "label_selector", "header_selector"}
                )
                reading.update(
                    observation=f.observation_identity(),
                    pdf_sha256=salt * 64,
                    pdf_page=7 + doc,
                    verification_reference=f"verify/{doc}/{attempt}/{i}",
                    reused_from=f.observation_identity().model_copy(update={"snapshot_id": parent})
                    if parent
                    else None,
                )
                cells = [
                    dict(text=f.context.raw_item_label, row=1, column=0, reading="observed"),
                    dict(text="unused", row=1, column=1, reading="observed"),
                    dict(text=f.value.raw_value, row=1, column=2, reading="observed"),
                ]
                table = dict(
                    cells=cells,
                    headers=[dict(text=f.raw_header, row=0, column=2, reading="observed")],
                )
                payload = dict(tables=[{}] * (doc + i) + [table])
                reviews.append(bind_source_review(f, reading, payload))
                evidence.append(
                    TableEvidence(
                        document_id=f.document_id,
                        snapshot_id=attempt,
                        local_evidence_id=f"table-{i}",
                        member_sources=f.sources,
                    )
                )
            basis = old_bases[0].model_copy(deep=True)
            basis.document_id, basis.snapshot_id, basis.pdf_sha256 = (
                descriptor.document_id,
                attempt,
                salt * 64,
            )
            basis.verification_reference = f"basis/{doc}/{attempt}"
            basis.reused_from_snapshot = parent
            bases.append(basis)
            definition = FormulaDefinition(
                formula_reference=f"synthetic/{doc}",
                formula_version="v1",
                name=f"arbitrary_metric_{doc}",
                expression=" / ".join(roles),
                compatibility=spec,
            )
            metrics.extend(
                rebuild_snapshot_metrics(
                    [
                        (
                            definition,
                            {r: f.context.period for r, f in zip(roles, selected, strict=True)},
                        )
                    ],
                    descriptor,
                    selected,
                )
            )
            facts.extend(selected)
    return dict(
        descriptors=descriptors,
        facts=facts,
        evidence=evidence,
        metrics=metrics,
        graph=build_graph(facts, evidence, metrics),
        source_reviews=reviews,
        accounting_bases=bases,
        approval=preparation_approval(),
    )


def test_independent_documents_deep_chains_roles_and_restart():
    inputs = fixture()
    before = [f.model_dump_json() for f in inputs["facts"]]
    catalog = SnapshotCatalog(**inputs)
    for descriptor in inputs["descriptors"]:
        selected = catalog.select(descriptor.document_id, descriptor.snapshot_id)
        assert selected.status == "selected"
        entry = selected.candidates[0]
        assert entry.readiness == "closed" and entry.fact_count == 2
        assert entry.metrics[0].preparation_ready and not entry.metrics[0].calculation_eligible
        assert entry.metrics[0].resolved_operands == entry.metrics[0].operand_count
        overlay = catalog.reviewed_lineage(descriptor, entry.metrics[0].metric_id)
        assert overlay.status == "found" and overlay.lineage.completeness == "complete"
        assert all(
            b.matches[0].status == "value_row_verified"
            for o in overlay.operands
            for b in o.bindings
        )
        assert all(
            a.reference.anchor.status == "uncertain"
            for o in overlay.lineage.operands
            for a in o.anchors
        )
        if descriptor.snapshot_id == "fix-two":
            assert entry.snapshot_chain == ["fix-two", "fix-one", "original"]
        assert catalog.select(descriptor.document_id).status == "ambiguous"
    reloaded = [
        SnapshotDescriptor.model_validate_json(d.model_dump_json()) for d in inputs["descriptors"]
    ]
    restarted = SnapshotCatalog(**{**inputs, "descriptors": reloaded})
    assert (
        restarted.select(reloaded[0].document_id).model_dump()
        == catalog.select(reloaded[0].document_id).model_dump()
    )
    assert before == [f.model_dump_json() for f in inputs["facts"]]


@pytest.mark.parametrize(
    "damage,code",
    [
        ("parent_review", "unverified"),
        ("missing_review", "unverified"),
        ("hash", "document_hash_mismatch"),
        ("row", "source_inconsistent"),
        ("duplicate_review", "source_inconsistent"),
        ("conflicting_review", "source_inconsistent"),
        ("basis", "accounting_basis_missing"),
        ("wrong_metric", "metric_snapshot_mismatch"),
        ("edge", "missing_used_in_edge"),
        ("ambiguous_fact", "operand_ambiguous"),
        ("missing_fact", "operand_missing"),
        ("source", "source_snapshot_mismatch"),
        ("association_edge", "missing_associated_with_edge"),
        ("basis_hash", "accounting_basis_source_inconsistent"),
        ("review_verification", "source_inconsistent"),
        ("missing_evidence", "document_evidence_missing"),
    ],
)
def test_exact_bindings_fail_closed(damage, code):
    inputs = fixture()
    d = inputs["descriptors"][2]
    metric = inputs["metrics"][2]
    fact = next(
        f for f in inputs["facts"] if f.observation_identity() == metric.operands[0].observation
    )
    review = next(
        r for r in inputs["source_reviews"] if r.observation == fact.observation_identity()
    )
    if damage in {"parent_review", "missing_review"}:
        inputs["source_reviews"].remove(review)
    elif damage == "hash":
        d.pdf_sha256 = "e" * 64
    elif damage == "row":
        fact.sources[0].reference.source_pointer = "/tables/0/cells/999"
    elif damage in {"duplicate_review", "conflicting_review"}:
        duplicate = review.model_copy(deep=True)
        if damage == "conflicting_review":
            duplicate.raw_label = "different row, same value"
        inputs["source_reviews"].append(duplicate)
    elif damage == "basis":
        inputs["accounting_bases"] = [
            b
            for b in inputs["accounting_bases"]
            if (b.document_id, b.snapshot_id) != (d.document_id, d.snapshot_id)
        ]
    elif damage == "wrong_metric":
        metric = inputs["metrics"][0]
    elif damage == "edge":
        inputs["graph"] = EvidenceGraph(
            nodes=inputs["graph"].nodes,
            edges=[e for e in inputs["graph"].edges if e.relation != "used_in"],
        )
    elif damage == "ambiguous_fact":
        duplicate = fact.model_copy(deep=True)
        duplicate.value.raw_value = "9.999"
        inputs["facts"].append(duplicate)
    elif damage == "missing_fact":
        inputs["facts"].remove(fact)
    elif damage == "source":
        fact.sources[0].snapshot_id = "original"
    elif damage == "association_edge":
        inputs["graph"].edges = [
            e for e in inputs["graph"].edges if e.relation != "associated_with"
        ]
    elif damage == "basis_hash":
        next(
            b
            for b in inputs["accounting_bases"]
            if (b.document_id, b.snapshot_id) == (d.document_id, d.snapshot_id)
        ).pdf_sha256 = "f" * 64
    elif damage == "review_verification":
        review.verification_reference = None
    elif damage == "missing_evidence":
        inputs["evidence"] = []
    result = SnapshotCatalog(**inputs).assess_metric(d, metric)
    assert result.status != "closed" and not result.preparation_ready
    assert code in [i.code for i in result.issues]


def test_parent_cycles_quality_and_snapshot_isolation():
    inputs = fixture()
    d, metric = inputs["descriptors"][2], inputs["metrics"][2]
    f = next(
        f for f in inputs["facts"] if f.observation_identity() == metric.operands[0].observation
    )
    for decision in ("insufficient", "conflicted"):
        f.quality_context[0].decision = decision
        result = SnapshotCatalog(**inputs).assess_metric(d, metric)
        assert not result.preparation_ready and not result.calculation_eligible
    inputs["descriptors"][0].parent_snapshot_id = "fix-two"
    assert SnapshotCatalog(**inputs).select(d.document_id, d.snapshot_id).status == "blocked"
    inputs["descriptors"][0].parent_snapshot_id = "absent"
    catalog = SnapshotCatalog(**inputs)
    assert catalog.select(d.document_id, d.snapshot_id).status == "blocked"
    # Another document remains selectable and sources retain its own PDF page.
    other = inputs["descriptors"][-1]
    assert catalog.select(other.document_id, other.snapshot_id).status == "selected"
    identity = inputs["metrics"][-1].operands[0].observation
    assert (
        catalog.api.get_source_review(identity)
        .matches[0]
        .original_sources[0]
        .reference.anchor.page.page
        == 8
    )
    assert (
        catalog.api.get_source_review(identity.model_copy(update={"snapshot_id": "absent"})).status
        == "not_found"
    )
