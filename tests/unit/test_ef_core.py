"""EF-CORE integration controls; synthetic fixtures do not prove PDF accuracy."""

from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
    LiteTask,
    compact_graph_context,
    inventory,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerLLMMetadata
from vietnamese_financial_multi_agent.evidence.graph import build_graph
from vietnamese_financial_multi_agent.tools.graph_retrieval import (
    GetGraphContextRequest,
    GetSnapshotGraphContextRequest,
    GraphRetrievalTools,
)
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input

from .test_composition_graph import inputs as composition_inputs
from .test_composition_graph import project
from .test_m5_lite import inputs


def test_catalog_graph_lineage_citations_and_wrong_snapshot(tmp_path):
    catalog, context = inputs()
    tools = GraphRetrievalTools.from_catalog(
        catalog, document_id=context.document_id, snapshot_id=context.snapshot_id
    )
    request = GetSnapshotGraphContextRequest(
        document_id=context.document_id,
        snapshot_id=context.snapshot_id,
        node_id=catalog.metrics[0].metric_id,
        depth=2,
        limit=50,
    )
    response = tools.get_graph_context(request)
    assert response.status == "found"
    assert {e.edge.relation for e in response.edges} >= {"used_in", "from_source"}
    assert all(e.verification == "structural_only" for e in response.edges)
    assert all(n.original_citations for n in response.matches)
    assert not response.financial_fact_verified
    # Repeated full source payloads must not crowd metric operand relations out
    # of the bounded Specialist projection (observed on real BBS citations).
    for node in [response.start, *response.matches]:
        node.original_citations *= 40
    projected = compact_graph_context([response], [])
    assert {r["operand_role"] for r in projected if r["relation"] == "used_in"}
    assert len(str(projected)) < 14000
    assert (
        tools.get_graph_context(request.model_copy(update={"snapshot_id": "foreign"})).status
        == "unavailable"
    )
    assert (
        tools.get_graph_context(request.model_copy(update={"node_id": "invented"})).status
        == "not_found"
    )
    assert not tools.get_graph_context(
        request.model_copy(update={"relations": ["same_extraction_context"]})
    ).edges
    with pytest.raises(ValueError, match="snapshot_missing"):
        GraphRetrievalTools.from_catalog(
            catalog, document_id=context.document_id, snapshot_id="foreign"
        )
    manifest, repo, _, fact, composition_catalog = composition_inputs(tmp_path)
    for i in range(12):
        anchor = fact.sources[0].model_copy(deep=True)
        anchor.reference.source_pointer += f"/synthetic-{i}"
        fact.sources.append(anchor)
    composition_catalog.facts = [fact]
    composition_catalog.graph = build_graph([fact])
    projection = project(manifest, repo, composition_catalog)
    tools = GraphRetrievalTools(projection)
    response = tools.get_graph_context(
        GetGraphContextRequest(
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
            node_id=projection.view.contextual_relations[0].source,
            limit=2,
        )
    )
    assert {e.edge.relation for e in response.edges} == {"from_source", "same_extraction_context"}
    assert response.truncated


def test_lite_graph_bundle_and_off_control_keep_m6_boundary():
    catalog, context = inputs()
    supervisor = Mock()
    supervisor.plan.return_value = (
        LitePlan(
            tasks=[
                LiteTask(
                    specialist="profitability",
                    objective="Truy vết nguồn và thành phần biên lợi nhuận gộp",
                    use_graph=True,
                    sources=list(inventory(catalog, context)),
                )
            ]
        ),
        PlannerLLMMetadata(),
        [],
    )
    for enabled in (True, False):
        result = FinancialLiteOrchestrator(
            catalog, supervisor=supervisor, graph_enabled=enabled
        ).run(question="Truy vết", context=context)
        assert result.candidates, result.errors
        assert not to_verification_input(result).issues
        bundle = result.supervisor_result.evidence_bundle
        assert bool(bundle.graph_contexts) == enabled
        supplied = [
            t
            for t in result.specialist_executions[0].result.trace
            if t.outcome == "graph_context_supplied"
        ]
        assert bool(supplied) == enabled
        assert all(not c.financial_fact_verified for c in result.candidates)


def test_missing_graph_preserves_financial_fallback():
    catalog, context = inputs()
    catalog.graph = None
    supervisor = Mock()
    supervisor.plan.return_value = (
        LitePlan(
            tasks=[
                LiteTask(
                    specialist="profitability",
                    objective="nguồn doanh thu",
                    use_graph=True,
                    sources=list(inventory(catalog, context)),
                )
            ]
        ),
        PlannerLLMMetadata(),
        [],
    )
    result = FinancialLiteOrchestrator(catalog, supervisor=supervisor).run(
        question="nguồn", context=context
    )
    assert result.candidates and not result.errors
    assert "pinned_graph_missing" in result.missing_evidence
    assert all(
        g.status == "unavailable" for g in result.supervisor_result.evidence_bundle.graph_contexts
    )
