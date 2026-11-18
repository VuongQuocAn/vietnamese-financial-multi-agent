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
        after=[],
    )
    wire = dict(
        goals=[dict(text="Doanh thu thuần năm 2030")],
        tasks=[dict(task, after=[2]), dict(task, role="invented"), task],
    )
    plan, errors = adapt_plan(wire)
    assert [t.task_id for t in plan.tasks] == ["T1", "T3"]
    assert [t.task_id for t in schedule_tasks(plan.tasks)[0]] == ["T3", "T1"]
    assert plan.blocked_tasks == {"T2": "task_schema_invalid"} and errors
    assert plan.requirements[0].requirement_id == "G1"
    cyclic = deepcopy(wire)
    cyclic["tasks"][2]["after"] = [0]
    assert set(adapt_plan(cyclic)[0].blocked_tasks) == {"T1", "T2", "T3"}
    unknown = deepcopy(wire)
    unknown["tasks"][0]["after"] = [42]
    parsed, _ = adapt_plan(unknown)
    assert [t.task_id for t in schedule_tasks(parsed.tasks)[0]] == ["T3"]
    assert not adapt_plan(dict(wire, goals=[dict(text="")]))[0].tasks
    assert not adapt_plan(dict(wire, tasks=wire["tasks"] * 3))[0].tasks
    missing, errors = adapt_plan(dict(wire, tasks=[]))
    assert not missing.tasks and errors == ["goal_owner_unresolved:G1"]
    context.mode = "gemini"
    valid = dict(wire, tasks=[task])
    seen = []
    parsed, metadata, errors = SupervisorLite(gateway_for(valid, seen)).plan(
        "Doanh thu thuần năm 2030?", context, sources
    )
    assert not errors and metadata.calls == 1 and parsed.tasks[0].task_id == "T1"
    prompt = json.loads(seen[0].messages[0].content)
    schema = prompt["output_schema"]
    assert set(schema["properties"]) == {"goals", "tasks"}
    assert set(schema["$defs"]["GoalProposal"]["properties"]) == {"text"}
    assert set(schema["$defs"]["TaskProposal"]["properties"]) == {
        "goal_indexes",
        "role",
        "objective",
        "after",
    }
    assert "inventory" not in prompt and schema["properties"]["tasks"]["minItems"] == 1


def test_dag_executes_just_in_time_and_keeps_independent_outputs():
    _, context, engine, _ = setup_engine()
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


def test_single_pipeline_requires_coordinator_and_rejects_legacy_switches(tmp_path):
    import pytest
    from pydantic import ValidationError

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
        question="Doanh thu TEST 2030?",
        company_id=context.company_id,
        document_id=context.document_id,
        snapshot_id=context.snapshot_id,
        allow_gateway=False,
        execution_mode="deterministic",
    )
    response = service.run(request)
    assert not response.trace.native_decisions and not response.used_verified_claim_ids
    assert response.trace.integration_context["requirements"][0]["kind"] == "unsupported"
    assert not response.trace.provider_calls
    for flag in ("integration_v2", "adaptive_coordinator", "m5_lite", "m6_lite", "m7_lite"):
        with pytest.raises(ValidationError):
            FinancialQARequest.model_validate(dict(question="x", **{flag: True}))


def test_specialist_can_request_a_calculator_metric_with_operand_provenance():
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import inventory

    catalog, context, engine, _ = setup_engine()
    context.mode = "gemini"
    sources = inventory(catalog, context)
    metric = next(handle for handle, source in sources.items() if source["kind"] == "metric")
    plan, errors = adapt_plan(
        dict(
            goals=[dict(text="Biên lợi nhuận gộp")],
            tasks=[
                dict(goal_indexes=[0], role="profitability", objective="Tra biên gộp", after=[])
            ],
        )
    )
    assert not errors
    engine.supervisor.plan.return_value = plan, engine.supervisor.plan.return_value[1], []
    engine.gateway = gateway_for(dict(retrieve=[dict(source=metric)]), [])
    with patch.object(
        engine,
        "_specialist",
        return_value=SpecialistResult(
            question="Tra biên gộp", role="profitability", upstream_status="completed"
        ),
    ):
        output = engine.run(question="Biên lợi nhuận gộp là bao nhiêu?", context=context)
    tools = output.supervisor_result.tool_trace
    calculation = next(t.response for t in tools if t.operation == "calculate_financial_metric")
    assert calculation.trace.operands
    assert any(t.operation == "get_evidence_sources" for t in tools)
    assert output.integration_context["task_results"]["T1"]["selected_observations"]


