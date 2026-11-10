"""Contracts only; these controls do not certify real-PDF financial accuracy."""

from types import SimpleNamespace as NS

import pytest
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerProposal,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import (
    matches_financial_target,
    planned_requirements,
)
from vietnamese_financial_multi_agent.outputs.qa_contracts import QARequirement

from .test_financial_qa import gateway_for
from .test_query_planner import planner

PREMISES = ["b02.profit_after_tax", "b03.operating_cash_flow"]


@pytest.mark.parametrize("target_id", [None, "b02.net_revenue"])
def test_fact_relation_with_formula_aspect_is_not_a_calculation(target_id):
    instance = planner()
    question = "Doanh thu TEST 2030"
    payload = instance._deterministic(question)
    # One-premise metric meaning exercises the same representation recovery.
    payload["user_requested_targets"] = [
        dict(
            kind="explanation",
            target_id=target_id,
            interpretation=True,
            interpretation_topic="metric_meaning",
            aspect="formula",
            required_indicators=["b02.net_revenue"],
        )
    ]
    instance._gateway = gateway_for(payload, [])
    result = instance.plan(question, PlannerContext(mode="auto"))
    assert result.status == "planned", result.reasons
    assert result.raw_proposal == payload
    goal = result.effective_proposal.user_requested_targets[0]
    assert (goal.kind, goal.aspect) == ("fact", "value")
    assert not result.effective_proposal.formula_ids


def test_relational_requirements_merge_equivalent_fact_anchors():
    proposal = PlannerProposal(
        intent="multi_step_analysis",
        user_requested_targets=[
            dict(
                kind="fact",
                target_id=item,
                interpretation=True,
                interpretation_topic="earnings_quality",
                required_indicators=PREMISES,
            )
            for item in PREMISES
        ],
    )
    goals = planned_requirements("Đánh giá chất lượng lợi nhuận", proposal)
    assert len([r for r in goals if r.interpretation]) == 1
    assert set(next(r for r in goals if r.interpretation).required_indicators) == set(PREMISES)


@pytest.mark.parametrize(
    "content,expected",
    [
        (
            "Dòng tiền kinh doanh vượt lợi nhuận sau thuế, cho thấy lợi nhuận có hỗ trợ bằng tiền.",
            True,
        ),
        ("Báo cáo có lợi nhuận sau thuế và dòng tiền để xem xét.", False),
        ("Dòng tiền kinh doanh dương.", False),
        ("Chưa đủ bằng chứng để kết luận.", False),
    ],
)
def test_relational_matching_uses_premises_and_assertion_not_exact_topic_phrase(content, expected):
    claim = NS(
        kind="supported_interpretation",
        period="2030",
        content=content,
        supporting_evidence=[NS(kind="fact", canonical_item_id=i) for i in PREMISES],
    )
    goal = QARequirement(
        requirement_id="relation",
        text="",
        kind="fact",
        target_id=PREMISES[0],
        interpretation=True,
        interpretation_topic="earnings_quality",
        required_indicators=PREMISES,
    )
    assert matches_financial_target(claim, goal) == expected
    claim.supporting_evidence.pop()
    assert not matches_financial_target(claim, goal)


def test_partial_goal_and_duplicate_dependencies_preserve_raw_and_independent_plan():
    instance = planner()
    question = "Doanh thu TEST 2030"
    payload = instance._deterministic(question)
    payload["user_requested_targets"] = [
        dict(kind="fact", target_id="b02.net_revenue"),
        dict(kind="metric", target_id="unknown_formula"),
    ]
    payload["operations"][-1]["dependencies"] *= 2
    instance._gateway = gateway_for(payload, [])
    result = instance.plan(question, PlannerContext(mode="auto"))
    assert result.status == "planned", result.reasons
    assert result.raw_proposal == payload
    assert "unknown_formula" not in result.effective_proposal.formula_ids
    assert "answer_target_outside_plan_formulas" in result.caveats
    assert any(t.outcome == "duplicate_dependencies_removed" for t in result.trace)


def test_bad_analysis_envelope_keeps_independent_numeric_candidates():
    from vietnamese_financial_multi_agent.agents import ProfitabilitySpecialist

    from .test_profitability_specialist import upstream

    payload = dict(
        claims=[dict(evidence_id="E001", kind="fact", meaning="fact_value", period="2030")],
        missing_information=[],
        analyses="malformed",
    )
    result = ProfitabilitySpecialist(gateway_for(payload, [])).analyze(
        question="Doanh thu TEST 2030", supervisor_result=upstream()
    )
    assert result.status == "partial"
    assert result.candidates and all(c.kind == "fact" for c in result.candidates)
    assert result.raw_output == payload
    assert any("invalid_analysis_envelope" in t.reasons for t in result.trace)


def test_exact_facts_and_citations_do_not_require_graph_edges():
    from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
    from vietnamese_financial_multi_agent.tools.financial_retrieval import (
        FinancialRetrievalTools,
        FindFinancialFactsRequest,
    )

    from .test_m4_execution import fixture

    data = fixture()
    data["graph"] = None
    fact = data["facts"][0]
    result = FinancialRetrievalTools(SnapshotCatalog(**data)).find_financial_facts(
        FindFinancialFactsRequest(
            document_id=fact.document_id,
            snapshot_id=fact.snapshot_id,
            canonical_item_id=fact.canonical_item_id,
            period=fact.context.period,
        )
    )
    assert result.status == "found"
    assert result.matches[0].record == fact
    assert result.matches[0].citations
    assert result.matches[0].source_review.matches


def test_typed_critic_purpose_matches_only_native_accept_and_correct_period():
    from vietnamese_financial_multi_agent.outputs.qa_composer import _matches_target

    goal = QARequirement(
        requirement_id="R",
        text="",
        kind="fact",
        target_id=PREMISES[0],
        period="2030",
        interpretation=True,
        interpretation_topic="earnings_quality",
        required_indicators=PREMISES,
    )
    claim = NS(
        kind="supported_interpretation",
        period="2030",
        content="Lợi nhuận được chuyển thành tiền từ hoạt động kinh doanh.",
        supporting_evidence=[NS(kind="fact", canonical_item_id=i) for i in PREMISES],
    )
    entry = NS(
        identity=NS(period="2030", kind=claim.kind),
        accepted_claim=claim,
        verification_status="verified",
        decision=NS(
            decision="ACCEPT",
            logic=NS(
                assertions=[NS(status="consistent", required_premises=["earnings_quality_context"])]
            ),
        ),
    )
    assert _matches_target(entry, goal)
    entry.decision.decision = "INVESTIGATE"
    assert not _matches_target(entry, goal)
    entry.decision.decision = "ACCEPT"
    entry.identity.period = "2029"
    assert not _matches_target(entry, goal)
