"""Negative controls M3-05; synthetic fixtures không là financial verification."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.evidence import (
    DerivedMetric,
    EvidenceGraph,
    FormulaDefinition,
    MetricRequest,
    PeriodPair,
    TaskQualityContext,
    build_graph,
    build_metric,
    validate_graph,
)
from vietnamese_financial_multi_agent.evidence.graph import graph_id

from .test_evidence_contracts import scenario


def inputs():
    spec, operands = scenario()
    definition = FormulaDefinition(
        formula_reference="M3-05/reference/gross-margin",
        formula_version="1",
        name="gross_margin",
        expression="right / left",
        compatibility=spec,
    )
    facts = [o.fact for o in operands]
    request = MetricRequest(
        document_id=facts[0].document_id,
        snapshot_id=facts[0].snapshot_id,
        operand_periods={"left": "2024", "right": "2024"},
    )
    return definition, request, facts


def test_binding_roundtrip_graph_and_no_execution():
    definition, request, facts = inputs()
    before = [f.model_dump_json() for f in facts]
    metric = build_metric(definition, request, facts)
    assert metric.compatibility.status == "compatible"
    assert metric.structural_readiness == "complete"
    assert metric.preparation_blockers == [
        "formula_policy_not_approved",
        "operand_evidence_not_displayable",
    ]
    assert metric.result is None and metric.result_status == "not_computed"
    assert DerivedMetric.model_validate_json(metric.model_dump_json()) == metric
    assert build_metric(definition, request, reversed(facts)) == metric
    graph = build_graph(facts, metrics=[metric])
    assert EvidenceGraph.model_validate_json(graph.model_dump_json()) == graph
    validation = validate_graph(graph, facts, metrics=[metric])
    assert {a.status for a in validation.nodes + validation.edges} == {"valid"}
    assert len([e for e in graph.edges if e.relation == "used_in"]) == 2
    assert before == [f.model_dump_json() for f in facts]
    old = build_graph(facts)
    assert graph.nodes[:-1] == old.nodes
    assert [e for e in graph.edges if e.relation != "used_in"] == old.edges
    with pytest.raises(ValidationError):
        DerivedMetric.model_validate_json(
            metric.model_dump_json().replace('"not_computed"', '"computed"')
        )
    payload = metric.model_dump()
    payload["result"] = Decimal("0.5")
    with pytest.raises(ValidationError):
        DerivedMetric.model_validate(payload)
    payload = metric.model_dump()
    payload["operands"][1]["role"] = "left"
    with pytest.raises(ValidationError):
        DerivedMetric.model_validate(payload)


def test_missing_ambiguous_and_attempt_isolation():
    definition, request, facts = inputs()
    metric = build_metric(definition, request, facts[:1])
    assert metric.binding_status == "partially_bound"
    assert metric.operands[1].status == "missing"
    assert [r.code for r in metric.compatibility.reasons] == ["missing_operand"]
    assert (
        len([e for e in build_graph(facts[:1], metrics=[metric]).edges if e.relation == "used_in"])
        == 1
    )
    duplicate = facts[0].model_copy(update={"local_observation_id": "another"})
    ambiguous = build_metric(definition, request, [*facts, duplicate])
    assert ambiguous.operands[0].candidate_count == 2
    assert ambiguous.binding_status == "ambiguous_candidates"
    assert ambiguous.operands[0].observation is None
    for field in ("document_id", "snapshot_id"):
        other = facts[1].model_copy(update={field: "other"})
        assert build_metric(definition, request, [facts[0], other]).operands[1].status == "missing"
    assert (
        build_metric(definition, request, [*facts, facts[0]]).binding_status
        == "ambiguous_candidates"
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("semantic_role", "wrong", "semantic_role_mismatch"),
        ("company_id", None, "missing_company_id"),
        ("reporting_scope", "consolidated", "reporting_scope_mismatch"),
        ("currency", "USD", "currency_mismatch"),
        ("scale", Decimal("1000"), "scale_mismatch"),
        ("unit", "USD", "unit_mismatch"),
        ("provenance", "cell", "unsupported_cell_provenance"),
    ],
)
def test_compatibility_reuses_m3_01(field, value, reason):
    definition, request, facts = inputs()
    f = facts[1]
    if field in {"reporting_scope", "currency", "scale"}:
        setattr(f.context, field, value)
    elif field == "unit":
        f.value.unit = value
    elif field == "provenance":
        f.sources[0].reference.provenance_level = value
    else:
        setattr(f, field, value)
    metric = build_metric(definition, request, facts)
    assert metric.structural_readiness == "complete"
    assert reason in [r.code for r in metric.compatibility.reasons]
    assert metric.compatibility.status != "compatible"


def test_wrong_statement_period_and_reference_integrity():
    definition, request, facts = inputs()
    facts[1].context.statement_type = "B01"
    assert build_metric(definition, request, facts).operands[1].status == "missing"
    facts[1].context.statement_type = "B02"
    facts[1].context.period = "2025"
    request.operand_periods["right"] = "2025"
    metric = build_metric(definition, request, facts)
    assert "period_mismatch" in [r.code for r in metric.compatibility.reasons]
    graph = build_graph(facts, metrics=[metric])
    assert "missing_operand_reference" in {
        r for a in validate_graph(graph, facts[:1], metrics=[metric]).nodes for r in a.reasons
    }
    edge = next(e for e in graph.edges if e.relation == "used_in")
    edge.operand_role = "wrong"
    edge.edge_id = graph_id("used_in", [edge.source, edge.target, "wrong"])
    validation = validate_graph(graph, facts, metrics=[metric])
    assert "operand_relation_mismatch" in {r for a in validation.edges for r in a.reasons}
    assert "missing_operand_edge" in {r for a in validation.nodes for r in a.reasons}
    edge.source, edge.target = edge.target, edge.source
    assert "edge_domain_mismatch" in {
        r for a in validate_graph(graph, facts, metrics=[metric]).edges for r in a.reasons
    }


def test_ordered_pair_quality_missing_source_and_snapshot_tampering():
    definition, request, facts = inputs()
    definition.compatibility.period_relation = "ordered_pair"
    definition.compatibility.period_pairs = [
        PeriodPair(left="2025", right="2024", period_type="fiscal_year")
    ]
    metric = build_metric(definition, request, facts)
    assert "period_relation_mismatch" in [r.code for r in metric.compatibility.reasons]
    facts[0].sources = []
    facts[0].value.normalized_value = None
    facts[0].quality_context = [
        TaskQualityContext(
            task_type="direct_qa",
            decision="insufficient",
            evidence_ids=["original"],
            caveats=["preserved"],
        )
    ]
    metric = build_metric(definition, request, facts)
    assert "missing_provenance" in [r.code for r in metric.compatibility.reasons]
    assert metric.evidence_usability[0].display_status == "blocked"
    assert metric.evidence_usability[0].quality_context == facts[0].quality_context
    assert "missing_operand_value" in metric.preparation_blockers
    metric.operands[0].observation = metric.operands[0].observation.model_copy(
        update={"snapshot_id": "other"}
    )
    graph = build_graph(facts, metrics=[metric])
    validation = validate_graph(graph, facts, metrics=[metric])
    assert "operand_document_snapshot_mismatch" in {r for a in validation.nodes for r in a.reasons}
    # Không tạo SourceFact/cạnh thay thế cho reference không tồn tại.
    assert len([e for e in graph.edges if e.relation == "used_in"]) == 1
