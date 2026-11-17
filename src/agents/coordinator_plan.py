"""Small planning wire and stable task scheduling for the existing V2 runtime."""

import re
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..outputs.qa_composer import _targets
from ..tools.goal_targets import target_groups
from ..tools.question_understanding import normalize
from .contracts import SpecialistRole
from .integration_workspace import IntegrationRequirement
from .python_agent import PythonRequirement


class GoalProposal(FinancialModel):
    text: str = Field(min_length=1, max_length=2000)
    mode: Literal["value", "analysis"] = Field(
        description="value: số liệu hoặc phép tính; analysis: nhận xét có nghĩa tài chính"
    )


class TaskProposal(FinancialModel):
    goal_indexes: list[int] = Field(
        min_length=1, max_length=16, description="Indexes 0-based của goals mà task phục vụ"
    )
    role: SpecialistRole
    objective: str = Field(min_length=1, max_length=600)
    input_handles: list[str] = Field(
        max_length=16,
        description="S handles đúng label và kỳ trong inventory; [] để dùng nguồn từ dependencies",
    )
    after: list[int] = Field(
        max_length=6,
        description="Indexes 0-based của tasks phải hoàn tất trước. Task độc lập: []. Task index2 dùng kết quả task0 và task1: [0,1]. Không chứa index của chính nó; không dùng số thứ tự 1-based.",
    )
    python_requirement: PythonRequirement | None = Field(
        default=None,
        description="Chỉ primitive Calculator chưa hỗ trợ; phép tính thông thường dùng null",
    )


def proposal_schema():
    """All fields required; source identities and internal contracts stay in Python."""
    return {
        "goals": GoalProposal.model_json_schema(),
        "tasks": TaskProposal.model_json_schema(),
        "bounds": {"goals": 16, "tasks": 6},
    }


class PlanProposal(FinancialModel):
    goals: list[GoalProposal] = Field(min_length=1, max_length=16)
    tasks: list[TaskProposal] = Field(min_length=1, max_length=6)


def output_schema(sources):
    schema = PlanProposal.model_json_schema()
    schema["$defs"]["TaskProposal"]["properties"]["input_handles"]["items"] = {
        "enum": list(sources)
    }
    return schema


def preserve_question_plan(question, sources):
    """One owned goal for an unparseable/drifting plan; never invent an omitted subquestion."""
    targets = _targets(normalize(question))
    relevant = [s for s in sources.values() if any(s["item"] == target for _, target in targets)]
    role = next((r for s in relevant for r in s["roles"]), "profitability")
    mode = (
        "analysis"
        if re.search(r"\b(dien bien|nhan xet|so sanh|giai thich)\b", normalize(question))
        else "value"
    )
    return adapt_plan(
        dict(
            goals=[dict(text=question, mode=mode)],
            tasks=[
                dict(goal_indexes=[0], role=role, objective=question, input_handles=[], after=[])
            ],
        ),
        sources,
    )[0]


def grounding_issue(question, plan):
    """Reject clear added targets/years; this is not a semantic verifier."""
    text = normalize(question)
    targets = set(_targets(text))
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", question))
    comparative = bool(
        re.search(r"\b(so voi|so sanh|bien dong|tang truong|ky truoc|nam truoc|dau nam)\b", text)
    )
    for requirement in plan.requirements:
        if targets and set(_targets(normalize(requirement.text))) - targets:
            return "unrequested_target"
        if (
            not comparative
            and years
            and set(re.findall(r"\b(?:19|20|21)\d{2}\b", requirement.text)) - years
        ):
            return "unrequested_period"
    # A source lookup without a canonical numeric target is not an invitation to compute.
    if not targets and not re.search(
        r"\b(tinh|chenh lech|ty le|ty suat|he so|trung binh|so sanh|lon nhat|nho nhat)\b",
        re.sub(r"\buoc tinh\b", "", text),
    ):
        if (
            len(plan.requirements) != 1
            or normalize(plan.requirements[0].text) != text
            or len(plan.tasks) != 1
            or normalize(plan.tasks[0].objective) != text
        ):
            return "lookup_goal_changed"
    return None


