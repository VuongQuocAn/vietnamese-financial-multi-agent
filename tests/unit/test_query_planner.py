"""Planner controls; mock understanding không là Gemini/research evidence."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.agents import (
    EvidenceAwareQueryPlanner,
    PlannerContext,
    PlannerResult,
    validate_plan,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import QADocument

from .test_financial_qa import gateway_for
from .test_m4_execution import fixture


def planner(data=None, gateway=None):
    data = data or fixture()
    document = QADocument(
        document_id=data["descriptors"][0].document_id,
        company_id=data["facts"][0].company_id,
        company_aliases=["TEST"],
        reporting_year=2030,
    )
    return EvidenceAwareQueryPlanner(SnapshotCatalog(**data), [document], gateway)


def test_metric_expands_approved_operands_and_keeps_pending_roundtrip():
    data = fixture()
    before = deepcopy(data)
    result = planner(data).plan(
        "Biên lợi nhuận gộp TEST năm 2030?", PlannerContext(mode="deterministic")
    )
    assert result.status == "planned", result.model_dump()
    assert result.validation.structurally_valid and result.validation.execution_eligible
    assert [s.tool for s in result.plan.steps if s.tool] == [
        "find_financial_facts",
        "find_financial_facts",
        "calculate_financial_metric",
        "get_metric_evidence_lineage",
    ]
    facts = [s for s in result.plan.steps if s.tool == "find_financial_facts"]
    assert all(s.prerequisite_step_ids == ["snapshot"] for s in facts)
    assert all(s.status == "pending" for s in result.plan.steps)
    assert all(r.resolution == "unresolved" for r in result.plan.requirements)
    assert not result.financial_fact_verified and data == before and result.llm.calls == 0
    assert PlannerResult.model_validate_json(result.model_dump_json()) == result


def test_gemini_multitarget_proposal_drives_real_dag_without_m4_single_target_parser():
    proposal = dict(
        intent="multi_step_analysis",
        company_alias="TEST",
        reporting_years=[2030],
        required_indicators=["b02.net_revenue", "b02.gross_profit"],
        evidence_needs=["fact", "citations", "analysis_bundle"],
        operations=[
            dict(
                operation_id="r",
                operation="find_financial_facts",
                canonical_item_id="b02.net_revenue",
            ),
            dict(
                operation_id="p",
                operation="find_financial_facts",
                canonical_item_id="b02.gross_profit",
            ),
            dict(operation_id="rs", operation="get_evidence_sources", dependencies=["r"]),
            dict(operation_id="ps", operation="get_evidence_sources", dependencies=["p"]),
            dict(operation_id="analysis", operation="prepare_bundle", dependencies=["rs", "ps"]),
        ],
    )
    seen = []
    result = planner(gateway=gateway_for(proposal, seen)).plan(
        "Phân tích doanh thu và lợi nhuận gộp TEST 2030"
    )
    assert result.status == "planned", result.reasons
    assert result.llm.calls == len(seen) == 1
    assert result.plan.steps[-1].prerequisite_step_ids == ["op_2", "op_3"]
    assert validate_plan(result.plan, catalog=planner()._catalog).execution_eligible
    assert "approved_formula_candidates" in seen[0].messages[0].content


@pytest.mark.parametrize(
    "question,status",
    [
        ("Phân tích doanh thu TEST 2021 và 2030", "blocked"),
        ("ROE TEST 2030", "unsupported"),
        ("Doanh thu TEST", "clarification_required"),
        ("Doanh thu TEST 2030 hợp nhất", "blocked"),
    ],
)
def test_policy_and_missing_metadata_gates(question, status):
    result = planner().plan(question, PlannerContext(mode="deterministic"))
    assert result.status == status and not result.financial_fact_verified
    assert result.reasons


def test_no_latest_on_original_recovery_ambiguity_and_scope_context_conflict():
    data = fixture()
    descriptor = data["descriptors"][0].model_copy(deep=True)
    descriptor.snapshot_id, descriptor.parent_snapshot_id = "recovered", descriptor.snapshot_id
    descriptor.origin = "recovery"
    data["descriptors"].append(descriptor)
    result = planner(data).plan("Doanh thu TEST 2030", PlannerContext(mode="deterministic"))
    assert result.status == "clarification_required" and len(result.snapshot_candidates) == 2
    alternative = planner(data).plan(
        "Doanh thu TEST 2030, chưa quyết định bản gốc hay recovery",
        PlannerContext(mode="deterministic"),
    )
    assert (
        alternative.status == "clarification_required" and len(alternative.snapshot_candidates) == 2
    )
    conflict = planner().plan(
        "Doanh thu TEST 2030 riêng",
        PlannerContext(mode="deterministic", reporting_scope="consolidated"),
    )
    assert conflict.status == "clarification_required" and not conflict.plan


def test_malformed_and_cyclic_proposals_fail_without_retry():
    for payload in (
        {"intent": "direct_fact", "financial_value": "100"},
        dict(
            intent="direct_fact",
            company_alias="TEST",
            reporting_years=[2030],
            operations=[
                dict(
                    operation_id="cycle",
                    operation="find_financial_facts",
                    canonical_item_id="b02.net_revenue",
                    dependencies=["cycle"],
                )
            ],
        ),
    ):
        seen = []
        result = planner(gateway=gateway_for(payload, seen)).plan("Doanh thu TEST 2030")
        assert result.status == "failed" and len(seen) == result.llm.calls == 1
        assert (
            result.raw_proposal == payload
            and not result.plan
            and result.trace[-1].outcome == "failed"
        )


def test_short_profit_label_retains_both_targets_instead_of_silent_partial_plan():
    result = planner().plan(
        "Phân tích doanh thu và lợi nhuận trước thuế TEST 2030",
        PlannerContext(mode="deterministic"),
    )
    assert result.query.intent == "multi_step_analysis"
    assert set(result.query.required_indicators) == {"b02.net_revenue", "b02.profit_before_tax"}
    # Fixture không có profit_before_tax: không trả planned cho phần evidence còn thiếu.
    assert result.status == "blocked" and result.plan and result.validation.structurally_valid


def test_multiple_targets_cannot_be_mislabeled_direct_fact_by_gemini():
    api = planner()
    proposal = api._deterministic("Doanh thu và lợi nhuận gộp TEST 2030")
    proposal["intent"] = "direct_fact"
    seen = []
    result = planner(gateway=gateway_for(proposal, seen)).plan(
        "Doanh thu và lợi nhuận gộp TEST 2030"
    )
    assert result.status == "failed" and "proposal_intent_target_mismatch" in result.reasons
    assert len(seen) == 1 and result.raw_proposal == proposal


def test_keep_evidence_separate_does_not_invent_reporting_scope():
    result = planner().plan(
        "Doanh thu và lợi nhuận gộp TEST 2030, giữ riêng bằng chứng của mỗi chỉ tiêu",
        PlannerContext(mode="deterministic"),
    )
    assert result.status == "planned" and result.query.reporting_scope is None


def test_explicit_evidence_route_normalization_preserves_raw_model_intent():
    payload = planner()._deterministic("Biên lợi nhuận gộp TEST 2030")
    seen = []
    result = planner(gateway=gateway_for(payload, seen)).plan(
        "Lập kế hoạch kiểm tra nguồn và cách tính biên lợi nhuận gộp TEST 2030"
    )
    assert result.status == "planned" and result.query.intent == "evidence_explanation"
    assert result.proposal.intent == "calculated_metric" and result.raw_proposal == payload
    assert any(t.outcome == "explicit_evidence_intent_normalized" for t in result.trace)


def test_two_explicit_operand_years_in_approved_same_filing_yoy_are_not_cross_document():
    result = planner(fixture(formula="revenue_yoy")).plan(
        "Tăng trưởng doanh thu TEST trong báo cáo năm 2030 so với 2029, dùng cùng báo cáo",
        PlannerContext(mode="deterministic"),
    )
    assert result.status == "planned", result.reasons
    assert not result.query.cross_document_comparison
    assert set(result.query.reporting_periods) == {"2029", "2030"}
    assert len({s.selector.document_id for s in result.plan.steps}) == 1