def test_mixed_request_runs_one_plan_and_releases_m6_claims_with_sources(tmp_path):
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

    from .test_json_source_readiness import catalog_fixture

    catalog = catalog_fixture(tmp_path / "sources")
    descriptor = catalog.descriptors[0]
    company = catalog.facts[0].company_id
    numbers = "Giá vốn hàng bán của TEST năm 2025 là bao nhiêu?"
    document = "Tài liệu ghi đơn vị tính nào?"
    calls = []

    def transport(request):
        prefix = request.request_id.rsplit("-", 1)[0]
        if prefix == "m5-coordinator-plan":
            payload = dict(
                goals=[dict(text=numbers), dict(text=document)],
                tasks=[
                    dict(
                        goal_indexes=[0],
                        role="cash_flow_and_earnings_quality",
                        objective=numbers,
                        after=[],
                    ),
                    dict(goal_indexes=[1], role="profitability", objective=document, after=[0]),
                ],
            )
        elif prefix == "m5-evidence-demand":
            prompt = json.loads(request.messages[0].content)
            if prompt["role"] == "cash_flow_and_earnings_quality":
                source = next(
                    key
                    for key, row in prompt["inventory"].items()
                    if row["item"] == "b02.cost_of_sales" and row["period"] == "2025"
                )
                payload = dict(retrieve=[dict(source=source)], use_graph=True)
            else:
                assert "T1" in prompt["dependency_results"]
                payload = dict(
                    document_search=dict(kind="exact_text", query="Đơn vị tính", goal_id="G2")
                )
        elif prefix == "m5-lite-cash_flow_and_earnings_quality":
            prompt = json.loads(request.messages[0].content)
            handle = prompt["numeric_choices"][0]["evidence_id"]
            payload = dict(claims=[handle], analyses=[], missing_information=[])
        elif prefix == "m6-document":
            row = json.loads(request.messages[1].content)
            payload = dict(
                verdicts=[
                    dict(
                        claim_id=row["claim"]["candidate_id"],
                        verdict="SUPPORTED",
                        reason="Exact source answers the goal",
                        supported_requirement_ids=[
                            g["requirement_id"] for g in row["local_requirements"]
                        ],
                        issues=[],
                    )
                ]
            )
        elif prefix == "m6-lite":
            payload = dict(
                verdicts=[
                    dict(
                        claim_id=r["claim_id"],
                        verdict="SUPPORTED",
                        reason="exact source",
                        supported_requirement_ids=[
                            g["requirement_id"] for g in r["local_requirements"]
                        ],
                        issues=[],
                    )
                    for r in json.loads(request.messages[1].content)
                ]
            )
        else:
            assert prefix == "m7-lite"
            rows = json.loads(request.messages[1].content)["verified_claims"]
            assert {r["kind"] for r in rows} == {"fact", "document"}
            payload = dict(
                segments=[dict(text=r["content"], claim_ids=[r["claim_id"]]) for r in rows], gaps=[]
            )
        return gateway_for(payload, calls).generate(request)

    service = FinancialQAPipeline(
        catalog=catalog,
        documents=[
            QADocument(
                document_id=descriptor.document_id,
                company_id=company,
                reporting_year=2025,
                company_aliases=["TEST"],
            )
        ],
        gateway=SharedLLMGateway({"gemini": transport}),
        repository=VerifiedClaimRepository(tmp_path / "ledger"),
    )
    from vietnamese_financial_multi_agent.api.conversations import ConversationService

    conversation = ConversationService(service)
    session = conversation.create()
    response = conversation.send(
        session.conversation_id,
        FinancialQARequest(
            question=numbers + " " + document,
            company_id=company,
            document_id=descriptor.document_id,
            snapshot_id=descriptor.snapshot_id,
            force_refresh=True,
        ),
    )
    response = response.response
    trace = response.trace
    assert sum(r.request_id.startswith("m5-coordinator-plan-") for r in calls) == 1
    assert {e["tool"] for e in trace.tool_calls} >= {
        "get_financial_fact",
        "search_document_evidence",
        "get_graph_context",
    }
    assert trace.integration_context["task_results"]["T2"]["input_results"][0]["task_id"] == "T1"
    assert sum(r.request_id.startswith("m5-evidence-demand-") for r in calls) == 2
    assert trace.native_decisions == {"ACCEPT": 2}
    assert len(response.used_verified_claim_ids) == 2 and response.citations
    assert trace.m7_lite["coverage"]["complete"]

    followup = conversation.send(
        session.conversation_id,
        FinancialQARequest(question="Repeat those findings.", force_refresh=True),
    )
    assert followup.original_question == followup.resolved_question == "Repeat those findings."
    assert followup.response.used_verified_claim_ids and followup.response.citations
    plans = [r for r in calls if r.request_id.startswith("m5-coordinator-plan-")]
    history = json.loads(plans[-1].messages[0].content)["conversation_context"]
    assert history[0]["question"] == numbers + " " + document
    assert history[0]["verified_claim_ids"] == response.used_verified_claim_ids

    import pytest
    from vietnamese_financial_multi_agent.verification.document_verification import (
        DocumentVerificationHistory,
    )
    from vietnamese_financial_multi_agent.verification.ledger import (
        LedgerAdmissionError,
        build_verified_claim,
    )

    document_entry = next(
        e
        for e in service.repository.list_all()
        if isinstance(e.history, DocumentVerificationHistory)
    )
    tampered = document_entry.history.model_copy(deep=True)
    tampered.goal_context["question"] = "Changed request"
    with pytest.raises(LedgerAdmissionError, match="document_goal_proof_invalid"):
        build_verified_claim(tampered)
