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
from .document_qa_contracts import DocumentKind
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


class DocumentSearchDemand(FinancialModel):
    query: str = Field(min_length=1, max_length=600)
    kind: DocumentKind
    goal_id: str | None = None
    selection_period: str | None = None
    from_comparison: bool = False


class CoordinationProposal(FinancialModel):
    retrieve: list[RetrievalDemand] = Field(default_factory=list, max_length=6)
    selection: SelectionDemand | None = None
    use_graph: bool = False
    document_search: DocumentSearchDemand | None = None
    # Additions reuse the ordinary task wire, with backend-preallocated IDs.
    add_tasks: list[ExpansionTask] = Field(default_factory=list, max_length=5)


def propose(gateway, context, task, workspace, sources):
    """One demand pass per task, no retries and the ordinary Gateway budget."""

    dependencies = {
        tid: {
            k: workspace.task_results[tid][k]
            for k in ("handle", "task_id", "revision", "digest", "verification")
        }
        | {
            "candidate_statements": workspace.tasks[tid].get("candidate_statements", []),
            "selected_observations": [
                prompt_observation(r) for r in workspace.task_results[tid]["selected_observations"]
            ],
        }
        for tid in task.depends_on
    }
    schema = CoordinationProposal.model_json_schema()
    del schema["properties"]["add_tasks"]
    del schema["$defs"]["ExpansionTask"]
    dependency_ids = workspace.dependency_ids(task)
    reusable = [
        r["evidence_id"]
        for tid in dependency_ids
        for r in workspace.task_results[tid].get("selected_observations", [])
    ]
    schema["$defs"]["RetrievalDemand"]["properties"]["source"] = {
        "enum": [
            *sources,
            *dependency_ids,
            *[workspace.task_results[t]["handle"] for t in dependency_ids],
            *reusable,
        ],
        "description": "S = retrieve a source, T/result/E from dependencies = reuse exact parent evidence; never arbitrary IDs.",
    }
    schema["$defs"]["RetrievalDemand"]["properties"]["period_from_task"] = {
        "enum": [None, *task.depends_on],
        "description": "Chỉ task dependency đã có output; root phải null.",
    }
    prompt = dict(
        instruction=(
            "Bạn là Specialist. Chọn công cụ để thực hiện objective và trả JSON theo schema. "
            "retrieve chọn từng S handle đúng chỉ tiêu và kỳ từ inventory. Fact gọi Financial Tools, "
            "metric gọi Calculator; nếu phải tính mới, lấy đủ facts làm toán hạng. "
            "Dùng lại facts và kết quả từ dependency_results. Chỉ dùng period_from_task khi "
            "cần tra chỉ tiêu theo kỳ thực tế của dependency. Root cần dữ liệu phải yêu cầu "
            "retrieve hoặc document_search. Đặt use_graph=true nếu cần EF-EG để lần theo nguồn "
            "hoặc quan hệ giữa dữ liệu. "
            "Dùng document_search cho BM25 khi cần nội dung văn bản, bảng hoặc thuyết minh. "
            "query là cụm từ ngắn có trong tài liệu. Chọn kind=table_selection cho yêu cầu "
            "chọn đối tượng cực trị trong bảng và selection_period là ngày ISO nếu biết. "
            "Nếu chủ đề bảng do phép so sánh của dependency quyết định, đặt from_comparison=true. "
            "Đặt goal_id là ID được giao khi BM25 phục vụ trực tiếp goal đó; bỏ qua cho bước trung gian. "
            "selection chỉ dùng để tìm cực trị của cùng chỉ tiêu qua nhiều kỳ. Khai toàn bộ kỳ. "
            "Các mục tùy chọn có thể bỏ. Không trả đáp án hay tự tạo handle."
        ),
        verification_feedback=workspace.tasks[task.task_id].get("repair_feedback", []),
        role=task.specialist,
        objective=task.objective,
        goals={
            r.requirement_id: r.text
            for r in workspace.requirements
            if r.requirement_id in task.requirement_ids
        },
        dependency_results=dependencies,
        inventory={
            h: {k: s[k] for k in ("kind", "item", "label", "period")} for h, s in sources.items()
        },
        schema=schema,
        empty_response_example={"retrieve": [], "selection": None},
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
    batches = parse_retrieval_batches(payload)
    workspace.tasks[task.task_id]["retrieval_batches"] = [
        [d.model_dump(mode="json") for d in batch.retrieve] for batch in batches
    ]
    return batches[0], metadata


def parse_retrieval_batches(payload):
    """Validate all requested inputs before execution, max6 per batch, no truncation."""
    requested = payload.get("retrieve", [])
    if not isinstance(requested, list) or len(requested) > 16:
        raise ValueError("demand_total_input_limit")
    return [
        CoordinationProposal.model_validate(
            payload | {"retrieve": requested[i : i + 6], "add_tasks": []}
        )
        for i in range(0, max(1, len(requested)), 6)
    ]


def resolve_demand_batches(proposal, batches, task, workspace, sources):
    handles, lineage = [], []
    for demands in batches or [[d.model_dump(mode="json") for d in proposal.retrieve]]:
        batch = CoordinationProposal(retrieve=[RetrievalDemand.model_validate(d) for d in demands])
        selected, reused = resolve_demands(batch, task, workspace, sources)
        handles.extend(selected)
        lineage.extend(reused)
    return list(dict.fromkeys(handles)), lineage


def resolve_demands(proposal, task, workspace, sources):
    handles, lineage = [], []
    for demand in proposal.retrieve:
        dependencies = workspace.dependency_ids(task)
        parents = [
            workspace.task_results[tid]
            for tid in dependencies
            if demand.source in {tid, workspace.task_results[tid]["handle"]}
            or any(
                r["evidence_id"] == demand.source
                for r in workspace.task_results[tid].get("selected_observations", [])
            )
        ]
        if parents:
            if demand.period_from_task and demand.period_from_task not in dependencies:
                raise ValueError("demand_dependency_unknown")
            for parent in parents:
                rows = parent.get("selected_observations", [])
                if demand.source.startswith("E-"):
                    rows = [r for r in rows if r["evidence_id"] == demand.source]
                for row in rows:
                    handles.extend(
                        h
                        for h, s in sources.items()
                        if s["kind"] == "fact"
                        and any(
                            f.observation_identity().model_dump(mode="json")
                            == row["reference"]["observation"]
                            for f in s["records"]
                        )
                    )
                lineage.append(
                    dict(
                        from_result={k: parent[k] for k in ("handle", "revision", "digest")},
                        mode="reuse_exact_dependency",
                        requested_handle=demand.source,
                        selected_evidence_ids=[r["evidence_id"] for r in rows],
                        source_context_handles=[
                            c["handle"] for c in parent.get("source_context", [])
                        ],
                    )
                )
            continue
        source = sources.get(demand.source)
        if source is None or (demand.period_from_task is not None and source["kind"] != "fact"):
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
    from .coordinator_plan import schedule_tasks
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

        if (
            any(i < 0 or i >= len(workspace.requirements) for i in entry["goal_indexes"])
            or set(entry["input_handles"]) - sources.keys()
        ):
            raise ValueError("expansion_reference_invalid")
        tasks.append(
            LiteTask(
                task_id=entry["task_id"],
                specialist=entry["role"],
                objective=entry["objective"],
                requirement_ids=[
                    workspace.requirements[i].requirement_id for i in entry["goal_indexes"]
                ],
                sources=entry["input_handles"],
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
