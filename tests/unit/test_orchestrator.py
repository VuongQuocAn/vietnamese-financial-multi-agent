"""Synthetic orchestration controls; persisted BBS/live evaluation is separate."""

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents import (
    AdaptiveSpecialistRouter,
    FinancialMultiAgentOrchestrator,
    OrchestrationResult,
    PlannerContext,
    ProfitabilitySpecialist,
    SpecialistExecution,
    aggregate_candidates,
    build_specialist_context,
)

from .test_adaptive_router import inputs
from .test_financial_qa import gateway_for


def pipeline(p, s, specialists):
    planner, supervisor = Mock(), Mock()
    planner.plan.return_value = p
    supervisor.execute.return_value = s
    router = Mock(wraps=AdaptiveSpecialistRouter())
    return (
        FinancialMultiAgentOrchestrator(
            planner=planner, supervisor=supervisor, router=router, specialists=specialists
        ),
        planner,
        supervisor,
        router,
    )


def metric_specialist(seen):
    return ProfitabilitySpecialist(
        gateway_for(
            dict(
                claims=[
                    dict(
                        evidence_id="E001",
                        kind="approved_metric",
                        meaning="metric_value",
                        period="2030",
                        statement=None,
                    )
                ],
                missing_information=[],
            ),
            seen,
        )
    )


def test_single_metric_projection_closure_no_operand_claims_and_roundtrip():
    p, s = inputs()
    before = deepcopy((p, s))
    seen = []
    instance, planner, supervisor, router = pipeline(
        p, s, {"profitability": metric_specialist(seen)}
    )
    context = PlannerContext(mode="deterministic")
    output = instance.run(question=p.question, context=context)
    assert output.status == "completed", output.model_dump()
    assert planner.plan.call_count == supervisor.execute.call_count == router.route.call_count == 1
    assert len(output.specialist_executions) == len(seen) == len(output.candidates) == 1
    execution = output.specialist_executions[0]
    projection = execution.projection
    assert projection.claim_fact_references == []
    assert len(projection.supporting_operand_references) == 2
    assert (
        projection.supervisor_result.evidence_bundle.calculations == s.evidence_bundle.calculations
    )
    assert projection.supervisor_result.evidence_bundle.facts == s.evidence_bundle.facts
    assert projection.supervisor_result.final_plan_state.query.original_question == p.question
    assert projection.supervisor_result.final_plan_state.query.required_indicators == []
    assert [e.kind for e in execution.result.supporting_evidence] == ["metric"]
    prompt = json.loads(seen[0].messages[0].content)
    assert prompt["orchestration_assignment"]["assigned_fact_targets"] == []
    assert prompt["orchestration_assignment"]["assigned_formula_targets"] == ["gross_margin"]
    assert output.candidates[0].calculation == s.evidence_bundle.calculations[0]
    assert output.candidates[0].citations == s.evidence_bundle.calculations[0].evidence.citations
    assert not output.financial_fact_verified and not output.candidates[0].financial_fact_verified
    assert output.usage.calls == output.usage.calls_with_unknown_tokens == 1
    assert output.usage.total_tokens is None
    assert (p, s) == before
    assert OrchestrationResult.model_validate_json(output.model_dump_json()) == output
    assert [t.stage for t in output.trace] == [
        "planning",
        "supervisor",
        "routing",
        "context_projection",
        "specialist_execution",
        "candidate_aggregation",
        "finalization",
    ]


@pytest.mark.parametrize("status", ["clarification_required", "unsupported", "blocked", "failed"])
def test_planner_stops_without_supervisor_or_specialists(status):
    p, s = inputs()
    p.status = status
    instance, _, supervisor, router = pipeline(p, s, {})
    output = instance.run(question=p.question, context=PlannerContext())
    assert output.status == status
    supervisor.execute.assert_not_called()
    router.route.assert_not_called()
    assert not output.specialist_executions
    assert output.trace[-1].stage == "finalization"
    if status == "failed":
        assert output.errors[0].code == "planner_failed"


@pytest.mark.parametrize("status", ["blocked", "failed"])
def test_supervisor_stops_before_routing(status):
    p, s = inputs()
    s.status = status
    instance, _, _, router = pipeline(p, s, {})
    output = instance.run(question=p.question, context=PlannerContext())
    assert output.status == status and not output.candidates
    router.route.assert_not_called()


@pytest.mark.parametrize("missing", ["operand", "citation"])
def test_projection_rejects_incomplete_dependency_closure(missing):
    p, s = inputs()
    decision = AdaptiveSpecialistRouter().route(
        question=p.question, planner_result=p, supervisor_result=s
    )
    if missing == "operand":
        s.evidence_bundle.facts.pop()
    else:
        s.evidence_bundle.citations.clear()
    with pytest.raises(ValueError):
        build_specialist_context(s, decision.routes[0])


