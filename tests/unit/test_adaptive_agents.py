"""Focused synthetic controls; live research evidence is recorded separately."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.adaptive_controller import AdaptiveFinancialController
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerProposal,
    SpecialistAssignment,
)
from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway
from vietnamese_financial_multi_agent.verification.adaptive_judge import (
    AdaptiveJudge,
    JudgeFeedback,
    JudgeIssue,
)

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


@pytest.mark.parametrize("verdict", ["REVISION_NEEDED", "JUDGE_ERROR"])
def test_feedback_reaches_planner_and_stops_at_two_revisions(monkeypatch, verdict):
    import vietnamese_financial_multi_agent.agents.adaptive_controller as module

    proposals = [
        PlannerProposal(
            intent="direct_fact",
            reasoning_required=True,
            assignments=[SpecialistAssignment(role="profitability", task=f"affected_task_{i}")],
        )
        for i in range(3)
    ]
    outputs = [
        SimpleNamespace(
            status="completed",
            supervisor_result=None,
            planner_result=SimpleNamespace(effective_proposal=p, model_dump=lambda **_: {}),
            specialist_executions=[],
        )
        for p in proposals
    ]
    m5 = Mock()
    m5.run.side_effect = outputs
    monkeypatch.setattr(module, "to_verification_input", lambda _: None)
    runtime = Mock(provider_metadata=[], stage_latency_ms={})
    runtime.verify.return_value = []
    monkeypatch.setattr(module, "VerificationRuntime", lambda *a, **kw: runtime)
    feedback = JudgeFeedback(
        assessment=verdict,
        revision_required=verdict == "REVISION_NEEDED",
        issues=[
            JudgeIssue(
                issue_type="MISSING_EVIDENCE",
                explanation="Need CFO",
                required_evidence=["b03.operating_cash_flow"],
                suggested_action="REQUEST_ADDITIONAL_EVIDENCE",
            )
        ],
    )
    judge = Mock(latency_ms=1)
    judge.assess.return_value = feedback
    monkeypatch.setattr(module, "AdaptiveJudge", lambda *a: judge)
    controller = AdaptiveFinancialController(m5, None, SimpleNamespace(exhausted=False), None)
    controller.run("question", PlannerContext(mode="auto"))
    count = 3 if verdict == "REVISION_NEEDED" else 1
    assert len(controller.rounds) == judge.assess.call_count == m5.run.call_count == count
    assert all(call.kwargs == {"allow_revision": False} for call in runtime.verify.call_args_list)
    if count == 3:
        context = m5.run.call_args_list[1].kwargs["context"]
        assert context.feedback["issues"][0]["required_evidence"] == ["b03.operating_cash_flow"]
        assert context.previous_proposal == proposals[0]
        assert controller.rounds[-1]["stop_reason"] == "revision_or_request_budget_exhausted"


def test_shared_gateway_budget_counts_only_actual_transport_calls():
    gateway = Mock()
    gateway.generate.side_effect = lambda req: __import__(
        "vietnamese_financial_multi_agent.core.fake_llm_transport", fromlist=["FakeLLMTransport"]
    ).FakeLLMTransport()(req)
    budget = RequestGateway(gateway, max_calls=1, timeout_seconds=10)
    assert budget.generate(request()).status == "success"
    assert budget.generate(request("second")).status == "error"
    assert gateway.generate.call_count == len(budget.events) == 1 and budget.exhausted


def test_judge_pass_cannot_promote_native_m6_rejection(monkeypatch):
    import vietnamese_financial_multi_agent.agents.adaptive_controller as module

    proposal = PlannerProposal(intent="direct_fact", reasoning_required=True)
    output = SimpleNamespace(
        status="completed",
        supervisor_result=None,
        specialist_executions=[],
        planner_result=SimpleNamespace(effective_proposal=proposal, model_dump=lambda **_: {}),
    )
    rejected = SimpleNamespace(
        outcome=SimpleNamespace(
            parent_candidate_id="bad",
            final=SimpleNamespace(
                candidate_id="bad",
                decision="INVESTIGATE",
                original_claim=SimpleNamespace(kind="fact"),
            ),
        )
    )
    monkeypatch.setattr(module, "to_verification_input", lambda _: None)
    monkeypatch.setattr(
        module,
        "VerificationRuntime",
        lambda *a, **kw: SimpleNamespace(
            verify=lambda *a, **kw: [rejected], provider_metadata=[], stage_latency_ms={}
        ),
    )
    monkeypatch.setattr(AdaptiveJudge, "assess", lambda *a: JudgeFeedback(assessment="PASS"))
    controller = AdaptiveFinancialController(Mock(run=lambda **_: output), None, None, None)
    _, histories = controller.run("q", PlannerContext(mode="auto"))
    assert histories == [rejected] and histories[0].outcome.final.decision == "INVESTIGATE"


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


def test_singleton_document_envelope_and_shared_revision_judge_limits():
    from vietnamese_financial_multi_agent.agents.qa_planning import (
        DocumentPlan,
        plan_fusion,
        structured_call,
    )
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
    from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity

    payload = dict(
        requirements=[dict(target="source", label="source", kind="exact_text", query="source")],
        selection_reason="lookup",
    )
    result = structured_call(
        gateway_for([payload], []),
        ModelIdentity(provider="gemini", model="test"),
        DocumentPlan,
        dict(question="source"),
        "document-planner",
    )
    assert result.requirements[0].target == "source"
    planned = plan_fusion(
        gateway_for(
            dict(
                question="source",
                requirements=[
                    dict(
                        requirement_id="relation",
                        original_span="source",
                        lane="relation",
                        kind="source_context",
                        dependencies=["fact"],
                    ),
                    dict(
                        requirement_id="fact", original_span="source", lane="financial", kind="fact"
                    ),
                ],
            ),
            [],
        ),
        FinancialQARequest(question="source"),
    )
    assert [r.requirement_id for r in planned.requirements] == ["fact", "relation"]
    gateway = Mock(generate=lambda req: FakeLLMTransport()(req))
    budget = RequestGateway(gateway, max_calls=10, timeout_seconds=10)
    assert budget.reserve_revision() and budget.reserve_revision() and not budget.reserve_revision()
    for index in range(3):
        assert budget.generate(request(f"adaptive-judge-{index}")).status == "success"
    assert budget.generate(request("document-judge-fourth")).status == "error"
    assert budget.judge_calls == len(budget.events) == 3