def adapt_plan(payload, sources):
    from .lite_orchestrator import LitePlan, LiteTask

    empty = LitePlan()
    if not isinstance(payload, dict) or set(payload) != {"goals", "tasks"}:
        return empty, ["supervisor_invalid_envelope"]
    goals, raw_tasks = payload["goals"], payload["tasks"]
    if (
        not isinstance(goals, list)
        or not 1 <= len(goals) <= 16
        or not isinstance(raw_tasks, list)
        or len(raw_tasks) > 6
    ):
        return empty, ["supervisor_invalid_envelope"]
    try:
        goals = [GoalProposal.model_validate(g, strict=True) for g in goals]
    except ValidationError:
        return empty, ["supervisor_invalid_goals"]
    requirements = []
    for index, goal in enumerate(goals):
        # A uniquely named catalog concept may be bound by the existing resolver.
        # Period/unit are not inferred from objective, source handle or filename.
        groups = target_groups(normalize(goal.text)) if goal.mode == "value" else []
        targets = [next(iter(group)) for group in groups if len(group) == 1]
        target = targets[0] if len(groups) == len(targets) == 1 else None
        selection_goal = any(
            term in normalize(goal.text)
            for term in (
                "lon nhat",
                "nho nhat",
                "cao nhat",
                "thap nhat",
                "chon nam",
                "nam nao",
                "ky nao",
            )
        )
        if selection_goal:
            # A scalar's truth cannot certify an extremum over a comparison domain.
            # Preserve a gap until M6 has selection obligations; do not change M6 here.
            target = None
        years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", goal.text))
        periods = {
            s["period"]
            for s in sources.values()
            if target
            and s["item"] == target[1]
            and s["period"]
            and (not years or s["period"][:4] in years)
        }
        requirements.append(
            IntegrationRequirement(
                requirement_id=f"G{index + 1}",
                text=goal.text,
                kind=target[0] if target else "explanation",
                target_id=target[1] if target else None,
                period=next(iter(periods)) if len(periods) == 1 else None,
                answer_goal=goal.mode,
                interpretation=goal.mode == "analysis" or target is None,
                interpretation_topic="dynamic_calculation"
                if goal.mode == "value" and target is None and not selection_goal
                else None,
                required_indicators=[item for kind, item in targets if kind == "fact"]
                if target is None
                else [],
                reason="selection_requires_obligations"
                if selection_goal
                else None
                if target
                else "goal_context_unresolved",
            )
        )
    tasks, blocked, errors = [], {}, []
    for index, raw in enumerate(raw_tasks):
        tid = f"T{index + 1}"
        try:
            task = TaskProposal.model_validate(raw, strict=True)
            if any(i < 0 or i >= len(goals) for i in task.goal_indexes):
                raise ValueError("goal_reference_unknown")
            if set(task.input_handles) - sources.keys():
                raise ValueError("source_handle_unknown")
            if any(i < 0 or i >= len(raw_tasks) for i in task.after):
                raise ValueError("task_reference_unknown")
            # Exact goal/item/period resolution is stronger than a model's numeric S ordinal.
            assigned = [requirements[i] for i in task.goal_indexes]
            if len(assigned) == 1 and assigned[0].target_id and assigned[0].period:
                goal = assigned[0]
                correct = [
                    h
                    for h, s in sources.items()
                    if s["item"] == goal.target_id and s["period"] == goal.period
                ]
                if (
                    len(correct) == 1
                    and task.input_handles
                    and all(sources[h]["kind"] == "fact" for h in task.input_handles)
                ):
                    task.input_handles = correct
            tasks.append(
                LiteTask(
                    task_id=tid,
                    specialist=task.role,
                    objective=task.objective,
                    requirement_ids=[f"G{i + 1}" for i in dict.fromkeys(task.goal_indexes)],
                    sources=list(dict.fromkeys(task.input_handles)),
                    depends_on=[f"T{i + 1}" for i in dict.fromkeys(task.after)],
                    use_graph=bool(task.after) or len(task.input_handles) > 1,
                    python_requirement=task.python_requirement,
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
        for r in requirements
        if r.requirement_id not in owned
    )
    return LitePlan(tasks=tasks, requirements=requirements, blocked_tasks=blocked), errors


def schedule_tasks(tasks):
    """Stable Kahn order; cycles, unknown refs and their closures never execute."""
    by_id = {t.task_id: t for t in tasks}
    ordered, done, remaining = [], set(), list(tasks)
    while remaining:
        ready = [t for t in remaining if set(t.depends_on) <= done]
        if not ready:
            break
        task = min(
            ready,
            key=lambda t: (
                min(
                    (int(r[1:]) for r in t.requirement_ids if re.fullmatch(r"G\d+", r)), default=17
                ),
                tasks.index(t),
            ),
        )
        ordered.append(task)
        done.add(task.task_id)
        remaining.remove(task)
    blocked = {
        t.task_id: "task_reference_unknown"
        if set(t.depends_on) - by_id.keys()
        else "task_cycle_or_blocked_dependency"
        for t in remaining
    }
    return ordered, blocked
