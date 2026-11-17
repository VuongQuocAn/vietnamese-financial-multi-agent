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


def test_invalid_or_drifting_plan_keeps_original_owned_question_and_exact_item():
    catalog, context, _, _ = setup_engine()
    context.mode = "gemini"
    sources = inventory(catalog, context)
    base = dict(
        goal_indexes=[0], role="profitability", objective="Tra số liệu", input_handles=[], after=[]
    )
    question = "Thời hạn sử dụng thiết bị được công bố năm 2030 là bao lâu?"
    for raw in (
        dict(goals=[dict(text=question, mode="value")], tasks=[base] * 7),
        dict(goals=[dict(text="Tính trung bình năm 2029", mode="value")], tasks=[base]),
        dict(goals=[dict(text=question, mode="value")], tasks=[]),
    ):
        seen = []
        supervisor = SupervisorLite(
            gateway_for(raw, seen), integration_v2=True, adaptive_coordinator=True
        )
        plan, metadata, errors = supervisor.plan(question, context, sources)
        assert not errors and metadata.calls == 1 and len(seen) == 1
        assert len(plan.requirements) == 1 and plan.requirements[0].text == question
        assert plan.tasks[0].objective == question and plan.tasks[0].requirement_ids == ["G1"]
        assert supervisor.adaptation_events[0]["raw_plan"] == raw
        schema = json.loads(seen[0].messages[0].content)["output_schema"]
        assert schema["properties"]["tasks"]["maxItems"] == 6
    correct = next(h for h, s in sources.items() if s["item"] == "b02.net_revenue")
    wrong = next(h for h, s in sources.items() if s["item"] != "b02.net_revenue")
    plan, errors = adapt_plan(
        dict(
            goals=[dict(text="Doanh thu thuần năm 2030", mode="value")],
            tasks=[dict(base, input_handles=[wrong])],
        ),
        sources,
    )
    assert not errors and plan.tasks[0].sources == [correct]


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
    base = dict(role="profitability", objective="Đơn vị tính", input_handles=[])
    plan, errors = adapt_plan(
        dict(
            goals=[dict(text="Tra nội dung được công bố", mode="analysis")],
            tasks=[dict(base, goal_indexes=[0], after=[]), dict(base, goal_indexes=[0], after=[0])],
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
    )
    result = engine.run(question="Đơn vị tính trong tài liệu là gì?", context=context)
    assert not result.errors, result.model_dump_json()[-3000:]
    w = result.integration_context
    assert w["tasks"]["T1"]["status"] == "source_only" and w["task_results"]["T1"]["source_context"]
    prompts = [
        json.loads(r.messages[0].content) for r in captured if r.request_id.startswith("m5-lite-")
    ]
    assert len(prompts) == 2
    parent = prompts[1]["dependency_results"]["T1"]
    assert parent["digest"] == w["task_results"]["T1"]["digest"]
    assert parent["source_context"] == w["task_results"]["T1"]["source_context"]
    assert not w["task_results"]["T1"]["candidate_ids"]
    assert all(not c["financial_fact_verified"] for c in parent["source_context"])
