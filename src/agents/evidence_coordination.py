"""Bounded request-local retrieval/selection; never grants verification authority."""

import hashlib
import json
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from .contracts import SpecialistRole
from .planner_contracts import PlannerLLMMetadata


def content_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def prompt_observation(row):
    """Bounded projection; complete selectors/quality remain in the workspace."""
    return {
        k: v for k, v in row.items() if k not in {"selectors", "citations", "quality", "issues"}
    } | {
        "sources": [
            {
                "page": c["source"]["reference"]["anchor"]["page"]["page"],
                "pointer": c["source"]["reference"]["source_pointer"],
                "limitations": c["limitations"],
            }
            for c in row["citations"]
        ],
        "quality": row["quality"],
        "issues": row["issues"],
    }


def prompt_coordination(record):
    """Do not duplicate full input closure inside every join and result prompt."""
    projected = {k: record[k] for k in ("retrieval_lineage", "expansion_error") if k in record}
    if record.get("selection"):
        selection = record["selection"]
        projected["selection"] = {k: v for k, v in selection.items() if k != "domain"}
        projected["selection"]["domain"] = [prompt_observation(r) for r in selection["domain"]]
    projected["joins"] = [
        {k: v for k, v in join.items() if k not in {"left", "right"}}
        for join in record.get("joins", [])
    ]
    return projected


def observation(match):
    """Projection of an existing source fact, including unmapped facts, without promotion."""
    fact = match.record
    reference = match.reference.model_dump(mode="json")
    return dict(
        evidence_id="E-"
        + hashlib.sha256(match.reference.model_dump_json().encode()).hexdigest()[:20],
        reference=reference,
        source_digest=content_digest(fact.model_dump(mode="json")),
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        item=fact.canonical_item_id,
        label=fact.context.raw_item_label,
        header=fact.raw_header,
        raw_value=fact.value.raw_value,
        value=str(fact.value.normalized_value) if fact.value.normalized_value is not None else None,
        unit=fact.value.unit,
        context=fact.context.model_dump(mode="json"),
        selectors=[s.model_dump(mode="json") for s in fact.sources],
        citations=[c.model_dump(mode="json") for c in match.citations],
        quality=[q.model_dump(mode="json") for q in fact.quality_context],
        issues=[q.model_dump(mode="json") for q in fact.resolution_issues],
        parser="existing_financial_normalization_v1",
        verification="unverified_source_observation",
    )


class RetrievalDemand(FinancialModel):
    source: str
    period_from_task: str | None = None


class SelectionDemand(FinancialModel):
    item: str
    periods: list[str] = Field(min_length=1, max_length=8)
    comparator: Literal["max", "min", "max_abs", "min_abs"]


class ExpansionTask(FinancialModel):
    task_id: str
    goal_indexes: list[int] = Field(min_length=1, max_length=16)
    role: SpecialistRole
    objective: str = Field(min_length=1, max_length=600)
    input_handles: list[str] = Field(max_length=16)
    after_tasks: list[str] = Field(min_length=1, max_length=6)


class CoordinationProposal(FinancialModel):
    retrieve: list[RetrievalDemand] = Field(default_factory=list, max_length=6)
    selection: SelectionDemand | None = None
    # Additions reuse the ordinary task wire, with backend-preallocated IDs.
    add_tasks: list[ExpansionTask] = Field(default_factory=list, max_length=5)


