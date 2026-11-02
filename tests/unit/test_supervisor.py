"""Supervisor engineering controls; fixture tổng hợp không là financial evaluation."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.agents import (
    EvidencePlan,
    EvidenceRequirement,
    PlannerContext,
    RiskAwareSupervisor,
    SupervisorResult,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    FinancialCalculator,
    FindFinancialFactsRequest,
)

from .test_m4_execution import fixture
from .test_query_planner import planner


def planned(question="Biên lợi nhuận gộp TEST 2030?"):
    data = fixture()
    plan = planner(data).plan(question, PlannerContext(mode="deterministic")).plan
    assert plan
    return data, plan


def test_metric_exact_m4_evidence_lifecycle_roundtrip_and_immutable_inputs():
    data, plan = planned()
    before = deepcopy(plan)
    supervisor = RiskAwareSupervisor(SnapshotCatalog(**data))
    result = supervisor.execute(plan)
    assert result.status == "completed", result.model_dump()
    calc_step = next(s for s in plan.steps if s.tool == "calculate_financial_metric")
    expected = FinancialCalculator(SnapshotCatalog(**data)).calculate_financial_metric(
        CalculateFinancialMetricRequest(**calc_step.arguments)
    )
    assert result.evidence_bundle.calculations == [expected]
    assert result.evidence_bundle.complete and result.evidence_bundle.citations
    assert all(
        t.transitions == ["pending", "ready", "running", "completed"] for t in result.step_results
    )
    assert all(r.resolution == "resolved" for r in result.resolved_requirements)
    assert result.triggered_stop_conditions == ["all_required_evidence_resolved"]
    assert not result.financial_fact_verified and plan == before
    assert EvidencePlan.model_validate_json(result.final_plan_state.model_dump_json())
    assert SupervisorResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("mode", ["missing", "conflicted", "optional", "exception"])
def test_runtime_branch_failure_blocks_dependents_but_preserves_independent_outputs(
    monkeypatch, mode
):
    data, plan = planned("Phân tích doanh thu và lợi nhuận gộp TEST 2030")
    target = next(s for s in plan.steps if s.tool == "get_evidence_sources")
    if mode == "optional":
        for req in plan.requirements:
            if req.requirement_id in target.output_evidence_ids:
                req.importance = "optional"
        # Optional work must not be an explicit prerequisite for required bundle.
        bundle = plan.steps[-1]
        bundle.prerequisite_step_ids.remove(target.step_id)
        bundle.required_evidence_ids = [
            k for k in bundle.required_evidence_ids if k not in target.output_evidence_ids
        ]
        req = plan.requirements[-1]
        req.dependencies = list(bundle.required_evidence_ids)
    supervisor = RiskAwareSupervisor(SnapshotCatalog(**data))
    original = supervisor._dispatch

    def injected(operation, request):
        response = original(operation, request)
        if operation == target.tool and request.reference.observation.local_id == target_id:
            if mode == "exception":
                raise RuntimeError("injected")
            response.status = "conflicted" if mode == "conflicted" else "unavailable"
            response.matches = []
            response.reasons = ["injected_runtime_" + mode]
        return response

    producer = next(s for s in plan.steps if s.step_id in target.prerequisite_step_ids)
    found = supervisor._financial.find_financial_facts(
        FindFinancialFactsRequest(**producer.arguments)
    )
    target_id = found.matches[0].reference.observation.local_id
    monkeypatch.setattr(supervisor, "_dispatch", injected)
    result = supervisor.execute(plan)
    assert result.initial_validation.execution_eligible
    assert result.status == ("completed" if mode == "optional" else "partial")
    assert any(
        t.final_state == "completed" and t.operation == "get_evidence_sources"
        for t in result.tool_trace
    )
    assert result.step_results[-1].final_state == ("completed" if mode == "optional" else "skipped")
    assert result.evidence_bundle.complete == (mode == "optional")
    assert any(
        r.blocking == (mode != "optional")
        for r in result.risk_signals
        if r.step_ids == [target.step_id]
    )


def test_preflight_invalid_policy_and_budget_never_dispatch_extra_steps(monkeypatch):
    data, plan = planned()
    supervisor = RiskAwareSupervisor(SnapshotCatalog(**data))
    before = plan.model_dump_json()
    result = supervisor.execute(plan, max_steps=2)
    assert result.executed_steps == 2 and result.skipped_steps == len(plan.steps) - 2
    assert "execution_limit_reached" in result.triggered_stop_conditions
    assert result.status == "partial" and not result.evidence_bundle.complete
    assert plan.model_dump_json() == before
    plan.query.cross_document_comparison = True
    monkeypatch.setattr(supervisor, "_dispatch", lambda *args: pytest.fail("policy bypass"))
    blocked = supervisor.execute(plan)
    assert blocked.status == "blocked" and blocked.executed_steps == 0
    assert "compatibility_gate_blocked" in blocked.triggered_stop_conditions
    invalid = plan.model_dump()
    invalid["steps"][0]["prerequisite_step_ids"] = ["unknown"]
    assert supervisor.execute(invalid).status == "failed"


def test_runtime_rejects_false_found_and_bound_selector_mismatch(monkeypatch):
    data, plan = planned("Doanh thu TEST 2030?")
    supervisor = RiskAwareSupervisor(SnapshotCatalog(**data))
    original = supervisor._dispatch

    def injected(operation, request):
        response = original(operation, request)
        if operation == "find_financial_facts":
            response.matches[0].record.context.period = "1999"
        return response

    monkeypatch.setattr(supervisor, "_dispatch", injected)
    result = supervisor.execute(plan)
    assert result.status == "partial"  # Snapshot resolved, financial evidence unavailable.
    assert not result.evidence_bundle.facts and not result.evidence_bundle.complete
    assert any("selector_mismatch" in reason for t in result.step_results for reason in t.reasons)
    assert all(t.operation != "get_evidence_sources" for t in result.tool_trace)


def test_evidence_edges_schedule_producers_first_and_optional_absence_is_not_global():
    data, plan = planned("Phân tích doanh thu và lợi nhuận gộp TEST 2030")
    bundle = plan.steps.pop()
    bundle.prerequisite_step_ids = []  # Evidence dependency edges still enforce scheduling.
    plan.steps.insert(1, bundle)
    plan.requirements.append(
        EvidenceRequirement(
            requirement_id="optional_absent",
            evidence_type="text",
            importance="optional",
            resolution="missing",
            reasons=["no_optional_record"],
        )
    )
    result = RiskAwareSupervisor(SnapshotCatalog(**data)).execute(plan)
    assert result.status == "completed"
    assert result.execution_order[-1] == bundle.step_id
    assert result.evidence_bundle.complete
    assert any(r.requirement_id == "optional_absent" for r in result.missing_requirements)
