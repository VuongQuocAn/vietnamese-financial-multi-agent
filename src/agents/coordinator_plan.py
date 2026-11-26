"""Small planning wire and stable task scheduling for the existing V2 runtime."""

from datetime import date
from typing import Annotated, Literal, get_args

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..core.llm_schema_validation import schema_issues
from ..tools.financial_calculator import DynamicOperation
from .integration_workspace import GoalCalculationIntent, IntegrationRequirement


class GoalProposal(FinancialModel):
    kind: Literal["fact", "metric", "document", "explanation"] = Field(
        description="Loại đầu ra được hỏi, không phải loại tên chỉ tiêu: fact đọc giá trị đã báo cáo (kể cả tỷ lệ có sẵn); metric cần tính hoặc so sánh; document trích nguồn; explanation giải thích/tổng hợp grounded. Một financial indicator không tự là metric."
    )
    text: str = Field(
        min_length=1,
        max_length=2000,
        description="Đầu ra cần trả lời có bằng chứng; doanh nghiệp/kỳ/chỉ tiêu là ràng buộc của đầu ra, không phải ba goals metadata riêng.",
    )
    # Reuse the existing FusionRequirement vocabulary without adding another EO graph.
    evidence_needs: list[Annotated[str, Field(min_length=1, max_length=400)]] = Field(
        default_factory=list,
        max_length=8,
        description="Bằng chứng cần cho đầu ra: đối tượng, nguồn/section, kỳ/cột, đơn vị và quan hệ cần giữ. Không chứa đáp án hoặc locator chưa biết.",
    )
    verification_requirements: list[Annotated[str, Field(min_length=1, max_length=400)]] = Field(
        default_factory=list,
        max_length=8,
        description="Điều kiện đủ EO: dữ liệu nguồn nào phải có, ràng buộc/miền so sánh/phép tính nào phải đáp ứng. Found/top5 không là completion; M6 quyết định cuối.",
    )
    reasoning_operations: list[str] = Field(
        default_factory=list,
        max_length=12,
        description="Chỉ khai operators mà yêu cầu thật sự đòi, theo thứ tự; không lập tool DAG trước khi đọc nguồn. Comparison dùng kind=metric và equal/greater/less tương ứng. Bỏ trống khi chỉ đọc giá trị đã báo cáo; không thêm phép tính để xác nhận fact.",
    )


class QuestionUnderstanding(FinancialModel):
    """Preliminary goals before source selection or DAG compilation."""

    goals: list[GoalProposal] = Field(min_length=1, max_length=4)


class TaskProposal(FinancialModel):
    goal_indexes: list[int] = Field(
        default_factory=list,
        max_length=16,
        description="Indexes 0-based của goals mà task phục vụ; mặc định task nhận toàn bộ evidence_needs của các goals này. Bỏ qua hoặc [] giữ phạm vi toàn bộ goals để tương thích.",
    )
    role: Literal["retrieval", "reasoning"] = Field(
        description="retrieval chỉ tìm/mở và bàn giao nguồn; reasoning dùng evidence tạo candidate. Khi cần retrieval, phải giao reasoning consumer nhận kết quả qua after."
    )
    need_refs: list[str] = Field(
        default_factory=list,
        max_length=128,
        description="Tùy chọn, thường bỏ qua: Python lấy toàn bộ needs thuộc goal_indexes. Chỉ dùng để giao một phần needs: G{goal_index+1}.need[need_index], need_index từ 0, ví dụ G1.need[0]. Không dùng tên báo cáo/nguồn/chỉ tiêu làm ID; refs phải thuộc goals được giao. [] cũng lấy toàn bộ needs.",
    )
    objective: str = Field(
        min_length=1,
        max_length=600,
        description="Phân công coarse theo EO: năng lực acquisition hoặc reasoning, đầu ra và context cần dùng; không liệt kê tool calls/trang hay toàn bộ bước chưa biết.",
    )
    after: list[int] = Field(
        default_factory=list,
        max_length=6,
        description="Indexes 0-based của dependencies, [] nếu độc lập. Không tự tham chiếu.",
    )