def propose(gateway, context, task, workspace, sources, observations, available_ids):
    """One demand pass per task, no retries and the ordinary Gateway budget."""

    dependencies = {
        tid: {
            k: workspace.task_results[tid][k]
            for k in ("handle", "task_id", "revision", "digest", "verification")
        }
        | {
            "selected_observations": [
                prompt_observation(r) for r in workspace.task_results[tid]["selected_observations"]
            ]
        }
        for tid in task.depends_on
    }
    schema = CoordinationProposal.model_json_schema()
    schema["$defs"]["RetrievalDemand"]["properties"]["period_from_task"] = {
        "enum": [None, *task.depends_on],
        "description": "Chỉ task dependency đã có output; root phải null.",
    }
    prompt = dict(
        instruction=(
            "Điều phối truy xuất bằng evidence thực tế, không trả đáp án. Chỉ JSON theo schema. "
            "Chỉ làm objective của task hiện tại. Không làm trước task sau. "
            "retrieve chọn S handle đúng item/kỳ từ inventory. Nếu cần dữ liệu cùng kỳ với output "
            "đã chọn của dependency, period_from_task là task ID đó; backend lấy kỳ từ selected_observations "
            "và chọn đúng item cùng kỳ, không lấy kỳ trong objective làm evidence. "
            "period_from_task CHỈ thuộc dependency_results; tuyệt đối không dùng task hiện tại hoặc task tương lai. "
            "Root không có dependencies: mọi period_from_task phải null. "
            "Không retrieve lại dữ liệu đã có nếu chỉ cần phép tính. "
            "selection chỉ dùng khi objective yêu cầu chọn lớn/nhỏ nhất: item canonical có thật, "
            "periods là TOÀN BỘ kỳ phải so sánh, comparator=max|min|max_abs|min_abs; "
            "không dùng selection để chọn operands của phép tính hoặc gộp nhiều chỉ tiêu. "
            "Backend so Decimal, giữ ties/null/conflicts và provenance. Không chọn winner bằng prose. "
            "Sau khi có thông tin mới, có thể add_tasks đúng existing goals, dùng ID trong available_ids; "
            "mỗi object {task_id,goal_indexes,role,objective,input_handles,after_tasks}. "
            "after_tasks chỉ trỏ task hiện tại, dependencies đã có kết quả hoặc task mới. "
            "Đọc existing_tasks: không add task trùng việc đã có. Chỉ mở rộng khi thông tin MỚI làm "
            "thiếu bước trong plan; mặc định add_tasks=[]. Không sửa goals. "
            "Role chỉ profitability|liquidity_and_leverage|cash_flow_and_earnings_quality; không dùng explanation. "
            "Các candidates là chưa verified; không dùng interpretation như canonical fact."
            " Nếu có verification_feedback, sửa đúng nguồn/selection/join hoặc goal binding được chỉ ra; "
            "đối chiếu goals, không lặp lại lựa chọn sai. Không có evidence thì không đoán."
        ),
        verification_feedback=workspace.tasks[task.task_id].get("repair_feedback", []),
        question=workspace.question,
        task=task.model_dump(mode="json"),
        goals=[r.model_dump(mode="json") for r in workspace.requirements],
        dependency_results=dependencies,
        existing_tasks={
            tid: {
                k: s.get(k)
                for k in ("objective", "depends_on", "status", "role", "requirement_ids")
            }
            for tid, s in workspace.tasks.items()
        },
        observations=[prompt_observation(r) for r in observations],
        inventory={h: {k: v for k, v in s.items() if k != "records"} for h, s in sources.items()},
        available_ids=available_ids,
        schema=schema,
        empty_response_example={"retrieve": [], "selection": None, "add_tasks": []},
    )
    wire = json.dumps(prompt, ensure_ascii=False)
    if len(wire) > 48000:
        raise ValueError("coordination_payload_limit")
    response = gateway.generate(
        LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m5-evidence-demand-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(role="system", content=wire),
                Message(role="user", content=task.objective),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=1200),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=context.provider_timeout_seconds),
        )
    )
    metadata = PlannerLLMMetadata(
        calls=1,
        model=context.model,
        status=response.status,
        usage=response.usage,
        cost=response.cost,
        error=response.error,
        provenance=response.provenance,
    )
    workspace.tasks[task.task_id]["coordination_response"] = response.model_dump(mode="json")
    # Keep usage even when the model violates the local schema.
    workspace.tasks[task.task_id]["coordination_usage"] = metadata.model_dump(mode="json")
    if response.status != "success" or not isinstance(response.output, JSONOutput):
        raise ValueError("coordination_provider_failure")
    payload = response.output.payload
    if not isinstance(payload, dict):
        raise ValueError("coordination_schema_invalid")
    workspace.tasks[task.task_id]["expansion_proposal"] = payload.get("add_tasks", [])
    # An optional append patch is validated atomically on its own. A rejected
    # patch must not erase independent retrieval/selection outputs.
    return CoordinationProposal.model_validate(payload | {"add_tasks": []}), metadata


