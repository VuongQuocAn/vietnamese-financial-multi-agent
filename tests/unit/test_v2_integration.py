"""Minimal offline integration controls; synthetic fixtures are not financial evaluation."""

import json
from unittest.mock import Mock, patch

from vietnamese_financial_multi_agent.agents.integration_workspace import IntegrationRequirement
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
    LiteTask,
    SupervisorLite,
    integration_plan,
    inventory,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import JSONOutput, parse_json_output
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification.ledger import validate_entry
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_qa import gateway_for
from .test_m4_execution import fixture
from .test_m6_lite import semantic_gateway
from .test_multihop_reasoning import reasoning_case


def setup_engine():
    data = fixture()
    catalog = SnapshotCatalog(**data)
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2030",
        mode="deterministic",
    )
    sources = inventory(catalog, context)
    requirements = [
        IntegrationRequirement(
            requirement_id=f"R{i}",
            text=s["label"],
            kind="fact",
            target_id=s["item"],
            period=s["period"],
        )
        for i, s in enumerate((s for s in sources.values() if s["kind"] == "fact"), 1)
    ]
    tasks = [
        LiteTask(
            task_id=f"T{i}",
            specialist=role,
            objective=req.text,
            requirement_ids=[req.requirement_id],
            sources=[handle],
        )
        for i, (req, handle, role) in enumerate(
            zip(
                requirements,
                [h for h, s in sources.items() if s["kind"] == "fact"],
                ["profitability", "liquidity_and_leverage"],
                strict=True,
            ),
            1,
        )
    ]
    supervisor = Mock()
    supervisor.plan.return_value = (
        LitePlan(tasks=tasks, requirements=requirements),
        PlannerLLMMetadata(),
        [],
    )
    return (
        catalog,
        context,
        FinancialLiteOrchestrator(catalog, supervisor=supervisor, integration_v2=True),
        requirements,
    )


def test_plan_retains_valid_requirements_and_tasks_with_explicit_failure():
    _, _, engine, _ = setup_engine()
    plan = engine.supervisor.plan.return_value[0]
    wire = plan.model_dump(mode="json")
    wire["use_graph"] = False  # Saved C01 transport shape: unrelated root field.
    wire["tasks"].append({"specialist": "invented"})
    parsed, errors = integration_plan(wire)
    assert len(parsed.tasks) == 2 and parsed.requirements == plan.requirements
    assert errors == ["supervisor_invalid_task:T3", "requirement_plan_incomplete"]
    fenced = '```json\n{"tasks": []}\n```'
    assert parse_json_output(fenced, allow_markdown_fence=True).payload == {"tasks": []}
    parsed_output = parse_json_output(fenced, allow_markdown_fence=True)
    assert JSONOutput.model_validate_json(parsed_output.model_dump_json()) == parsed_output
    assert parse_json_output(fenced).validation_status == "invalid_json"
    assert parse_json_output(fenced + " trailing", allow_markdown_fence=True).payload is None
    catalog, context, _, _ = setup_engine()
    context.mode = "gemini"
    seen = []
    supervisor = SupervisorLite(
        gateway_for(plan.model_dump(mode="json"), seen), integration_v2=True
    )
    decoded, _, errors = supervisor.plan("TEST 2030", context, inventory(catalog, context))
    assert not errors and decoded.requirements == plan.requirements
    prompt = json.loads(seen[0].messages[0].content)
    assert "{requirements:[...],tasks:[...]}" in prompt["instruction"]
    assert "Không DAG, approval, coverage" not in prompt["instruction"]
    service = FinancialQAPipeline(catalog=SnapshotCatalog([]), documents=[], repository=Mock())
    with patch("vietnamese_financial_multi_agent.api.fusion_pipeline.run_fusion") as fusion:
        service.run(
            FinancialQARequest(
                question="Lợi nhuận sau thuế TEST năm 2030 và chính sách chi phí đi vay trong thuyết minh?",
                integration_v2=True,
                execution_mode="deterministic",
                allow_gateway=False,
            )
        )
        assert fusion.call_count == 1
        assert fusion.call_args.args[1].m7_lite  # Presentation flag cannot bypass mixed routing.
        fusion.reset_mock()
        service.run(
            FinancialQARequest(
                question="Lợi nhuận sau thuế TEST năm 2030 và chính sách chi phí đi vay trong thuyết minh?",
                integration_v2=True,
                integration_lane="financial",
                execution_mode="deterministic",
                allow_gateway=False,
            )
        )
        assert not fusion.called  # A bound lane is never decomposed recursively.


