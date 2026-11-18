"""Focused synthetic controls; live research evidence is recorded separately."""

from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerProposal,
)
from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway

from .test_financial_qa import gateway_for
from .test_llm_gateway import request
from .test_query_planner import planner


@pytest.mark.parametrize("reasoning", [False, True])
def test_auto_planner_preserves_dynamic_selection_and_tool_only(reasoning):
    instance = planner()
    proposal = instance._deterministic("Doanh thu TEST 2030")
    proposal.update(reasoning_required=reasoning, selection_reason="user_goal")
    if reasoning:
        proposal["assignments"] = [
            dict(role="profitability", task="Đánh giá doanh thu", indicators=["b02.net_revenue"])
        ]
    seen = []
    instance._gateway = gateway_for(proposal, seen)
    result = instance.plan("Đánh giá hoạt động TEST 2030", PlannerContext(mode="auto"))
    assert result.status == "planned", result.reasons
    assert len(seen) == result.llm.calls == 1
    assert result.effective_proposal.reasoning_required == reasoning
    assert bool(result.effective_proposal.assignments) == reasoning
    assert result.plan.query.required_indicators == ["b02.net_revenue"]
    if reasoning:
        from vietnamese_financial_multi_agent.agents import (
            AdaptiveSpecialistRouter,
            RiskAwareSupervisor,
        )

        result.effective_proposal.assignments[0].depends_on = [
            result.effective_proposal.operations[0].operation_id
        ]
        supervisor = RiskAwareSupervisor(instance._catalog).execute(result.plan)
        routed = AdaptiveSpecialistRouter().route(
            question=result.question, planner_result=result, supervisor_result=supervisor
        )
        assert routed.selected_roles == ["profitability"]


def test_shared_gateway_budget_counts_only_actual_transport_calls():
    gateway = Mock()
    gateway.generate.side_effect = lambda req: __import__(
        "vietnamese_financial_multi_agent.core.fake_llm_transport", fromlist=["FakeLLMTransport"]
    ).FakeLLMTransport()(req)
    budget = RequestGateway(gateway, max_calls=1, timeout_seconds=10)
    assert budget.generate(request()).status == "success"
    assert budget.generate(request("second")).status == "error"
    assert gateway.generate.call_count == len(budget.events) == 1 and budget.exhausted


def test_invalid_analysis_does_not_erase_numeric_claim_or_inflate_replan_context():
    from vietnamese_financial_multi_agent.agents import ProfitabilitySpecialist

    from .test_adaptive_router import inputs

    _, supervisor = inputs("Doanh thu TEST 2030")
    payload = dict(
        claims=[dict(evidence_id="E001", kind="fact", meaning="fact_value", period="2030")],
        missing_information=[],
        analyses=[dict(statement="Bounded claim", evidence_ids=["E001"], limitations=["flag"] * 9)],
    )
    specialist = ProfitabilitySpecialist(gateway_for(payload, []))
    result = specialist.analyze(question="Doanh thu TEST 2030", supervisor_result=supervisor)
    assert result.status == "partial" and len(result.candidates) == 1
    assert result.candidates[0].kind == "fact"
    assert any("invalid_analysis_schema" in t.reasons for t in result.trace)
    context = PlannerContext(
        mode="auto",
        feedback={"issues": []},
        previous_proposal=PlannerProposal(intent="direct_fact"),
        reusable_results=[
            dict(
                evidence_inventory=[
                    dict(indicator="b02.net_revenue", value="10", native_status="M6_ACCEPT")
                ]
            )
        ],
    )
    prompt = planner()._prompt(context)
    import json

    assert len(json.dumps(prompt, ensure_ascii=False)) < 16000
    assert "approved_formula_candidates" not in prompt