def test_raised_specialist_error_is_structured_and_never_retried():
    p, s = inputs()
    failed = Mock()
    failed.analyze.side_effect = RuntimeError("private transport details")
    instance, _, _, _ = pipeline(p, s, {"profitability": failed})
    output = instance.run(question=p.question, context=PlannerContext())
    assert output.status == "failed"
    failed.analyze.assert_called_once()
    assert output.errors[0].error_type == "RuntimeError"
    assert "private transport details" not in output.model_dump_json()
    assert output.specialist_executions[0].usage_unknown


def test_dedup_origins_conflict_context_and_deterministic_ids():
    p, s = inputs()
    instance, _, _, _ = pipeline(p, s, {"profitability": metric_specialist([])})
    output = instance.run(question=p.question, context=PlannerContext())
    first = output.specialist_executions[0]
    duplicate = first.model_copy(deep=True)
    duplicate.role = "liquidity_and_leverage"
    duplicate.execution_id = "second"
    duplicate.result.candidates[0].candidate_id = "random-other-id"
    candidates, conflicts = aggregate_candidates([first, duplicate])
    assert len(candidates) == 1 and not conflicts
    assert len(candidates[0].origins) == 2
    assert candidates[0].origin_roles == ["profitability", "liquidity_and_leverage"]
    assert candidates[0].candidate_id == output.candidates[0].candidate_id
    different = duplicate.model_copy(deep=True)
    different.result.candidates[0].snapshot_id = "different-snapshot"
    candidates, conflicts = aggregate_candidates([first, different])
    assert len(candidates) == 2 and len(conflicts) == 1
    assert all(c.conflict_ids and not c.financial_fact_verified for c in candidates)
    # No winner, original content and both source result pointers remain available.
    assert {o.execution_id for c in candidates for o in c.origins} == {first.execution_id, "second"}
    malformed = SpecialistExecution(
        execution_id="empty", role="profitability", assigned_requirement_ids=[]
    )
    assert aggregate_candidates([malformed]) == ([], [])


def test_specialist_cannot_return_operand_as_independently_assigned_evidence():
    p, s = inputs()
    # Standalone legacy selector includes operands; orchestration assignment does not.
    legacy = ProfitabilitySpecialist(gateway_for(dict(claims=[], missing_information=[]), []))
    result = legacy.analyze(question=p.question, supervisor_result=s)
    rogue = Mock()
    rogue.analyze.return_value = result
    instance, _, _, _ = pipeline(p, s, {"profitability": rogue})
    output = instance.run(question=p.question, context=PlannerContext())
    assert output.status == "failed" and not output.candidates
    assert output.specialist_executions[0].status == "failed"
    assert output.missing_evidence == output.specialist_executions[0].assigned_requirement_ids


def test_missing_factual_coverage_is_not_completed():
    p, s = inputs()
    instance, _, _, _ = pipeline(p, s, {"profitability": metric_specialist([])})
    result = (
        instance.run(question=p.question, context=PlannerContext()).specialist_executions[0].result
    )
    # A source-backed interpretation alone does not supply the requested metric value claim.
    result.candidates[0].kind = "supported_interpretation"
    result.status = "generated"
    specialist = Mock()
    specialist.analyze.return_value = result
    instance, _, _, _ = pipeline(p, s, {"profitability": specialist})
    output = instance.run(question=p.question, context=PlannerContext())
    assert output.status == "partial" and len(output.candidates) == 1
    assert output.missing_evidence == output.specialist_executions[0].assigned_requirement_ids


def test_model_limitations_are_preserved_without_inventing_missing_assigned_targets():
    p, s = inputs()
    instance, _, _, _ = pipeline(p, s, {"profitability": metric_specialist([])})
    result = (
        instance.run(question=p.question, context=PlannerContext()).specialist_executions[0].result
    )
    result.status = "partial"
    result.missing_evidence = ["Other specialist's workload and an unrequested comparison"]
    specialist = Mock()
    specialist.analyze.return_value = result
    instance, _, _, _ = pipeline(p, s, {"profitability": specialist})
    output = instance.run(question=p.question, context=PlannerContext())
    assert output.status == "completed" and output.missing_evidence == []
    execution = output.specialist_executions[0]
    assert execution.status == "generated" and execution.result.status == "partial"
    assert execution.covered_requirement_ids == execution.assigned_requirement_ids
    assert execution.result.missing_evidence == result.missing_evidence
    assert any(result.missing_evidence[0] in caveat for caveat in output.caveats)
