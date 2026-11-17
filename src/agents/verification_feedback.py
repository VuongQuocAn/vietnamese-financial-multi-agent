"""One request-local repair frontier; M6 retains all decision authority."""

from copy import deepcopy
from time import perf_counter

from .lite_orchestrator import inventory


def repair_frontier(context, feedback, histories):
    """Route replay failures to their producing task, then close over consumers."""
    tasks = context.get("tasks", {})
    proofs = {h.outcome.final.candidate_id: h.proof for h in histories}
    covered = {
        rid
        for item in feedback
        if item["decision"] == "ACCEPT"
        for rid in item["supported_requirement_ids"]
    }
    roots, routed = set(), []
    for item in feedback:
        proof = proofs.get(item["candidate_id"])
        for issue in item["issues"]:
            if not issue["repairable"]:
                continue
            missing = set(issue["requirement_ids"]) - covered
            if issue["requirement_ids"] and not missing:
                if issue["check"] == "goal_support":
                    continue
                branch = set(item["task_ids"])
                while True:
                    children = {
                        tid for tid, t in tasks.items() if branch.intersection(t["depends_on"])
                    }
                    if children <= branch:
                        break
                    branch.update(children)
                if all(set(tasks[tid].get("requirement_ids", [])) <= covered for tid in branch):
                    continue
            producers = []
            if proof:
                producers = [
                    c.expected["task_id"]
                    for c in proof.validation.claims[0].checks
                    if c.check_id == issue["check"]
                    and c.status in {"fail", "undetermined"}
                    and isinstance(c.expected, dict)
                    and c.expected.get("task_id") in tasks
                ]
                if not producers and issue["check"] in {"selection", "entity_join"}:
                    key = "selection" if issue["check"] == "selection" else "joins"
                    producers = [
                        tid
                        for tid, result in proof.goal_context.get("task_results", {}).items()
                        if result.get("coordination", {}).get(key)
                    ]
            goal_owners = (
                [
                    tid
                    for tid, task in tasks.items()
                    if missing.intersection(task.get("requirement_ids", []))
                ]
                if issue["check"] == "goal_support"
                else []
            )
            owners = producers or goal_owners or item["task_ids"]
            for tid in owners:
                if tid in tasks:
                    roots.add(tid)
                    routed.append(dict(task_id=tid, candidate_id=item["candidate_id"], **issue))
    affected = set(roots)
    while True:
        descendants = {
            tid for tid, task in tasks.items() if affected.intersection(task["depends_on"])
        }
        if descendants <= affected:
            break
        affected.update(descendants)
    return roots, affected, routed


def _proposal_state(context, ids):
    """Compare semantic work, ignoring newly minted candidate/result identities."""
    return {
        tid: dict(
            candidates=[
                {k: c.get(k) for k in ("content", "reasoning", "supporting_evidence_ids")}
                for c in context.get("task_results", {}).get(tid, {}).get("candidates", [])
            ],
            selected=context.get("task_results", {}).get(tid, {}).get("selected_observations", []),
            proposal=context["tasks"][tid].get("coordination", {}).get("proposal"),
        )
        for tid in ids
    }