@pytest.mark.parametrize("supported", [True, False])
def test_analysis_numeric_proof_bridge_keeps_native_release_authority(tmp_path, supported):
    from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
    from vietnamese_financial_multi_agent.verification import (
        DeterministicFinancialValidator,
        EvidenceCritic,
        FinancialLogicCritic,
    )
    from vietnamese_financial_multi_agent.verification.judge import VerificationJudge

    from .test_evidence_critic import semantic_gateway
    from .test_financial_logic_critic import gateway as logic_gateway
    from .test_financial_validators import batch_for
    from .test_m4_execution import fixture

    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind = "supported_interpretation"
    claim.analysis_premises = [claim.content]
    claim.content = "Doanh thu trong kỳ được ghi nhận trong báo cáo."
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)

    def semantic(result):
        for a in result["assertions"]:
            a.update(
                status="supported" if supported else "unsupported",
                evidence_ids=["E1"],
                reason="direct_support" if supported else "beyond_evidence",
                missing=[],
            )

    evidence = EvidenceCritic(catalog, semantic_gateway(semantic)).assess(batch, validation)
    assertion = evidence.claims[0].assertions[0]
    assert bool(assertion.check_references) == supported
    logic = FinancialLogicCritic(logic_gateway(status="consistent")).assess(
        batch, validation, evidence
    )
    decision = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert (decision.decision == "ACCEPT") == supported
    from vietnamese_financial_multi_agent.verification.decision_contracts import (
        VerificationLoopResult,
    )
    from vietnamese_financial_multi_agent.verification.ledger_contracts import (
        VerificationHistory,
        VerificationProofContext,
    )
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    history = VerificationHistory(
        contexts=[
            VerificationProofContext(
                batch=batch, validation=validation, evidence=evidence, logic=logic
            )
        ],
        outcome=VerificationLoopResult(
            parent_candidate_id=claim.candidate_id,
            initial_input=batch,
            attempts=[decision],
            stopped=True,
            stop_reason="initial_decision_terminal",
        ),
    )
    admission = VerifiedClaimRepository(tmp_path).admit_many([history])[0]
    assert admission.status == ("stored" if supported else "rejected")
    if supported:
        assert logic.claims[0].trace.llm.calls == 1
        assert all(a.status == "consistent" for a in logic.claims[0].assertions)


def test_analysis_premises_keep_decimal_source_and_semantic_gates():
    from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
    from vietnamese_financial_multi_agent.verification import DeterministicFinancialValidator
    from vietnamese_financial_multi_agent.verification.evidence_critic import EvidenceCritic

    from .test_financial_validators import batch_for
    from .test_m4_execution import fixture

    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    original = claim.content
    claim.kind = "supported_interpretation"
    claim.analysis_premises = [original]
    claim.content = "Nguồn này chỉ cho biết doanh thu trong kỳ, chưa đủ kết luận nguyên nhân."
    validator = DeterministicFinancialValidator(SnapshotCatalog(**data))
    validation = validator.validate(batch).claims[0]
    assert all(c.status == "pass" for c in validation.checks if c.check_id == "numeric")
    assert EvidenceCritic._consistent(claim, validation)
    assert (
        next(c for c in validation.checks if c.check_id == "semantic_conclusion").status
        == "undetermined"
    )
    claim.supporting_evidence[0].value = "999"
    invalid = validator.validate(batch).claims[0]
    assert any(c.status == "fail" and c.check_id == "supporting_fact" for c in invalid.checks)
    claim.content += " 999 VND."
    invalid = validator.validate(batch).claims[0]
    assert any(c.check_id == "numeric" and c.status == "fail" for c in invalid.checks)
    claim.content = "Tỷ lệ CFO trên lợi nhuận tốt."
    invalid = validator.validate(batch).claims[0]
    assert any(c.check_id == "formula" and c.status == "fail" for c in invalid.checks)


def test_same_filing_year_echo_and_periods_stay_bound():
    from .test_m4_execution import fixture

    instance = planner(fixture(formula="revenue_yoy"))
    proposal = instance._deterministic("Doanh thu TEST 2030")
    proposal.update(intent="multi_step_analysis", period="2030")
    proposal["operations"][0]["period"] = "2030"
    proposal["operations"] += [
        dict(
            operation_id="prior",
            operation="find_financial_facts",
            canonical_item_id="b02.net_revenue",
            period="2029",
        ),
        dict(operation_id="prior_source", operation="get_evidence_sources", dependencies=["prior"]),
        dict(
            operation_id="bundle",
            operation="prepare_bundle",
            dependencies=["sources_0", "prior_source"],
        ),
    ]
    instance._gateway = gateway_for(proposal, [])
    result = instance.plan(
        "So sánh doanh thu TEST 2030 với năm 2029 theo báo cáo năm 2030.",
        PlannerContext(mode="auto", reporting_year=2030),
    )
    assert result.status == "planned", result.reasons
    assert result.proposal.period == "2030" and result.effective_proposal.period is None
    assert not result.query.cross_document_comparison
    assert {r.selector.period for r in result.plan.requirements if r.evidence_type == "fact"} == {
        "2029",
        "2030",
    }
