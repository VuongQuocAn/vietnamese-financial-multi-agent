"""Synthetic engineering controls; real BBS evaluation is a separate runner."""

from copy import deepcopy

from vietnamese_financial_multi_agent.agents import (
    AdaptiveSpecialistRouter,
    PlannerContext,
    PlannerOperation,
    PlannerProposal,
    RiskAwareSupervisor,
    RiskSignal,
    RoutingDecision,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

from .test_m4_execution import fixture
from .test_query_planner import planner


def inputs(question="Biên lợi nhuận gộp TEST năm 2030?"):
    data = fixture()
    planned = planner(data).plan(question, PlannerContext(mode="deterministic"))
    assert planned.plan is not None, planned.reasons
    upstream = RiskAwareSupervisor(SnapshotCatalog(**data)).execute(planned.plan)
    return planned, upstream


def test_metric_uses_one_role_without_operand_workload_and_is_read_only(monkeypatch):
    p, s = inputs()
    before = deepcopy((p, s))

    def forbidden(*args, **kwargs):
        raise AssertionError("router_must_not_execute_tools_or_specialists")

    monkeypatch.setattr(RiskAwareSupervisor, "execute", forbidden)
    router = AdaptiveSpecialistRouter()
    decision = router.route(question=p.question, planner_result=p, supervisor_result=s)
    assert decision.status == "routed", decision.model_dump()
    assert decision.selected_roles == ["profitability"]
    assert [(r.kind, r.target_id) for r in decision.requirements] == [("metric", "gross_margin")]
    assert decision.routes[0].assigned_items == []
    assert decision.routes[0].citations
    assert not decision.financial_fact_verified
    assert RoutingDecision.model_validate_json(decision.model_dump_json()) == decision
    s.evidence_bundle.facts.reverse()
    assert router.route(question=p.question, planner_result=p, supervisor_result=s) == decision
    s.evidence_bundle.facts.reverse()
    assert (p, s) == before


def test_metric_gate_preserves_independent_fact_and_partial_status():
    p, s = inputs("Phân tích doanh thu thuần và lợi nhuận gộp TEST năm 2030")
    target = next(
        r for r in s.final_plan_state.requirements if r.canonical_item_id == "b02.net_revenue"
    )
    s.risk_signals.append(
        RiskSignal(
            code="conflicting_evidence", reason="injected", requirement_ids=[target.requirement_id]
        )
    )
    result = AdaptiveSpecialistRouter().route(
        question=p.question, planner_result=p, supervisor_result=s
    )
    assert result.status == "partial"
    assert result.selected_roles == ["profitability"]
    assert result.routes[0].assigned_items == ["b02.gross_profit"]
    assert any(r.reasons == ["conflicting_evidence"] for r in result.requirements)
    s.status = "blocked"
    assert (
        AdaptiveSpecialistRouter()
        .route(question=p.question, planner_result=p, supervisor_result=s)
        .selected_roles
        == []
    )


def test_missing_inputs_mismatched_plan_and_formula_risk_abstain():
    router = AdaptiveSpecialistRouter()
    assert router.route(question="x").status == "incomplete"
    p, s = inputs()
    assert router.route(question=p.question, planner_result=p).status == "incomplete"
    changed = s.model_copy(deep=True)
    changed.plan_id = "another-plan"
    assert router.route(
        question=p.question, planner_result=p, supervisor_result=changed
    ).stop_reasons == ["planner_supervisor_binding_mismatch"]
    s.risk_signals.append(RiskSignal(code="formula_not_approved", reason="injected"))
    result = router.route(question=p.question, planner_result=p, supervisor_result=s)
    assert result.status == "blocked"
    assert result.selected_roles == []
    assert result.requirements[0].reasons == ["formula_not_approved"]
    s.risk_signals.clear()
    s.evidence_bundle.calculations[0].evidence.closure.readiness["formula_policy"][
        "execution_approved"
    ] = False
    result = router.route(question=p.question, planner_result=p, supervisor_result=s)
    assert result.status == "blocked"
    assert result.requirements[0].reasons == ["metric_formula_not_approved"]


def test_missing_metric_lineage_does_not_block_independently_requested_operand(monkeypatch):
    data = fixture()
    instance = planner(data)
    proposal = PlannerProposal(
        intent="multi_step_analysis",
        company_alias="TEST",
        reporting_years=[2030],
        required_indicators=["b02.gross_profit"],
        formula_ids=["gross_margin"],
        operations=[
            PlannerOperation(
                operation_id="profit",
                operation="find_financial_facts",
                canonical_item_id="b02.gross_profit",
            ),
            PlannerOperation(
                operation_id="source", operation="get_evidence_sources", dependencies=["profit"]
            ),
            PlannerOperation(
                operation_id="margin",
                operation="calculate_financial_metric",
                formula_id="gross_margin",
            ),
            PlannerOperation(
                operation_id="lineage",
                operation="get_metric_evidence_lineage",
                dependencies=["margin"],
            ),
            PlannerOperation(
                operation_id="bundle",
                operation="prepare_bundle",
                dependencies=["source", "lineage"],
            ),
        ],
    )
    monkeypatch.setattr(instance, "_deterministic", lambda _: proposal.model_dump(mode="json"))
    p = instance.plan(
        "Lợi nhuận gộp và biên lợi nhuận gộp TEST năm 2030?", PlannerContext(mode="deterministic")
    )
    assert p.plan is not None, p.reasons
    s = RiskAwareSupervisor(SnapshotCatalog(**data)).execute(p.plan)
    lineage = next(r for r in s.final_plan_state.requirements if r.evidence_type == "lineage")
    lineage.resolution, lineage.reasons = "missing", ["injected_lineage_missing"]
    s.status = "partial"
    d = AdaptiveSpecialistRouter().route(question=p.question, planner_result=p, supervisor_result=s)
    assert d.status == "partial"
    assert d.routes[0].assigned_items == ["b02.gross_profit"]
    assert d.routes[0].assigned_formulas == []
    assert next(r for r in d.requirements if r.kind == "fact").status == "covered"