def repair_once(engine, output, runtime, histories):
    """Return current output/histories and a bounded, serializable before/after trace."""
    summary = deepcopy(runtime.summary)
    feedback = summary.get("feedback", [])
    trace = dict(
        rounds=0, feedback=feedback, repaired_task_ids=[], stop_reason="no_repairable_feedback"
    )
    workspace = engine.workspace
    if workspace.repair_used:
        trace["stop_reason"] = "repair_limit_reached"
        return output, histories, trace
    roots, affected, routed = repair_frontier(output.integration_context, feedback, histories)
    if not affected:
        return output, histories, trace
    # Reserve both demand/specialist calls per task and the final M6 batch.
    # Deterministic tasks require no provider reservation.
    gateway = engine.gateway
    if gateway is not None and hasattr(gateway, "events"):
        needed = 2 * len(affected) + 1
        if (
            gateway.max_calls - len(gateway.events) < needed
            or gateway.deadline - perf_counter() < 1
            or gateway.failure_category
            or any(e["tokens"] is None for e in gateway.events)
        ):
            trace["stop_reason"] = "repair_budget_unavailable"
            return output, histories, trace
    workspace.repair_used = True
    before = deepcopy(output.integration_context)
    trace.update(
        rounds=1,
        root_task_ids=sorted(roots),
        repaired_task_ids=[t.task_id for t in engine._active_plan.tasks if t.task_id in affected],
        reused_task_ids=sorted(set(workspace.tasks) - affected),
        routed_issues=routed,
        before=before,
        m6_before=summary,
    )
    repaired = output.model_copy(deep=True)
    repaired.specialist_executions = [
        e for e in repaired.specialist_executions if e.execution_id not in affected
    ]
    for tid in affected:
        state = workspace.tasks[tid]
        previous = workspace.task_results.pop(tid, {})
        workspace.tasks[tid] = {
            k: state[k] for k in ("requirement_ids", "depends_on", "objective", "role", "revision")
        }
        workspace.tasks[tid].update(
            status="pending",
            revision=state["revision"] + 1,
            previous_candidate_ids=previous.get("candidate_ids", []),
            repair_feedback=[r for r in routed if r["task_id"] == tid]
            or [dict(action="refresh_dependency", task_ids=sorted(roots))],
        )
    repaired = engine._run_tasks(
        output.question,
        output.context,
        inventory(engine.catalog, output.context.model_copy(update={"period": None})),
        engine._active_plan,
        repaired,
        [],
        repair_ids=affected,
    )
    trace["after"] = deepcopy(repaired.integration_context)
    trace["candidate_lineage"] = {
        c.candidate_id: [
            old.candidate_id
            for old in output.candidates
            if {o.execution_id for o in old.origins}.intersection(o.execution_id for o in c.origins)
        ]
        for c in repaired.candidates
        if any(o.execution_id in affected for o in c.origins)
    }
    trace["tools_after"] = [
        e.model_dump(mode="json") for e in repaired.supervisor_result.tool_trace
    ]
    if _proposal_state(before, affected) == _proposal_state(repaired.integration_context, affected):
        trace["stop_reason"] = "no_proposal_progress"
        trace["reused_candidate_ids"] = [h.outcome.final.candidate_id for h in histories]
        # The attempted execution remains in trace; keep the original verified frontier.
        output.usage = repaired.usage
        engine._last_output = output
        return output, histories, trace

    from ..verification.adapter import to_verification_input
    from ..verification.evidence_obligations import goal_context

    batch = to_verification_input(repaired)
    old = {h.outcome.final.candidate_id: h for h in histories}
    reused, pending = [], []
    for claim in batch.claims:
        history = old.get(claim.candidate_id)
        if (
            history is not None
            and claim == history.proof.batch.claims[0]
            and goal_context(repaired.integration_context, claim) == history.proof.goal_context
        ):
            reused.append(history)
        else:
            pending.append(claim)
    batch.claims = pending
    updated = (
        runtime.verify(batch, integration_context=repaired.integration_context) if pending else []
    )
    current = [*reused, *updated]
    after_summary = (
        deepcopy(runtime.summary)
        if pending
        else dict(findings=[], feedback=[], supported_requirements={})
    )
    ids = {h.outcome.final.candidate_id for h in reused}
    for key in ("findings", "feedback"):
        after_summary[key] = [
            r for r in summary.get(key, []) if r["candidate_id"] in ids
        ] + after_summary.get(key, [])
    after_summary["supported_requirements"] = {
        **{k: v for k, v in summary.get("supported_requirements", {}).items() if k in ids},
        **after_summary.get("supported_requirements", {}),
    }
    after_summary["candidate_count"] = len(current)
    after_summary["decisions"] = {
        state: sum(h.outcome.final.decision == state for h in current)
        for state in ("ACCEPT", "INVESTIGATE", "ABSTAIN")
    }
    runtime.summary = after_summary
    trace.update(
        reused_candidate_ids=sorted(ids),
        reverified_candidate_ids=[c.candidate_id for c in pending],
        superseded_candidate_ids=sorted(set(old) - {h.outcome.final.candidate_id for h in current}),
        m6_after=deepcopy(after_summary),
        stop_reason="repair_limit_reached"
        if sum(len(v) for v in after_summary["supported_requirements"].values())
        > sum(len(v) for v in summary.get("supported_requirements", {}).values())
        else "no_verified_progress",
    )
    previous_goals = {
        rid for ids in summary.get("supported_requirements", {}).values() for rid in ids
    }
    current_goals = {
        rid for ids in after_summary.get("supported_requirements", {}).values() for rid in ids
    }
    if not current_goals > previous_goals:
        # A failed optional repair must not replace the previous partial answer.
        trace["stop_reason"] = "no_verified_progress"
        trace["retained_original_frontier"] = True
        runtime.summary = summary
        output.usage = repaired.usage
        engine._last_output = output
        return output, histories, trace
    engine._last_output = repaired
    return repaired, current, trace
