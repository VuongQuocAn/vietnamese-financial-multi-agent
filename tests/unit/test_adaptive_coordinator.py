"""Targeted engineering controls; real Qwen evidence is recorded separately."""

import json
from copy import deepcopy
from unittest.mock import patch

from vietnamese_financial_multi_agent.agents.coordinator_plan import adapt_plan, schedule_tasks
from vietnamese_financial_multi_agent.agents.lite_orchestrator import LiteTask, SupervisorLite
from vietnamese_financial_multi_agent.agents.specialist_common import SpecialistResult
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

from .test_financial_qa import gateway_for
from .test_v2_integration import setup_engine


def test_small_plan_keeps_original_indexes_and_independent_tasks():
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import inventory

    catalog, context, _, _ = setup_engine()
    sources = inventory(catalog, context)
    task = dict(
        goal_indexes=[0],
        role="profitability",
        objective="Tra doanh thu",
        input_handles=[next(iter(sources))],
        after=[],
    )
    wire = dict(
        goals=[dict(text="Doanh thu thuần năm 2030", mode="value")],
        tasks=[dict(task, after=[2]), dict(task, role="invented"), task],
    )
    plan, errors = adapt_plan(wire, sources)
    assert [t.task_id for t in plan.tasks] == ["T1", "T3"]
    assert [t.task_id for t in schedule_tasks(plan.tasks)[0]] == ["T3", "T1"]
    assert plan.blocked_tasks == {"T2": "task_schema_invalid"} and errors
    assert plan.requirements[0].requirement_id == "G1"
    cyclic = deepcopy(wire)
    cyclic["tasks"][2]["after"] = [0]
    assert set(adapt_plan(cyclic, sources)[0].blocked_tasks) == {"T1", "T2", "T3"}
    unknown = deepcopy(wire)
    unknown["tasks"][0]["after"] = [42]
    parsed, _ = adapt_plan(unknown, sources)
    assert [t.task_id for t in schedule_tasks(parsed.tasks)[0]] == ["T3"]
    assert not adapt_plan(dict(wire, goals=[dict(text="x", mode="invented")]), sources)[0].tasks
    assert not adapt_plan(dict(wire, tasks=wire["tasks"] * 3), sources)[0].tasks
    context.mode = "gemini"
    valid = dict(wire, tasks=[task])
    seen = []
    parsed, metadata, errors = SupervisorLite(
        gateway_for(valid, seen), integration_v2=True, adaptive_coordinator=True
    ).plan("Doanh thu thuần năm 2030?", context, sources)
    assert not errors and metadata.calls == 1 and parsed.tasks[0].task_id == "T1"
    prompt = json.loads(seen[0].messages[0].content)
    assert set(prompt["schema"]) == {"goals", "tasks", "bounds"}
    assert "requirement_id" not in prompt["schema"]["goals"]["properties"]


def test_dag_executes_just_in_time_and_keeps_independent_outputs():
    _, context, engine, _ = setup_engine()
    engine.adaptive_coordinator = True
    plan = engine.supervisor.plan.return_value[0]
    first, second = plan.tasks
    first.depends_on = [second.task_id]
    plan.tasks.extend(
        [
            LiteTask(
                task_id="T3", specialist=first.specialist, objective="fail", requirement_ids=["R1"]
            ),
            LiteTask(
                task_id="T4",
                specialist=first.specialist,
                objective="blocked",
                requirement_ids=["R1"],
                depends_on=["T3"],
            ),
            LiteTask(
                task_id="T5", specialist=first.specialist, objective="empty", requirement_ids=["R1"]
            ),
            LiteTask(
                task_id="T6",
                specialist=first.specialist,
                objective="blocked",
                requirement_ids=["R1"],
                depends_on=["T5"],
            ),
        ]
    )
    original, called = engine._specialist, []

    def analyze(task, upstream, *args):
        called.append(task.task_id)
        if task.task_id == "T3":
            raise RuntimeError("independent failure")
        if task.task_id == "T5":
            return SpecialistResult(question="empty", upstream_status="partial", status="partial")
        if task.task_id == second.task_id:
            assert len(upstream.evidence_bundle.facts) == 1  # No future retrieval.
        else:
            assert len(upstream.evidence_bundle.facts) == 2
            assert engine.workspace.task_results[second.task_id]["candidate_ids"]
        return original(task, upstream, *args)

    engine._specialist = analyze
    output = engine.run(question="Tra doanh thu và lợi nhuận 2030", context=context)
    assert called == ["T2", "T1", "T3", "T5"]
    assert output.candidates
    workspace = output.integration_context
    assert workspace["tasks"]["T3"]["status"] == "failed"
    assert workspace["tasks"]["T4"]["status"] == workspace["tasks"]["T6"]["status"] == "blocked"
    dependency = workspace["task_results"]["T1"]["input_results"][0]
    assert dependency["handle"] == "result:T2:v1" and dependency["digest"]
    assert workspace["task_results"]["T2"]["evidence"][0]["reference"]


def test_pipeline_flag_keeps_existing_m6_m7_and_opt_out(tmp_path):
    catalog, context, _, _ = setup_engine()
    service = FinancialQAPipeline(
        catalog=catalog,
        documents=[
            QADocument(
                document_id=context.document_id,
                company_id=context.company_id,
                reporting_year=2030,
                company_aliases=["TEST"],
            )
        ],
        repository=VerifiedClaimRepository(tmp_path),
    )
    request = FinancialQARequest(
        question="Doanh thu thuần TEST năm 2030 là bao nhiêu?",
        company_id=context.company_id,
        document_id=context.document_id,
        snapshot_id=context.snapshot_id,
        integration_v2=True,
        adaptive_coordinator=True,
        execution_mode="deterministic",
        allow_gateway=False,
        force_refresh=True,
    )
    response = service.run(request)
    assert response.used_verified_claim_ids and response.citations, response.trace.errors
    assert response.trace.integration_context["task_results"]
    assert response.trace.m6_lite and response.trace.m7_lite
    with patch(
        "vietnamese_financial_multi_agent.agents.lite_orchestrator.FinancialLiteOrchestrator",
        wraps=__import__(
            "vietnamese_financial_multi_agent.agents.lite_orchestrator",
            fromlist=["FinancialLiteOrchestrator"],
        ).FinancialLiteOrchestrator,
    ) as factory:
        service._m5(
            request.model_copy(update={"adaptive_coordinator": False, "m5_lite": True}),
            catalog=catalog,
        )
        assert factory.call_args.kwargs["adaptive_coordinator"] is False
