"""Small synthetic controls; no claim of research/financial accuracy."""

import json
from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.agents.evidence_coordination import (
    SelectionDemand,
    expansion_tasks,
    join_observations,
    observation,
    select_observations,
)
from vietnamese_financial_multi_agent.agents.integration_workspace import IntegrationWorkspace
from vietnamese_financial_multi_agent.agents.lite_orchestrator import inventory
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)

from .test_financial_qa import gateway_for
from .test_v2_integration import setup_engine


def test_dependent_demand_uses_parent_source_period_and_joins_new_evidence():
    catalog, context, engine, _ = setup_engine()
    for fact in catalog.facts:
        fact.context.reporting_scope = "separate"  # Explicit synthetic fixture context.
    engine.adaptive_coordinator = True
    context.mode = "gemini"
    plan = engine.supervisor.plan.return_value[0]
    parent, child = plan.tasks
    second = child.sources[0]
    child.sources = []
    child.depends_on = [parent.task_id]
    child.resolve_inputs = True
    seen = []

    class TaskGateway:
        def generate(self, request):
            if request.request_id.startswith("m5-evidence-demand"):
                body = dict(
                    retrieve=[dict(source=second, period_from_task=parent.task_id)], selection=None
                )
            else:
                body = dict(claims=[], analyses=[], missing_information=[])
            return gateway_for(body, seen).generate(request)

    engine.gateway = TaskGateway()
    output = engine.run(
        question="Lấy kỳ của kết quả đầu rồi truy xuất chỉ tiêu thứ hai cùng kỳ", context=context
    )
    assert not output.errors, output.errors
    trace = output.integration_context
    result = trace["task_results"][child.task_id]
    parent_result = trace["task_results"][parent.task_id]
    lineage = result["coordination"]["retrieval_lineage"][0]
    assert lineage["from_result"]["digest"] == parent_result["digest"]
    assert lineage["value"] == parent_result["selected_observations"][0]["context"]["period"]
    join = result["coordination"]["joins"][0]
    assert join["status"] == "matched" and join["pairs"]
    assert join["left"][0]["item"] != join["right"][0]["item"]
    assert len(output.supervisor_result.evidence_bundle.facts) == 2
    prompt = json.loads(seen[0].messages[0].content)
    assert prompt["dependency_results"][parent.task_id]["digest"] == parent_result["digest"]
    assert len(prompt["dependency_results"][parent.task_id]["selected_observations"]) == 1
    assert engine.workspace.dependency_ids(
        child.model_copy(update={"depends_on": [child.task_id]})
    ) == [child.task_id, parent.task_id]
    assert result["selected_observations"][0]["selectors"]
    assert sum(
        r.request_id.startswith("m5-evidence-demand") for r in seen
    ) == 1 and output.usage.calls == len(seen)
    assert catalog.facts[0].financial_fact_verified is False


def test_selection_preserves_domain_sign_ties_and_blocks_incomplete_conflicts():
    catalog, context, _, _ = setup_engine()
    tools = FinancialRetrievalTools(catalog)
    fact = catalog.facts[0]
    match = tools.get_financial_fact(
        GetFinancialFactRequest(
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            local_observation_id=fact.local_observation_id,
        )
    ).matches[0]
    first = observation(match)
    first.update(header="Năm 2030", value="-8", raw_value="(8)")
    first["context"]["reporting_scope"] = "separate"
    second = deepcopy(first)
    second.update(evidence_id="other", value="-3", raw_value="(3)")
    second["context"]["period"] = "2029"
    other_fact = fact.model_copy(deep=True)
    other_fact.local_observation_id = "other"
    other_fact.context.period = "2029"
    second["reference"]["observation"] = other_fact.observation_identity().model_dump(mode="json")
    sources = {
        "S1": dict(kind="fact", item=first["item"], period="2030", records=[fact]),
        "S2": dict(kind="fact", item=first["item"], period="2029", records=[other_fact]),
    }
    demand = SelectionDemand(item=first["item"], periods=["2030", "2029"], comparator="max")
    selected, record = select_observations(demand, [first, second], sources)
    assert selected == [second] and len(record["domain"]) == 2 and record["excluded"]
    unknown_scope = deepcopy([first, second])
    for row in unknown_scope:
        row["context"]["reporting_scope"] = None
    assert select_observations(demand, unknown_scope, sources)[1]["caveats"]
    assert select_observations(
        demand.model_copy(update={"comparator": "max_abs"}), [first, second], sources
    )[0] == [first]
    second["value"] = first["value"]
    assert select_observations(demand, [first, second], sources)[1]["ties"]
    with pytest.raises(ValueError, match="domain_incomplete"):
        select_observations(demand, [first], sources)
    second["value"] = None
    with pytest.raises(ValueError, match="context_unresolved"):
        select_observations(demand, [first, second], sources)
    conflict = deepcopy(first)
    conflict["value"] = "9"
    second["value"] = "-3"
    with pytest.raises(ValueError, match="conflicting_values"):
        select_observations(demand, [first, conflict, second], sources)
    parent = dict(handle="result:T1:v1", revision=1, digest="pin", selected_observations=[first])
    assert join_observations(parent, [first, deepcopy(first)])["status"] == "ambiguous"
    assert join_observations(parent, [second])["unmatched_left"]


def test_expansion_validates_atomically_with_existing_goals_and_budget():
    catalog, context, engine, requirements = setup_engine()
    task = engine.supervisor.plan.return_value[0].tasks[0]
    workspace = IntegrationWorkspace(requirements)
    addition = dict(
        task_id="T3",
        goal_indexes=[0],
        role=task.specialist,
        objective="Truy xuất theo phát hiện mới",
        input_handles=[],
        after_tasks=[task.task_id],
    )
    sources = inventory(catalog, context)
    assert expansion_tasks([addition], task, workspace, sources, ["T3"])[0].depends_on == [
        task.task_id
    ]
    assert not workspace.tasks  # Validation has no partial mutations.
    for invalid in [
        dict(addition, task_id="T7"),
        dict(addition, goal_indexes=[42]),
        dict(addition, after_tasks=["T3"]),
        dict(addition, input_handles=["invented"]),
    ]:
        with pytest.raises(ValueError):
            expansion_tasks([invalid], task, workspace, sources, ["T3"])
    assert not workspace.tasks
