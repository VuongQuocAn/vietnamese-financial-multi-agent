"""Synthetic orchestration controls; persisted BBS/live evaluation is separate."""

from vietnamese_financial_multi_agent.agents import (
    SpecialistExecution,
    aggregate_candidates,
)


def pipeline():
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import inventory

    from .test_v2_integration import setup_engine

    catalog, context, engine, _ = setup_engine()
    plan = engine.supervisor.plan.return_value[0]
    plan.tasks = plan.tasks[:1]
    metric = next(
        key for key, row in inventory(catalog, context).items() if row["kind"] == "metric"
    )
    plan.tasks[0].sources = [metric]
    plan.requirements = plan.requirements[:1]
    plan.requirements[0].kind = "metric"
    plan.requirements[0].target_id = "gross_margin"
    return engine, context


def test_dedup_origins_conflict_context_and_deterministic_ids():
    instance, context = pipeline()
    output = instance.run(question="Synthetic metric", context=context)
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
