"""Bounded Planner DAG controls; these do not grant financial acceptance."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.agents import AdaptiveSpecialistRouter
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerProposal,
    SpecialistAssignment,
)

from .test_adaptive_router import inputs


def proposal():
    return dict(
        intent="multi_step_analysis",
        reasoning_required=True,
        operations=[
            dict(operation_id=key, operation="find_financial_facts")
            for key in ("op_pat", "op_cfo", "op_bundle")
        ],
        assignments=[
            dict(role="profitability", task="PAT", depends_on=["op_pat"]),
            dict(
                role="cash_flow_and_earnings_quality",
                task="PAT/CFO",
                depends_on=["op_pat", "op_cfo", "op_bundle"],
            ),
        ],
    )


def test_three_tools_and_topological_role_dependencies_preserve_references():
    payload = proposal()
    parsed = PlannerProposal.model_validate(payload)
    assert parsed.assignments[1].depends_on == ["op_pat", "op_cfo", "op_bundle"]
    payload["assignments"].reverse()
    payload["assignments"][0]["depends_on"].append("profitability")
    parsed = PlannerProposal.model_validate(payload)
    assert parsed.ordered_specialist_roles() == ["profitability", "cash_flow_and_earnings_quality"]
    assert PlannerProposal.model_validate_json(parsed.model_dump_json()) == parsed
    # The wire cap follows 32 operations + 3 roles; a self edge is still invalid.
    assignment = deepcopy(payload["assignments"][0])
    assignment["depends_on"] = [f"op_{i}" for i in range(35)]
    assert len(SpecialistAssignment.model_validate(assignment).depends_on) == 35
    assignment["depends_on"].append("op_35")
    with pytest.raises(ValidationError, match="at most 35"):
        SpecialistAssignment.model_validate(assignment)

    payload = proposal()
    payload["operations"] = [
        dict(operation_id=f"op_{i}", operation="find_financial_facts") for i in range(32)
    ]
    payload["assignments"][0]["depends_on"] = []
    payload["assignments"].append(dict(role="liquidity_and_leverage", task="Liquidity"))
    payload["assignments"][1]["depends_on"] = [
        *(op["operation_id"] for op in payload["operations"]),
        "profitability",
        "liquidity_and_leverage",
    ]
    assert PlannerProposal.model_validate(payload).ordered_specialist_roles() == [
        "profitability",
        "liquidity_and_leverage",
        "cash_flow_and_earnings_quality",
    ]


@pytest.mark.parametrize(
    "invalid",
    [
        "unknown",
        "duplicate",
        "self",
        "role_cycle",
        "tool_cycle",
        "tool_to_role",
        "collision",
        "wrong_role",
    ],
)
def test_invalid_graph_is_rejected_before_materialization(invalid):
    payload = proposal()
    first, second = payload["assignments"]
    if invalid == "unknown":
        second["depends_on"].append("missing")
    elif invalid == "duplicate":
        second["depends_on"].append("op_pat")
    elif invalid == "self":
        first["depends_on"].append(first["role"])
    elif invalid == "role_cycle":
        first["depends_on"].append(second["role"])
        second["depends_on"].append(first["role"])
    elif invalid == "tool_cycle":
        payload["operations"][0]["dependencies"] = ["op_cfo"]
        payload["operations"][1]["dependencies"] = ["op_pat"]
    elif invalid == "tool_to_role":
        payload["operations"][0]["dependencies"] = [first["role"]]
    elif invalid == "collision":
        payload["operations"][0]["operation_id"] = first["role"]
    else:
        second["role"] = "unregistered_specialist"
    with pytest.raises(ValidationError):
        PlannerProposal.model_validate(payload)


def test_router_rechecks_mutated_graph_and_preserves_capability_gate():
    planned, supervisor = inputs()
    original = planned.effective_proposal or planned.proposal
    assignment = SpecialistAssignment(
        role="profitability", task="Explain margin", formulas=["gross_margin"]
    )
    original.reasoning_required = True
    original.assignments = [assignment]

    def route():
        return AdaptiveSpecialistRouter().route(
            question=planned.question, planner_result=planned, supervisor_result=supervisor
        )

    assert route().selected_roles == ["profitability"]
    assignment.depends_on = ["missing"]
    assert route().status == "blocked"
    assignment.depends_on = []
    assignment.indicators = ["b03.operating_cash_flow"]
    assert route().stop_reasons == ["assignment_outside_specialist_boundary"]
    assignment.indicators = []
    assignment.depends_on = ["cash_flow_and_earnings_quality"]
    original.assignments.append(
        SpecialistAssignment(role="cash_flow_and_earnings_quality", task="No covered evidence")
    )
    assert route().stop_reasons == ["specialist_dependency_not_eligible"]
