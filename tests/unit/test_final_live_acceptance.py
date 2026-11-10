"""Targeted engineering controls for live-discovered integration failures."""

import json
from types import SimpleNamespace as NS

from vietnamese_financial_multi_agent.agents.fusion_contracts import decompose, is_mixed
from vietnamese_financial_multi_agent.agents.query_planner import (
    _complete_proposal_fields,
    _explicit_constraints,
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