def resolve_demands(proposal, task, workspace, sources):
    handles, lineage = [], []
    for demand in proposal.retrieve:
        source = sources.get(demand.source)
        if source is None or source["kind"] != "fact":
            raise ValueError("demand_source_unknown_or_not_fact")
        resolved = demand.source
        if demand.period_from_task is not None:
            tid = demand.period_from_task
            if tid not in task.depends_on:
                raise ValueError("demand_dependency_unknown")
            parent = workspace.task_results[tid]
            rows = parent["selected_observations"]
            periods = {r["context"]["period"] for r in rows}
            if not rows or None in periods or len(periods) != 1:
                raise ValueError("demand_period_ambiguous")
            matches = [
                h
                for h, s in sources.items()
                if s["kind"] == "fact" and s["item"] == source["item"] and s["period"] in periods
            ]
            if len(matches) != 1:
                raise ValueError("demand_source_ambiguous_or_missing")
            resolved = matches[0]
            lineage.append(
                dict(
                    from_result={k: parent[k] for k in ("handle", "revision", "digest")},
                    field="context.period",
                    value=next(iter(periods)),
                    selected_evidence_ids=[r["evidence_id"] for r in rows],
                    requested_handle=demand.source,
                    resolved_handle=resolved,
                )
            )
        handles.append(resolved)
    return list(dict.fromkeys(handles)), lineage


def select_observations(demand, rows, sources):
    """Complete declared item/period domain; equal maxima remain a set."""
    domain = [
        r for r in rows if r["item"] == demand.item and r["context"]["period"] in demand.periods
    ]
    expected = {
        f.observation_identity().model_dump_json()
        for s in sources.values()
        if s["kind"] == "fact" and s["item"] == demand.item and s["period"] in demand.periods
        for f in s["records"]
    }
    actual = {json.dumps(r["reference"]["observation"], separators=(",", ":")) for r in domain}
    # Reference identity uses the existing ObservationIdentity serialization.
    if (
        not expected
        or actual != expected
        or {r["context"]["period"] for r in domain} != set(demand.periods)
    ):
        raise ValueError("selection_domain_incomplete")
    contexts = {
        (
            r["company_id"],
            r["document_id"],
            r["snapshot_id"],
            r["unit"],
            r["context"]["currency"],
            r["context"]["scale"],
            r["context"]["reporting_scope"],
            r["context"]["period_type"],
        )
        for r in domain
    }
    if (
        len(contexts) != 1
        or any(
            any(value is None for i, value in enumerate(context) if i != 6) for context in contexts
        )
        or any(r["value"] is None or not r["selectors"] or not r["header"] for r in domain)
    ):
        raise ValueError("selection_context_unresolved")
    by_period = {}
    for row in domain:
        by_period.setdefault(row["context"]["period"], set()).add(row["value"])
    if any(len(values) != 1 for values in by_period.values()):
        raise ValueError("selection_conflicting_values")

    def key(row):
        value = Decimal(row["value"])
        return abs(value) if demand.comparator.endswith("_abs") else value

    best = (max if demand.comparator.startswith("max") else min)(map(key, domain))
    selected = [r for r in domain if key(r) == best]
    record = dict(
        domain=domain,
        domain_scope="declared_item_and_periods_in_pinned_inventory",
        selection=demand.model_dump(mode="json"),
        selected_ids=[r["evidence_id"] for r in selected],
        excluded=[
            dict(evidence_id=r["evidence_id"], reason="comparator_not_equal_to_extremum")
            for r in domain
            if key(r) != best
        ],
        ties=len({r["context"]["period"] for r in selected}) > 1,
        caveats=["reporting_scope_unresolved_within_pinned_snapshot"]
        if any(r["context"]["reporting_scope"] is None for r in domain)
        else [],
        verification="unverified_selection_semantics",
    )
    record["digest"] = content_digest(record)
    return selected, record