class PlanProposal(FinancialModel):
    goals: list[GoalProposal] = Field(default_factory=list, max_length=16)
    tasks: list[TaskProposal] = Field(
        min_length=1,
        max_length=6,
        description="Phân công theo goal_indexes, thường bỏ need_refs. Retrieval chỉ bàn giao nguồn; mỗi đầu ra cần reasoning tạo candidate. after chỉ nối task thực sự dùng kết quả task trước, không thêm nghĩa vụ đối chiếu ngoài câu hỏi.",
    )


_NEED_HANDLES = [f"N{i}" for i in range(8)]
_STEP_HANDLES = [f"R{i}" for i in range(1, 13)]
_COMPARISONS = {"equal", "greater", "less"}
_AGGREGATES = {"sum", "mean"}
_OPERAND_ROLES = {
    "percentage_of": ("numerator", "denominator"),
    "divide": ("numerator", "denominator"),
    "ratio": ("numerator", "denominator"),
    "percentage_change": ("target", "baseline"),
    "relative_difference": ("target", "baseline"),
    "subtract": ("minuend", "subtrahend"),
    "greater": ("left", "right"),
    "less": ("left", "right"),
    "equal": ("left", "right"),
    "add": ("term", "term"),
    "multiply": ("factor", "factor"),
}
_ROLE_OBJECTIVES = {
    "retrieval": "Thu thập nguồn cho EO được giao.",
    "reasoning": "Tạo candidate từ Goal, EO và kết quả nguồn được giao.",
}


def compact_plan_schema(*, version: Literal[1, 2, 3, 4, 5] = 5):
    """Build the current C schema or reproduce a schema bound to an archived request."""

    def closed(properties, *required):
        return dict(
            type="object",
            properties=properties,
            required=list(required),
            additionalProperties=False,
        )

    def array(items, minimum, maximum):
        return dict(type="array", items=items, minItems=minimum, maxItems=maximum)

    def string(maximum):
        return dict(type="string", minLength=1, maxLength=maximum)

    def strings(values):
        return dict(type="string", enum=list(values))

    def ref(name):
        return {"$ref": f"#/$defs/{name}"}

    scope = dict(
        company=string(80),
        filing=string(160),
        statement=string(24 if version == 1 else 160),
        reporting_scope=strings(("separate", "consolidated")),
        unit=string(24),
        item=string(140),
    )
    operations = DynamicOperation.model_fields
    schema = dict(
        closed(
            dict(goals=array(ref("Goal"), 1, 16), tasks=array(ref("Task"), 1, 6)),
            "goals",
            "tasks",
        ),
        **{
            "$defs": dict(
                Goal=closed(
                    dict(
                        kind=strings(get_args(GoalProposal.model_fields["kind"].annotation)),
                        scope=ref("Scope"),
                        output=string(24),
                        needs=array(ref("Need"), 1, 8),
                        steps=array(ref("Step"), 1, 12),
                        detail=string(360),
                        checks=array(string(400), 1, 8),
                    ),
                    "kind",
                    "needs",
                ),
                Need=closed(
                    dict(**scope, period=string(48), column=string(72), detail=string(180))
                ),
                Step=closed(
                    dict(
                        op=strings(get_args(operations["operator"].annotation)),
                        inputs=array(strings(_NEED_HANDLES + _STEP_HANDLES[:-1]), 2, 16),
                        relation=strings(get_args(operations["period_relation"].annotation)),
                    ),
                    "op",
                    "inputs",
                    "relation",
                ),
                Task=closed(
                    dict(
                        role=strings(_ROLE_OBJECTIVES),
                        goal_indexes=array({"enum": list(range(16))}, 0, 16),
                        need_refs=array(string(32), 0, 128),
                        after=array({"enum": list(range(6))}, 0, 6),
                        objective=string(300),
                    ),
                    "role",
                ),
                Scope=closed(scope),
            )
        },
    )
    definitions = schema["$defs"]
    task = definitions["Task"]
    if version >= 2:
        definitions["Step"]["properties"]["inputs"]["description"] = (
            "Toán hạng có thứ tự: N0 là EO đầu, R1 là kết quả bước đầu đã khai."
        )
    if version == 2:
        task["properties"]["need_refs"]["description"] = (
            "Bỏ nếu nhận toàn bộ EO của goals được giao. Chỉ thu hẹp bằng G1.need[0] và các refs cùng dạng."
        )
    elif version >= 3:
        goal_indexes = task["properties"]["goal_indexes"]
        goal_indexes["minItems"] = 1
        task["required"].append("goal_indexes")
        pair = closed(
            dict(
                goal_index=goal_indexes["items"],
                need_index={"enum": list(range(len(_NEED_HANDLES)))},
            ),
            "goal_index",
            "need_index",
        )
        task["properties"]["need_refs"] = array(pair, 0, 128)
    if version == 4:
        schema["required"].remove("tasks")
    elif version == 5:
        goals = schema["properties"]["goals"]
        return {
            "type": "object",
            "oneOf": [
                closed(
                    dict(workflow={"const": "single_batch"}, goals=goals | {"maxItems": 1}),
                    "workflow",
                    "goals",
                ),
                closed(
                    dict(workflow={"const": "coordinated"}, **schema["properties"]),
                    "workflow",
                    "goals",
                    "tasks",
                ),
            ],
            "$defs": definitions,
        }
    return schema


