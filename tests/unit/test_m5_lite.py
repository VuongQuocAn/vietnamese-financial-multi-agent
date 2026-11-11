"""Small offline controls; real BBS evaluation is the opt-in script."""

from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
    LiteTask,
    SupervisorLite,
    fallback_plan,
    inventory,
)
from vietnamese_financial_multi_agent.agents.orchestrator import FinancialMultiAgentOrchestrator
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input

from .test_financial_qa import gateway_for
from .test_m4_execution import fixture


def inputs():
    catalog = SnapshotCatalog(**fixture())
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2030",
        mode="deterministic",
    )
    return catalog, context


@pytest.mark.parametrize(
    "formula,question,role",
    [
        ("gross_margin", "Doanh thu thuần và biên lợi nhuận gộp năm 2030?", "profitability"),
        (
            "debt_to_assets",
            "Tổng tài sản và tỷ lệ nợ phải trả trên tổng tài sản năm 2030?",
            "liquidity_and_leverage",
        ),
    ],
)
def test_single_plan_tools_and_native_adapter_keep_candidates_unverified(formula, question, role):
    catalog = SnapshotCatalog(**fixture(formula))
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2030",
        mode="deterministic",
    )
    result = FinancialLiteOrchestrator(catalog).run(question=question, context=context)
    assert result.status == "completed", result.model_dump()
    assert result.routing_decision.selected_roles == [role]
    assert len(result.specialist_executions) == 1
    assert len([t for t in result.trace if t.stage == "planning"]) == 1
    assert {t.operation for t in result.supervisor_result.tool_trace} >= {
        "get_financial_fact",
        "calculate_financial_metric",
        "get_evidence_sources",
    }
    batch = to_verification_input(result)
    assert len(batch.claims) == len(result.candidates) >= 2
    assert not batch.issues, batch.issues
    assert all(c.status == "candidate" and not c.financial_fact_verified for c in batch.claims)
    assert any(c.calculation for c in batch.claims)
    assert all(c.fact_references and c.citations for c in batch.claims)


def test_multiple_dispatch_isolates_failure_and_bad_sources_without_replan():
    catalog, context = inputs()
    sources = inventory(catalog, context)
    selected = fallback_plan("Doanh thu thuần năm 2030", sources).tasks[0]
    supervisor = Mock()
    supervisor.plan.return_value = (
        LitePlan(
            tasks=[
                selected,
                LiteTask(specialist="liquidity_and_leverage", objective="Tổng tài sản"),
                LiteTask(specialist="profitability", objective="missing", sources=["invented"]),
            ]
        ),
        PlannerLLMMetadata(),
        [],
    )
    engine = FinancialLiteOrchestrator(catalog, supervisor=supervisor)
    original = engine._specialist

    def specialist(task, *args):
        if task.specialist == "liquidity_and_leverage":
            raise RuntimeError("test failure")
        return original(task, *args)

    engine._specialist = specialist
    result = engine.run(question="Doanh thu thuần năm 2030", context=context)
    assert result.status == "partial" and result.candidates
    assert len(result.specialist_executions) == 3
    assert len(result.errors) == 1
    assert supervisor.plan.call_count == 1
    assert result.candidates[0].fact_references
    assert "unknown_or_foreign_source:invented" in result.missing_evidence
    assert not to_verification_input(result).issues


def test_supervisor_json_fallback_payload_and_legacy_flag():
    catalog, context = inputs()
    seen = []
    supervisor = SupervisorLite(gateway_for({"invalid": True}, seen))
    context.mode = "gemini"
    plan, metadata, gaps = supervisor.plan(
        "Doanh thu thuần năm 2030", context, inventory(catalog, context)
    )
    assert plan.tasks[0].specialist == "profitability"
    assert metadata.calls == len(seen) == 1
    assert gaps == ["supervisor_invalid_json_fallback"]
    assert len(seen[0].messages[0].content) < 8000
    # A real provider JSON shorthand remains a candidate, with backend numbers.
    numeric_gateway = gateway_for({"claims": ["E001", "invented"], "missing_information": []}, [])
    result = FinancialLiteOrchestrator(catalog, numeric_gateway, supervisor=SupervisorLite()).run(
        question="Doanh thu thuần năm 2030", context=context
    )
    assert result.status == "partial" and len(result.candidates) == 1
    assert result.candidates[0].kind == "fact"
    assert result.candidates[0].fact_references and not to_verification_input(result).issues
    service = FinancialQAPipeline(catalog=catalog, documents=[], repository=Mock())
    assert isinstance(
        service._m5(FinancialQARequest(question="x")), FinancialMultiAgentOrchestrator
    )
    assert isinstance(
        service._m5(FinancialQARequest(question="x", m5_lite=True, m7_lite=True)),
        FinancialLiteOrchestrator,
    )
