"""Small planning wire and stable task scheduling for the existing V2 runtime."""

from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from .contracts import SpecialistRole
from .document_qa_contracts import DocumentRequirement
from .integration_workspace import IntegrationRequirement
from .python_agent import PythonRequirement


class GoalProposal(FinancialModel):
    text: str = Field(min_length=1, max_length=2000)
    mode: Literal["value", "calculation", "analysis", "document"]
    source: str | None = Field(
        default=None, description="S handle của chính kết quả tra cứu, không dùng handle toán hạng"
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
    use_graph: bool = False
    resolve_inputs: bool = Field(
        default=False, description="Bổ sung nguồn chỉ khi cần quyết định từ kết quả dependency"
    )
    document_search: DocumentRequirement | None = None
    query_from_dependencies: bool = False


class PlanProposal(FinancialModel):
    goals: list[GoalProposal] = Field(min_length=1, max_length=16)
    tasks: list[TaskProposal] = Field(min_length=1, max_length=6)


def output_schema(sources):
    schema = PlanProposal.model_json_schema()
    schema["$defs"]["TaskProposal"]["properties"]["input_handles"]["items"] = {
        "enum": list(sources)
    }
    return schema


def adapt_plan(payload, sources):
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
            source = sources.get(goal.source)
            if goal.source is not None and (source is None or goal.mode != "value"):
                raise ValueError("goal_source_invalid")
        except (ValidationError, ValueError) as error:
            reason = "goal_schema_invalid" if isinstance(error, ValidationError) else str(error)
            errors.append(f"supervisor_invalid_goal:{gid}:{reason}")
            continue
        requirements[index] = IntegrationRequirement(
            requirement_id=gid,
            text=goal.text,
            kind=source["kind"]
            if source
            else "document"
            if goal.mode == "document"
            else "explanation",
            target_id=source["item"] if source else None,
            period=source["period"] if source else None,
            answer_goal="analysis" if goal.mode == "analysis" else "value",
            interpretation=goal.mode in {"analysis", "calculation"},
            interpretation_topic="dynamic_calculation" if goal.mode == "calculation" else None,
            reason="goal_context_unresolved" if goal.mode == "calculation" else None,
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
            handles = [h for h in dict.fromkeys(task.input_handles) if h in sources]
            if len(handles) != len(set(task.input_handles)):
                errors.append(f"supervisor_unknown_source_handle:{tid}")
            if (
                task.input_handles
                and not handles
                and not (task.after or task.document_search or task.resolve_inputs)
            ):
                raise ValueError("source_handle_unknown")
            if any(i < 0 or i >= len(raw_tasks) for i in task.after):
                raise ValueError("task_reference_unknown")
            if task.query_from_dependencies and not (task.after and task.document_search):
                raise ValueError("document_query_dependency_missing")
            if task.document_search and sum(r.kind == "document" for r in assigned) > 1:
                raise ValueError("one_document_goal_per_search")
            tasks.append(
                LiteTask(
                    task_id=tid,
                    specialist=task.role,
                    objective=task.objective,
                    requirement_ids=[r.requirement_id for r in assigned],
                    sources=handles,
                    depends_on=[f"T{i + 1}" for i in dict.fromkeys(task.after)],
                    use_graph=task.use_graph,
                    resolve_inputs=task.resolve_inputs,
                    document_search=task.document_search,
                    query_from_dependencies=task.query_from_dependencies,
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