def simple_plan_schema():
    """Reproduce the original Simple wire for schema-bound replay."""
    current = compact_plan_schema(version=5)
    branch = current["oneOf"][0]
    branch["properties"].pop("workflow")
    branch["required"].remove("workflow")
    current["$defs"].pop("Task")
    return branch | {"$defs": current["$defs"]}


def semantic_plan_schema():
    """Goal and source contracts only. The compiler owns execution assignments."""
    schema = simple_plan_schema()
    schema["properties"]["goals"]["maxItems"] = 16
    defs = schema["$defs"]
    goal = defs["Goal"]
    goal["required"].append("detail")
    goal["properties"]["uses_goals"] = dict(
        type="array",
        items={"enum": list(range(16))},
        maxItems=15,
        description="Chỉ số 0-based của các Goal trước có kết luận cần dùng cho Goal này.",
    )
    # Only emit selectors supported by P1. Qualitative conditions belong in
    # item, with their interpretation and joins in Goal.detail/checks.
    need = defs["Need"]["properties"]
    for field in ("column", "filing", "detail"):
        need.pop(field)
    for field in ("code", "table", "group"):
        need[field] = dict(type="string", minLength=1, maxLength=140)
    need["scope"] = need.pop("reporting_scope")
    defs["Scope"]["properties"] = {
        k: need[k] for k in ("company", "scope", "statement", "period", "unit")
    }
    return schema


def _semantic_tasks(goals):
    """Group acquisition by declared source and prerequisite conclusions."""
    groups = {}
    for i, goal in enumerate(goals):
        parents = tuple(sorted(set(goal.get("uses_goals", ()))))
        if any(parent >= i for parent in parents):
            raise ValueError(f"G{i + 1}:prior_goal_required")
        groups.setdefault(parents, []).append(i)

    tasks, owners = [], {}
    for parents, indexes in groups.items():
        upstream = list(dict.fromkeys(owners[i] for i in parents))
        sources = {}
        for i in indexes:
            goal = goals[i]
            if not goal["detail"].strip():
                raise ValueError(f"G{i + 1}:goal_detail_required")
            for j, need in enumerate(goal["needs"]):
                row = goal.get("scope", {}) | need
                for field in ("company", "period", "item"):
                    if not row.get(field, "").strip():
                        raise ValueError(f"G{i + 1}.need[{j}]:{field}_required")
                if "code" in row and not row.get("statement"):
                    raise ValueError(f"G{i + 1}.need[{j}]:statement_required_for_code")
                if row.get("statement") == "B01":
                    try:
                        if date.fromisoformat(row["period"]).isoformat() != row["period"]:
                            raise ValueError
                    except ValueError:
                        raise ValueError(f"G{i + 1}.need[{j}]:as_of_date_required") from None
                key = tuple(row.get(k) for k in ("company", "scope", "statement", "table"))
                sources.setdefault(key, []).append((i, j))
        producers = {i: [] for i in indexes}
        for refs in sources.values():
            assigned = list(dict.fromkeys(i for i, _ in refs))
            for i in assigned:
                producers[i].append(len(tasks))
            tasks.append(
                dict(
                    role="retrieval",
                    goal_indexes=assigned,
                    need_refs=[dict(goal_index=i, need_index=j) for i, j in refs],
                    after=upstream,
                )
            )
        consumers = {}
        for i, dependencies in producers.items():
            consumers.setdefault(tuple(dependencies), []).append(i)
        for dependencies, assigned in consumers.items():
            owners.update(dict.fromkeys(assigned, len(tasks)))
            objective = (
                goals[assigned[0]]["detail"]
                if len(assigned) == 1
                else _ROLE_OBJECTIVES["reasoning"]
            )
            tasks.append(
                dict(
                    role="reasoning",
                    goal_indexes=assigned,
                    objective=objective,
                    after=[*upstream, *dependencies],
                )
            )
    if len(tasks) > 6:
        raise ValueError("task_cap_exceeded")
    return tasks


