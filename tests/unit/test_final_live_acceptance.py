"""Targeted engineering controls for live-discovered integration failures."""

import json
from types import SimpleNamespace as NS

import pytest
from vietnamese_financial_multi_agent.agents.fusion_contracts import decompose, is_mixed
from vietnamese_financial_multi_agent.agents.orchestrator import _check_assignment
from vietnamese_financial_multi_agent.agents.query_planner import (
    _complete_proposal_fields,
    _explicit_constraints,
)
from vietnamese_financial_multi_agent.api.qa_gateway import QAGeminiAdapter
from vietnamese_financial_multi_agent.core.llm_contracts import (
    GenerationParameters,
    LLMRequest,
    Message,
    ModelIdentity,
    OutputSpec,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import _reasoning_matches
from vietnamese_financial_multi_agent.outputs.qa_contracts import QARequirement


def test_financial_citations_keep_one_lane_without_losing_document_or_causal_requests():
    assert not is_mixed("Tính chênh lệch doanh thu và lợi nhuận TEST 2030; dẫn nguồn hai số liệu.")
    assert not is_mixed("Cho biết doanh thu và lợi nhuận TEST 2030; dẫn nguồn từng chỉ tiêu.")
    assert is_mixed("Doanh thu TEST 2030 và thuyết minh nói gì về hàng tồn kho?")
    causal = decompose("Doanh thu TEST 2030 tăng là do chính sách kế toán?")
    assert any(r.kind == "causal_explanation" for r in causal.requirements)


def test_malformed_tail_recovers_complete_plan_fields_only_and_rejects_incomplete_dag():
    core = dict(
        intent="multi_step_analysis",
        company_alias="TEST",
        reporting_years=[2030],
        operations=[dict(operation="find_financial_facts", operation_id="f")],
        user_requested_targets=[dict(kind="fact", target_id="b02.net_revenue")],
    )
    prefix = json.dumps(core)[:-1]
    assert _complete_proposal_fields(prefix + ', "reasoning_steps": [{"broken') == core
    assert _complete_proposal_fields('{"intent":"direct_fact","operations":[') is None
    assert _complete_proposal_fields(prefix + ', "intent": "direct_fact"}') is None
    assert _explicit_constraints("Tổng tài sản TEST cuối năm 2030")[3] == ["2030-12-31"]
    request = LLMRequest(
        contract_version="llm_gateway_v1",
        request_id="planner-control",
        model=ModelIdentity(provider="gemini", model="gemini-3.5-flash-lite"),
        messages=[Message(role="user", content="Plan")],
        generation=GenerationParameters(temperature=0),
        output_spec=OutputSpec(format="json"),
    )
    _, config = QAGeminiAdapter(object())._config(request)
    assert "operations" in config.response_json_schema["properties"]
    assert request.output_spec.schema_ref is None  # No invented validation attestation.


def test_goal_operations_distinguish_planning_steps_from_verified_arithmetic():
    goal = QARequirement(
        requirement_id="comparison",
        text="So sánh lợi nhuận hai kỳ",
        kind="fact",
        interpretation=True,
        reasoning_operations=["find_financial_facts", "compare"],
    )
    proof = NS(calculation=NS(steps=[NS(operation=NS(operator="subtract"))]))
    assert _reasoning_matches(proof, goal)
    goal.reasoning_operations = ["subtract"]
    proof.calculation.steps[0].operation.operator = "ratio"
    assert not _reasoning_matches(proof, goal)
    assert not _reasoning_matches(None, goal)
    first = NS(
        evidence_id="E1",
        reference="r1",
        company_id="C",
        document_id="D",
        snapshot_id="S",
        period="2030",
    )
    prior = NS(
        evidence_id="E2",
        reference="r2",
        company_id="C",
        document_id="D",
        snapshot_id="S",
        period="2029",
    )
    calculation = NS(
        operands={"E1": first, "E2": prior},
        steps=[NS(operation=NS(period_relation="across_periods"), operands=["E1", "E2"])],
    )
    candidate = NS(
        supporting_evidence_ids=["E1", "E2"],
        reasoning=NS(calculation=calculation),
        company_id="C",
        document_id="D",
        snapshot_id="S",
        period="2030",
        citations=[],
    )
    result = NS(supporting_evidence=[first, prior], candidates=[candidate])
    _check_assignment(result, NS(citations=[]), NS(supporting_references=["r1", "r2"]))
    candidate.period = "2028"
    with pytest.raises(ValueError, match="candidate_provenance_outside_assignment"):
        _check_assignment(result, NS(citations=[]), NS(supporting_references=["r1", "r2"]))
