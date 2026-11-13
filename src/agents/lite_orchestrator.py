"""One Supervisor plan, independent specialist executions, ordinary M6 candidates."""

import json
import re
from time import perf_counter
from uuid import uuid4

from pydantic import Field, ValidationError, model_validator

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..evidence.graph import graph_id
from ..tools.evidence_retrieval import EvidenceRetrievalTools, GetEvidenceSourcesRequest
from ..tools.financial_calculator import CalculateFinancialMetricRequest, FinancialCalculator
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest
from ..tools.graph_retrieval import (
    GetGraphContextRequest,
    GetSnapshotGraphContextRequest,
    GraphContextResponse,
    GraphRetrievalTools,
)
from ..tools.question_understanding import normalize
from . import cash_flow_earnings_quality_specialist as cash
from . import liquidity_leverage_specialist as liquidity
from . import profitability_specialist as profit
from .contracts import PlanValidation, SpecialistRole
from .grounded_observations import observation_proposal
from .integration_workspace import (
    INTERPRETATION_TERMS,
    IntegrationRequirement,
    IntegrationWorkspace,
    evidence_handle,
)
from .orchestration_contracts import (
    OrchestrationError,
    OrchestrationResult,
    SpecialistExecution,
    StageExecution,
)
from .orchestrator import aggregate_candidates
from .planner_contracts import PlannerLLMMetadata
from .routing_contracts import RoutingDecision
from .specialist_common import (
    AnalysisProposal,
    SpecialistResult,
    SpecialistTrace,
    _numeric_proposals,
    generate_candidates,
    select_evidence,
    source_projection,
)
from .supervisor import ExecutionEvidenceBundle, StepExecutionResult, SupervisorResult

DOMAINS = {
    "profitability": (profit, profit.ProfitabilityProposal),
    "liquidity_and_leverage": (liquidity, liquidity.LiquidityLeverageProposal),
    "cash_flow_and_earnings_quality": (cash, cash.CashFlowEarningsQualityProposal),
}