def join_observations(parent, current):
    """Exact source context join; no fuzzy entities or inferred accounting meaning."""
    fields = ["company_id", "document_id", "snapshot_id", "period"]
    left, right = parent["selected_observations"], current
    # Exact document/snapshot membership is known even when accounting scope is
    # unresolved. Never manufacture separate/consolidated from that membership.
    missing_scope = all(r["context"]["reporting_scope"] is None for r in [*left, *right])
    if not missing_scope:
        fields.append("reporting_scope")

    def key(row):
        return tuple(row.get(f) if f in row else row["context"].get(f) for f in fields)

    pairs = [(a, b) for a in left for b in right if None not in key(a) and key(a) == key(b)]
    unmatched_left = [a["evidence_id"] for a in left if not any(a == p[0] for p in pairs)]
    unmatched_right = [b["evidence_id"] for b in right if not any(b == p[1] for p in pairs)]
    # Multiple rows for one item/key cannot silently turn into a many-to-many join.
    identities = [
        (side, row["item"], key(row))
        for side, rows in [("left", left), ("right", right)]
        for row in rows
    ]
    ambiguous = len(identities) != len(set(identities))
    record = dict(
        from_result={k: parent[k] for k in ("handle", "revision", "digest")},
        keys=fields,
        normalization="identity",
        caveats=["reporting_scope_unresolved_within_pinned_snapshot"] if missing_scope else [],
        left=left,
        right=right,
        pairs=[[a["evidence_id"], b["evidence_id"]] for a, b in pairs],
        cardinality=dict(left=len(left), right=len(right), matched=len(pairs)),
        unmatched_left=unmatched_left,
        unmatched_right=unmatched_right,
        status="ambiguous"
        if ambiguous
        else "unmatched"
        if unmatched_left or unmatched_right
        else "matched",
        verification="unverified_join_semantics",
    )
    record["digest"] = content_digest(record)
    return record


def expansion_tasks(raw, task, workspace, sources, available_ids):
    """One atomic append-only expansion within the original six-task budget."""
    from .coordinator_plan import TaskProposal, schedule_tasks
    from .lite_orchestrator import LiteTask

    if not raw:
        return []
    if not isinstance(raw, list) or len(raw) > 5:
        raise ValueError("expansion_schema_invalid")
    raw = [ExpansionTask.model_validate(r).model_dump(mode="json") for r in raw]
    ids = [r.get("task_id") for r in raw]
    if len(ids) != len(set(ids)) or set(ids) - set(available_ids):
        raise ValueError("expansion_task_ids_invalid")
    allowed = {task.task_id, *task.depends_on, *ids}
    tasks = []
    for entry in raw:
        if set(entry) != {
            "task_id",
            "goal_indexes",
            "role",
            "objective",
            "input_handles",
            "after_tasks",
        }:
            raise ValueError("expansion_schema_invalid")
        after = entry["after_tasks"]
        if not isinstance(after, list) or not after or any(t not in allowed for t in after):
            raise ValueError("expansion_dependency_invalid")
        wire = TaskProposal.model_validate(
            {k: v for k, v in entry.items() if k not in {"task_id", "after_tasks"}} | {"after": []}
        )
        if (
            any(i < 0 or i >= len(workspace.requirements) for i in wire.goal_indexes)
            or set(wire.input_handles) - sources.keys()
        ):
            raise ValueError("expansion_reference_invalid")
        tasks.append(
            LiteTask(
                task_id=entry["task_id"],
                specialist=wire.role,
                objective=wire.objective,
                requirement_ids=[
                    workspace.requirements[i].requirement_id for i in wire.goal_indexes
                ],
                sources=wire.input_handles,
                depends_on=after,
                use_graph=True,
            )
        )
    # Already executed parents are roots for validating the added sub-DAG.
    roots = [
        LiteTask(task_id=tid, specialist=task.specialist, objective="existing result")
        for tid in allowed - set(ids)
    ]
    ordered, blocked = schedule_tasks([*roots, *tasks])
    if blocked:
        raise ValueError("expansion_cycle")
    return [t for t in ordered if t.task_id in ids]
