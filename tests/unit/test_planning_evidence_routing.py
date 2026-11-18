"""Bounded planning/routing controls; no Gold or live network."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.coordinator_plan import adapt_plan
from vietnamese_financial_multi_agent.agents.evidence_coordination import (
    observation,
    parse_retrieval_batches,
    resolve_demand_batches,
)
from vietnamese_financial_multi_agent.agents.integration_workspace import IntegrationWorkspace
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    SupervisorLite,
    inventory,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)

from .test_financial_qa import gateway_for
from .test_json_source_readiness import catalog_fixture
from .test_v2_integration import setup_engine


def test_partial_plan_preserves_goals_and_sources_without_semantic_fallback():
    catalog, context, _, _ = setup_engine()
    context.mode = "gemini"
    sources = inventory(catalog, context)
    known = next(iter(sources))
    question = "Đối chiếu hai chỉ tiêu rồi giải thích kết quả"
    base = dict(role="profitability", objective="Tra số liệu", after=[])
    payload = dict(
        goals=[
            dict(text="Tra chỉ tiêu đã chọn", mode="value", source=known),
            dict(text="Yêu cầu sai schema", mode="unknown"),
            dict(text="Nhận xét quan hệ giữa hai chỉ tiêu", mode="analysis"),
        ],
        tasks=[
            dict(base, goal_indexes=[0, 1], input_handles=[known, "S999"]),
            dict(base, goal_indexes=[1], input_handles=[]),
            dict(base, goal_indexes=[2], input_handles=[], after=[0]),
        ],
    )
    seen = []
    supervisor = SupervisorLite(
        gateway_for(payload, seen), integration_v2=True, adaptive_coordinator=True
    )
    plan, metadata, errors = supervisor.plan(question, context, sources)
    assert metadata.calls == len(seen) == 1
    assert [r.requirement_id for r in plan.requirements] == ["G1", "G3"]
    assert [t.task_id for t in plan.tasks] == ["T1", "T3"]
    assert plan.tasks[0].sources == [known]
    assert plan.tasks[1].depends_on == ["T1"]
    assert plan.blocked_tasks == {"T2": "goal_reference_unknown"}
    assert "supervisor_invalid_goal:G2:goal_schema_invalid" in errors
    assert "supervisor_unknown_source_handle:T1" in errors
    assert (
        json.loads(seen[0].messages[0].content)["output_schema"]["properties"]["tasks"]["maxItems"]
        == 6
    )


def test_twelve_demands_preserve_all_sources_in_batches_and_reuse_exact_parent():
    catalog, context, _, _ = setup_engine()
    fact = catalog.facts[0]
    match = (
        FinancialRetrievalTools(catalog)
        .get_financial_fact(
            GetFinancialFactRequest(
                document_id=fact.document_id,
                snapshot_id=fact.snapshot_id,
                local_observation_id=fact.local_observation_id,
            )
        )
        .matches[0]
    )
    row = observation(match)
    sources = {
        f"S{i}": dict(
            kind="fact", item=fact.canonical_item_id, period=fact.context.period, records=[fact]
        )
        for i in range(1, 13)
    }
    wire = dict(retrieve=[dict(source=s) for s in sources], selection=None, add_tasks=[])
    batches = parse_retrieval_batches(wire)
    assert [len(b.retrieve) for b in batches] == [6, 6]
    workspace = IntegrationWorkspace([])
    workspace.task_results["T1"] = dict(
        handle="result:T1:v1",
        revision=1,
        digest="source-pin",
        input_results=[],
        selected_observations=[row],
        source_context=[],
    )
    task = SimpleNamespace(depends_on=["T1"])
    handles, _ = resolve_demand_batches(
        batches[0],
        [[d.model_dump() for d in b.retrieve] for b in batches],
        task,
        workspace,
        sources,
    )
    assert handles == list(sources)
    reuse = parse_retrieval_batches(
        dict(
            retrieve=[
                dict(source="T1"),
                dict(source="result:T1:v1"),
                dict(source=row["evidence_id"]),
            ]
        )
    )
    handles, lineage = resolve_demand_batches(reuse[0], [], task, workspace, sources)
    assert handles == list(sources) and len(lineage) == 3
    assert all(r["from_result"]["digest"] == "source-pin" for r in lineage)
    with pytest.raises(ValueError, match="unknown_or_not_fact"):
        bad = parse_retrieval_batches(dict(retrieve=[dict(source="T999")]))
        resolve_demand_batches(bad[0], [], task, workspace, sources)
    with pytest.raises(ValueError, match="total_input_limit"):
        parse_retrieval_batches(dict(retrieve=wire["retrieve"] * 2))


def test_source_only_dependency_retains_exact_context_digest_and_reaches_consumer(tmp_path):
    catalog = catalog_fixture(tmp_path)
    d = catalog.descriptors[0]
    context = PlannerContext(
        company_id=catalog.facts[0].company_id,
        document_id=d.document_id,
        snapshot_id=d.snapshot_id,
        model=ModelIdentity(provider="gemini", model="test"),
        mode="gemini",
    )
    sources = inventory(catalog, context)
    from vietnamese_financial_multi_agent.evidence.json_catalog import json_document_composition

    base = dict(role="profitability", objective="Đơn vị tính", input_handles=[])
    search = dict(target="đơn vị tính", label="Đơn vị tính", kind="exact_text", query="đơn vị tính")
    plan, errors = adapt_plan(
        dict(
            goals=[dict(text="Tra nội dung được công bố", mode="analysis")],
            tasks=[
                dict(base, goal_indexes=[0], after=[], document_search=search),
                dict(base, goal_indexes=[0], after=[0]),
            ],
        ),
        sources,
    )
    assert not errors
    captured = []

    def generate(request):
        captured.append(request)
        payload = (
            dict(retrieve=[dict(source="T1")], selection=None, add_tasks=[])
            if request.request_id.startswith("m5-evidence-demand")
            else dict(claims=[], analyses=[], missing_information=["no canonical target"])
        )
        return gateway_for(payload, []).generate(request)

    engine = FinancialLiteOrchestrator(
        catalog,
        Mock(generate=generate),
        supervisor=Mock(plan=Mock(return_value=(plan, PlannerLLMMetadata(), []))),
        integration_v2=True,
        adaptive_coordinator=True,
        graph_enabled=False,
        composition=json_document_composition(catalog),
        document_repository=catalog,
    )
    result = engine.run(question="Đơn vị tính trong tài liệu là gì?", context=context)
    assert not result.errors, result.model_dump_json()[-3000:]
    w = result.integration_context
    assert w["tasks"]["T1"]["status"] == "source_only" and w["task_results"]["T1"]["source_context"]
    prompts = [
        json.loads(r.messages[0].content) for r in captured if r.request_id.startswith("m5-lite-")
    ]
    assert len(prompts) == 2
    parent = prompts[1]["dependency_sources"]["T1"]
    assert parent["digest"] == w["task_results"]["T1"]["digest"]
    assert parent["source_context"] == w["task_results"]["T1"]["source_context"]
    assert not w["task_results"]["T1"]["candidate_ids"]
    assert all(c["reference"]["evidence"] and c["citations"] for c in parent["source_context"])