def simple_hybrid_plan_schema():
    """Bind one Goal with inline source operands or an existing multi-step graph."""
    schema = simple_plan_schema()
    definitions = schema["$defs"]
    goal = definitions["Goal"]
    fields = goal["properties"]
    plain = {k: v for k, v in fields.items() if k != "steps"}
    plain["kind"] = fields["kind"] | {
        "enum": [kind for kind in fields["kind"]["enum"] if kind != "metric"]
    }
    graph = fields | {
        "kind": {"const": "metric"},
        "steps": fields["steps"] | {"minItems": 2},
    }
    inline = {k: v for k, v in fields.items() if k not in {"needs", "steps", "kind"}}
    step = definitions["Step"]["properties"]
    roles = sorted({r for roles in _OPERAND_ROLES.values() for r in roles} | {"member"})
    definitions.update(
        Goal={
            "oneOf": [
                {"$ref": "#/$defs/PlainGoal"},
                {"$ref": "#/$defs/SemanticGoal"},
                {"$ref": "#/$defs/GraphGoal"},
            ]
        },
        PlainGoal=goal | {"properties": plain},
        GraphGoal=goal | {"properties": graph, "required": ["kind", "needs", "output", "steps"]},
        SemanticGoal=goal
        | {
            "properties": {
                "kind": {"const": "metric"},
                **inline,
                "calculation": {"$ref": "#/$defs/Calculation"},
            },
            "required": ["kind", "output", "calculation"],
        },
        Calculation=dict(
            type="object",
            properties=dict(
                operator=step["op"],
                relation=step["relation"],
                operands=dict(
                    type="array",
                    items={"$ref": "#/$defs/SourceOperand"},
                    minItems=2,
                    maxItems=len(_NEED_HANDLES),
                ),
            ),
            required=["operator", "relation", "operands"],
            additionalProperties=False,
        ),
        SourceOperand=dict(
            type="object",
            properties=dict(role={"enum": roles}, source={"$ref": "#/$defs/Need"}),
            required=["role", "source"],
            additionalProperties=False,
        ),
    )
    return {"$id": "urn:dacntt:coordinator:simple-hybrid:v1", **schema}