def test_shared_evidence_ids_and_task_outputs_survive_sibling_failure():
    _, context, engine, _ = setup_engine()
    plan = engine.supervisor.plan.return_value[0]
    plan.tasks.append(
        LiteTask(
            task_id="T3",
            specialist="cash_flow_and_earnings_quality",
            objective="fail",
            requirement_ids=["R1"],
        )
    )
    plan.tasks.append(
        LiteTask(
            task_id="T4",
            specialist="profitability",
            objective="combine",
            requirement_ids=["R1", "R2"],
            depends_on=["T1", "T2"],
        )
    )
    original = engine._specialist
    seen = {}

    def analyze(task, upstream, *args):
        if task.task_id == "T3":
            raise RuntimeError("isolated failure")
        assert len(upstream.evidence_bundle.facts) == 2
        if task.task_id == "T4":
            assert engine.workspace.tasks["T1"]["candidate_statements"]
            assert engine.workspace.tasks["T2"]["candidate_statements"]
        result = original(task, upstream, *args)
        seen[task.task_id] = {
            e.reference.model_dump_json(): e.evidence_id for e in result.supporting_evidence
        }
        return result

    engine._specialist = analyze
    output = engine.run(question="Doanh thu thuần và lợi nhuận gộp năm 2030", context=context)
    assert output.status == "partial" and len(output.errors) == 1
    assert seen["T1"] == seen["T2"] == seen["T4"]
    assert output.integration_context["tasks"]["T3"]["status"] == "technical_error"
    assert all(e.assigned_requirement_ids for e in output.specialist_executions)
    assert all(c.origins and c.citations for c in output.candidates)


def test_pipeline_preserves_requirements_through_native_m6_ledger_and_m7(tmp_path):
    catalog, context, engine, requirements = setup_engine()
    repository = VerifiedClaimRepository(tmp_path)
    document = QADocument(
        document_id=context.document_id,
        company_id=context.company_id,
        company_aliases=["TEST"],
        reporting_year=2030,
    )
    service = FinancialQAPipeline(
        catalog=catalog, documents=[document], repository=repository, orchestrator=engine
    )
    response = service.run(
        FinancialQARequest(
            question="Doanh thu thuần và lợi nhuận gộp TEST năm 2030?",
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            integration_v2=True,
            execution_mode="deterministic",
            allow_gateway=False,
        )
    )
    assert response.status == "completed_with_caveats", response.model_dump()
    coverage = response.trace.m7_lite["coverage"]
    assert coverage["complete"]
    assert {r["requirement_id"] for r in coverage["requirements"]} == {
        r.requirement_id for r in requirements
    }
    assert set(response.used_verified_claim_ids) == {
        key for r in coverage["requirements"] for key in r["verified_claim_ids"]
    }
    for entry in VerifiedClaimRepository(tmp_path).list_all():
        validate_entry(entry)
        assert entry.identity.policy_version == "verification_lite_v2"
    # M6 assesses the local proposition, and independently confirms relevance;
    # assignment alone cannot mark every requirement covered.
    data, batch = reasoning_case()
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.content = "Các số liệu đã chọn cho phép đối chiếu hai chỉ tiêu trong cùng kỳ."
    gateway = semantic_gateway()
    original = gateway.generate.side_effect

    def assess(request):
        rows = json.loads(request.messages[-1].content)
        assert all("question" not in row and row["local_requirements"] for row in rows)
        response = original(request)
        body = response.output.payload
        body["verdicts"][0]["supported_requirement_ids"] = ["R1"]
        return response.model_copy(update={"output": parse_json_output(json.dumps(body))})

    gateway.generate.side_effect = assess
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway, integration_v2=True)
    histories = runtime.verify(
        batch,
        integration_context=dict(
            candidate_requirements={claim.candidate_id: ["R1", "R2"]},
            requirements=[
                dict(requirement_id="R1", text="Đối chiếu"),
                dict(requirement_id="R2", text="Kết luận khác"),
            ],
        ),
    )
    assert histories[0].outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {claim.candidate_id: ["R1"]}
    engine.supervisor.plan.return_value = (
        LitePlan(),
        PlannerLLMMetadata(),
        ["supervisor_invalid_task:T1"],
    )
    service.repository = VerifiedClaimRepository(tmp_path / "invalid-plan")
    failed = service.run(
        FinancialQARequest(
            question="Doanh thu thuần TEST năm 2030?",
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            integration_v2=True,
            execution_mode="deterministic",
            allow_gateway=False,
        )
    )
    assert failed.status == "internal_error" and not failed.used_verified_claim_ids
    assert failed.trace.integration_context["technical_errors"]