def normalize_candidate_envelope(payload):
    """Relocate strictly typed analyses from a provider's numeric claims slot.

    No text, values, operations or evidence IDs are repaired. The unchanged
    analysis still passes ordinary grounding, Calculator and M6 gates. Model
    limitations on a pure arithmetic proposal stay in raw output: deterministic
    arithmetic does not verify those additional prose assertions.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        return payload
    analyses = payload.get("analyses", [])
    if not isinstance(analyses, list):
        return payload
    moved, remaining = [], []
    for raw in payload["claims"]:
        if isinstance(raw, dict) and {"statement", "evidence_ids"} <= raw.keys():
            try:
                AnalysisProposal.model_validate(raw)
                moved.append(raw)
                continue
            except ValueError:
                pass
        remaining.append(raw)
    cleaned = []
    changed = bool(moved)
    for raw in [*analyses, *moved]:
        if isinstance(raw, dict) and raw.get("claim_type") == "derived_fact":
            try:
                AnalysisProposal.model_validate(raw)
                if raw.get("limitations"):
                    raw = dict(raw, limitations=[])
                    changed = True
            except ValueError:
                pass
        cleaned.append(raw)
    return dict(payload, claims=remaining, analyses=cleaned) if changed else payload


def compact_graph_context(contexts, evidence):
    """Bounded relations; raw tool traces retain complete original records."""
    from ..evidence.composition_graph import node_reference

    def citations(values):
        # Group original selectors by source/page. Full anchors remain in the
        # typed tool trace; repeated bbox/image payloads would crowd out lineage.
        groups = {}
        for citation in values:
            key = (
                citation.document_id,
                citation.snapshot_id,
                citation.pdf_page,
                citation.provenance_level,
            )
            group = groups.setdefault(
                key,
                dict(
                    document_id=key[0],
                    snapshot_id=key[1],
                    pdf_page=key[2],
                    provenance_level=key[3],
                    selectors=[],
                    limitations=[],
                ),
            )
            pointer = (
                citation.source.reference.source_pointer
                if citation.source.reference is not None
                else None
            )
            if pointer is not None and pointer not in group["selectors"]:
                group["selectors"].append(pointer)
            group["limitations"] = sorted(set(group["limitations"] + citation.limitations))
        return list(groups.values())

    rows, seen, pending = [], set(), []
    for context in contexts:
        if context.status != "found":
            continue
        nodes = {n.node.node_id: n for n in [context.start, *context.matches] if n}
        for relation in sorted(
            context.edges,
            key=lambda r: (
                {
                    "used_in": 0,
                    "same_extraction_context": 1,
                    "associated_with": 2,
                    "from_source": 3,
                }[r.edge.relation],
                r.edge.edge_id,
            ),
        ):
            edge = relation.edge
            if edge.edge_id in seen:
                continue
            seen.add(edge.edge_id)
            endpoints = []
            caveats = set(context.caveats)
            for nid in (edge.source, edge.target):
                node = nodes[nid]
                caveats.update(node.caveats)
                ref = node_reference(node.node)
                selected = [e for e in evidence if e.reference == ref]
                endpoints.append(
                    dict(
                        kind=node.node.kind,
                        evidence_ids=[e.evidence_id for e in selected],
                        labels=[e.label for e in selected],
                        # Exact typed references remain in the tool response;
                        # prompt endpoints bind by immutable node ID and retain
                        # original document/snapshot/page citations below.
                        reference=dict(kind=ref.kind, node_id=nid),
                        citations=citations(node.original_citations),
                        quality=node.quality.model_dump(mode="json", exclude_defaults=True),
                        grounding=node.grounding.model_dump(mode="json", exclude_defaults=True),
                        evidence_status=node.evidence.status,
                        text_excerpts=[
                            dict(
                                text=m.record.raw_text[:600], truncated=len(m.record.raw_text) > 600
                            )
                            for m in node.evidence.matches
                            if getattr(m.record, "raw_text", None)
                        ],
                    )
                )
            row = dict(
                id="",
                relation=edge.relation,
                operand_role=getattr(edge, "operand_role", None),
                basis=relation.basis,
                verification=relation.verification,
                endpoints=endpoints,
                caveats=sorted(caveats),
            )
            pending.append(row)
    # Balance relation types across the entire bundle, not per starting node.
    groups = {}
    for row in pending:
        groups.setdefault(row["relation"], []).append(row)
    ordered = [
        row
        for i in range(max((len(g) for g in groups.values()), default=0))
        for group in groups.values()
        for row in group[i : i + 1]
    ]
    for row in ordered:
        row["id"] = f"G{len(rows) + 1}"
        if len(json.dumps([*rows, row], ensure_ascii=False)) <= 14000:
            rows.append(row)
    return rows


class LiteTask(FinancialModel):
    specialist: SpecialistRole
    objective: str = Field(min_length=1, max_length=600)
    # Optional retrieval handles, never coverage obligations or claim approvals.
    sources: list[str] = Field(default_factory=list, max_length=16)
    use_graph: bool = False
    task_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list, max_length=16)
    depends_on: list[str] = Field(default_factory=list, max_length=6)


class LitePlan(FinancialModel):
    tasks: list[LiteTask] = Field(default_factory=list, max_length=6)
    requirements: list[IntegrationRequirement] = Field(default_factory=list, max_length=16)


def integration_plan(payload):
    """Keep independently valid tasks; malformed goals remain visible, never approved."""
    if not isinstance(payload, dict):
        return LitePlan(), ["supervisor_invalid_envelope"]
    requirements, tasks, errors = [], [], []
    raw_requirements, raw_tasks = payload.get("requirements", []), payload.get("tasks", [])
    if not isinstance(raw_requirements, list) or not isinstance(raw_tasks, list):
        return LitePlan(), ["supervisor_invalid_envelope"]
    if len(raw_requirements) > 16 or len(raw_tasks) > 6:
        errors.append("supervisor_plan_limit_exceeded")
    for raw in raw_requirements[:16]:
        try:
            if isinstance(raw, dict):
                raw = dict(raw)
                # Provider shorthand for an existing goal, not new authority.
                if raw.get("kind") == "calculation":
                    raw["kind"] = "metric"
                elif raw.get("kind") in {"analysis", "synthesis", "limitation"}:
                    raw["answer_goal"] = raw["kind"]
                    raw["kind"] = "explanation"
                if raw.get("answer_goal", "value") != "value":
                    raw.update(
                        kind="explanation",
                        aspect="value",
                        target_id=None,
                        requested_unit=None,
                        interpretation=True,
                    )
            requirement = IntegrationRequirement.model_validate(raw)
            if not requirement.requirement_id.strip() or not requirement.text.strip():
                raise ValueError("empty_requirement")
            if any(r.requirement_id == requirement.requirement_id for r in requirements):
                raise ValueError("duplicate_requirement")
            requirements.append(requirement)
        except (ValidationError, ValueError):
            errors.append("supervisor_invalid_requirement")
    ids = {r.requirement_id for r in requirements}
    for index, raw in enumerate(raw_tasks[:6]):
        try:
            if isinstance(raw, dict):
                raw = dict(raw)
                raw["sources"] = [
                    s for s in raw.get("sources", []) if s not in raw.get("depends_on", [])
                ]
            task = LiteTask.model_validate(raw)
            task.task_id = task.task_id or f"T{index + 1}"
            if not task.requirement_ids or set(task.requirement_ids) - ids:
                raise ValueError("task_requirement_binding_missing")
            if any(t.task_id == task.task_id for t in tasks):
                raise ValueError("duplicate_task")
            tasks.append(task)
        except (ValidationError, ValueError):
            errors.append(f"supervisor_invalid_task:T{index + 1}")
    # Dependencies must point backward; no graph engine or recursive scheduling.
    seen = set()
    for task in tasks:
        if set(task.depends_on) - seen:
            errors.append("task_dependency_unresolved:" + task.task_id)
        seen.add(task.task_id)
    if not requirements or errors or not ids <= {r for t in tasks for r in t.requirement_ids}:
        errors.append("requirement_plan_incomplete")
    return LitePlan(tasks=tasks, requirements=requirements), errors


def inventory(catalog, context):
    """Small metadata-only inventory; source identities remain in Python."""
    entries = {}
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", context.period or ""))
    for fact in catalog.facts:
        if (fact.company_id, fact.document_id, fact.snapshot_id) != (
            context.company_id,
            context.document_id,
            context.snapshot_id,
        ):
            continue
        scope = catalog.get_reporting_scope(fact.document_id, fact.snapshot_id)
        if context.reporting_scope and (
            scope.status != "resolved"
            or scope.evidence_status != "confirmed"
            or scope.reporting_scope != context.reporting_scope
        ):
            continue
        if years and fact.context.period[:4] not in years:
            continue
        for role, (module, _) in DOMAINS.items():
            if fact.canonical_item_id in module.ITEM_LABELS:
                key = ("fact", fact.canonical_item_id, fact.context.period)
                entry = entries.setdefault(
                    key,
                    dict(
                        kind="fact",
                        item=fact.canonical_item_id,
                        period=fact.context.period,
                        label=module.ITEM_LABELS[fact.canonical_item_id],
                        roles=[],
                        records=[],
                    ),
                )
                if role not in entry["roles"]:
                    entry["roles"].append(role)
                if fact not in entry["records"]:
                    entry["records"].append(fact)
        # A Specialist's vocabulary is not the EF-EG coverage boundary. Route
        # other mapped facts by their existing statement, retaining source labels.
        if fact.canonical_item_id and not any(
            fact.canonical_item_id in module.ITEM_LABELS for module, _ in DOMAINS.values()
        ):
            role = {
                "B01": "liquidity_and_leverage",
                "B02": "profitability",
                "B03": "cash_flow_and_earnings_quality",
            }.get(fact.context.statement_type)
            if role:
                key = ("fact", fact.canonical_item_id, fact.context.period)
                entry = entries.setdefault(
                    key,
                    dict(
                        kind="fact",
                        item=fact.canonical_item_id,
                        period=fact.context.period,
                        label=fact.context.raw_item_label or fact.canonical_item_id,
                        roles=[role],
                        records=[],
                    ),
                )
                if fact not in entry["records"]:
                    entry["records"].append(fact)
    available = {(s["item"], s["period"]) for s in entries.values()}
    for metric in catalog.metrics:
        if (metric.request.document_id, metric.request.snapshot_id) != (
            context.document_id,
            context.snapshot_id,
        ):
            continue
        if not all(
            (operand.canonical_item_id, metric.request.operand_periods.get(operand.role))
            in available
            for operand in metric.definition.compatibility.operands
        ):
            continue
        for role, (module, _) in DOMAINS.items():
            labels = getattr(module, "METRIC_LABELS", {})
            if metric.definition.name not in labels:
                continue
            if years and max(metric.request.operand_periods.values())[:4] not in years:
                continue
            key = ("metric", metric.metric_id)
            entries[key] = dict(
                kind="metric",
                item=metric.definition.name,
                period=max(metric.request.operand_periods.values()),
                label=labels[metric.definition.name],
                roles=[role],
                records=[metric],
            )
    return {f"S{i}": value for i, value in enumerate(entries.values(), 1)}


def resolve_source(reference, sources, periods=()):
    """Resolve only within the pinned inventory; a canonical item needs a unique period."""
    choices = [
        (handle, source)
        for handle, source in sources.items()
        if (handle == reference or source["item"] == reference)
    ]
    if not choices:
        return None, "source_unknown"
    choices = [
        (handle, source) for handle, source in choices if not periods or source["period"] in periods
    ]
    if not choices:
        return None, "source_period_mismatch"
    if len(choices) != 1 or len(choices[0][1]["records"]) != 1:
        return None, "source_ambiguous"
    return choices[0][0], None


def resolve_requirements(plan, sources):
    """Normalize model identifiers, retaining IDs/text and unresolved obligations."""
    from ..outputs.qa_composer import INTERPRETATION_TERMS

    targets = {}
    for requirement in plan.requirements:
        if requirement.answer_goal != "value":
            continue
        error = None
        indicators = []
        for reference in requirement.required_indicators:
            # Indicators identify a concept, not a particular source period.
            items = {
                s["item"] for h, s in sources.items() if h == reference or s["item"] == reference
            }
            if len(items) != 1:
                error = "requirement_indicator_unresolved"
                break
            indicators.append(items.pop())
        if error:
            requirement.reason, requirement.target_id = error, None
            continue
        requirement.required_indicators = list(dict.fromkeys(indicators))
        if requirement.interpretation_topic == "dynamic_calculation":
            requirement.requested_unit = {"lần": "ratio", "%": "percent", "đồng": "VND"}.get(
                requirement.requested_unit, requirement.requested_unit
            )
            # A named result may be absent from the catalog; its explicitly
            # declared operands still have independent canonical bindings.
            for item in requirement.required_indicators:
                for period in dict.fromkeys([requirement.period, *requirement.reasoning_periods]):
                    operand_handle, operand_error = resolve_source(
                        item, sources, [period] if period else []
                    )
                    if operand_error or sources[operand_handle]["kind"] != "fact":
                        continue
                    for task in plan.tasks:
                        if (
                            requirement.requirement_id in task.requirement_ids
                            and operand_handle not in task.sources
                        ):
                            task.sources.append(operand_handle)
        if not requirement.target_id or requirement.kind not in {"fact", "metric", "explanation"}:
            continue
        handle, error = resolve_source(
            requirement.target_id, sources, [requirement.period] if requirement.period else []
        )
        if error:
            requirement.reason = error
            requirement.target_id = None
            continue
        source = sources[handle]
        requirement.target_id = source["item"]
        if requirement.kind in {"fact", "metric"}:
            requirement.kind = source["kind"]
        # A scalar retrieval is not a metric interpretation merely because the
        # provider set those flags. Explicit interpretation requests keep them.
        text = normalize(requirement.text)
        if (
            source["kind"] in {"fact", "metric"}
            and not requirement.reasoning_operations
            and requirement.interpretation_topic != "dynamic_calculation"
            and re.match(r"^(?:tinh|tim|neu)\b", text)
            and not any(term in text for term in INTERPRETATION_TERMS)
        ):
            requirement.interpretation = False
            requirement.interpretation_topic = None
        targets[requirement.requirement_id] = source
        if requirement.interpretation_topic != "dynamic_calculation":
            # A resolved requested metric is already an executable catalog source.
            # Models sometimes select only its operands in task.sources. Retrieve
            # that same unambiguous target too, instead of asking another LLM to
            # reconstruct the formula that M4 can execute and M6 replay.
            for task in plan.tasks:
                if (
                    requirement.requirement_id in task.requirement_ids
                    and handle not in task.sources
                ):
                    task.sources.append(handle)
    # Narrative plans may name the numeric requirement IDs they depend on.
    # Expand only resolved references, preserving unknown obligations visibly.
    for requirement in plan.requirements:
        if requirement.answer_goal == "value":
            continue
        indicators = []
        for reference in requirement.required_indicators:
            source = targets.get(reference)
            if source is None:
                matches = [
                    s for h, s in sources.items() if h == reference or s["item"] == reference
                ]
                source = matches[0] if len({s["item"] for s in matches}) == 1 else None
            if source is None:
                indicators.append(reference)
            elif source["kind"] == "fact":
                indicators.append(source["item"])
            else:
                indicators.extend(
                    o.canonical_item_id
                    for o in source["records"][0].definition.compatibility.operands
                )
        requirement.required_indicators = list(dict.fromkeys(indicators))
    return targets


def preserve_answer_goal(plan, question, targets):
    """Keep explicit discourse goals even when the model only planned numbers.

    Language cues preserve an obligation, never infer an accounting conclusion.
    """
    text = normalize(question)
    requested = any(
        term in text
        for term in (
            *INTERPRETATION_TERMS,
            "tong hop",
            "dat hai ket qua",
            "dat ben canh",
            "gioi han",
            "han che",
            "khong suy",
        )
    )
    if not requested or not plan.tasks or not targets:
        return
    indicators = set()
    for requirement in plan.requirements:
        if (
            requirement.answer_goal == "value"
            and requirement.reason != "requirement_indicator_unresolved"
        ):
            indicators.update(requirement.required_indicators)
    for source in targets.values():
        if source["kind"] == "fact":
            indicators.add(source["item"])
        else:
            indicators.update(
                o.canonical_item_id for o in source["records"][0].definition.compatibility.operands
            )
    goals = [r for r in plan.requirements if r.answer_goal != "value"]
    if not any(normalize(r.text) == text for r in goals):
        rid = "R-response"
        while any(r.requirement_id == rid for r in plan.requirements):
            rid += "-next"
        whole_goal = [
            IntegrationRequirement(
                requirement_id=rid,
                text=question,
                kind="explanation",
                interpretation=True,
                answer_goal="synthesis" if len(indicators) > 1 else "analysis",
                required_indicators=sorted(indicators),
                depends_on=[r.requirement_id for r in plan.requirements],
            )
        ]
        plan.requirements.extend(whole_goal)
        goals.extend(whole_goal)
    task = next((t for t in plan.tasks if t.depends_on), None)
    if task is None:
        goal_ids = {r.requirement_id for r in goals}
        task = next(
            (t for t in plan.tasks if t.requirement_ids and set(t.requirement_ids) <= goal_ids),
            None,
        )
        if task is not None:
            plan.tasks.remove(task)
            task.depends_on = [t.task_id for t in plan.tasks if t.task_id]
            plan.tasks.append(task)
    if task is None:
        if len(plan.tasks) >= 6:
            return  # Keep the obligation visibly unverified when no task slot remains.
        tid = "T-response"
        while any(t.task_id == tid for t in plan.tasks):
            tid += "-next"
        task = LiteTask(
            task_id=tid,
            specialist=plan.tasks[-1].specialist,
            objective=question[:600],
            depends_on=[t.task_id for t in plan.tasks if t.task_id],
        )
        plan.tasks.append(task)
    task.requirement_ids = list(
        dict.fromkeys([*task.requirement_ids, *(r.requirement_id for r in goals)])
    )
    for goal in goals:
        goal.required_indicators = sorted(indicators)


def preserve_explicit_facts(plan, question, sources):
    """Reuse the existing alias inventory to retain omitted explicit fact requests.

    Only a unique fact in an explicitly named year is added; no fuzzy source or
    accounting formula is inferred. Existing indicator/operand goals are kept.
    """
    from ..outputs.qa_composer import _targets

    if not plan.tasks or not plan.requirements:
        return
    covered = {r.target_id for r in plan.requirements if r.answer_goal == "value"}
    covered.update(
        i for r in plan.requirements if r.answer_goal == "value" for i in r.required_indicators
    )
    covered = {sources.get(reference, {}).get("item", reference) for reference in covered}
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", question))
    for kind, item in _targets(normalize(question)):
        if kind != "fact" or item in covered:
            continue
        matches = [
            (h, s)
            for h, s in sources.items()
            if s["kind"] == "fact"
            and s["item"] == item
            and s["period"][:4] in years
            and len(s["records"]) == 1
        ]
        if len(matches) != 1 or len(plan.tasks) >= 6:
            continue
        handle, source = matches[0]
        rid, tid = "R-explicit", "T-explicit"
        while any(r.requirement_id == rid for r in plan.requirements):
            rid += "-next"
        while any(t.task_id == tid for t in plan.tasks):
            tid += "-next"
        req = IntegrationRequirement(
            requirement_id=rid,
            text=f"Nêu {source['label']} kỳ {source['period']}",
            kind="fact",
            target_id=item,
            period=source["period"],
            required_indicators=[item],
        )
        task = LiteTask(
            task_id=tid,
            specialist=source["roles"][0],
            objective=req.text,
            sources=[handle],
            requirement_ids=[rid],
        )
        position = next((i for i, t in enumerate(plan.tasks) if t.depends_on), len(plan.tasks))
        plan.tasks.insert(position, task)
        for dependent in plan.tasks[position + 1 :]:
            if dependent.depends_on:
                dependent.depends_on.append(tid)
        plan.requirements.append(req)
        covered.add(item)


def retain_requested_periods(plan, question):
    """Do not turn unsolicited standalone model years into user obligations."""
    text = normalize(question)
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", question))
    if not years or any(w in text for w in ("so voi", "so sanh", "nam truoc", "tang", "giam")):
        return
    for req in plan.requirements:
        if (
            req.answer_goal == "value"
            and not req.interpretation
            and req.period
            and req.period[:4] not in years
        ):
            req.required = False
            req.reason = "period_not_requested"
    optional = {r.requirement_id for r in plan.requirements if not r.required}
    for task in plan.tasks:
        task.requirement_ids = [rid for rid in task.requirement_ids if rid not in optional]
    plan.tasks = [t for t in plan.tasks if t.requirement_ids]
    ids = {t.task_id for t in plan.tasks}
    for task in plan.tasks:
        task.depends_on = [tid for tid in task.depends_on if tid in ids]


def fallback_plan(question, sources):
    """Conservative lexical routing; no guessed company, document or numbers."""
    text = normalize(question)
    tasks = {}
    for key, source in sources.items():
        label = normalize(source["label"])
        aliases = {
            "revenue_yoy": ["tang truong doanh thu", "doanh thu tang"],
            "gross_margin": ["bien loi nhuan gop"],
            "debt_to_assets": ["no phai tra tren tong tai san"],
        }.get(source["item"], [])
        if not any(term in text for term in [label, *aliases]):
            continue
        years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", question))
        if years and source["period"][:4] not in years:
            continue
        role = source["roles"][0]
        task = tasks.setdefault(role, LiteTask(specialist=role, objective=question[:600]))
        task.sources.append(key)
    return LitePlan(tasks=list(tasks.values()))


class SupervisorLite:
    def __init__(self, gateway=None, *, integration_v2=False):
        self.gateway = gateway
        self.integration_v2 = integration_v2

    def plan(self, question, context, sources):
        metadata = PlannerLLMMetadata(status="deterministic")
        if self.gateway is None or context.mode == "deterministic":
            plan = fallback_plan(question, sources)
            if self.integration_v2:
                from ..outputs.qa_composer import understand_requirements

                plan.requirements = [
                    IntegrationRequirement(**r.model_dump())
                    for r in understand_requirements(question)
                ]
                for index, task in enumerate(plan.tasks, 1):
                    task.task_id = f"T{index}"
                    task.requirement_ids = [
                        r.requirement_id
                        for r in plan.requirements
                        if any(sources[h]["item"] == r.target_id for h in task.sources)
                    ]
            return plan, metadata, []
        prompt = dict(
            instruction=(
                "Supervisor tài chính. Chọn ít Specialist thực sự cần thiết từ roles trong nguồn. "
                "Chỉ lập kế hoạch MỘT lần. JSON {tasks:[{specialist,objective,sources:[S1,...],use_graph:false}]}. "
                "Đặt use_graph=true khi cần truy vết nguồn, thành phần metric, phân tích nhiều bước, "
                "kết hợp bảng/thuyết minh hoặc kiểm tra ngữ cảnh phép tính. Tra một giá trị đơn giản "
                "không cần graph. Graph chỉ cung cấp structural/contextual relations, không chứng minh claim. "
                "objective là công việc ngắn tiếng Việt; sources là handles phù hợp trong inventory. "
                "Không DAG, approval, coverage hoặc suy đoán identities. Câu hỏi đơn giản một role; "
                "Không có nguồn đúng mục tiêu thì tasks=[]; không thay bằng chỉ tiêu gần giống. "
                "Nếu inventory có metric đúng tên câu hỏi, chọn metric đó; công thức/operands "
                "đi kèm metric được Tools cung cấp. Không tự thay mẫu số hoặc đổi đơn vị %. "
                "nhiều phần chọn các role cần thiết, không gọi tất cả mặc định. "
                "Hiểu ý định ngữ nghĩa, không yêu cầu đúng tên chỉ tiêu. Tăng/giảm phần trăm cần "
                "metric tăng trưởng và hai kỳ; tỷ trọng nguồn vốn cần metric nợ/tài sản. "
                "Phân tích tổng quát sinh lời và cơ cấu vốn giao profitability và liquidity_and_leverage, "
                "kèm facts, metrics và kỳ so sánh phù hợp. Objective phải yêu cầu diễn giải khi người dùng "
                "hỏi ý nghĩa/nhận xét/nguyên nhân/giới hạn. Chọn cả metric handles để gọi Calculator. "
                "Thiếu dữ liệu vẫn chọn các nguồn độc lập phù hợp; không bịa handles."
                " Giữ đủ từng chỉ tiêu, kỳ gốc/kỳ mục tiêu, biến động tuyệt đối/phần trăm "
                "và từng loại quan hệ được người dùng yêu cầu trong objective."
            ),
            context={
                k: getattr(context, k)
                for k in ("company_id", "document_id", "snapshot_id", "period", "reporting_scope")
            },
            inventory={
                k: {n: v for n, v in s.items() if n != "records"} for k, s in sources.items()
            },
        )
        if self.integration_v2:
            prompt["integration_contract"] = dict(
                instruction=(
                    "Phân rã TẤT CẢ yêu cầu thành requirements độc lập. "
                    "Viết tiếng Việt. Giữ original text, từng chỉ tiêu/kỳ/đơn vị và kết luận. "
                    "Mỗi task phải có task_id, requirement_ids và depends_on:[task_id] nếu cần "
                    "tổng hợp liên nhánh. Giao kết luận liên nhánh cho một trong ba specialist "
                    "hiện có, sau task độc lập. Evidence được chia sẻ trong request; role không "
                    "cấm đọc nguồn khác domain. Tối đa 4 tasks, một supervisor call. "
                    "Không claim mọi yêu cầu đã đủ, không thay chỉ tiêu bằng mục gần giống. "
                    "Requirement không hỗ trợ vẫn giữ kind=unsupported. Mỗi requirement chỉ "
                    "một output; calculation dùng interpretation=true, "
                    "interpretation_topic=dynamic_calculation, required_indicators, "
                    "reasoning_operations, reasoning_periods; nhận xét dùng metric_meaning. "
                    "Khi inventory có metric đúng định nghĩa, chọn source metric đó thay vì "
                    "yêu cầu Specialist tự tính lại từ facts. Chỉ khai dynamic_calculation "
                    "khi chưa có metric phù hợp. "
                    "target_id là canonical item/formula trong inventory; requested_unit là "
                    "VND/ratio/percent hoặc null. Không quy % thành ratio. "
                    "answer_goal=value cho số liệu/phép tính; analysis cho nhận xét, synthesis "
                    "cho tổng hợp liên nhánh, limitation cho giới hạn. Phải có requirement riêng "
                    "cho yêu cầu nhận xét/tổng hợp/không suy diễn, giữ nguyên câu hỏi trong text. "
                    "Không thay nhận xét bằng định nghĩa công thức. Task tổng hợp phụ thuộc các "
                    "task nguồn và do một specialist hiện có đảm nhiệm; không thêm chỉ tiêu/năm. "
                    "Trả {requirements:[...],tasks:[...]}, không field khác."
                ),
                requirement_schema=IntegrationRequirement.model_json_schema(),
                task_schema=LiteTask.model_json_schema(),
            )
            contract = prompt.pop("integration_contract")
            prompt["instruction"] = contract.pop("instruction")
            prompt.update(contract)
        payload = json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))
        if len(payload) + len(question) > 48000:
            return fallback_plan(question, sources), metadata, ["supervisor_payload_limit_fallback"]
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m5-lite-supervisor-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(role="system", content=payload),
                Message(role="user", content=question),
            ],
            generation=GenerationParameters(
                temperature=0.0, max_output_tokens=2500 if self.integration_v2 else 900
            ),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=context.provider_timeout_seconds),
        )
        response = self.gateway.generate(request)
        metadata = PlannerLLMMetadata(
            calls=1,
            model=context.model,
            status=response.status,
            usage=response.usage,
            cost=response.cost,
            error=response.error,
            provenance=response.provenance,
        )
        if response.status != "success" or not isinstance(response.output, JSONOutput):
            if self.integration_v2:
                return LitePlan(), metadata, ["supervisor_provider_failure"]
            return fallback_plan(question, sources), metadata, ["supervisor_provider_failure"]
        if self.integration_v2:
            plan, errors = integration_plan(response.output.payload)
            return plan, metadata, errors
        try:
            plan = LitePlan.model_validate(response.output.payload)
        except ValidationError:
            return fallback_plan(question, sources), metadata, ["supervisor_invalid_json_fallback"]
        return plan, metadata, []


class FinancialLiteOrchestrator:
    def __init__(
        self,
        catalog,
        gateway=None,
        *,
        supervisor=None,
        graph_enabled=True,
        composition=None,
        document_repository=None,
        integration_v2=False,
    ):
        self.catalog, self.gateway = catalog, gateway
        self.integration_v2 = integration_v2
        self.supervisor = supervisor or SupervisorLite(gateway, integration_v2=integration_v2)
        self.graph_enabled = graph_enabled
        self.composition, self.document_repository = composition, document_repository

    def _graph_tools(self, context):
        manifest = self.composition
        if manifest is not None and self.document_repository is not None:
            from ..evidence.composition_graph import CompositionGraphView

            if (
                manifest.financial_snapshot.document_id,
                manifest.financial_snapshot.snapshot_id,
            ) != (context.document_id, context.snapshot_id):
                raise ValueError("composition_financial_snapshot_mismatch")
            return GraphRetrievalTools(
                CompositionGraphView(
                    manifest,
                    self.document_repository,
                    self.catalog,
                    document_id=manifest.logical_document_id,
                    composition_id=manifest.composition_id,
                )
            )
        return GraphRetrievalTools.from_catalog(
            self.catalog, document_id=context.document_id, snapshot_id=context.snapshot_id
        )

    def run_document(self, *args, **kwargs):
        raise ValueError("m5_lite_financial_scope_only")

    def reset_request(self):
        pass

    def _specialist(self, task, upstream, question, context):
        module, proposal = DOMAINS[task.specialist]
        render = module._render
        if self.integration_v2:
            from .specialist_common import _number

            def render(selected, evidence):
                if selected.meaning == "fact_value" and selected.kind == evidence.kind == "fact":
                    if selected.period != evidence.period:
                        raise ValueError("wrong_period")
                    label = "tại ngày" if len(evidence.period) > 4 else "kỳ"
                    scale = f" (hệ số đơn vị {evidence.scale})" if evidence.scale != "1" else ""
                    return (
                        f"{evidence.label} {label} {evidence.period} là "
                        f"{_number(evidence.value)} {evidence.unit}{scale}."
                    )
                return module._render(selected, evidence)

        result = SpecialistResult(
            question=question, role=task.specialist, upstream_status=upstream.status
        )
        roles = {
            "profitability": {"gross_margin": "revenue", "revenue_yoy": "current_revenue"},
            "liquidity_and_leverage": {"debt_to_assets": "assets"},
        }.get(task.specialist, {})
        item_labels = dict(module.ITEM_LABELS)
        metric_labels = dict(getattr(module, "METRIC_LABELS", {}))
        if self.integration_v2:
            item_labels = {
                key: value
                for domain, _ in DOMAINS.values()
                for key, value in domain.ITEM_LABELS.items()
            }
            metric_labels = {
                key: value
                for domain, _ in DOMAINS.values()
                for key, value in getattr(domain, "METRIC_LABELS", {}).items()
            }
            roles.update(
                gross_margin="revenue", revenue_yoy="current_revenue", debt_to_assets="assets"
            )
        for match in upstream.evidence_bundle.facts:
            record = match.record
            if record.canonical_item_id:
                item_labels.setdefault(
                    record.canonical_item_id,
                    record.context.raw_item_label or record.canonical_item_id,
                )
        select_evidence(
            upstream,
            result,
            item_labels=item_labels,
            metric_labels=metric_labels,
            period_roles=roles,
            balance_sheet=task.specialist == "liquidity_and_leverage",
        )
        if self.integration_v2:
            for evidence in result.supporting_evidence:
                evidence.evidence_id = evidence_handle(evidence)
        choices = _numeric_proposals(result.supporting_evidence)
        by_handle = {choice["evidence_id"]: choice for choice in choices}
        graph_context = compact_graph_context(
            upstream.evidence_bundle.graph_contexts, result.supporting_evidence
        )
        if graph_context:
            result.trace.append(
                SpecialistTrace(
                    stage="selection",
                    outcome="graph_context_supplied",
                    reasons=[json.dumps(graph_context, ensure_ascii=False)],
                )
            )

        class LiteProposal(proposal):
            @model_validator(mode="before")
            @classmethod
            def expand_handle(cls, value):
                # JSON shorthand selects an existing backend fact/calculation;
                # unknown handles still fail ordinary candidate validation.
                return by_handle.get(value, value) if isinstance(value, str) else value

        prompt = dict(
            instruction=(
                "Bạn là Specialist tài chính. Dùng evidence liên quan để trả lời objective. "
                "JSON {claims:[],missing_information:[],analyses:[]}. claims chọn objects hoặc "
                "evidence_id từ numeric_choices; "
                "không tự tính số. Mọi so sánh, diễn giải, nhận xét hay giới hạn có căn cứ phải ở "
                "analyses, không đặt trong claims. Khi objective yêu cầu phân tích, tạo analyses "
                "có ý nghĩa từ evidence, không chỉ liệt kê số liệu. analyses [{statement,evidence_ids,goal,operations:[],"
                "assumptions:[],limitations:[],claim_type:reasoned_conclusion}]. "
                "Được phân tích quan hệ, so sánh và nêu giới hạn dựa trên nguồn, không chỉ điền số. "
                "Phép tính mới chỉ khai báo operations để Financial Calculator thực thi: "
                "{operation_id,operator,inputs:[evidence_id hoặc operation_id],period_relation}. "
                "operator: sum,subtract,ratio,percentage_change,mean,greater,less,equal; period_relation "
                "same hoặc across_periods. Không bịa giá trị/nguồn, không ACCEPT claim. "
                "Các metric đã được Calculator tính có thể dùng trực tiếp làm evidence cho analyses "
                "với operations rỗng. Không tính lại metric hoặc dùng metric làm DynamicOperand. "
                "Source caveats do backend giữ trong sources/caveats; không chép chúng vào "
                "analysis.limitations (chỉ giới hạn riêng của nhận định, tối đa 8). "
                "Nếu dùng facts để tính, evidence_ids phải chứa các fact operands của operations; "
                "chỉ tham chiếu evidence đã được giao hoặc operation trước đó. "
                "Nếu không có evidence nhân quả, phân biệt biến động quan sát với nguyên nhân chưa chứng minh. "
                "Không khẳng định thu hẹp hoạt động, tái cơ cấu, tuân thủ chuẩn mực, đã kiểm toán hay "
                "số liệu phản ánh chính xác thực tế chỉ từ biến động các chỉ tiêu. Assumptions không "
                "được biến thành sự thật; tránh giả định không cần thiết. Tách các nhận định độc lập "
                "thành analyses riêng để thiếu bằng chứng cho một ý không làm mất các ý có căn cứ. "
                "Không đưa evidence_id vào statement. Không đưa hằng số/ngưỡng so sánh vào nhận định "
                "nếu không có trong evidence hoặc kết quả Calculator. Dùng claim_type=reasoned_conclusion "
                "cho diễn giải; derived_fact chỉ dành cho phép tính thuần túy không assumptions. "
                "Chỉ trả missing_information cho objective của Specialist này, không báo thiếu phần "
                "được giao Specialist khác. "
                "percentage_change có inputs=[kỳ mục tiêu,kỳ gốc] để tính (mục tiêu/gốc-1)*100. "
                "Trả phần có căn cứ khi thiếu phần khác. M6 sẽ xác minh mọi candidate."
                " Xem xét từng chỉ tiêu trong câu hỏi/objective; khi so sánh hai kỳ, nêu hướng "
                "và mức biến động được yêu cầu, dùng subtract và percentage_change trên facts "
                "nếu chưa có metric tương ứng. Không bỏ chỉ tiêu còn lại sau khi tính chỉ tiêu đầu. "
                "source_metadata là binding nguồn đã có: linked không phải missing; page-level "
                "hoặc uncertain vẫn có trang nhưng giới hạn độ chính xác. Selector tồn tại không "
                "tự chứng minh cell-level precision. Chỉ báo thiếu trang khi binding thực sự thiếu. "
                "Nếu được hỏi phân biệt relations, giải thích từng loại có trong graph_context: "
                "from_source là nguồn gốc, associated_with là association selector, used_in là "
                "vai trò toán hạng, same_extraction_context chỉ là cùng ngữ cảnh trích xuất."
                " graph_context giữ liên kết nguồn/operand; structural_only và contextual_only "
                "không phải semantic support hoặc nhân quả. Chỉ dùng evidence_ids số thực trong analyses. "
                "Nếu một quan hệ graph giúp chọn nguồn hoặc diễn giải, ghi handle G tương ứng và "
                "cách dùng cụ thể trong goal của analysis; không dùng thì không ghi. Không đưa G vào statement."
            ),
            graph_context=graph_context,
            objective=task.objective,
            user_question=question,
            analysis_schema=AnalysisProposal.model_json_schema(),
            numeric_choices=choices,
            evidence=[
                dict(
                    id=e.evidence_id,
                    label=e.label,
                    value=e.value,
                    unit=e.unit,
                    scale=e.scale,
                    period=e.period,
                    operand_periods=e.operand_periods,
                    source_metadata=source_projection(e),
                )
                for e in result.supporting_evidence
            ],
        )
        if self.integration_v2:
            prompt["assigned_requirements"] = [
                r.model_dump(mode="json")
                for r in self.workspace.requirements
                if r.requirement_id in task.requirement_ids
            ]
            prompt["shared_tasks"] = {
                key: dict(
                    status=state["status"],
                    requirement_ids=state["requirement_ids"],
                    candidate_statements=list(dict.fromkeys(state.get("candidate_statements", []))),
                    candidate_proofs=[
                        dict(
                            operations=[s["operation"] for s in proof["calculation"]["steps"]],
                            results=[
                                {k: s[k] for k in ("result", "unit", "periods")}
                                for s in proof["calculation"]["steps"]
                            ],
                        )
                        for proof in state.get("candidate_proofs", [])
                    ],
                )
                for key, state in self.workspace.tasks.items()
                if key in task.depends_on
            }
            prompt["user_question"] = self.workspace.question
            analysis_schema = AnalysisProposal.model_json_schema()
            narrative_only = bool(prompt["assigned_requirements"]) and all(
                r["answer_goal"] != "value" for r in prompt["assigned_requirements"]
            )
            required_items = {
                item
                for r in prompt["assigned_requirements"]
                if r["answer_goal"] != "value"
                for item in r["required_indicators"]
            }
            prompt["required_evidence_ids"] = [
                e.evidence_id
                for e in result.supporting_evidence
                if e.kind == "fact" and e.canonical_item_id in required_items
            ]
            prompt["response_schema"] = dict(
                type="object",
                properties=dict(
                    claims=dict(
                        type="array",
                        items=dict(enum=list(by_handle)),
                        maxItems=0 if narrative_only else 32,
                    ),
                    analyses=dict(
                        type="array", items=analysis_schema, maxItems=1 if narrative_only else 8
                    ),
                    missing_information=dict(type="array", items=dict(type="string")),
                ),
                required=["claims", "analyses", "missing_information"],
                additionalProperties=False,
            )
            prompt["response_schema"]["$defs"] = analysis_schema.pop("$defs", {})
            # V2 has typed goals and shared evidence. A second, legacy instruction
            # manual mixed numeric generation with commentary and obscured that
            # distinction for the small model. Give one task-local contract.
            prompt["instruction"] = (
                "Bạn là Specialist tài chính. Chỉ giải assigned_requirements từ evidence. "
                "Trả đúng JSON {claims:[],analyses:[],missing_information:[]}. "
                "1. answer_goal=value: chọn evidence_id trong numeric_choices vào claims. "
                "Nếu cần tính mới, đặt analysis claim_type=derived_fact, evidence_ids là "
                "facts đầu vào, operations theo analysis_schema; backend tính và viết kết quả. "
                "percentage_change dùng [kỳ mục tiêu,kỳ gốc], across_periods; ratio/subtract "
                "giữ đúng thứ tự toán hạng. Không tự viết kết quả số trong statement. "
                "2. answer_goal=analysis/synthesis/limitation: viết MỘT analysis ngắn đáp ứng "
                "đồng thời các mục tiêu nhận xét được giao. statement phải liên kết các nhánh "
                "bằng quan sát cụ thể, sau đó nêu giới hạn kết luận. Dẫn evidence_ids từ TẤT CẢ "
                "nhánh được nhận xét; claim_type=reasoned_conclusion, operations=[]. "
                "evidence_ids phải chứa required_evidence_ids để M6 kiểm đủ các nhánh. "
                "Không lặp số hoặc công thức; mô tả hướng biến động, dấu hoặc quan hệ từ "
                "evidence/shared proofs. Không thay tổng hợp bằng các analyses riêng từng nhánh. "
                "Không suy cao/thấp nếu thiếu chuẩn, nguyên nhân, ổn định dài hạn hoặc khả năng "
                "thanh toán tương lai từ một kỳ. Giới hạn phải gắn với kết luận được hỏi. "
                "goal dùng nguyên text requirement, limitations chỉ chứa giới hạn nhận định, "
                "không chép source caveats. Không thêm năm/chỉ tiêu. "
                "shared_tasks là candidates, không phải verdict; M6 kiểm lại mọi nhận định. "
                "Đọc dấu/quan hệ của facts và shared proofs: dương chỉ có nghĩa thu vào ròng, "
                "không có nghĩa ổn định hay tốt; chênh lệch âm chỉ là thiếu hụt tại ngày đó, "
                "không phải giảm so với kỳ trước. Không gọi tỷ trọng nợ cao/thấp khi thiếu chuẩn. "
                "Khi ghép số dư tại ngày cuối năm và dòng tiền cả năm, nói rõ hai thời điểm đo "
                "khác nhau: dòng tiền dương không tự xóa thiếu hụt vốn lưu động hoặc đảm bảo "
                "trả nợ tương lai. Doanh thu tăng, cơ cấu tài trợ và dòng tiền là các khía cạnh "
                "riêng, không dùng một khía cạnh để kết luận sức khỏe tổng thể. Chỉ nêu quan sát "
                "này nếu evidence tương ứng thực sự có. Không bịa xu hướng hay nguyên nhân. "
                "Nguồn page-level vẫn có trang; graph chỉ thể hiện nguồn/cấu trúc, không nhân quả. "
                "Thiếu evidence chỉ báo missing_information trong scope được giao."
            )
        deterministic = self.gateway is None or context.mode == "deterministic"
        observation = None
        if self.integration_v2:
            assigned = [
                r for r in self.workspace.requirements if r.requirement_id in task.requirement_ids
            ]
            observation = observation_proposal(
                assigned, result.supporting_evidence, self.workspace.question
            )
            if observation is not None:
                deterministic = True
            # The numeric path already emits these exact facts/approved metrics.
            # Reserve generation for new arithmetic or actual interpretation.
            if assigned and all(
                r.answer_goal == "value"
                and r.interpretation_topic != "dynamic_calculation"
                and r.target_id
                and any(
                    r.target_id
                    == (
                        e.canonical_item_id
                        if r.kind == "fact"
                        else e.calculation.formula_id
                        if e.calculation
                        else None
                    )
                    and (not r.period or r.period == e.period)
                    for e in result.supporting_evidence
                )
                for r in assigned
            ):
                deterministic = True
        if len(json.dumps(prompt, ensure_ascii=False)) + len(question) > 48000:
            deterministic = True
            result.limitations.append("specialist_payload_limit_numeric_fallback")
        generate_candidates(
            gateway=self.gateway,
            model=context.model,
            result=result,
            prompt=prompt,
            proposal_type=LiteProposal,
            render=render,
            prefix="m5-lite-" + task.specialist,
            deterministic=deterministic,
            emit_derived=True,
            normalize_payload=normalize_candidate_envelope if self.integration_v2 else None,
            operation_inputs_only=self.integration_v2,
            candidate_analyses=[observation] if observation is not None else None,
        )
        for candidate in result.candidates:
            if candidate.reasoning:
                for relation in graph_context:
                    if re.search(r"\b" + relation["id"] + r"\b", candidate.reasoning.goal):
                        result.trace.append(
                            SpecialistTrace(
                                stage="grounding",
                                outcome="graph_use_reported_pending_M6",
                                evidence_id=candidate.candidate_id,
                                reasons=[relation["id"], candidate.reasoning.goal],
                            )
                        )
        if self.integration_v2:
            # Numeric source candidates survive a failed/empty prose branch.
            numeric = SpecialistResult(
                question=task.objective,
                role=task.specialist,
                upstream_status=upstream.status,
                supporting_evidence=result.supporting_evidence,
            )
            generate_candidates(
                gateway=None,
                model=context.model,
                result=numeric,
                prompt={},
                proposal_type=proposal,
                render=render,
                prefix="m5-v2-numeric-" + task.specialist,
                deterministic=True,
            )
            seen = {c.content for c in result.candidates}
            result.candidates.extend(c for c in numeric.candidates if c.content not in seen)
            if result.candidates and result.status == "abstained":
                result.status = "partial"
        return result

    def run(self, *, question, context):
        started = perf_counter()
        output = OrchestrationResult(question=question, context=context.model_copy(deep=True))
        if not all((context.company_id, context.document_id, context.snapshot_id)):
            output.status = "clarification_required"
            output.stop_conditions = ["trusted_context_required"]
            return output
        # The pinned filing contains comparative columns. Let the semantic plan
        # select supporting periods; a target year is not an operand-year filter.
        retrieval_context = context.model_copy(update={"period": None})
        sources = inventory(self.catalog, retrieval_context)
        plan, metadata, gaps = self.supervisor.plan(question, context, sources)
        output.usage.stages["planning"] = metadata
        output.trace.append(
            StageExecution(
                stage="planning", outcome="single_plan", reasons=[plan.model_dump_json(), *gaps]
            )
        )
        output.caveats.extend(gaps)
        workspace, prepared = None, []
        if self.integration_v2:
            retain_requested_periods(plan, question)
            preserve_explicit_facts(plan, question, sources)
            targets = resolve_requirements(plan, sources)
            preserve_answer_goal(plan, question, targets)
            requirements = plan.requirements or [
                IntegrationRequirement(
                    requirement_id="R-unresolved", text=question, kind="unsupported"
                )
            ]
            workspace = self.workspace = IntegrationWorkspace(requirements)
            workspace.targets = targets
            workspace.question = question
            if gaps:
                output.errors.append(
                    OrchestrationError(stage="planning", code="integration_plan_incomplete")
                )
                output.stop_conditions.extend(gaps)
        tools = FinancialRetrievalTools(self.catalog)
        calculator = FinancialCalculator(self.catalog)
        evidence_tools = EvidenceRetrievalTools(self.catalog)
        graph_tools, graph_error = None, None
        if self.graph_enabled and any(t.use_graph for t in plan.tasks):
            try:
                graph_tools = self._graph_tools(context)
            except ValueError as error:
                graph_error = str(error)
        all_upstream = SupervisorResult(
            plan_id=None,
            status="completed",
            initial_validation=PlanValidation(
                structurally_valid=True, execution_eligible=True, disposition="valid"
            ),
        )
        output.supervisor_result = all_upstream
        output.routing_decision = RoutingDecision(
            question=question,
            status="routed",
            selected_roles=list(dict.fromkeys(t.specialist for t in plan.tasks)),
        )
        for index, task in enumerate(plan.tasks):
            execution = SpecialistExecution(
                execution_id=task.task_id or f"m5-lite-{index}",
                role=task.specialist,
                assigned_requirement_ids=task.requirement_ids,
            )
            output.specialist_executions.append(execution)
            if workspace is not None:
                workspace.tasks[execution.execution_id] = dict(
                    requirement_ids=task.requirement_ids,
                    depends_on=task.depends_on,
                    status="retrieving",
                )
            bundle = ExecutionEvidenceBundle()
            upstream = all_upstream.model_copy(update={"evidence_bundle": bundle}, deep=True)

            def call(operation, request, function):
                begin = perf_counter()
                try:
                    response = function(request)
                except Exception as error:
                    all_upstream.tool_trace.append(
                        StepExecutionResult(
                            step_id=f"lite-tool-{len(all_upstream.tool_trace)}",
                            operation=operation,
                            bound_request=request.model_dump(mode="json"),
                            final_state="failed",
                            reasons=["tool_execution_error", type(error).__name__],
                            latency_ms=(perf_counter() - begin) * 1000,
                        )
                    )
                    raise
                event = StepExecutionResult(
                    step_id=f"lite-tool-{len(all_upstream.tool_trace)}",
                    operation=operation,
                    bound_request=request.model_dump(mode="json"),
                    response=response,
                    final_state="completed",
                    latency_ms=(perf_counter() - begin) * 1000,
                )
                all_upstream.tool_trace.append(event)
                return response

            def retrieve(fact, bundle=bundle):
                request = GetFinancialFactRequest(
                    document_id=context.document_id,
                    snapshot_id=context.snapshot_id,
                    local_observation_id=fact.local_observation_id,
                )
                response = call("get_financial_fact", request, tools.get_financial_fact)
                if response.status != "found":
                    bundle.limitations.extend(
                        response.reasons or ["financial_evidence_" + response.status]
                    )
                for match in response.matches:
                    if match.record.company_id != context.company_id:
                        continue
                    if match not in bundle.facts:
                        bundle.facts.append(match)
                        bundle.citations.extend(
                            c for c in match.citations if c not in bundle.citations
                        )
                        sources_response = call(
                            "get_evidence_sources",
                            GetEvidenceSourcesRequest(
                                reference=match.reference,
                                document_id=context.document_id,
                                snapshot_id=context.snapshot_id,
                            ),
                            evidence_tools.get_evidence_sources,
                        )
                        bundle.sources_and_lineage.append(sources_response)

            try:
                selected = task.sources or next(
                    (
                        t.sources
                        for t in fallback_plan(task.objective, sources).tasks
                        if t.specialist == task.specialist
                    ),
                    [],
                )
                for handle in dict.fromkeys(selected):
                    resolved = handle
                    if self.integration_v2:
                        periods = {
                            period
                            for r in workspace.requirements
                            if r.requirement_id in task.requirement_ids
                            for period in [r.period, *r.reasoning_periods]
                            if period
                        }
                        for rid in task.requirement_ids:
                            target = workspace.targets.get(rid)
                            if target and target["kind"] == "metric":
                                periods.update(
                                    target["records"][0].request.operand_periods.values()
                                )
                        resolved, resolution_error = resolve_source(handle, sources, periods)
                        if resolution_error:
                            bundle.limitations.append(resolution_error + ":" + handle)
                            continue
                    source = sources.get(resolved)
                    if source is None or (
                        not self.integration_v2 and task.specialist not in source["roles"]
                    ):
                        bundle.limitations.append("unknown_or_foreign_source:" + handle)
                        continue
                    for record in source["records"]:
                        if source["kind"] == "fact":
                            retrieve(record)
                        else:
                            calc = call(
                                "calculate_financial_metric",
                                CalculateFinancialMetricRequest(
                                    metric_id=record.metric_id,
                                    document_id=context.document_id,
                                    snapshot_id=context.snapshot_id,
                                ),
                                calculator.calculate_financial_metric,
                            )
                            bundle.calculations.append(calc)
                            if calc.trace:
                                for operand in calc.trace.operands:
                                    for fact in self.catalog.facts:
                                        if fact.observation_identity() == operand.observation:
                                            retrieve(fact)
                bundle.claim_fact_references = [f.reference for f in bundle.facts]
                if self.graph_enabled and task.use_graph:
                    starts = list(
                        dict.fromkeys(
                            [c.metric_id for c in bundle.calculations if c.metric_id]
                            + [
                                graph_id(
                                    "source_fact", f.record.observation_identity().model_dump()
                                )
                                for f in bundle.facts
                            ]
                        )
                    )[:6]
                    if not starts:
                        bundle.limitations.append("graph_no_valid_starting_nodes")
                    for node_id in starts:
                        request = (
                            GetGraphContextRequest(
                                document_id=self.composition.logical_document_id,
                                composition_id=self.composition.composition_id,
                                node_id=node_id,
                                depth=2,
                                limit=8,
                                relations=(
                                    [
                                        "used_in",
                                        "from_source",
                                        "same_extraction_context",
                                        "associated_with",
                                    ]
                                    if node_id.startswith("derived_metric:")
                                    else [
                                        "from_source",
                                        "same_extraction_context",
                                        "associated_with",
                                        "used_in",
                                    ]
                                ),
                            )
                            if self.composition is not None and graph_tools is not None
                            else GetSnapshotGraphContextRequest(
                                document_id=context.document_id,
                                snapshot_id=context.snapshot_id,
                                node_id=node_id,
                                depth=2,
                                limit=8,
                            )
                        )
                        response = call(
                            "get_graph_context",
                            request,
                            graph_tools.get_graph_context
                            if graph_tools
                            else lambda r: GraphContextResponse(
                                request=r,
                                status="unavailable",
                                reasons=[graph_error or "graph_unavailable"],
                            ),
                        )
                        bundle.graph_contexts.append(response)
                        if response.status != "found":
                            bundle.limitations.extend(response.reasons)
                if workspace is not None:
                    workspace.merge(bundle)
                    workspace.tasks[execution.execution_id]["status"] = "retrieved"
                    prepared.append((task, execution, bundle))
                    continue
                upstream.status = "partial" if bundle.limitations else "completed"
                result = self._specialist(task, upstream, question, context)
                result.limitations.extend(bundle.limitations)
                execution.result, execution.llm = result, result.llm
                execution.status = result.status
                output.usage.stages[f"specialist_{index}_{task.specialist}"] = result.llm
                output.missing_evidence.extend(result.missing_evidence + result.limitations)
                all_upstream.evidence_bundle.facts.extend(bundle.facts)
                all_upstream.evidence_bundle.calculations.extend(bundle.calculations)
                all_upstream.evidence_bundle.citations.extend(bundle.citations)
                all_upstream.evidence_bundle.graph_contexts.extend(bundle.graph_contexts)
            except Exception as error:
                execution.status = "failed"
                execution.error = OrchestrationError(
                    stage="specialist_execution",
                    code="specialist_execution_failed",
                    error_type=type(error).__name__,
                    role=task.specialist,
                )
                output.errors.append(execution.error)
                if workspace is not None:
                    workspace.tasks[execution.execution_id]["status"] = "technical_error"
            output.trace.append(
                StageExecution(
                    stage="specialist_execution",
                    outcome=execution.status,
                    role=task.specialist,
                    reasons=[task.objective, *bundle.limitations],
                )
            )
        if workspace is not None:
            all_upstream.evidence_bundle = workspace.evidence
            for task, execution, bundle in prepared:
                state = workspace.tasks[execution.execution_id]
                if not task.requirement_ids or any(
                    workspace.tasks.get(key, {}).get("status") not in {"generated", "partial"}
                    for key in task.depends_on
                ):
                    state["status"] = "dependency_unavailable"
                    execution.missing_requirement_ids = task.requirement_ids
                    continue
                try:
                    upstream = all_upstream.model_copy(deep=True)
                    upstream.status = "partial" if bundle.limitations else "completed"
                    result = self._specialist(task, upstream, task.objective, context)
                    execution.result, execution.llm = result, result.llm
                    execution.status = result.status
                    state.update(
                        status=result.status,
                        candidate_statements=[c.content for c in result.candidates],
                        candidate_proofs=[
                            c.reasoning.model_dump(mode="json")
                            for c in result.candidates
                            if c.reasoning and c.reasoning.calculation
                        ],
                        missing_inputs=result.missing_evidence,
                    )
                    output.usage.stages[execution.execution_id] = result.llm
                    output.missing_evidence.extend(
                        result.missing_evidence + result.limitations + bundle.limitations
                    )
                    if "specialist_processing_failure" in result.limitations:
                        output.errors.append(
                            OrchestrationError(
                                stage="specialist_execution",
                                code="specialist_output_invalid",
                                role=task.specialist,
                            )
                        )
                except Exception as error:
                    state["status"] = "technical_error"
                    execution.error = OrchestrationError(
                        stage="specialist_execution",
                        code="specialist_execution_failed",
                        error_type=type(error).__name__,
                        role=task.specialist,
                    )
                    output.errors.append(execution.error)
                output.trace.append(
                    StageExecution(
                        stage="specialist_execution",
                        outcome=execution.status,
                        role=task.specialist,
                        reasons=[task.objective, *bundle.limitations],
                    )
                )
        output.candidates, output.conflicts = aggregate_candidates(output.specialist_executions)
        if workspace is not None:
            output.integration_context = workspace.export(output.candidates)
        output.status = (
            (
                "partial"
                if output.errors
                or output.missing_evidence
                or gaps
                or any(e.status != "generated" for e in output.specialist_executions)
                else "completed"
            )
            if output.candidates
            else "blocked"
        )
        output.trace.append(StageExecution(stage="candidate_aggregation", outcome=output.status))
        values = list(output.usage.stages.values())
        output.usage.calls = sum(m.calls for m in values)
        output.usage.calls_with_unknown_tokens = sum(
            m.calls for m in values if m.calls and (m.usage is None or m.usage.total_tokens is None)
        )
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            known = [
                getattr(m.usage, key)
                for m in values
                if m.usage and getattr(m.usage, key) is not None
            ]
            setattr(output.usage, key, sum(known) if known else None)
        output.latency_ms = (perf_counter() - started) * 1000
        return output