def _compact_steps(goal, rows):
    steps = goal.get("steps", ())
    if (goal["kind"] == "metric") != bool(steps):
        raise ValueError("metric_steps_required_or_inapplicable")
    if not steps:
        return [], [], []
    if not goal.get("output", "").strip():
        raise ValueError("output_dimension_required")
    operators = [step["op"] for step in steps]
    if (operators[-1] in _COMPARISONS) != (goal["output"] == "boolean"):
        raise ValueError("output_dimension_conflict")

    references = {_NEED_HANDLES[i]: {i} for i in range(len(rows))}
    lineage, rendered = {}, []
    for handle, step in zip(_STEP_HANDLES, steps, strict=False):
        inputs = step["inputs"]
        if step["op"] not in _AGGREGATES and len(inputs) != 2:
            raise ValueError("operator_arity")
        if any(ref not in references for ref in inputs):
            raise ValueError("operand_reference")
        indexes = set().union(*(references[ref] for ref in inputs))
        lineage[handle] = {handle}.union(*(lineage.get(ref, ()) for ref in inputs))
        references[handle] = indexes
        periods = {rows[i].get("period") for i in indexes}
        known = periods - {None}
        if (
            len(known) > 1
            and step["relation"] == "same"
            or (len(known) == 1 and None not in periods and step["relation"] == "across_periods")
        ):
            raise ValueError("period_relation_conflict")
        rendered.append(f"{handle}={step['op']}({','.join(inputs)}) [{step['relation']}]")
    if len(lineage[handle]) != len(steps):
        raise ValueError("unused_step")
    periods = (
        list(dict.fromkeys(row["period"] for row in rows))
        if references[handle] == set(range(len(rows))) and all(row.get("period") for row in rows)
        else []
    )
    return operators, rendered, periods


def _project_compact_plan(payload, *, indexed_ownership):
    goals, metadata = [], []
    for goal in payload["goals"]:
        if calculation := goal.get("calculation"):
            operator, operands = calculation["operator"], calculation["operands"]
            roles = (
                ("member",) * len(operands) if operator in _AGGREGATES else _OPERAND_ROLES[operator]
            )
            if tuple(operand["role"] for operand in operands) != roles:
                raise ValueError("operand_roles_or_arity")
            goal = goal | dict(
                needs=[operand["source"] for operand in operands],
                steps=[
                    dict(
                        op=operator,
                        inputs=_NEED_HANDLES[: len(operands)],
                        relation=calculation["relation"],
                    )
                ],
            )
        rows = [goal.get("scope", {}) | need for need in goal["needs"]]
        if any(not (row.get("item", "").strip() or row.get("detail", "").strip()) for row in rows):
            raise ValueError("evidence_obligation_empty")
        if goal["kind"] in {"explanation", "document"} and not goal.get("detail", "").strip():
            raise ValueError("goal_detail_required")
        operators, intent, periods = _compact_steps(goal, rows)
        text = goal.get("detail", goal["kind"])
        if goal.get("output"):
            text += f" ({goal['output']})"
        if intent:
            text += " | " + "; ".join(intent)
        goals.append(
            dict(
                kind=goal["kind"],
                text=text,
                evidence_needs=[
                    f"{_NEED_HANDLES[i]}: "
                    + ", ".join(f"{key}={value}" for key, value in row.items())
                    for i, row in enumerate(rows)
                ],
                verification_requirements=goal.get("checks", []),
                reasoning_operations=operators,
            )
        )
        fields = dict(requested_unit=goal.get("output"), reasoning_periods=periods)
        if steps := goal.get("steps"):
            fields["calculation_intent"] = GoalCalculationIntent(
                steps=[
                    DynamicOperation(
                        operation_id=handle,
                        operator=step["op"],
                        inputs=step["inputs"],
                        period_relation=step["relation"],
                    )
                    for handle, step in zip(_STEP_HANDLES, steps, strict=False)
                ],
                operand_constraints=[
                    {key: row[key] for key in ("period", "unit") if key in row} for row in rows
                ],
            )
        metadata.append(fields)
    tasks = []
    for task in payload["tasks"]:
        projected = {"objective": _ROLE_OBJECTIVES[task["role"]]} | task
        if indexed_ownership and (refs := task.get("need_refs")):
            projected["need_refs"] = [
                f"G{ref['goal_index'] + 1}.need[{ref['need_index']}]" for ref in refs
            ]
        tasks.append(projected)
    return dict(goals=goals, tasks=tasks), metadata


