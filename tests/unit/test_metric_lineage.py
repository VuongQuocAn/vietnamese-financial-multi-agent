"""Focused lineage controls; synthetic cases không chứng minh financial accuracy."""

import pytest
from vietnamese_financial_multi_agent.evidence import (
    MetricLineage,
    TaskQualityContext,
    TextEvidence,
    build_graph,
    build_metric,
    trace_metric_lineage,
)
from vietnamese_financial_multi_agent.evidence.graph import graph_id

from .test_derived_metrics import inputs


def trace(facts=None):
    definition, request, original = inputs()
    facts = original if facts is None else facts
    metric = build_metric(definition, request, facts)
    graph = build_graph(facts, metrics=[metric])
    return metric, graph, facts


def test_complete_roundtrip_exact_association_and_no_result():
    metric, _, facts = trace()
    evidence = TextEvidence(
        document_id=facts[0].document_id,
        snapshot_id=facts[0].snapshot_id,
        local_evidence_id="exact",
        raw_text="synthetic",
        sources=facts[0].sources,
    )
    graph = build_graph(facts, [evidence], [metric])
    before = [f.model_dump_json() for f in facts]
    result = trace_metric_lineage(metric, graph, facts, [evidence])
    assert result.completeness == "complete"
    assert result.compatibility == metric.compatibility
    assert result.tasks.arithmetic_preparation == "prepared"
    assert result.tasks.calculation == "blocked"
    assert result.tasks.analytical_interpretation == "undetermined"
    assert result.tasks.claim_verification == "not_verified"
    assert result.result is None and result.result_status == "not_computed"
    assert result.operands[0].associations[0].evidence.local_id == "exact"
    assert result.operands[0].anchors == facts[0].sources
    assert MetricLineage.model_validate_json(result.model_dump_json()) == result
    assert trace_metric_lineage(metric, graph, reversed(facts), [evidence]) == result
    result.operands[0].observations[0].value.raw_value = "changed-copy"
    assert before == [f.model_dump_json() for f in facts]


@pytest.mark.parametrize(
    "damage",
    [
        "fact",
        "anchor",
        "source_edge",
        "dangling_used_in",
        "role",
        "binding_role",
        "document",
        "snapshot",
        "formula_version",
        "formula_reference",
        "metric_node",
    ],
)
def test_broken_references(damage):
    metric, graph, facts = trace()
    expected = None
    if damage == "fact":
        facts = facts[1:]
    elif damage == "anchor":
        graph.nodes = [n for n in graph.nodes if n.kind != "anchor"]
    elif damage == "source_edge":
        graph.edges = [e for e in graph.edges if e.relation != "from_source"]
    elif damage == "metric_node":
        graph.nodes = [n for n in graph.nodes if n.kind != "derived_metric"]
    elif damage == "binding_role":
        metric.operands[0].role = "wrong"
    elif damage in {"document", "snapshot"}:
        field = damage + "_id"
        metric.operands[0].observation = metric.operands[0].observation.model_copy(
            update={field: "other"}
        )
    elif damage.startswith("formula"):
        expected = metric.definition.model_copy(update={damage: "other"})
    else:
        edge = next(e for e in graph.edges if e.relation == "used_in")
        if damage == "dangling_used_in":
            edge.source = "absent"
        else:
            edge.operand_role = "wrong"
        edge.edge_id = graph_id("used_in", [edge.source, edge.target, edge.operand_role])
    result = trace_metric_lineage(metric, graph, facts, expected_formula=expected)
    assert result.completeness == "broken"
    assert result.unresolved
    assert result.tasks.calculation == "blocked"


def test_partial_ambiguous_missing_history_and_observation_identity():
    definition, request, facts = inputs()
    for field in ("document_id", "snapshot_id"):
        other = facts[1].model_copy(update={field: "other"})
        metric, graph, selected = trace([facts[0], other])
        result = trace_metric_lineage(metric, graph, selected)
        assert result.completeness == "partial"
        assert result.operands[1].observations == []
    request.operand_periods["left"] = "2021"
    missing = build_metric(definition, request, facts)
    assert (
        trace_metric_lineage(missing, build_graph(facts, metrics=[missing]), facts).completeness
        == "partial"
    )
    duplicate = facts[0].model_copy(update={"local_observation_id": "duplicate"})
    metric, graph, selected = trace([*facts, duplicate])
    result = trace_metric_lineage(metric, graph, selected)
    assert result.completeness == "ambiguous"
    assert len(result.operands[0].observations) == 2
    # Original/comparative cùng financial period/value vẫn hai identities, không merge.
    original = facts[0].model_copy(update={"document_id": "original-filing"})
    metric, graph, selected = trace([*facts, original])
    result = trace_metric_lineage(metric, graph, selected)
    assert result.operands[0].observations == [facts[0]]
    assert original.observation_identity() != facts[0].observation_identity()


@pytest.mark.parametrize("decision", ["usable", "usable_with_caveat", "insufficient", "conflicted"])
def test_quality_propagation_and_uncertain_page(decision):
    definition, request, facts = inputs()
    facts[0].company_id = None
    facts[0].context.reporting_scope = None
    facts[0].sources[0].reference.provenance_level = "page"
    facts[0].sources[0].reference.anchor.status = "uncertain"
    facts[0].sources[0].reference.source_pointer = "/distinct-source"
    facts[0].quality_context = [
        TaskQualityContext(
            task_type="direct_qa",
            decision=decision,
            evidence_ids=["original"],
            issues=[dict(code="original_reason", detail="kept")],
            caveats=["kept caveat"],
        )
    ]
    metric = build_metric(definition, request, facts)
    result = trace_metric_lineage(metric, build_graph(facts, metrics=[metric]), facts)
    assert result.completeness == "complete"
    assert result.compatibility.status == "undetermined"
    assert {r.code for r in result.compatibility.reasons} >= {
        "missing_company_id",
        "missing_reporting_scope",
        "source_reference_uncertain",
    }
    operand = result.operands[0]
    assert operand.usability.quality_context == facts[0].quality_context
    assert operand.observations[0].quality_context == facts[0].quality_context
    assert operand.usability.grounding_levels == ["page"]
    assert operand.usability.grounding_statuses == ["uncertain"]
    assert operand.usability.display_status == (
        "blocked" if decision in {"insufficient", "conflicted"} else "display_with_caveat"
    )
    assert result.tasks.calculation == "blocked"
    assert len(result.document_scoped_observations) == 2


def test_unrelated_graph_damage_does_not_block_selected_metric():
    metric, graph, facts = trace()
    other = metric.model_copy(update={"metric_id": "unrelated-invalid"})
    graph.nodes.extend(build_graph([], metrics=[other]).nodes)
    assert trace_metric_lineage(metric, graph, facts).completeness == "complete"


@pytest.mark.parametrize("missing", ["sources", "reference", "local_identity"])
def test_partial_unresolved_source_metadata(missing):
    definition, request, facts = inputs()
    if missing == "sources":
        facts[0].sources = []
    elif missing == "reference":
        facts[0].sources[0].reference = None
    else:
        facts[0].local_observation_id = None
    metric = build_metric(definition, request, facts)
    result = trace_metric_lineage(metric, build_graph(facts, metrics=[metric]), facts)
    assert result.completeness == "partial"
    assert result.operands[0].observations == [facts[0]]
    assert result.operands[0].anchors == []
    assert result.operands[0].unresolved
