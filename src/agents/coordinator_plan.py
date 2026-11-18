"""Small planning wire and stable task scheduling for the existing V2 runtime."""

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from .contracts import SpecialistRole
from .integration_workspace import IntegrationRequirement


class GoalProposal(FinancialModel):
    text: str = Field(min_length=1, max_length=2000)


class TaskProposal(FinancialModel):
    goal_indexes: list[int] = Field(
        min_length=1, max_length=16, description="Indexes 0-based của goals mà task phục vụ"
    )
    role: SpecialistRole
    objective: str = Field(min_length=1, max_length=600)
    after: list[int] = Field(
        max_length=6,
        description="Indexes 0-based của tasks phải hoàn tất trước. Task độc lập: []. Task index2 dùng kết quả task0 và task1: [0,1]. Không chứa index của chính nó; không dùng số thứ tự 1-based.",
    )


class PlanProposal(FinancialModel):
    goals: list[GoalProposal] = Field(min_length=1, max_length=16)
    tasks: list[TaskProposal] = Field(min_length=1, max_length=6)


def adapt_plan(payload):
    from .lite_orchestrator import LitePlan, LiteTask

    empty = LitePlan()
    if not isinstance(payload, dict):
        return empty, ["supervisor_invalid_envelope"]
    goals, raw_tasks = payload.get("goals"), payload.get("tasks")
    if (
        not isinstance(goals, list)
        or not 1 <= len(goals) <= 16
        or not isinstance(raw_tasks, list)
        or len(raw_tasks) > 6
    ):
        return empty, ["supervisor_invalid_envelope"]
    requirements, errors = {}, []
    for index, raw in enumerate(goals):
        gid = f"G{index + 1}"
        try:
            goal = GoalProposal.model_validate(raw, strict=True)
        except ValidationError:
            errors.append(f"supervisor_invalid_goal:{gid}:goal_schema_invalid")
            continue
        requirements[index] = IntegrationRequirement(
            requirement_id=gid, text=goal.text, kind="explanation"
        )
    tasks, blocked = [], {}
    for index, raw in enumerate(raw_tasks):
        tid = f"T{index + 1}"
        try:
            task = TaskProposal.model_validate(raw, strict=True)
            assigned = [
                requirements[i] for i in dict.fromkeys(task.goal_indexes) if i in requirements
            ]
            if len(assigned) != len(set(task.goal_indexes)):
                errors.append(f"supervisor_unknown_goal_reference:{tid}")
            if not assigned:
                raise ValueError("goal_reference_unknown")
            if any(i < 0 or i >= len(raw_tasks) for i in task.after):
                raise ValueError("task_reference_unknown")
            tasks.append(
                LiteTask(
                    task_id=tid,
                    specialist=task.role,
                    objective=task.objective,
                    requirement_ids=[r.requirement_id for r in assigned],
                    depends_on=[f"T{i + 1}" for i in dict.fromkeys(task.after)],
                    resolve_inputs=True,
                )
            )
        except (ValidationError, ValueError) as error:
            reason = str(error) if not isinstance(error, ValidationError) else "task_schema_invalid"
            blocked[tid] = reason
            errors.append(f"supervisor_invalid_task:{tid}:{reason}")
    ordered, invalid = schedule_tasks(tasks)
    blocked.update(invalid)
    errors.extend(f"{reason}:{tid}" for tid, reason in invalid.items())
    owned = {rid for t in ordered for rid in t.requirement_ids if t.task_id not in blocked}
    errors.extend(
        f"goal_owner_unresolved:{r.requirement_id}"
        for r in requirements.values()
        if r.requirement_id not in owned
    )
    return LitePlan(
        tasks=tasks, requirements=list(requirements.values()), blocked_tasks=blocked
    ), errors


def schedule_tasks(tasks):
    """Stable Kahn order; cycles, unknown refs and their closures never execute."""
    known = {t.task_id for t in tasks}
    ordered, done, remaining = [], set(), list(tasks)
    while remaining:
        task = next((t for t in remaining if set(t.depends_on) <= done), None)
        if task is None:
            break
        ordered.append(task)
        done.add(task.task_id)
        remaining.remove(task)
    blocked = {
        t.task_id: "task_reference_unknown"
        if set(t.depends_on) - known
        else "task_cycle_or_blocked_dependency"
        for t in remaining
    }
    return ordered, blocked