def decode_coordinator_plan(payload, question, schema):
    """Decode using the request's schema, including archived A and C requests."""
    from .lite_orchestrator import LitePlan

    semantic = schema == semantic_plan_schema()
    workflow = schema == compact_plan_schema()
    minimal = schema == compact_plan_schema(version=4)
    simple = not (workflow or minimal) and schema in (
        simple_plan_schema(),
        simple_hybrid_plan_schema(),
    )
    indexed_ownership = semantic or workflow or minimal or schema == compact_plan_schema(version=3)
    compact = (
        simple
        or indexed_ownership
        or schema == compact_plan_schema(version=2)
        or schema == compact_plan_schema(version=1)
    )
    if not compact and schema != PlanProposal.model_json_schema():
        return LitePlan(), ["supervisor_unknown_plan_schema"]
    if issues := schema_issues(schema, payload):
        if semantic:
            return LitePlan(), [
                f"supervisor_plan_schema_mismatch:{'.'.join(map(str, issue.path))}:{issue.code}"
                for issue in issues
            ]
        return LitePlan(), ["supervisor_plan_schema_mismatch"]
    if not compact:
        errors = [
            f"supervisor_invalid_task:T{index + 1}:dependency_index_not_before_task"
            for index, task in enumerate(payload["tasks"])
            if any(not 0 <= parent < index for parent in task.get("after", ()))
        ]
        if errors:
            return LitePlan(), errors
        plan, errors = adapt_plan(payload, question, explicit_assignments=True)
        return (LitePlan() if errors else plan), errors

    default_retrieval = simple or (
        payload["workflow"] == "single_batch" if workflow else minimal and "tasks" not in payload
    )
    if default_retrieval:
        if minimal and len(payload["goals"]) != 1:
            return LitePlan(), ["explicit_coordination_required"]
        payload = payload | {"tasks": [{"role": "retrieval", "goal_indexes": [0]}]}

    try:
        if semantic:
            payload = payload | {"tasks": _semantic_tasks(payload["goals"])}
        projected, metadata = _project_compact_plan(payload, indexed_ownership=indexed_ownership)
    except ValueError as error:
        return LitePlan(), [f"supervisor_compact_{error}"]
    plan, errors = adapt_plan(projected, question, explicit_assignments=semantic)
    if errors:
        return LitePlan(), errors
    if (simple or workflow) and default_retrieval:
        plan.projected_task_id = plan.tasks[0].task_id
    elif default_retrieval:
        plan.scheduler_task_ids.insert(0, plan.tasks[0].task_id)
    elif workflow and len(payload["goals"]) == len(payload["tasks"]) == 1:
        (task,) = payload["tasks"]
        if task["role"] == "retrieval" and not (
            task.get("need_refs") or task.get("after") or task.get("objective")
        ):
            return LitePlan(), ["explicit_coordination_basis_missing"]
    plan.requirements = [
        requirement.model_copy(update=fields)
        for requirement, fields in zip(plan.requirements, metadata, strict=True)
    ]
    return plan, []


