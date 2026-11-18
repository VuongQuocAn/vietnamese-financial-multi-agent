"""QA-Fix-02 offline controls; synthetic fixtures are not financial evaluation."""

import pytest
from google.genai import errors
from vietnamese_financial_multi_agent.agents import (
    AdaptiveSpecialistRouter,
    PlannerContext,
    RiskAwareSupervisor,
)

from .test_financial_qa import gateway_for
from .test_query_planner import planner

ROLES = ["profitability", "liquidity_and_leverage", "cash_flow_and_earnings_quality"]


def rejected(**changes):
    return dict(intent="unsupported", unsupported_capabilities=ROLES, **changes)


@pytest.mark.parametrize(
    "question",
    [
        "Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh TEST 2030",
        "Đánh giá dòng tiền, đòn bẩy và khả năng sinh lời TEST năm 2030",
        "Cho biết thanh khoản và khả năng sinh lời TEST 2030",
    ],
)
def test_broad_supported_domains_clarify_without_selecting_metrics(question):
    raw = rejected()
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.status == "clarification_required", result.reasons
    assert result.missing_information and not result.plan
    assert result.raw_proposal == raw and result.proposal.intent == "unsupported"
    assert result.effective_proposal.formula_ids == []
    assert any(t.stage == "semantic_policy" for t in result.trace)


@pytest.mark.parametrize(
    "question,items,formulas",
    [
        ("Biên lợi nhuận gộp và tổng tài sản TEST 2030", ["b01.total_assets"], ["gross_margin"]),
        (
            "Dòng tiền thuần từ hoạt động kinh doanh, tổng tài sản và biên lợi nhuận gộp TEST 2030",
            ["b01.total_assets", "b03.operating_cash_flow"],
            ["gross_margin"],
        ),
        ("Doanh thu và lợi nhuận gộp TEST 2030", ["b02.net_revenue", "b02.gross_profit"], []),
    ],
)
def test_explicit_targets_recover_rejected_or_omitted_proposal(question, items, formulas):
    raw = rejected()
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.status in {"planned", "blocked"}, result.reasons
    assert result.plan and result.validation.structurally_valid
    effective = result.effective_proposal
    assert set(effective.formula_ids) == set(formulas)
    assert set(effective.required_indicators) == set(items)
    assert (
        effective.intent == "multi_step_analysis"
        and effective.operations[-1].operation == "prepare_bundle"
    )
    assert not effective.unsupported_capabilities and result.raw_proposal == raw
    assert result.query.reporting_scope is None and not result.financial_fact_verified


def test_partial_support_keeps_unsupported_target_for_router():
    question = "Doanh thu thuần và ROE TEST 2030"
    raw = dict(intent="unsupported", unsupported_capabilities=["ROE"])
    instance = planner(gateway=gateway_for(raw, []))
    result = instance.plan(question)
    assert result.status == "planned", result.reasons
    upstream = RiskAwareSupervisor(instance._catalog).execute(result.plan)
    routing = AdaptiveSpecialistRouter().route(
        question=question, planner_result=result, supervisor_result=upstream
    )
    assert routing.status == "partial" and routing.selected_roles == ["profitability"]
    assert any(
        r.status == "unsupported" and r.target_id.lower() == "roe" for r in routing.requirements
    )
    assert result.effective_proposal.unsupported_capabilities == ["ROE"]
    assert result.query.requested_formula_ids == []


def test_unapproved_substitution_is_never_executed():
    question = "ROE TEST 2030"
    raw = planner()._deterministic("Biên lợi nhuận gộp TEST 2030")
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.status == "unsupported" and not result.plan
    assert result.raw_proposal == raw


@pytest.mark.parametrize(
    "question,changes,context,status",
    [
        ("Doanh thu TEST 2030", {"reporting_scope": "separate"}, {}, "failed"),
        (
            "Doanh thu TEST 2030 riêng",
            {},
            {"reporting_scope": "consolidated"},
            "clarification_required",
        ),
        ("Doanh thu TEST 2030", {}, {"reporting_year": 2029}, "clarification_required"),
        ("Doanh thu TEST 2029 và 2030", {}, {}, "blocked"),
    ],
)
def test_recovery_preserves_scope_year_and_cross_document_gates(question, changes, context, status):
    raw = rejected(**changes)
    result = planner(gateway=gateway_for(raw, [])).plan(question, PlannerContext(**context))
    assert result.status == status and not result.plan


def test_missing_evidence_blocks_recovery_instead_of_computing_zero():
    instance = planner()
    data = instance._catalog
    result = planner(gateway=gateway_for(rejected(), [])).plan("Lợi nhuận trước thuế TEST 2030")
    assert result.status == "blocked" and result.plan
    assert not result.financial_fact_verified
    assert all(s.status == "pending" for s in result.plan.steps)
    assert data.facts  # Original catalog untouched.


def api_error(code):
    return errors.APIError(code, {"error": {"code": code, "message": "synthetic provider failure"}})


def test_omission_and_approved_metric_substitution_require_clarification():
    raw = planner()._deterministic("Biên lợi nhuận gộp TEST 2030")
    raw["formula_ids"] = ["debt_to_assets"]
    raw["operations"][0]["formula_id"] = "debt_to_assets"
    result = planner(gateway=gateway_for(raw, [])).plan("Biên lợi nhuận gộp TEST 2030")
    assert result.status == "clarification_required" and not result.plan
    assert result.raw_proposal == raw


def test_registered_capability_contradiction_without_exact_question_alias_clarifies():
    result = planner(gateway=gateway_for(rejected(), [])).plan("Đánh giá doanh nghiệp TEST 2030")
    assert result.status == "clarification_required" and not result.plan


@pytest.mark.parametrize("cash_label", ["dòng tiền kinh doanh", "CFO"])
def test_cash_flow_paraphrases_preserve_explicit_targets_without_quality_verdict(cash_label):
    question = (
        f"Doanh thu thuần và {cash_label} TEST 2030 có cho thấy chất lượng lợi nhuận tốt không?"
    )
    raw = dict(intent="unsupported", unsupported_capabilities=["earnings_quality_evidence"])
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.effective_proposal.required_indicators == [
        "b02.net_revenue",
        "b03.operating_cash_flow",
    ]
    assert result.status == "blocked" and result.plan  # CFO absent in fixture.
    assert not result.effective_proposal.unsupported_capabilities
    assert result.effective_proposal.formula_ids == [] and not result.financial_fact_verified


def test_valid_clarification_reason_is_preserved_when_operations_are_deliberately_empty():
    raw = dict(
        intent="ambiguous",
        required_indicators=["b02.net_revenue", "b03.operating_cash_flow"],
        missing_information=["earnings_quality_criteria_required"],
    )
    result = planner(gateway=gateway_for(raw, [])).plan(
        "Doanh thu và CFO TEST 2030 có cho thấy chất lượng lợi nhuận tốt không?"
    )
    assert result.status == "clarification_required" and not result.plan
    assert result.effective_proposal.missing_information == raw["missing_information"]
    assert result.query.missing_information == raw["missing_information"]