def adapt_plan(payload, question="", *, explicit_assignments=False):
    from .lite_orchestrator import LitePlan, LiteTask

    empty = LitePlan()
    if not isinstance(payload, dict):
        return empty, ["supervisor_invalid_envelope"]
    goals, raw_tasks = payload.get("goals") or [dict(text=question)], payload.get("tasks")
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
        # Preserve EO/criteria in the existing requirement text, which already
        # reaches Specialists and M6; no second completion state or verifier schema.
        text = goal.text
        for label, entries in (
            ("Bằng chứng cần", goal.evidence_needs),
            ("Điều kiện đủ", goal.verification_requirements),
        ):
            if entries:
                text += "\n" + label + ": " + "; ".join(entries)
        requirements[index] = IntegrationRequirement(
            requirement_id=gid,
            text=text,
            kind=goal.kind,
            evidence_needs=goal.evidence_needs,
            verification_requirements=goal.verification_requirements,
            reasoning_operations=goal.reasoning_operations,
        )
    tasks, blocked, scheduler_task_ids = [], {}, []
    for index, raw in enumerate(raw_tasks):
        tid = f"T{index + 1}"
        try:
            task = TaskProposal.model_validate(raw, strict=True)
            assigned = [
                requirements[i]
                for i in dict.fromkeys(task.goal_indexes or list(requirements))
                if i in requirements
            ]
            if len(assigned) != len(set(task.goal_indexes or list(requirements))):
                raise ValueError("goal_reference_unknown")
            if not assigned:
                raise ValueError("goal_reference_unknown")
            available_needs = [ref for r in assigned for ref in r.need_refs]
            if set(task.need_refs) - set(available_needs):
                raise ValueError("need_reference_unknown")
            if any(i < 0 or i >= len(raw_tasks) for i in task.after):
                raise ValueError("task_reference_unknown")
            tasks.append(
                LiteTask(
                    task_id=tid,
                    specialist=task.role,
                    objective=task.objective,
                    requirement_ids=[r.requirement_id for r in assigned],
                    need_refs=list(dict.fromkeys(task.need_refs or available_needs)),
                    depends_on=[f"T{i + 1}" for i in dict.fromkeys(task.after)],
                )
            )
        except (ValidationError, ValueError) as error:
            reason = str(error) if not isinstance(error, ValidationError) else "task_schema_invalid"
            blocked[tid] = reason
            errors.append(f"supervisor_invalid_task:{tid}:{reason}")
    ordered, invalid = schedule_tasks(tasks)
    blocked.update(invalid)
    errors.extend(f"{reason}:{tid}" for tid, reason in invalid.items())
    if explicit_assignments and len(requirements) == len(tasks) == 1:
        # Preserve the original single-batch handoff for one complete acquisition task.
        (task,) = tasks
        (requirement,) = requirements.values()
        explicit_assignments = task.specialist != "retrieval" or set(task.need_refs) != set(
            requirement.need_refs
        )
    owned = {
        rid
        for task in ordered
        if task.task_id not in blocked
        and (not explicit_assignments or task.specialist == "reasoning")
        for rid in task.requirement_ids
    }
    errors.extend(
        f"goal_owner_unresolved:{r.requirement_id}"
        for r in requirements.values()
        if r.requirement_id not in owned
    )
    # Complete capabilities, never infer financial needs or repair invalid plans.
    if not errors:
        ancestors = {}
        for task in ordered:
            ancestors[task.task_id] = set(task.depends_on)
            for parent in task.depends_on:
                ancestors[task.task_id].update(ancestors[parent])
        consumers = []
        for requirement in requirements.values():
            rid, missing, producers = requirement.requirement_id, set(), []
            reasoners = [
                task
                for task in ordered
                if task.specialist == "reasoning" and rid in task.requirement_ids
            ]
            if explicit_assignments and set(requirement.need_refs) - {
                ref for task in reasoners for ref in task.need_refs
            }:
                errors.append(f"goal_need_owner_unresolved:{rid}")
            for producer in ordered:
                if producer.specialist != "retrieval" or rid not in producer.requirement_ids:
                    continue
                existing = [t for t in reasoners if producer.task_id in ancestors[t.task_id]]
                needs = set(producer.need_refs) & set(requirement.need_refs)
                covered = {ref for t in existing for ref in t.need_refs}
                if needs - covered or not requirement.need_refs and not existing:
                    missing.update(needs - covered)
                    producers.append(producer.task_id)
            if producers and explicit_assignments:
                errors.append(f"goal_evidence_consumer_unresolved:{rid}")
            elif producers:
                consumers.append(
                    LiteTask(
                        task_id=f"T{len(raw_tasks) + len(consumers) + 1}",
                        specialist="reasoning",
                        objective="Đọc source results được giao và tạo candidate cho Goal; thiếu nguồn thì request_work hoặc báo thiếu.",
                        requirement_ids=[rid],
                        need_refs=[ref for ref in requirement.need_refs if ref in missing],
                        depends_on=producers,
                    )
                )
        if len(tasks) + len(consumers) > 6:
            errors.append("workflow_consumer_task_cap")
        else:
            tasks.extend(consumers)
            scheduler_task_ids = [task.task_id for task in consumers]
    return LitePlan(
        tasks=tasks,
        requirements=list(requirements.values()),
        blocked_tasks=blocked,
        scheduler_task_ids=scheduler_task_ids,
    ), errors


def schedule_tasks(tasks, *, completed=()):
    """Stable Kahn order; cycles, unknown refs and their closures never execute."""
    known = {t.task_id for t in tasks} | set(completed)
    ordered, done, remaining = [], set(completed), list(tasks)
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
