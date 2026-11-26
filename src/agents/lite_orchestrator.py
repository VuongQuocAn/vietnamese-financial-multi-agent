"""One Coordinator and tool-using Specialists; M6 alone verifies candidates."""

import json
import re
import traceback
from copy import deepcopy
from sqlite3 import Error as SQLiteError
from time import perf_counter
from uuid import uuid4

from pydantic import Field

from ..accounting.arithmetic import ARITHMETIC_RULES
from ..accounting.context_resolution import resolve_financial_context
from ..accounting.contracts import FinancialModel
from ..accounting.item_mapping import _label
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_schema_validation import schema_issues
from ..core.prompt_payload import compact_prompt, document_view
from ..evidence.graph import graph_id
from ..evidence.json_catalog import (
    json_cell_observation,
    json_evidence_bound,
    json_filing_issuer,
    json_page_context,
    json_table_cells,
)
from ..evidence.search import (
    DocumentSearchMatch,
    DocumentSearchResponse,
    SearchDocumentEvidenceRequest,
    _cells,
    normalize_search,
    rank_search_candidates,
)
from ..tools.evidence_retrieval import (
    EvidenceRetrievalTools,
    FindDocumentEvidenceRequest,
    GetEvidenceItemRequest,
    GetEvidenceSourcesRequest,
)
from ..tools.financial_calculator import (
    CalculateFinancialMetricRequest,
    DynamicOperation,
    FinancialCalculator,
)
from ..tools.financial_retrieval import (
    FinancialRetrievalTools,
    FindFinancialFactsRequest,
    GetFinancialFactRequest,
)
from ..tools.graph_retrieval import (
    GetGraphContextRequest,
    GetSnapshotGraphContextRequest,
    GraphRetrievalTools,
)
from ..tools.hybrid_rag import HybridRAGTool, SearchHybridEvidenceRequest
from ..tools.question_understanding import EXTRA_ALIASES, FORMULA_LABELS, ITEM_RULES
from . import indexed_reasoning
from .contracts import PlanValidation, SpecialistRole
from .document_qa import document_candidates, document_operations
from .document_qa_contracts import DocumentEvidenceBundle, DocumentRequirement
from .evidence_coordination import content_digest, observation
from .integration_workspace import (
    IntegrationRequirement,
    IntegrationWorkspace,
    QuestionRequirement,
    evidence_handle,
    expected_answer_set,
)
from .orchestration_contracts import (
    OrchestrationError,
    OrchestrationResult,
    SpecialistExecution,
    StageExecution,
)
from .orchestrator import _check_assignment, aggregate_candidates
from .planner_contracts import PlannerLLMMetadata
from .routing_contracts import RoutingDecision
from .specialist_common import (
    CALCULATION_OPERATORS,
    SPECIALIST_TOOLS_BY_ROLE,
    AnalysisProposal,
    ScalarProposal,
    SpecialistResult,
    _fact_error,
    _number,
    _numeric_proposals,
    bind_specialist_schema,
    check_requirement_mapping,
    formula_decision_schema,
    generate_candidates,
    indexed_calculation_schema,
    parse_specialist_output,
    project_reasoning_actions,
    select_evidence,
)
from .supervisor import ExecutionEvidenceBundle, StepExecutionResult, SupervisorResult

FINANCIAL_DATA_GUIDE = {
    "B01": "Bảng cân đối kế toán: số dư tại ngày; tài sản, nợ, vốn. Số dư không thay thế phát sinh trong kỳ dù nhãn gần giống.",
    "B02": "Kết quả hoạt động kinh doanh: doanh thu, chi phí, lãi/lỗ trong kỳ; phân biệt tổng và chi tiết, trước và sau các khoản điều chỉnh.",
    "B03": "Lưu chuyển tiền tệ: dòng tiền trong kỳ và số dư tiền đầu/cuối kỳ; dòng tiền không đồng nghĩa kết quả kinh doanh.",
    "B09": "Thuyết minh: chi tiết khoản mục, chính sách và giải thích. Chỉ lấy phần cần cho câu hỏi hoặc ngữ cảnh còn thiếu; không mặc định đọc toàn bộ.",
}


def _map_evidence_handles(value, mapping):
    """Request-local wire aliases; exact references only, never rewrite prose."""
    if isinstance(value, dict):
        return {mapping.get(k, k): _map_evidence_handles(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_evidence_handles(v, mapping) for v in value]
    return mapping.get(value, value) if isinstance(value, str) else value


def compact_graph_context(contexts, evidence):
    """Bounded relations; raw tool traces retain complete original records."""
    from ..evidence.composition_graph import node_reference

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
    task_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list, max_length=16)
    need_refs: list[str] = Field(default_factory=list, max_length=128)
    depends_on: list[str] = Field(default_factory=list, max_length=6)


class LitePlan(FinancialModel):
    tasks: list[LiteTask] = Field(default_factory=list, max_length=6)
    requirements: list[QuestionRequirement | IntegrationRequirement] = Field(
        default_factory=list, max_length=16
    )
    blocked_tasks: dict[str, str] = Field(default_factory=dict, exclude=True)
    scheduler_task_ids: list[str] = Field(default_factory=list, exclude=True)
    projected_task_id: str | None = Field(default=None, exclude=True)


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
            or scope.evidence_status not in {"confirmed", "json_bound"}
            or scope.reporting_scope != context.reporting_scope
        ):
            continue
        if years and (fact.context.period or "")[:4] not in years:
            continue
        key = ("fact", fact.canonical_item_id or fact.local_observation_id, fact.context.period)
        entry = entries.setdefault(
            key,
            dict(
                kind="fact",
                item=fact.canonical_item_id,
                period=fact.context.period,
                label=fact.context.raw_item_label or fact.canonical_item_id,
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
        if metric.definition.name not in FORMULA_LABELS:
            continue
        if years and max(metric.request.operand_periods.values())[:4] not in years:
            continue
        key = ("metric", metric.metric_id)
        entries[key] = dict(
            kind="metric",
            item=metric.definition.name,
            period=max(metric.request.operand_periods.values()),
            label=FORMULA_LABELS[metric.definition.name],
            records=[metric],
        )
    return {f"S{i}": value for i, value in enumerate(entries.values(), 1)}


def _catalog_item(fact, label, rule_labels):
    """Use the same exact statement/code/label binding for EOs and formula roles."""
    if fact.canonical_item_id:
        return fact.canonical_item_id
    matches = [
        key
        for key, rule in ITEM_RULES.items()
        if (fact.context.statement_type, fact.source_item_code)
        == (rule.statement_type, rule.observed_source_code)
        and label in rule_labels[key]
    ]
    return matches[0] if len(matches) == 1 else None


_CATALOG_LABELS = {
    key: {normalize_search(_label(alias, strip_ordinal=True)) for alias in rule.aliases}
    for key, rule in ITEM_RULES.items()
}
_PROFIT_BEFORE_TAX_EO_ALIAS = normalize_search("lợi nhuận kế toán trước thuế")


# Statement and row-code aliases for EO matching only. Each tuple starts with an
# exact source label. These rows need no canonical observation to identify them.
_EO_ROW_LABELS = {
    ("B02", "23"): (("trong do chi phi lai vay",), ("chi phi lai vay",)),
    ("B03", "21"): (
        (
            "tien chi de mua sam xay dung tscd va cac tsdh khac",
            "tien chi mua sam xay dung tscd va cac tai san dai han khac",
        ),
        ("chi phi mua sam xay dung tscd",),
    ),
    ("B03", "34"): (("tien tra no goc vay",), ("chi tra no goc vay",)),
    ("B03", "36"): (
        ("co tuc loi nhuan da tra cho chu so huu",),
        ("chi tra co tuc loi nhuan",),
    ),
}
_EO_ITEM_ALIASES = {
    "b03.operating_cash_flow": ("cfo",),
    "b03.opening_cash": ("tien dau nam",),
    "b02.profit_before_tax": (_PROFIT_BEFORE_TAX_EO_ALIAS,),
}
_EO_CATALOG_LABELS = {
    item: labels
    | {normalize_search(item), *_EO_ITEM_ALIASES.get(item, ())}
    | {
        alias
        for alias in map(normalize_search, EXTRA_ALIASES.get(item, ()))
        if not any(
            other == alias or other.startswith(alias + " ")
            for key, other_labels in _CATALOG_LABELS.items()
            if key != item
            for other in other_labels
        )
    }
    for item, labels in _CATALOG_LABELS.items()
}
_EO_SCOPED_LABELS = {label for names in _EO_CATALOG_LABELS.values() for label in names} | {
    label for _, aliases in _EO_ROW_LABELS.values() for label in aliases
}


def _eo_fields(
    *,
    label,
    statement,
    code,
    period,
    unit,
    company,
    scope=None,
    table=None,
    title=None,
    group=None,
    item=None,
):
    raw = normalize_search(_label(label or "", strip_ordinal=True))
    printed = re.sub(r"\s*\([0-9=+*/ .\-\u2212]+\)\s*$", "", label or "")
    printed = normalize_search(_label(printed, strip_ordinal=True))
    # A catalog label and its abbreviation are scoped by their accounting row.
    # An observed label alone cannot override an explicitly conflicting row code.
    labels = {raw, printed}
    row_items = [
        key
        for key, rule in ITEM_RULES.items()
        if statement == rule.statement_type and code == rule.observed_source_code
    ]
    rules = [key for key in row_items if key == item or labels & _CATALOG_LABELS[key]]
    canonical = rules[0] if len(rules) == 1 else None
    if canonical is None and item in ITEM_RULES:
        rule = ITEM_RULES[item]
        if statement == rule.statement_type and not code and not rule.requires_source_code:
            canonical = item
    aliases = set()
    if canonical:
        aliases = _EO_CATALOG_LABELS[canonical]
    elif (row_labels := _EO_ROW_LABELS.get((statement, code))) and labels & set(row_labels[0]):
        aliases = set(row_labels[1])
    return {
        key: {normalize_search(value) for value in values if value}
        for key, values in dict(
            item=labels | aliases,
            period=[period],
            company=company,
            statement=[statement],
            code=[code],
            unit=[unit],
            scope=[scope],
            table=[table, title],
            group=[group],
            unmapped_items=row_items if canonical is None else [],
            scoped_items=aliases,
        ).items()
    }


def _need_match(ordinal, text, fields):
    """Exact matching of declared identity and metadata; no question interpretation."""
    prefix, _, body = text.partition(":")
    if prefix == f"N{ordinal}":
        pieces = [part.strip().partition("=") for part in body.split(",")]
        spec = {k.strip(): normalize_search(v) for k, equal, v in pieces if equal and v.strip()}
        if (
            len(spec) != len(pieces)
            or "period" not in spec
            or {"unmapped_items", "scoped_items"} & spec.keys()
            or not {"item", "code"} & spec.keys()
            or "code" in spec
            and "statement" not in spec
        ):
            return "item_mismatch"
        if any(
            v not in fields.get(k, ())
            for k, v in spec.items()
            if k not in {"company", "period", "item"}
        ):
            return "item_mismatch"
        if "item" in spec and spec["item"] not in fields["item"]:
            return (
                "canonical_mapping_missing"
                if spec["item"] in fields["unmapped_items"]
                else "item_mismatch"
            )
        if (
            spec.get("item") in _EO_SCOPED_LABELS
            and spec["item"] not in fields["scoped_items"]
            and not ({"table", "group", "code"} & spec.keys() and "statement" in spec)
        ):
            return "item_mismatch"
        if "company" in spec and spec["company"] not in fields["company"]:
            return "issuer_mismatch"
        if spec["period"] not in fields["period"]:
            return "period_unresolved"
        return None

    tail_words = {"cua", "tu", "ky", "nam", "bao", "cao", "don", "vi", "tien", "te"} | set(
        " ".join(
            v for key in ("period", "company", "statement", "unit") for v in fields[key]
        ).split()
    )
    text = normalize_search(text)
    if fields["period"] and any(
        text.startswith(label + " ")
        and (tail := text[len(label) + 1 :])
        and all(f" {p} " in f" {tail} " for p in fields["period"])
        and set(tail.split()) <= tail_words
        for label in fields["item"]
    ):
        return None
    return "item_mismatch"


def _assigned_needs(requirements, owned):
    return {
        ref: (i, text)
        for goal in requirements
        for i, (ref, text) in enumerate(zip(goal.need_refs, goal.evidence_needs, strict=True))
        if ref in owned
    }


def _fact_need_scope(requirements, owned, sources, issuer_aliases=None):
    """Index declared EOs against unique pinned observations."""
    assigned = _assigned_needs(requirements, owned)
    if not assigned:
        return {}, {}
    candidates, issues = {}, {}
    for source in sources.values():
        if source["kind"] != "fact":
            continue
        for fact in source["records"]:
            ctx = fact.context
            company = issuer_aliases
            if company is None:
                company = {
                    fact.company_id,
                    *(s.reference.anchor.page.symbol for s in fact.sources if s.reference),
                }
            row_path = fact.source_metadata.get("row_path") or []
            fields = _eo_fields(
                label=ctx.raw_item_label,
                statement=ctx.statement_type,
                code=fact.source_item_code,
                period=ctx.period,
                unit=fact.value.unit,
                company=company,
                scope=ctx.reporting_scope,
                table=fact.source_metadata.get("table_id"),
                group=row_path[-2] if len(row_path) > 1 else None,
                item=fact.canonical_item_id,
            )
            for ref, (ordinal, text) in assigned.items():
                reason = _need_match(ordinal, text, fields)
                if reason is None and issuer_aliases == set():
                    reason = "issuer_mismatch"
                if reason is None and not (fact.sources and fact.value.unit and ctx.scale):
                    reason = "provenance_insufficient"
                if reason != "item_mismatch":
                    issues.setdefault(fact.local_observation_id, {})[ref] = reason
                if reason is None:
                    candidates.setdefault(ref, set()).add(fact.local_observation_id)
    allowed = {}
    for ref, ids in candidates.items():
        if len(ids) == 1:
            allowed.setdefault(next(iter(ids)), []).append(ref)
        else:
            for identity in ids:
                issues[identity][ref] = "source_ambiguous"
    return allowed, issues


def _formula_options(evidence, facts, context):
    """Expose executable accounting rules for unambiguous, visible SourceFacts."""
    groups = {}
    for source in evidence:
        fact = facts.get(source.reference.observation)
        if fact is None or (fact.company_id, fact.document_id, fact.snapshot_id) != (
            context.company_id,
            context.document_id,
            context.snapshot_id,
        ):
            continue
        ctx = fact.context
        if (
            not ctx.period
            or (context.reporting_scope and ctx.reporting_scope != context.reporting_scope)
            or ctx.currency != source.unit
            or not source.citations
        ):
            continue
        label = normalize_search(_label(ctx.raw_item_label or "", strip_ordinal=True))
        item = _catalog_item(fact, label, _CATALOG_LABELS)
        scope = (ctx.statement_type, ctx.period_type, ctx.reporting_scope, ctx.period)
        groups.setdefault(scope, {}).setdefault(item, []).append(source)

    options = []
    for rule in ARITHMETIC_RULES:
        if rule.rule_id not in {"b01.total_assets", "b02.gross_profit"}:
            continue
        roles, signs = zip(*rule.operands, strict=True)
        operator = {(1, -1): "subtract", (1, 1): "add"}.get(signs)
        if not operator or rule.unavailable_reason:
            continue
        for (statement, period_type, scope, period), items in groups.items():
            if (
                statement != rule.statement_type
                or period_type not in rule.period_types
                or any(len(items.get(role, ())) != 1 for role in roles)
            ):
                continue
            sources = [items[role][0] for role in roles]
            if len({(source.unit, source.scale) for source in sources}) != 1:
                continue
            options.append(
                dict(
                    formula_id=rule.rule_id,
                    definition=rule.description,
                    version=rule.version,
                    operator=operator,
                    period=period,
                    period_type=period_type,
                    reporting_scope=scope,
                    unit=sources[0].unit,
                    scale=sources[0].scale,
                    operands={
                        role: source.evidence_id
                        for role, source in zip(roles, sources, strict=True)
                    },
                )
            )
    return options


def _task_evidence_view(objective, evidence, bindings, parents, sources, opened):
    """Defer owned observations only when receipts or parent proofs give a focused view."""
    text = f" {normalize_search(objective)} "
    periods = {
        row["period"]
        for row in evidence
        if row["period"] and f" {normalize_search(row['period'])} " in text
    }
    if parents:
        focus = {eid for proof in parents.values() for eid in proof["operands"]}
        focus.update(eid for refs in bindings.values() for eid in refs)
    elif len(periods) == 1 and all(bindings.values()):
        bound = {eid for refs in bindings.values() for eid in refs}
        focus = {row["id"] for row in evidence if row["period"] in periods and row["id"] in bound}
    else:
        focus = set()
    if not focus:
        return evidence, {}
    focus.update(opened)
    selectors = {
        source["records"][0].local_observation_id: handle
        for handle, source in sources.items()
        if source["kind"] == "fact" and len(source["records"]) == 1
    }
    shown, additional = [], {}
    for row in evidence:
        selector = selectors.get(row.get("observation_id"))
        if row["id"] in focus or not selector:
            shown.append(row)
        else:
            additional[selector] = {
                key: row[key] for key in ("label", "canonical_item_id", "period", "unit")
            }
    return shown, additional


def _atomic_calculation_ready(task, workspace, operand_count, bindings):
    """A sole consumer can use the Goal's explicit one-operator contract."""
    if len(task.requirement_ids) != 1 or operand_count < 2 or not all(bindings.values()):
        return False
    (rid,) = task.requirement_ids
    goal = next(r for r in workspace.requirements if r.requirement_id == rid)
    return (
        goal.kind == "metric"
        and goal.answer_goal == goal.aspect == "value"
        and not goal.interpretation
        and len(goal.reasoning_operations) == 1
        and goal.reasoning_operations[0] in CALCULATION_OPERATORS
        and set(task.need_refs) == set(goal.need_refs)
        and sum(
            row["role"] == "reasoning" and rid in row["requirement_ids"]
            for row in workspace.tasks.values()
        )
        == 1
    )


def _available_parent_proofs(calculations, evidence, context):
    """Use only complete proofs whose leaves still resolve to owned source facts."""
    references = {e.evidence_id: e.reference.model_dump(mode="json") for e in evidence}
    pins = (context.company_id, context.document_id, context.snapshot_id)
    return {
        ref: calc
        for ref, calc in calculations.items()
        if calc["steps"]
        and calc["operands"]
        and all(
            operand["reference"] == references.get(eid)
            and (operand["company_id"], operand["document_id"], operand["snapshot_id"]) == pins
            for eid, operand in calc["operands"].items()
        )
    }


def _parent_operand_scope(task, requirements, bindings, parents, tasks):
    """Prefer indexed parent outputs for a supported join, keeping E and tools accessible."""
    if len(requirements) != 1 or len(task.depends_on) < 2 or not task.objective.strip():
        return False
    (goal,) = requirements
    if (
        goal.kind != "metric"
        or goal.answer_goal != goal.aspect
        or goal.aspect != "value"
        or goal.interpretation
        or not goal.reasoning_operations
    ):
        return False
    producers = {
        tid
        for ref in parents
        for tid in [ref.split(":")[1]]
        if tasks[tid]["role"] == "reasoning"
        and goal.requirement_id in tasks[tid]["requirement_ids"]
    }
    owned = set().union(*(set(proof["operands"]) for proof in parents.values()))
    return (
        producers == set(task.depends_on)
        and bool(bindings)
        and all(ids and set(ids) <= owned for ids in bindings.values())
    )


def _single_formula_options(task, goals, bindings, local_bindings, options, tasks):
    """Offer formulas for a receipt-backed local result within the planned handoff."""
    if not options or not task.objective.strip() or len(goals) != 1 or not all(bindings.values()):
        return []
    (goal,) = goals
    if goal.kind != "metric" or goal.answer_goal != goal.aspect or goal.aspect != "value":
        return []
    operations = goal.reasoning_operations
    if goal.interpretation:
        return []
    goal_needs = set(goal.need_refs)
    local = {ref: set(ids) for ref, ids in local_bindings.items() if ids}
    if not local:
        return []
    if len(operations) == 1 and operations[0] in CALCULATION_OPERATORS:
        if local.keys() != goal_needs:
            return []
        options = [option for option in options if option["operator"] == operations[0]]
    elif not (
        operations
        and any(
            row["role"] == "reasoning"
            and goal.requirement_id in row["requirement_ids"]
            and task.task_id in row["depends_on"]
            and local.keys() < (goal_needs & set(row["need_refs"]))
            and any(
                parent != task.task_id
                and tasks[parent]["role"] == "reasoning"
                and goal.requirement_id in tasks[parent]["requirement_ids"]
                for parent in row["depends_on"]
            )
            for row in tasks.values()
        )
    ):
        return []
    owned = set().union(*local.values())
    return [
        option
        for option in options
        if (operands := set(option["operands"].values())) <= owned
        and all(operands & ids for ids in local.values())
    ]


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


class SupervisorLite:
    def __init__(self, gateway=None):
        self.gateway = gateway

    def _request(self, question, context, sources=None):
        from .coordinator_plan import semantic_plan_schema

        prompt = dict(
            instruction=(
                "Đọc nguyên văn câu hỏi và khai goals. Mỗi detail là một kết luận người dùng cần. "
                "Dùng fact cho giá trị đã báo cáo, document/explanation cho dẫn nguồn, phân loại "
                "và giải thích. Giữ các điều kiện so sánh, nhận diện đối tác và nối thuyết minh "
                "trong needs và checks. Chỉ dùng metric khi cần một kết quả tính toán. "
                "Khai từng dữ kiện nguồn độc lập trong needs, kể cả thành phần của toán hạng "
                "trung gian. Mỗi need nêu item, issuer (company), period, cùng statement, "
                "scope, table, group, code, unit khi biết. Scope chung của Goal được thừa kế. "
                "Đối tác là nội dung cần xác định, company là doanh nghiệp lập báo cáo. "
                "Số dư dùng ngày từ as_of_dates, số phát sinh dùng kỳ báo cáo. "
                "Với metric, khai output và steps theo phép tính được hỏi: N0 là EO đầu, "
                "R1 là kết quả bước đầu. Inputs có thứ tự, chỉ dùng N đã khai và R bước trước. "
                "Giữ chiều trừ/chia, percentage_of tự nhân 100. Chỉ khai công thức có căn cứ. "
                "Nếu một kết luận phụ thuộc kết luận khác, dùng uses_goals trỏ tới Goal trước. "
                "Thuộc tính của một đầu ra thuộc cùng Goal. Không đoán giá trị, ô hoặc trang nguồn."
            ),
            financial_data_guide=FINANCIAL_DATA_GUIDE,
            output_schema=semantic_plan_schema(),
            context={k: getattr(context, k) for k in ("period", "reporting_scope")},
            conversation_context=context.conversation_context,
        )
        as_of_dates = sorted(
            {
                fact.context.period
                for source in (sources or {}).values()
                if source["kind"] == "fact"
                for fact in source["records"]
                if fact.context.statement_type == "B01"
                and fact.context.period_type == "as_of"
                and fact.context.period
            }
        )
        if as_of_dates:
            prompt["context"]["as_of_dates"] = as_of_dates
        if hasattr(self.gateway, "verification_calls"):
            prompt["call_budget"] = dict(
                total=self.gateway.max_calls,
                planning=1,
                specialists=max(0, self.gateway.remaining_generation_calls - 1),
                verification_reserved=self.gateway.verification_calls,
            )
        payload = json.dumps(compact_prompt(prompt), ensure_ascii=False, separators=(",", ":"))
        if len(payload) + len(question) > 48000:
            return None
        return LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m5-coordinator-plan-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(role="system", content=payload),
                Message(role="user", content=question),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=2500),
            output_spec=OutputSpec(format="json", json_schema=prompt["output_schema"]),
            constraints=RequestConstraints(timeout_seconds=context.provider_timeout_seconds),
        )

    def plan(
        self,
        question,
        context,
        sources,
        *,
        retrieve=None,
        trace=None,
        stages=None,
        simplified_reasoning=False,
        simplified_verification=False,
    ):
        from .coordinator_plan import semantic_plan_schema

        if self.gateway is None or context.mode == "deterministic":
            return (
                LitePlan(),
                PlannerLLMMetadata(status="not_executed"),
                ["coordinator_gateway_required"],
            )
        if retrieve is not None and context.coordinator_interface is None:
            requirement = QuestionRequirement.from_request(question, context)
            draft, metadata = {}, PlannerLLMMetadata()
            if simplified_reasoning:
                draft, metadata = indexed_reasoning.understand_question(
                    self.gateway,
                    question,
                    context,
                    independent_requirements=simplified_verification,
                )
                retrieve(draft)
            else:
                retrieve()
            task = LiteTask(
                task_id="T1",
                specialist="reasoning",
                requirement_ids=[requirement.requirement_id],
                objective=question[:600],
            )
            return (
                LitePlan(tasks=[task], requirements=[requirement], scheduler_task_ids=["T1"]),
                metadata,
                [],
            )

        request = self._request(question, context, sources)
        if request is None:
            return LitePlan(), PlannerLLMMetadata(), ["supervisor_payload_limit"]
        if retrieve is None or request.output_spec.json_schema != semantic_plan_schema():
            plan, metadata, errors, _ = self._compile(request, question, context)
            return plan, metadata, errors

        initial = retrieve()
        plan, first, errors = LitePlan(), PlannerLLMMetadata(), []
        review = {}
        for attempt in range(2):
            if attempt:
                if getattr(self.gateway, "remaining_generation_calls", 1) < 1:
                    return plan, first, [*errors, "supervisor_plan_recovery_budget"]
                request = self._request(question, context, sources)
            if request is None:
                return plan, first, [*errors, "supervisor_plan_recovery_payload_limit"]
            payload = json.loads(request.messages[0].content) | {
                "initial_context": initial,
                "source_context_rule": (
                    "Các nguồn đã pin chỉ giúp xác định nghĩa, chỉ tiêu, kỳ và EO. "
                    "Giữ đủ các vế câu hỏi. Với Goal fact/document/explanation, bỏ steps; "
                    "chỉ Goal metric mới khai steps. Chưa có context thì dùng câu hỏi gốc."
                ),
                **review,
            }
            content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if len(content) + len(question) > 48000:
                if attempt:
                    return plan, first, [*errors, "supervisor_plan_recovery_payload_limit"]
                return LitePlan(), PlannerLLMMetadata(), ["supervisor_payload_limit"]
            request.messages[0].content = content
            if attempt:
                request.request_id = "m5-coordinator-recovery-" + uuid4().hex
            plan, metadata, errors, raw = self._compile(request, question, context)
            if not attempt:
                first = metadata
            else:
                stages["planning_recovery"] = metadata
            trace.append(
                StageExecution(
                    stage="planning",
                    outcome=("recovery_" if attempt else "initial_")
                    + ("rejected" if errors else "accepted"),
                    reasons=errors,
                )
            )
            if not errors or raw is None:
                return plan, first, errors
            review = {
                "plan_review": {
                    "instruction": "Điều chỉnh kế hoạch theo lỗi Compiler. Trả lại toàn bộ goals.",
                    "previous_plan": raw,
                    "compiler_errors": errors,
                }
            }
        return plan, first, [*errors, "supervisor_plan_recovery_rejected"]

    def _compile(self, request, question, context):
        from .coordinator_plan import decode_coordinator_plan

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
            diagnostics = (
                [
                    f"supervisor_plan_schema_mismatch:{'.'.join(map(str, issue.path))}:{issue.code}"
                    for issue in response.error.validation_issues
                ]
                if response.error
                else []
            )
            return LitePlan(), metadata, diagnostics or ["supervisor_provider_failure"], None
        plan, errors = decode_coordinator_plan(
            response.output.payload, question, request.output_spec.json_schema
        )
        return plan, metadata, errors, response.output.payload


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
        simplified_reasoning=False,
        simplified_verification=False,
    ):
        self.catalog, self.gateway = catalog, gateway
        self.supervisor = supervisor or SupervisorLite(gateway)
        self.graph_enabled = graph_enabled
        self.simplified_reasoning = simplified_reasoning
        self.simplified_verification = simplified_verification and simplified_reasoning
        self.composition, self.document_repository = composition, document_repository

    def reset_request(self):
        pass

    def _graph_tools(self, context):
        if self.composition is not None and self.document_repository is not None:
            from ..evidence.composition_graph import CompositionGraphView

            if (
                self.composition.financial_snapshot.document_id,
                self.composition.financial_snapshot.snapshot_id,
            ) != (context.document_id, context.snapshot_id):
                raise ValueError("composition_financial_snapshot_mismatch")
            return GraphRetrievalTools(
                CompositionGraphView(
                    self.composition,
                    self.document_repository,
                    self.catalog,
                    document_id=self.composition.logical_document_id,
                    composition_id=self.composition.composition_id,
                )
            )
        return GraphRetrievalTools.from_catalog(
            self.catalog, document_id=context.document_id, snapshot_id=context.snapshot_id
        )

    def _evidence(self, task, upstream, question):
        state = self.workspace.tasks[task.task_id]
        allowed = set(state.get("tool_evidence_ids", []))
        allowed.update(state.get("answer_recovery", {}).get("context_delta", ()))
        metrics = set(state.get("tool_metric_ids", []))
        for tid in self.workspace.dependency_ids(task):
            parent = self.workspace.task_results[tid]
            allowed.update(parent.get("tool_evidence_ids", []))
            allowed.update(parent.get("evidence_ids", []))
            metrics.update(parent.get("tool_metric_ids", []))
            allowed.update(r["evidence_id"] for r in parent.get("selected_observations", []))
        inherited = getattr(self, "_initial_refs", ()) if task.specialist == "reasoning" else ()
        supplemental, initial = [], []
        for fact in upstream.evidence_bundle.facts:
            handle = evidence_handle(fact)
            if handle in allowed:
                supplemental.append(fact)
            elif handle in inherited:
                initial.append(fact)
        upstream = upstream.model_copy(
            update={
                "evidence_bundle": upstream.evidence_bundle.model_copy(
                    update={"facts": [*supplemental, *initial]}
                )
            }
        )
        result = SpecialistResult(
            question=question, role=task.specialist, upstream_status=upstream.status
        )
        select_evidence(
            upstream,
            result,
            item_labels={key: rule.aliases[0] for key, rule in ITEM_RULES.items()},
            metric_labels=FORMULA_LABELS,
            period_roles=dict(
                gross_margin="revenue", revenue_yoy="current_revenue", debt_to_assets="assets"
            ),
        )
        for evidence in result.supporting_evidence:
            evidence.evidence_id = evidence_handle(evidence)
        result.supporting_evidence = [
            e
            for e in result.supporting_evidence
            if e.evidence_id in allowed
            or e.evidence_id in inherited
            or e.calculation
            and e.calculation.metric_id in metrics
        ]
        return result

    def _remember_document(self, response, hit, state, sources):
        handle = "D-" + content_digest(hit.evidence.reference.model_dump(mode="json"))[:20]
        self._document_hits[handle] = (response, hit)
        numeric_sources = {
            source: dict(
                row=cell.row,
                column=cell.column,
                label=sources[source]["label"],
                period=sources[source]["period"],
                header=sources[source]["records"][0].raw_header,
            )
            for cell in hit.cells
            for source in self._cell_sources.get(
                (
                    hit.document_id,
                    hit.snapshot_id,
                    hit.evidence.record.sources[0].reference.anchor.page.model_dump_json(),
                    cell.source_pointer,
                ),
                [],
            )
        }
        row = dict(
            handle=handle,
            text=hit.snippet,
            reference=hit.evidence.reference.model_dump(mode="json"),
            citations=[c.model_dump(mode="json") for c in hit.evidence.citations],
            cells=[c.model_dump(mode="json") for c in hit.cells],
            numeric_sources=numeric_sources,
        )
        state["source_context"] = [
            r for r in state.get("source_context", []) if r["handle"] != handle
        ] + [row]
        self._document_views[handle] = dict(
            handle=handle,
            reference=hit.evidence.reference.model_dump(mode="json"),
            graph_node_id=graph_id(
                hit.evidence.reference.kind, hit.evidence.reference.evidence.model_dump()
            ),
            text=hit.snippet,
            cell_columns=["row", "column", "text"],
            cells=[[c.row, c.column, c.text] for c in hit.cells],
            numeric_sources=numeric_sources,
            table_title=hit.evidence.record.source_metadata.get("original_table", {}).get("title"),
            headers=hit.evidence.record.source_metadata.get("original_table", {}).get(
                "columns", []
            ),
            source_page=hit.source_page or hit.pdf_page,
            source_caveats=hit.limitations,
            content_range=dict(
                offset=0,
                limit=None,
                total=len({c.row for c in hit.cells if c.row not in {None, 0}})
                if hit.cells
                else len(hit.snippet),
                unit="data_rows" if hit.cells else "characters",
            ),
            source_bindings=[
                dict(
                    source=s.reference.anchor.page.source_ref,
                    pointer=s.reference.source_pointer,
                    provenance_level=s.reference.provenance_level,
                )
                for s in hit.evidence.record.sources
                if s.reference
            ],
            cell_pointer_rule=(
                "JSON table root + /columns/[column] for row0; /rows/[row-1]/[column] for data rows"
                if hit.evidence.record.source_metadata.get("source_kind") == "refined_json"
                else None
            ),
        )
        neighbors = []
        for neighbor in hit.neighbors:
            record = neighbor.evidence.record
            child = hit.model_copy(
                update=dict(
                    evidence=neighbor.evidence,
                    evidence_ids=[neighbor.evidence.reference.evidence],
                    snippet=record.raw_text or "",
                    cells=[],
                    neighbors=[],
                    limitations=neighbor.evidence.issues,
                )
            )
            child_handle = self._remember_document(response, child, state, sources)
            neighbors.append(
                dict(
                    handle=child_handle,
                    order=neighbor.order,
                    relation="source_adjacent_not_semantic_support",
                )
            )
        self._document_views[handle]["neighbors"] = neighbors
        row["neighbors"] = neighbors
        return handle

    def _context_facts(self, bundle, hits, state, sources, context):
        """Hydrate bounded table candidates from existing cell selectors and Hybrid results."""
        handles = dict.fromkeys(
            source for handle in hits for source in self._document_views[handle]["numeric_sources"]
        )
        matches = {m.record.local_observation_id: m for m in bundle.facts}
        candidates = {key: match.record for key, match in matches.items()}
        for handle in handles:
            records = sources[handle]["records"]
            if len(records) == 1:
                fact = records[0]
                candidates[fact.local_observation_id] = fact
        if (
            hits
            and self.simplified_reasoning
            and self._eo_descriptor
            and self._eo_issuer_proof
            and getattr(self.catalog, "_request_snapshot", False)
        ):
            scope = self.catalog.get_reporting_scope(context.document_id, context.snapshot_id)
            for handle in hits:
                _, hit = self._document_hits[handle]
                issues = {}
                for cell in json_table_cells(
                    self.catalog, self._eo_descriptor, hit.evidence.record, hit.cells, scope
                ):
                    if context.reporting_scope and context.reporting_scope != cell["scope"]:
                        continue
                    fact, issue = json_cell_observation(
                        self._eo_descriptor, cell, self._eo_issuer_proof, context.company_id
                    )
                    if issue:
                        issues[cell["label"]] = issue
                    elif (
                        context.document_id,
                        context.snapshot_id,
                        fact.sources[0].reference.anchor.page.model_dump_json(),
                        cell["source_pointer"],
                    ) not in self._cell_sources:
                        candidates[fact.local_observation_id] = fact
                self._document_views[handle]["numeric_issues"] = issues
        rank = rank_search_candidates(
            {
                key: f"{f.context.raw_item_label} {f.context.period} {f.raw_header}"
                for key, f in candidates.items()
            },
            state["context_queries"],
            top_k=32,
        )
        priority = [key for key in candidates if key in state["fact_needs"]]
        selected = list(dict.fromkeys([*priority, *rank]))[:32]
        projected = [
            candidates[key]
            for key in selected
            if candidates[key].source_metadata.get("projection") == "document_cell"
        ]
        if projected:
            self.catalog.add_request_json_facts(projected)
        financial = FinancialRetrievalTools(self.catalog)
        bundle.facts = []
        for key in selected:
            if key not in matches:
                exact = financial.get_financial_fact(
                    GetFinancialFactRequest(
                        document_id=context.document_id,
                        snapshot_id=context.snapshot_id,
                        local_observation_id=key,
                    )
                )
                if exact.status != "found" or len(exact.matches) != 1:
                    continue
                matches[key] = exact.matches[0]
            match = matches[key]
            fact = match.record
            if (fact.document_id, fact.snapshot_id, fact.company_id) == (
                context.document_id,
                context.snapshot_id,
                context.company_id,
            ) and not _fact_error(match, ExecutionEvidenceBundle(citations=match.citations)):
                bundle.facts.append(match)
        bundle.citations = list(
            {c.model_dump_json(): c for m in bundle.facts for c in m.citations}.values()
        )

    def _tool(self, name, args, context, sources, state, upstream):
        """Bind pinned identities, call existing tools and retain full source records."""
        if name not in SPECIALIST_TOOLS_BY_ROLE.get(state.get("role"), ()):
            raise ValueError("tool_not_allowed_for_role")
        bundle = ExecutionEvidenceBundle()
        request = args
        context_handles = []
        if name in {"get_financial_fact", "calculate_financial_metric"}:
            if set(args) != {"source"} or args["source"] not in sources:
                raise ValueError("source_unknown")
            source = sources[args["source"]]
            expected = "fact" if name == "get_financial_fact" else "metric"
            if source["kind"] != expected or len(source["records"]) != 1:
                raise ValueError("source_ambiguous_or_wrong_kind")
            record = source["records"][0]
            if expected == "fact":
                request = GetFinancialFactRequest(
                    document_id=context.document_id,
                    snapshot_id=context.snapshot_id,
                    local_observation_id=record.local_observation_id,
                )
                known = next(
                    (
                        f
                        for f in self.workspace.evidence.facts
                        if f.reference.observation == record.observation_identity()
                    ),
                    None,
                )
                prior = next(
                    (
                        step
                        for step in reversed(upstream.tool_trace)
                        if known is not None
                        and evidence_handle(known) in step.output_evidence_ids
                        and step.final_state == "completed"
                        and not step.step_id.startswith("initial-tool-")
                    ),
                    None,
                )
                response = (
                    FinancialRetrievalTools(self.catalog).get_financial_fact(request)
                    if prior is None
                    else None
                )
                matches = response.matches if response is not None else [known]
                bundle.facts = [m for m in matches if m.record.company_id == context.company_id]
                bundle.citations = list(
                    {c.model_dump_json(): c for m in bundle.facts for c in m.citations}.values()
                )
                if response is None:
                    state["tool_evidence_ids"] = list(
                        dict.fromkeys(
                            [
                                *state.get("tool_evidence_ids", []),
                                *[observation(m)["evidence_id"] for m in matches],
                            ]
                        )
                    )
                    return dict(
                        ok=True,
                        result_id=prior.step_id,
                        data=dict(
                            reused=True, matches=[m.model_dump(mode="json") for m in matches]
                        ),
                        evidence_refs=[observation(m)["evidence_id"] for m in matches],
                        error=None,
                    )
            else:
                request = CalculateFinancialMetricRequest(
                    metric_id=record.metric_id,
                    document_id=context.document_id,
                    snapshot_id=context.snapshot_id,
                )
                response = FinancialCalculator(self.catalog).calculate_financial_metric(request)
                state["tool_metric_ids"] = list(
                    dict.fromkeys([*state.get("tool_metric_ids", []), record.metric_id])
                )
                bundle.calculations.append(response)
                if response.trace:
                    for operand in response.trace.operands:
                        fact = FinancialRetrievalTools(self.catalog).get_financial_fact(
                            GetFinancialFactRequest(
                                document_id=context.document_id,
                                snapshot_id=context.snapshot_id,
                                local_observation_id=operand.observation.local_id,
                            )
                        )
                        bundle.facts.extend(fact.matches)
                    bundle.citations = list(
                        {c.model_dump_json(): c for m in bundle.facts for c in m.citations}.values()
                    )
        elif name == "find_financial_facts":
            if set(args) - {
                "canonical_item_id",
                "source_label",
                "statement_type",
                "period",
                "source_page",
            } or not any(
                args.get(key)
                for key in ("canonical_item_id", "source_label", "statement_type", "source_page")
            ):
                raise ValueError("financial_filters_required")
            request = FindFinancialFactsRequest(
                **args,
                document_id=context.document_id,
                snapshot_id=context.snapshot_id,
                company_id=context.company_id,
                reporting_scope=context.reporting_scope,
            )
            response = FinancialRetrievalTools(self.catalog).find_financial_facts(request)
            if len(response.matches) > 40:
                response = response.model_copy(
                    update=dict(
                        status="ambiguous",
                        matches=[],
                        reasons=[*response.reasons, "financial_result_too_broad_refine_filters"],
                    )
                )
            bundle.facts = [
                m for m in response.matches if m.record.company_id == context.company_id
            ]
            bundle.citations = list(
                {c.model_dump_json(): c for m in bundle.facts for c in m.citations}.values()
            )
        elif name == "search_hybrid_evidence":
            if set(args) - {"query", "top_k"}:
                raise ValueError("tool_args_invalid")
            request = SearchHybridEvidenceRequest(
                **args, document_id=context.document_id, snapshot_id=context.snapshot_id
            )
            response = self._hybrid_tool.search(request, self.catalog, self.composition)
            bundle.facts = [f for f in response.facts if f.record.company_id == context.company_id]
            bundle.citations = list(
                {c.model_dump_json(): c for f in bundle.facts for c in f.citations}.values()
            )
            for hit in response.documents.matches:
                context_handles.append(
                    self._remember_document(response.documents, hit, state, sources)
                )
        elif name in {"search_document_evidence", "find_document_evidence"}:
            if self.composition is None or self.document_repository is None:
                raise ValueError("document_composition_unavailable")
            if set(args) - (
                {"source_page", "evidence_type"}
                if name == "find_document_evidence"
                else {"query", "evidence_type", "top_k", "context_radius", "source_page"}
            ):
                raise ValueError("tool_args_invalid")
            if name == "find_document_evidence" and not args.get("source_page"):
                raise ValueError("source_page_required")
            request = SearchDocumentEvidenceRequest(
                **(
                    args
                    if name == "search_document_evidence"
                    else dict(
                        query="",
                        source_page=args["source_page"],
                        evidence_type=args.get("evidence_type", "both"),
                    )
                ),
                document_id=self.composition.logical_document_id,
                composition_id=self.composition.composition_id,
                snapshot_id=context.snapshot_id
                if self.composition.financial_snapshot.source_kind == "json"
                else None,
            )
            key = request.model_dump_json()
            if key in self._document_searches:
                response = self._document_searches[key]
            else:
                if getattr(self, "_search_tools", None) is None:
                    self._search_tools = EvidenceRetrievalTools.from_composition(
                        self.composition,
                        self.document_repository,
                        document_id=self.composition.logical_document_id,
                        composition_id=self.composition.composition_id,
                    )
                if name == "find_document_evidence":
                    found = self._search_tools.find_document_evidence(
                        FindDocumentEvidenceRequest(
                            document_id=context.document_id, snapshot_id=context.snapshot_id, **args
                        )
                    )
                    response = DocumentSearchResponse(
                        request=request,
                        status="found" if found.matches else "not_found",
                        reasons=found.reasons,
                    )
                    for match in found.matches:
                        record = match.record
                        cells = _cells(record) if record.kind == "table" else []
                        response.matches.append(
                            DocumentSearchMatch(
                                rank=len(response.matches) + 1,
                                relevance_score=0,
                                evidence=match,
                                evidence_ids=[match.reference.evidence],
                                document_id=record.document_id,
                                snapshot_id=record.snapshot_id,
                                pdf_page=match.citations[0].pdf_page if match.citations else None,
                                source_page=args["source_page"],
                                snippet=record.raw_text
                                if record.kind == "text"
                                else "\n".join(c.text or "" for c in cells),
                                cells=cells,
                                matched_terms=[],
                                ranking_reasons=["exact_source_page"],
                                limitations=found.caveats,
                            )
                        )
                else:
                    response = self._search_tools.search_document_evidence(request)
                self._document_searches[key] = response
            for hit in response.matches:
                context_handles.append(self._remember_document(response, hit, state, sources))
        elif name == "get_evidence_item":
            if (
                set(args) - {"source", "offset", "limit"}
                or args.get("source") not in self._document_hits
            ):
                raise ValueError("source_unknown")
            saved_search, hit = self._document_hits[args["source"]]
            identity = hit.evidence.reference.evidence
            request = GetEvidenceItemRequest(
                document_id=identity.document_id,
                snapshot_id=identity.snapshot_id,
                local_evidence_id=identity.local_id,
                kind=identity.kind,
            )
            tools = EvidenceRetrievalTools.from_composition(
                self.composition,
                self.document_repository,
                document_id=self.composition.logical_document_id,
                composition_id=self.composition.composition_id,
            )
            try:
                response = tools.get_evidence_item(request)
            finally:
                tools.close_search()
            if response.status == "found" and len(response.matches) == 1:
                record = response.matches[0].record
                offset, limit = args.get("offset", 0), args.get("limit")
                if (
                    type(offset) is not int
                    or offset < 0
                    or (limit is not None and (type(limit) is not int or limit < 1))
                ):
                    raise ValueError("tool_args_invalid")
                cells = _cells(record) if record.kind == "table" else []
                if cells:
                    rows = sorted({c.row for c in cells if c.row is not None and c.row != 0})
                    selected = set(rows[offset : offset + limit if limit is not None else None]) | {
                        0
                    }
                    cells = [c for c in cells if c.row in selected or c.row is None]
                    snippet = "\n".join(c.text or "" for c in cells)
                else:
                    snippet = (record.raw_text or "")[
                        offset : offset + limit if limit is not None else None
                    ]
                full = hit.model_copy(update={"cells": cells, "snippet": snippet})
                handle = self._remember_document(saved_search, full, state, sources)
                if self.simplified_reasoning and cells and state.get("context_queries"):
                    context_handles.append(handle)
                self._document_views[handle]["content_range"] = dict(
                    offset=offset,
                    limit=limit,
                    total=len(rows) if cells else len(record.raw_text or ""),
                    unit="data_rows" if cells else "characters",
                )
                self._document_views[handle]["explicit_read"] = True
        elif name == "calculate_dynamic":
            if set(args) != {"evidence_ids", "operations"}:
                raise ValueError("tool_args_invalid")
            known = {
                observation(f)["evidence_id"]: f.reference for f in self.workspace.evidence.facts
            }
            if (
                not isinstance(args["evidence_ids"], list)
                or set(args["evidence_ids"]) - known.keys()
            ):
                raise ValueError("dynamic_operand_unknown")
            response = FinancialCalculator(self.catalog).calculate_dynamic(
                {key: known[key] for key in args["evidence_ids"]},
                [DynamicOperation.model_validate(op) for op in args["operations"]],
            )
        elif name == "get_evidence_sources":
            known = {
                observation(f)["evidence_id"]: f.reference for f in self.workspace.evidence.facts
            }
            if set(args) != {"evidence_id"} or args["evidence_id"] not in known:
                raise ValueError("source_unknown")
            request = GetEvidenceSourcesRequest(
                reference=known[args["evidence_id"]],
                document_id=context.document_id,
                snapshot_id=context.snapshot_id,
            )
            response = EvidenceRetrievalTools(self.catalog).get_evidence_sources(request)
            bundle.sources_and_lineage.append(response)
        elif name == "get_graph_context":
            if not self.graph_enabled:
                raise ValueError("graph_disabled")
            if set(args) - {"node_id", "depth", "limit", "relations"}:
                raise ValueError("tool_args_invalid")
            request = (
                GetGraphContextRequest(
                    **args,
                    document_id=self.composition.logical_document_id,
                    composition_id=self.composition.composition_id,
                )
                if self.composition is not None
                else GetSnapshotGraphContextRequest(
                    **args, document_id=context.document_id, snapshot_id=context.snapshot_id
                )
            )
            if getattr(self, "_request_graph_tools", None) is None:
                self._request_graph_tools = self._graph_tools(context)
            response = self._request_graph_tools.get_graph_context(request)
            bundle.graph_contexts.append(response)
        else:
            raise ValueError("tool_unknown")
        if (context_handles or name == "search_hybrid_evidence") and state.get("context_queries"):
            self._context_facts(bundle, context_handles, state, sources, context)
        self.workspace.merge(bundle)
        upstream.evidence_bundle = self.workspace.evidence
        refs = [observation(f)["evidence_id"] for f in bundle.facts]
        if context_handles:
            refs += context_handles
        elif name == "calculate_dynamic":
            refs = list(response.operands)
        elif name == "get_evidence_item":
            refs = [args["source"]]
        state["tool_evidence_ids"] = list(
            dict.fromkeys([*state.get("tool_evidence_ids", []), *refs])
        )
        status = getattr(response, "status", "computed")
        candidates = (
            name == "find_financial_facts" and status == "ambiguous" and bool(response.matches)
        )
        ok = status in {"found", "computed"} or candidates
        outcome = (
            "candidates"
            if candidates
            else "empty"
            if status == "not_found"
            else "refine"
            if status == "ambiguous"
            else "success"
            if ok
            else "error"
        )
        event = StepExecutionResult(
            step_id=f"{state['task_id']}-tool-{len(upstream.tool_trace) + 1}",
            operation=name,
            bound_request=request.model_dump(mode="json")
            if hasattr(request, "model_dump")
            else request,
            response=response,
            final_state="completed" if outcome != "error" else "failed",
            output_evidence_ids=refs,
            reasons=list(getattr(response, "reasons", [])),
        )
        upstream.tool_trace.append(event)
        return dict(
            ok=ok,
            status=outcome,
            result_id=event.step_id,
            data=response.model_dump(mode="json"),
            evidence_refs=refs,
            error=dict(code=status, reasons=getattr(response, "reasons", []))
            if outcome == "error"
            else None,
        )

    def _receipt_needs(self, task, call, result, context):
        declared = call.get("need_refs") or (
            task.need_refs if task.specialist != "retrieval" else []
        )
        # A single reported fact may carry several independently stated source attributes.
        goals = [r for r in self.workspace.requirements if r.requirement_id in task.requirement_ids]
        if (
            task.specialist != "retrieval"
            or call["tool"] not in {"find_financial_facts", "get_financial_fact"}
            or len(goals) != 1
            or goals[0].kind != "fact"
            or len(goals[0].evidence_needs) < 2
            or any(need.startswith(f"N{i}:") for i, need in enumerate(goals[0].evidence_needs))
        ):
            return list(dict.fromkeys(declared))
        if not result["ok"]:
            return list(dict.fromkeys(declared))
        refs = result["evidence_refs"]
        if len(refs) != 1 or result.get("status", "success") != "success":
            return []
        match = next(
            (f for f in self.workspace.evidence.facts if evidence_handle(f) == refs[0]), None
        )
        if match is None or not match.json_source_bound or not match.citations:
            return []
        fact = match.record
        if (fact.document_id, fact.snapshot_id, fact.company_id) != (
            context.document_id,
            context.snapshot_id,
            context.company_id,
        ):
            return []

        def literal(text):
            return _label(text or "", strip_numeric_ordinal=True)

        needs = {
            ref: literal(text)
            for ref, text in zip(goals[0].need_refs, goals[0].evidence_needs, strict=True)
        }
        # Resolve standalone item labels by exact catalog alias, including the short printed
        # label of an aggregate when it identifies a unique canonical item.
        item_ids = {key: set() for key in needs.values()}
        for rule in ITEM_RULES.values():
            for alias in {rule.canonical_item_id, *(literal(a) for a in rule.aliases)}:
                for key in {alias, alias.removeprefix("tổng ")} & item_ids.keys():
                    item_ids[key].add(rule.canonical_item_id)
        item_labels = {key for key, ids in item_ids.items() if ids == {fact.canonical_item_id}}
        if not item_labels or any(ids and key not in item_labels for key, ids in item_ids.items()):
            return []

        symbols = {s.reference.anchor.page.symbol for s in fact.sources}
        aliases = self._eo_issuer
        if aliases == set():
            return []
        company = {literal(context.company_id), *(literal(alias) for alias in aliases or ())}
        if len(symbols) == 1 and (symbol := next(iter(symbols))):
            company.update(
                literal(s) for s in (symbol, f"Doanh nghiệp {symbol}", f"Công ty {symbol}")
            )
        financial = fact.context
        periods = {literal(financial.period), literal(fact.raw_header)} - {""}
        if financial.period_type == "fiscal_year":
            periods.add(literal(f"Năm {financial.period}"))
        for key in needs.values():
            year = key.removeprefix("năm ")
            if (len(year) == 4 and year.isdecimal() and key not in periods) or (
                key.startswith(("doanh nghiệp ", "công ty ")) and key not in company
            ):
                return []
        units = {fact.value.unit} if financial.scale == 1 else set()
        if fact.value.unit == "VND":
            units.update(
                {
                    1: ("đồng", "đồng Việt Nam", "VNĐ"),
                    1000: ("nghìn đồng",),
                    1000000: ("triệu đồng",),
                }.get(financial.scale, ())
            )
        unit_labels = {literal(s) for u in units for s in (u, f"Đơn vị tính: {u}")}
        statement = financial.statement_type
        heading = FINANCIAL_DATA_GUIDE.get(statement, "").partition(":")[0]
        statement_labels = (
            {literal(statement), literal(f"Nguồn {statement}: {heading}")} if heading else set()
        )
        supported = item_labels | company | periods | unit_labels | statement_labels
        return [ref for ref in task.need_refs if needs.get(ref) in supported]

    def _record_source_receipts(self, task, state, call, result, context, sequence):
        if (
            not task.need_refs
            or not result.get("result_id")
            or call["tool"]
            not in {
                "get_financial_fact",
                "find_financial_facts",
                "search_document_evidence",
                "find_document_evidence",
                "search_hybrid_evidence",
                "get_evidence_item",
            }
        ):
            return
        handles = set(result["evidence_refs"]) if result["ok"] else set()
        assigned = _assigned_needs(self.workspace.requirements, task.need_refs)
        eligible = set(call.get("need_refs") or assigned) & assigned.keys()
        diagnostics = state.setdefault("need_source_issues", {})
        groups = {}
        receipts = []
        for fact in self.workspace.evidence.facts:
            handle, record = evidence_handle(fact), fact.record
            if handle not in handles:
                continue
            if (record.document_id, record.snapshot_id, record.company_id) != (
                context.document_id,
                context.snapshot_id,
                context.company_id,
            ):
                continue
            identity = record.local_observation_id
            refs = state["fact_needs"].get(identity, [])
            issues = self._eo_fact_issues.get(identity, {})
            issue = _fact_error(fact, self.workspace.evidence)
            for ref in eligible:
                reason = issues.get(ref) or (
                    "provenance_insufficient" if ref in refs and issue else "item_mismatch"
                )
                diagnostics.setdefault(ref, []).append(reason)
            if issue:
                continue
            if not refs and task.specialist == "retrieval":
                refs = [
                    ref
                    for ref in self._receipt_needs(task, call, result, context)
                    if not assigned[ref][1].startswith(f"N{assigned[ref][0]}:")
                ]
            refs = [ref for ref in refs if ref in eligible]
            if refs:
                groups.setdefault(tuple(refs), []).append(handle)
        receipts.extend(
            dict(need_refs=list(refs), evidence_refs=ids) for refs, ids in groups.items()
        )
        covered = {ref for refs in groups for ref in refs}
        if (
            task.specialist == "retrieval"
            and self._eo_descriptor
            and self._eo_issuer
            and eligible - covered
            and any(handle.startswith("D-") for handle in handles)
        ):
            cells_by_need = {}
            scope = self.catalog.get_reporting_scope(context.document_id, context.snapshot_id)
            for row in state.get("source_context", []):
                handle = row["handle"]
                if handle not in handles:
                    continue
                _, hit = self._document_hits[handle]
                for cell in json_table_cells(
                    self.catalog, self._eo_descriptor, hit.evidence.record, hit.cells, scope
                ):
                    fields = _eo_fields(
                        company=self._eo_issuer,
                        **{
                            key: cell[key]
                            for key in (
                                "label",
                                "statement",
                                "code",
                                "period",
                                "unit",
                                "scope",
                                "table",
                                "title",
                                "group",
                            )
                        },
                    )
                    for ref in eligible - covered:
                        ordinal, need = assigned[ref]
                        if not need.startswith(f"N{ordinal}:"):
                            continue
                        reason = _need_match(ordinal, need, fields)
                        if reason:
                            if reason != "item_mismatch":
                                diagnostics.setdefault(ref, []).append(reason)
                            continue
                        if not cell["unit"] or (
                            context.reporting_scope and context.reporting_scope != cell["scope"]
                        ):
                            diagnostics.setdefault(ref, []).append("provenance_insufficient")
                            continue
                        if cell["statement"] == "B09" and (
                            not fields["table"]
                            or not any(
                                field.strip().startswith(("group=", "table="))
                                for field in need.partition(":")[2].split(",")
                            )
                        ):
                            diagnostics.setdefault(ref, []).append("source_ambiguous")
                            continue
                        cells_by_need.setdefault(ref, []).append((handle, cell))
            for ref, cells in cells_by_need.items():
                if len(cells) != 1 or "source_ambiguous" in diagnostics.get(ref, ()):
                    diagnostics.setdefault(ref, []).append("source_ambiguous")
                    continue
                handle, cell = cells[0]
                receipts.append(
                    dict(
                        need_refs=[ref],
                        evidence_refs=[handle],
                        source_cell=dict(
                            **cell,
                            company_id=context.company_id,
                            document_id=context.document_id,
                            snapshot_id=context.snapshot_id,
                            verification="json_source_bound",
                        ),
                    )
                )
        unattributed = sorted(handles - {key for r in receipts for key in r["evidence_refs"]})
        if unattributed or not receipts:
            receipts.append(dict(need_refs=[], evidence_refs=unattributed))
        for index, receipt in enumerate(receipts):
            state.setdefault("need_tool_results", []).append(
                dict(
                    result_id=f"{task.task_id}:tool:{sequence}"
                    + (f":{index + 1}" if index else ""),
                    tool=call["tool"],
                    status=result.get("status", "success" if result["ok"] else "error"),
                    cached=result.get("cached", False),
                    source_result_id=result["result_id"],
                    **(
                        {"issuer": self._eo_issuer_proof}
                        if receipt["need_refs"] and self._eo_issuer_proof
                        else {}
                    ),
                    **receipt,
                )
            )

    def _handoff_table(self, handle, scope, *, include_selectors=False):
        """Read only complete, pinned JSON tables returned by a document tool."""
        saved = self._document_hits.get(handle)
        descriptor = getattr(self, "_eo_descriptor", None)
        if not saved or not descriptor or not self._eo_issuer:
            return None
        _, hit = saved
        record = hit.evidence.record
        pins = (scope["document_id"], scope["snapshot_id"])
        if (
            record.kind != "table"
            or record.source_metadata.get("uncertain")
            or (hit.document_id, hit.snapshot_id) != pins
            or (descriptor.document_id, descriptor.snapshot_id) != pins
            or not json_evidence_bound(self.catalog, descriptor, record)
            or not hit.cells
            or hit.cells != _cells(record)
        ):
            return None
        ref = record.sources[0].reference
        digest = descriptor.json_pages[ref.anchor.page.page]
        table = record.source_metadata["original_table"]
        page_context = resolve_financial_context(
            json_page_context(self.catalog.json_sources[digest], digest)
        )
        return dict(
            handle=handle,
            evidence_id=hit.evidence.reference.evidence.model_dump(mode="json"),
            table_title=table["title"],
            source_page=ref.anchor.page.page,
            source_hash=ref.anchor.page.source_ref,
            table_pointer=ref.source_pointer,
            headers=table["columns"],
            table_rows=table["rows"],
            **(
                dict(
                    cell_selectors_rc={
                        selector: [r, c]
                        for r, row in enumerate(table["rows"])
                        for c in range(len(row))
                        for selector in self._cell_sources.get(
                            (
                                *pins,
                                ref.anchor.page.model_dump_json(),
                                f"{ref.source_pointer}/rows/{r}/{c}",
                            ),
                            (),
                        )
                    }
                )
                if include_selectors
                else {}
            ),
            page_context={
                key: {
                    "status": field.status,
                    "sources": [
                        {
                            "text": c.evidence.raw_text,
                            "pointer": c.evidence.provenance[0].source_pointer,
                        }
                        for c in field.candidates
                    ],
                }
                for key, field in (("period", page_context.period), ("unit", page_context.unit))
            },
        )

    def _initial_context(
        self, question, context, sources, upstream, trace, question_understanding=None
    ):
        """Read pinned source evidence before any Goal or DAG exists."""
        scope = {
            key: getattr(context, key)
            for key in ("company_id", "document_id", "snapshot_id", "reporting_scope")
        }
        self.workspace.question_understanding = question_understanding or {}
        if self.simplified_verification and context.coordinator_interface is None:
            draft_answers = self.workspace.question_understanding
            proposals = draft_answers.get("requirements", [])
            self.workspace.expected_answers = expected_answer_set(
                QuestionRequirement.from_request(question, context).model_dump(mode="json"),
                proposals,
                context.reporting_scope or draft_answers.get("scope", ""),
            )
            if proposals:
                draft_answers["requirements"] = [row["text"] for row in proposals]
        needs = [
            need
            for goal in self.workspace.question_understanding.get("goals", ())
            for need in goal["evidence_needs"]
        ]
        draft = self.workspace.question_understanding.get("needs", [])
        direct = context.coordinator_interface is None
        payload = dict(scope=scope, facts=[], documents=[], status="initial_scope_unavailable")
        started = perf_counter()
        if (
            self._eo_descriptor
            and self._eo_issuer
            and self.composition
            and self.document_repository
        ):
            tool = (
                "search_hybrid_evidence"
                if self._hybrid_tool.available
                else "search_document_evidence"
            )
            self._recovery_searches.add((tool, normalize_search(question[:2000])))
            state = dict(
                task_id="initial",
                role="retrieval",
                fact_needs={},
                context_queries=[*[n["label"] for n in draft], *needs, question],
            )
            try:
                result = self._tool(
                    tool,
                    dict(query=question[:2000], top_k=12 if direct else 5),
                    context,
                    sources,
                    state,
                    upstream,
                )
                payload["status"] = result["status"]
                if self.simplified_reasoning:
                    self._initial_refs.update(result["evidence_refs"])
                upstream.tool_trace[-1].latency_ms = (perf_counter() - started) * 1000
                missing = []
                for need in draft:
                    if not need["label"].strip():
                        continue
                    args_options = (
                        indexed_reasoning.fact_lookup(need) if need["role"] != "relation" else ()
                    )
                    for args in args_options:
                        found = self._tool(
                            "find_financial_facts", args, context, sources, state, upstream
                        )
                        if found["evidence_refs"]:
                            self._initial_refs.update(found["evidence_refs"])
                            break
                    else:
                        missing.append(need["label"])
                if missing and tool == "search_hybrid_evidence":
                    self._tool(
                        "search_document_evidence",
                        dict(query=" ".join(dict.fromkeys(missing))[:2000], top_k=8),
                        context,
                        sources,
                        state,
                        upstream,
                    )
                    self._initial_refs.update(state["tool_evidence_ids"])
            except (ImportError, OSError, RuntimeError, SQLiteError, ValueError) as error:
                payload["status"] = f"initial_retrieval_unavailable:{type(error).__name__}"
            else:
                remaining = 20000 if direct else 8000
                for row in state.get("source_context", []):
                    handle = row["handle"]
                    if direct:
                        self._initial_refs.add(handle)
                    _, hit = self._document_hits[handle]
                    record = hit.evidence.record
                    view = self._handoff_table(handle, scope)
                    if (
                        record.kind == "text"
                        and (hit.document_id, hit.snapshot_id)
                        == (context.document_id, context.snapshot_id)
                        and json_evidence_bound(self.catalog, self._eo_descriptor, record)
                    ):
                        ref = record.sources[0].reference
                        view = dict(
                            handle=handle,
                            evidence_id=hit.evidence.reference.evidence.model_dump(mode="json"),
                            source_page=ref.anchor.page.page,
                            source_hash=ref.anchor.page.source_ref,
                            pointer=ref.source_pointer,
                            text=record.raw_text[:480],
                            truncated=len(record.raw_text) > 480,
                        )
                    if view is None:
                        continue
                    size = len(json.dumps(view, ensure_ascii=False, separators=(",", ":"))) + 1
                    if size > remaining:
                        payload["status"] = "initial_context_budget"
                        continue
                    payload["documents"].append(view)
                    self._initial_refs.add(handle)
                    remaining -= size
                for match in self.workspace.evidence.facts[: 20 if direct else 8]:
                    fact = match.record
                    if (
                        context.reporting_scope
                        and fact.context.reporting_scope != context.reporting_scope
                    ):
                        continue
                    row = observation(match)
                    view = {
                        k: row[k] for k in ("reference", "label", "value", "unit", "context")
                    } | {"selector": row["selectors"][:1]}
                    size = len(json.dumps(view, ensure_ascii=False, separators=(",", ":"))) + 1
                    if size > remaining:
                        payload["status"] = "initial_context_budget"
                        break
                    payload["facts"].append(view)
                    self._initial_refs.add(row["evidence_id"])
                    remaining -= size
        if payload["status"] == "success" and not self._initial_refs:
            payload["status"] = "initial_context_empty"
        trace.append(
            StageExecution(
                stage="context_projection",
                outcome="initial_retrieval",
                reasons=[
                    payload["status"],
                    f"facts={len(payload['facts'])}",
                    f"documents={len(payload['documents'])}",
                ],
                latency_ms=(perf_counter() - started) * 1000,
            )
        )
        return payload

    def _prompt_wire(self, prompt, question):
        """Keep full sources in workspace; bound bulk source previews on the wire."""
        wire = {k: v for k, v in prompt.items() if k != "response_schema"}
        # Source checks/provenance stay in workspace and the M6 input, not the E picker.
        wire["evidence"] = [
            {
                **{
                    k: v
                    for k, v in row.items()
                    if k
                    in {
                        "id",
                        "observation_id",
                        "canonical_item_id",
                        "need_refs",
                        "label",
                        "value",
                        "unit",
                        "scale",
                        "period",
                        "operand_periods",
                        "graph_node_id",
                        "statement_type",
                        "reporting_scope",
                    }
                },
                "source_context": {
                    k: v
                    for k, v in (row.get("source_context") or {}).items()
                    if k in {"header", "table_id", "row_path", "column", "bindings"}
                },
            }
            for row in prompt.get("evidence", [])
        ]
        wire.pop("source_pages", None)
        wire["document_source_context"] = [
            document_view(view) for view in prompt.get("document_source_context", [])
        ]
        for original, view in zip(
            prompt.get("document_source_context", []), wire["document_source_context"], strict=True
        ):
            cells, headers = original.get("cells", []), original.get("headers", [])
            coordinates = {(r, c): value for r, c, value in cells}
            rows = sorted({r for r, _, _ in cells if isinstance(r, int)})
            # Render only a complete rectangle with its original header row.
            # Irregular tables retain the existing coordinate view without guessing cells.
            if (
                not headers
                or not rows
                or rows[0] != 0
                or len(coordinates) != len(cells)
                or len(cells) != len(rows) * len(headers)
                or any((r, c) not in coordinates for r in rows for c in range(len(headers)))
                or [coordinates[0, c] for c in range(len(headers))] != headers
            ):
                continue
            selectors = {}
            for handle, source in original.get("numeric_sources", {}).items():
                selectors.setdefault((source["row"], source["column"]), []).append(handle)
            lines = []
            for r in rows:
                rendered = ["row index" if r == 0 else str(r)]
                for c in range(len(headers)):
                    value = coordinates[r, c]
                    text = "[null]" if value is None else str(value)
                    text = (
                        text.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace("|", "&#124;")
                        .replace("\r\n", "\n")
                        .replace("\r", "\n")
                        .replace("\n", "<br>")
                    )
                    rendered.append(text + "".join(f" ⟦{h}⟧" for h in selectors.get((r, c), [])))
                lines.append("| " + " | ".join(rendered) + " |")
                if r == 0:
                    lines.append("| " + " | ".join(["---"] * (len(headers) + 1)) + " |")
            view["table_markdown"] = "\n".join(lines)
            view["table_reading_rule"] = (
                "Cột đầu là row index nguồn, row0 là header; các cột nguồn đánh số từ0 sau cột index. "
                "⟦S…⟧ là selector được cấp cho ô, không thuộc giá trị nguồn; sao chép S vào "
                "get_financial_fact, không chép lại số. [null] biểu diễn null, ô trống giữ trống; "
                "HTML entities/<br> chỉ escape ký tự/xuống dòng. numeric_sources giữ metadata ô."
            )
            for key in ("cells", "cell_columns"):
                view.pop(key, None)
        # Hydrating a few chunks can yield many facts/tables. Limit bulk source
        # rendering, without selecting financial meaning or changing stored data.
        source_chars = sum(
            len(json.dumps(wire.get(key, []), ensure_ascii=False))
            for key in ("evidence", "document_source_context")
        )
        question_level = any(
            r.get("kind") == "question" for r in wire.get("assigned_requirements", [])
        )
        if source_chars > 12000 or question_level:
            wire["evidence"] = [
                dict(
                    **{
                        k: row[k]
                        for k in (
                            "id",
                            "observation_id",
                            "canonical_item_id",
                            "need_refs",
                            "label",
                            "value",
                            "unit",
                            "scale",
                            "period",
                            "statement_type",
                            "source_item_code",
                            "reporting_scope",
                        )
                        if k in row
                        and row[k] is not None
                        and (k not in {"canonical_item_id", "need_refs"} or row[k])
                    },
                    header=row.get("source_context", {}).get("header"),
                    **(
                        dict(
                            source_locators=list(
                                binding["pointer"]
                                for binding in row["source_context"].get("bindings", [])[:1]
                            )
                        )
                        if "observation_id" in row
                        else {}
                    ),
                )
                for row in wire["evidence"]
            ]
            requested = {
                row["args"]["source"]
                for row in prompt.get("tool_results", [])
                if row.get("tool") == "get_evidence_item" and row.get("ok")
            }
            requested.update(
                v["handle"] for v in wire["document_source_context"] if v.get("explicit_read")
            )
            evidence_chars = len(
                json.dumps(wire["evidence"], ensure_ascii=False, separators=(",", ":"))
            )
            remaining = 12000 - evidence_chars
            if question_level:
                base_chars = len(
                    json.dumps(
                        wire | {"document_source_context": []},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                remaining = max(0, min(35000 - evidence_chars, 43000 - len(question) - base_chars))
            reasoning = prompt["role"] == "reasoning"
            views = []
            hydrated = False
            for view in sorted(
                wire["document_source_context"], key=lambda v: v["handle"] not in requested
            ):
                handle = view["handle"]
                candidate = view if handle in requested else None
                if reasoning and candidate is None and view.get("headers"):
                    candidate = self._handoff_table(
                        handle, prompt["scope"], include_selectors=question_level
                    )
                if (
                    question_level
                    and candidate is None
                    and view.get("text")
                    and not view.get("cells")
                ):
                    candidate = view
                size = (
                    len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))) + 1
                    if candidate is not None
                    else 0
                )
                if candidate is not None and size <= remaining:
                    views.append(candidate)
                    hydrated |= "table_rows" in candidate
                    remaining -= size
                else:
                    preview = dict(
                        handle=view["handle"],
                        table_title=view.get("table_title"),
                        headers=view.get("headers", []),
                        text_preview=view.get("text", "")[:320],
                        preview_only=True,
                        omitted_reason="source_context_budget" if size else "source_read_required",
                        source_page=view.get("source_page"),
                        content_range=view.get("content_range"),
                        source_bindings=view.get("source_bindings", []),
                        neighbors=view.get("neighbors", []),
                        reopen=dict(
                            tool="get_evidence_item",
                            source=view["handle"],
                            offset=0,
                            limit="Chọn số dòng dữ liệu (bảng) hoặc ký tự (text); giảm limit nếu vẫn preview",
                        ),
                    )
                    size = len(json.dumps(preview, ensure_ascii=False, separators=(",", ":"))) + 1
                    if not question_level or size <= remaining:
                        views.append(preview)
                        remaining -= size
            wire["document_source_context"] = views
            wire["source_preview_rule"] = (
                "preview_only là trích xem trước, không phải toàn bộ nguồn/miền so sánh. "
                "Dùng get_evidence_item(source:D) để đọc tài liệu đã chọn hoặc search_document_evidence "
                "với query/filters cụ thể để lấy phần cần thiết. Facts đầy đủ còn trong workspace; "
                "dùng E handles đã cấp, không suy thiếu nguồn từ preview."
            )
            if hydrated:
                wire["table_handoff_rule"] = (
                    "table_rows giữ nguyên cả dòng nhóm và thứ tự nguồn. Chỉ số r/c bắt đầu từ 0: "
                    "ô nguồn = table_pointer + /rows/r/c, tiêu đề cột = /columns/c. "
                    "Đọc kỳ/đơn vị theo cột và page_context. Dùng D đã cấp để mở lại hoặc trích "
                    "nguồn; bảng hiển thị tự nó không phải EO receipt hay toán hạng E."
                )
        if prompt["role"] == "reasoning":
            wire.pop("financial_data_guide")
            wire.pop("financial_catalog")
            if wire.get("additional_sources") and wire["evidence"]:
                wire["document_source_context"] = [
                    {
                        key: view[key]
                        for key in (
                            "handle",
                            "table_title",
                            "headers",
                            "source_page",
                            "preview_only",
                            "omitted_reason",
                            "reopen",
                        )
                        if key in view
                    }
                    if view.get("preview_only")
                    else view
                    for view in wire["document_source_context"]
                ]
            first = (
                "objective",
                "available_operands",
                "instruction",
                "evidence",
                "hydrated_selectors",
                "tool_results",
                "parent_results",
                "assigned_requirements",
            )
            wire = {"question": question, **{key: wire[key] for key in first if key in wire}} | wire
        return json.dumps(compact_prompt(wire), ensure_ascii=False, separators=(",", ":"))

    def _specialist(self, task, upstream, question, context, sources, output):
        state = self.workspace.tasks[task.task_id]
        inventory_sources = sources
        dependencies = self.workspace.dependency_ids(task)
        requirements = [
            r for r in self.workspace.requirements if r.requirement_id in task.requirement_ids
        ]
        state["fact_needs"], self._eo_fact_issues = _fact_need_scope(
            self.workspace.requirements, task.need_refs, sources, self._eo_issuer
        )
        if task.specialist == "retrieval":
            state["context_queries"] = [
                task.objective,
                question,
                *(
                    text
                    for goal in self.workspace.requirements
                    for ref, text in zip(goal.need_refs, goal.evidence_needs, strict=True)
                    if ref in task.need_refs
                ),
            ]
        dependency_sources = {
            handle
            for tid in dependencies
            for row in self.workspace.task_results[tid].get("source_context", [])
            for handle in self._document_views.get(row["handle"], {}).get("numeric_sources", {})
        }
        if task.specialist == "reasoning" and task.depends_on:
            inherited = {
                json.dumps(row["reference"]["observation"], sort_keys=True)
                for tid in dependencies
                for row in self.workspace.task_results[tid].get("selected_observations", [])
            }
            inventory_sources = {
                handle: source
                for handle, source in sources.items()
                if handle in dependency_sources
                or source["kind"] == "fact"
                and any(
                    json.dumps(
                        record.observation_identity().model_dump(mode="json"), sort_keys=True
                    )
                    in inherited
                    for record in source["records"]
                )
            }
        proposal = ScalarProposal
        ranked = rank_search_candidates(
            {
                h: " ".join(str(s[k] or "") for k in ("label", "item", "period", "kind"))
                for h, s in inventory_sources.items()
            },
            [question, task.objective, *(r.text for r in self.workspace.requirements)],
        )
        financial_catalog = {}
        for source in inventory_sources.values():
            if source["kind"] != "fact":
                continue
            for fact in source["records"]:
                entry = financial_catalog.setdefault(
                    fact.context.statement_type, dict(periods=[], canonical_items={})
                )
                if fact.context.period not in entry["periods"]:
                    entry["periods"].append(fact.context.period)
                if fact.canonical_item_id:
                    entry["canonical_items"][fact.canonical_item_id] = source["label"]
        analysis_schema = AnalysisProposal.model_json_schema()
        definitions = analysis_schema.pop("$defs", {})
        prompt = dict(
            instruction=(
                "Bạn là Specialist. Đáp ứng nguyên văn câu hỏi và assigned_requirements bằng nguồn đã pin. "
                "Vai trò retrieval tập trung tìm/đọc nguồn; reasoning tập trung liên kết evidence "
                "và lựa chọn phép tính. Dùng financial_data_guide để hiểu loại dữ liệu trước khi chọn "
                "nguồn; đó là ưu tiên, không phải giới hạn cứng. Đối chiếu canonical ID/nhãn trong "
                "financial_catalog; chỉ dùng canonical ID khi nhãn đáp ứng đủ nghĩa yêu cầu, "
                "không thay bằng chỉ tiêu gần nghĩa. Thiếu mapping không đồng nghĩa thiếu fact. "
                "Financial Tools được ưu tiên khi mapping phù hợp; Document Tools luôn là lựa chọn "
                "để đọc nguồn, không cần gọi Financial Tool trước. Nếu mapping thiếu/khác nghĩa, "
                "lookup quá rộng hoặc fact nhận được chưa đáp ứng yêu cầu, dùng search_document_evidence "
                "tìm cụm chỉ tiêu/tên bảng; evidence_type=table để đọc số liệu, both/text cho nội dung. "
                "Scope đã pin, query nên tập trung nội dung cần tìm. Đọc document_source_context: "
                "table_title, headers, table_markdown (hoặc cells cho bảng không chữ nhật) và "
                "numeric_sources giữ nguyên ngữ cảnh bảng. Đọc bảng cùng đơn vị/kỳ, so sánh các "
                "dòng gần nghĩa và các cột trước khi chọn ô. ⟦S…⟧ cạnh giá trị là selector ô đã cấp. Chọn dòng/cột "
                "đúng nghĩa, dùng S từ numeric_sources qua get_financial_fact để nhận E rồi đề xuất claim. "
                "Không dừng chỉ vì chưa có canonical ID, không thay thao tác này bằng D quote chung. "
                "Nếu top5 chưa đủ nghĩa vụ, đổi query/top_k hoặc dùng find_document_evidence "
                "đọc trang đã định vị; không mặc định trang kế tiếp cùng section. Raw label/mã số "
                "trong bảng và S selectors vẫn dùng được khi canonical projection chưa có mapping. "
                "Preview không đủ dữ liệu hàng: mở D bằng get_evidence_item; nếu vẫn preview, "
                "giảm limit và đọc các offset cần thiết (bảng giữ header/tọa độ gốc). "
                "Retrieval bàn giao tự động sau batch có source refs thật, không cần lượt final summary. "
                "Chọn batch acquisition phù hợp; nguồn vẫn có thể thiếu/sai kỳ. Reasoning nhận context, "
                "exact-open/hydrate hoặc request_work khi cần nguồn mới, rồi mới tạo candidate/phép tính. "
                "Reasoning được final trực tiếp bằng E/nguồn đã cấp nếu đủ cho candidate được chọn; "
                "không bắt đọc D/hydrate lại chỉ vì có preview hoặc task cha có missing inputs. "
                "Nếu context chưa đủ, chọn Tool hoặc request_work; thiếu nguồn thì final báo thiếu. "
                "Chọn period đúng nguyên dạng catalog hoặc header nguồn, "
                "đọc header/cột; không tự đổi số dư tại ngày thành số phát sinh trong năm. "
                "Chỉ dùng Tools được cấp cho role; Reasoning dùng Calculator thực thi "
                "Decimal; chưa tích hợp PythonAgent nâng cao. Trước hành động, đối chiếu evidence, "
                "document views, calculations và dependency results hiện có. Nếu chúng đáp ứng đầu "
                "ra thì đề xuất candidate ngay; candidate chưa được M6 kiểm chứng không phải lý do "
                "gọi Tool xác nhận lại. Nếu thiếu evidence và còn Tool/budget, truy xuất phần thiếu "
                "trước khi final missing_information. Không coi inventory là nguồn đã đọc. "
                "Evidence/Document views là ứng viên chưa verified; tự đánh giá đúng đối tượng, chỉ tiêu, "
                "cột, kỳ và unit. Claim phải cung cấp đầu ra được giao hoặc tiền đề cần thiết cho task "
                "phụ thuộc; việc tìm thấy một đoạn cùng tài liệu chưa đáp ứng yêu cầu. "
                "Nếu hỏi giá trị, cần claim nêu đúng giá trị/đơn vị/kỳ từ nguồn phù hợp; không chọn "
                "D source/query chỉ để tạo 'Tài liệu ghi …' thay câu trả lời số liệu. "
                "Trích dẫn D chỉ dùng khi nội dung trích thực sự đáp ứng yêu cầu đọc/trích tài liệu. "
                "Phân biệt ba namespace: S là selector của inventory/numeric_sources, chưa phải "
                "evidence; gọi get_financial_fact({source:S}) để nhận E. "
                "S của metric đi qua calculate_financial_metric để nhận metric evidence E. "
                "E là numeric evidence đã hydrate, dùng trong claims/Calculator; D là tài liệu/bảng. "
                "Document Selection {source:D,query:...} chỉ chọn nhãn dòng hoặc đoạn NGUYÊN VĂN "
                "thực có trong D; query không phải S/E/D handle và không phải câu hỏi diễn đạt lại. "
                "Nếu numeric_sources đã chỉ tới S phù hợp, lấy E bằng Financial Tool; không đặt S "
                "vào query của D claim, không final bằng S, không suy lại một giá trị đã báo cáo. "
                "Sau Tool, đọc status cùng args đã thử. candidates không phải lỗi: đối chiếu nhãn, "
                "header, kỳ và unit để chọn E đáp ứng requirement. refine là kết quả quá rộng, "
                "không phải nguồn không tồn tại: thu hẹp bằng filter có căn cứ từ catalog/context, "
                "giữ các ràng buộc còn đúng. empty: xem lại filters/query hoặc tìm nguồn bổ trợ. "
                "Không tự đặt source_page hoặc S/E/D/node IDs. cached vẫn có thể trả evidence đủ; "
                "đọc các refs trước khi truy xuất tiếp. Không lặp cùng truy xuất nếu không thay "
                "đầu vào có ích. Nguồn không liên quan chưa đủ để final. "
                "Khi task yêu cầu tập đối tượng và chọn theo giao dịch/chỉ tiêu, phải lấy "
                "nguồn chứa đúng tập và giá trị so sánh; giới thiệu doanh nghiệp không thay "
                "cho danh sách hoặc bảng giao dịch. Query nhắm nhãn bảng/quan hệ cần tìm; "
                "nếu hit chỉ cùng tên doanh nghiệp, đổi truy xuất thay vì chọn đoạn đó. "
                "Trả đúng một envelope theo bound schema. Tool dùng tool_calls với tool và args. "
                "Giữ source handles đã cấp và báo thiếu ngắn gọn khi không đủ nguồn. "
                "M6 kiểm chứng độc lập mọi candidate; kết quả Tool và task khác chưa verified."
            ),
            objective=task.objective,
            role=task.specialist,
            scope=dict(
                company_id=context.company_id,
                document_id=context.document_id,
                snapshot_id=context.snapshot_id,
                reporting_scope=context.reporting_scope,
            ),
            assigned_requirements=[
                r.model_dump(
                    mode="json",
                    include={
                        "requirement_id",
                        "kind",
                        "answer_goal",
                        "aspect",
                        "requested_unit",
                        "reasoning_operations",
                        "calculation_intent",
                        "text",
                        "evidence_needs",
                        "verification_requirements",
                    },
                )
                for r in self.workspace.requirements
                if r.requirement_id in task.requirement_ids
            ],
            financial_data_guide=FINANCIAL_DATA_GUIDE,
            financial_catalog=financial_catalog,
            inventory={
                h: {k: sources[h][k] for k in ("kind", "item", "period", "label")}
                for h in ranked[:5]
            },
            tools=dict(
                find_document_evidence=dict(
                    source_page="Trang nguồn đã định vị; trả các records đúng trang, không tự suy trang kế tiếp cùng section",
                    evidence_type="text hoặc table; bỏ để đọc cả trang",
                ),
                find_financial_facts=dict(
                    canonical_item_id="Canonical ID từ financial_catalog nếu có mapping",
                    source_label="Nhãn dòng nguyên văn khi không có canonical ID",
                    statement_type="Loại báo cáo từ financial_catalog; tra SourceFacts khi chưa có canonical mapping",
                    period="Kỳ nguồn chính xác từ financial_catalog; các filters kết hợp AND",
                    source_page="Trang nguồn nếu cần thu hẹp; company/document/snapshot đã được pin",
                ),
                get_financial_fact=dict(source="S handle of fact"),
                calculate_financial_metric=dict(source="S handle of metric"),
                search_document_evidence=dict(
                    query="cụm chỉ tiêu hoặc tên bảng; không cần lặp doanh nghiệp/kỳ đã pin nếu không giúp tìm nguồn",
                    evidence_type="both",
                    top_k=5,
                    context_radius=1,
                ),
                search_hybrid_evidence=dict(
                    query="Hybrid BM25+Dense trên chunks, hydrate evidence/SourceFacts gốc; document/snapshot đã pin",
                    top_k=5,
                ),
                get_evidence_item=dict(
                    source="D handle đã được tool trả",
                    offset="Vị trí bắt đầu, mặc định0; dòng dữ liệu của bảng hoặc ký tự text",
                    limit="Số dòng/ký tự cần đọc; giữ headers và tọa độ gốc; bỏ để đọc toàn record",
                ),
                calculate_dynamic=dict(
                    steps="operator/inputs/period_relation; Python gán R1/R2 và lấy E operands từ inputs",
                ),
                get_evidence_sources=dict(evidence_id="E handle"),
                get_graph_context=dict(node_id="node ID returned by tool", depth=1, limit=8),
            ),
            response_schema=dict(
                **{"$defs": definitions},
                type="object",
                oneOf=[
                    dict(
                        required=["tool_calls"],
                        additionalProperties=False,
                        properties=dict(
                            tool_calls=dict(
                                type="array",
                                minItems=1,
                                maxItems=16,
                                items=dict(
                                    type="object",
                                    required=["tool", "args"],
                                    additionalProperties=False,
                                    properties=dict(
                                        tool=dict(type="string"), args=dict(type="object")
                                    ),
                                ),
                            ),
                        ),
                    ),
                    dict(
                        required=["claims", "analyses", "missing_information"],
                        additionalProperties=False,
                        properties=dict(
                            claims=dict(
                                type="array",
                                maxItems=32,
                                items=dict(
                                    oneOf=[
                                        dict(type="string", description="E handle đã nhận từ Tool"),
                                        dict(
                                            type="object",
                                            required=["source", "query"],
                                            additionalProperties=False,
                                            properties=dict(
                                                source=dict(
                                                    type="string", description="D handle đã lưu"
                                                ),
                                                query=dict(
                                                    type="string",
                                                    description="Đoạn hoặc nhãn dòng nguồn",
                                                ),
                                            ),
                                        ),
                                    ]
                                ),
                            ),
                            analyses=dict(type="array", maxItems=8, items=analysis_schema),
                            missing_information=dict(
                                type="array",
                                items=dict(type="string"),
                                description="Nếu chưa đề xuất claim, nêu requirement/phần bằng chứng còn thiếu và cần đối chiếu gì; không kết thúc bằng cả ba mảng rỗng.",
                            ),
                        ),
                    ),
                ],
            ),
            shared_tasks={
                tid: dict(
                    result_handle=r.get("result_handle"),
                    request_work=self.workspace.task_results[tid].get("request_work"),
                    statements=r.get("candidate_statements", []),
                    calculations=r.get("calculations", []),
                    missing_inputs=r.get("missing_inputs", []),
                )
                for tid in dependencies
                for r in [self.workspace.tasks[tid]]
            },
        )
        parent_calculations = {}
        if task.specialist == "reasoning":
            for tid in task.depends_on:
                parent = self.workspace.task_results[tid]
                for index, candidate in enumerate(parent["candidates"], 1):
                    if calculation := (candidate.get("reasoning") or {}).get("calculation"):
                        parent_calculations[f"R:{tid}:{index}"] = calculation
            prompt["instruction"] = (
                "Chỉ hoàn thành objective của task hiện tại. Câu hỏi gốc cho biết đích chung. "
                "Đối chiếu chỉ tiêu, kỳ, đơn vị và EO của objective với evidence đã cấp. "
                'Trả Final qua {"actions":[...]}. Với phép tính có các bước phụ thuộc nhau, '
                "dùng một action=calculate gồm prior_steps và final_step cho kết quả được hỏi. "
                "Nếu cần đúng một phép tính, dùng final_step trực tiếp trên E hoặc dạng indexed. "
                "E là SourceFact. Đọc một ô đã trả lời đủ thì chọn trực tiếp E. "
                "Trước khi chọn operator, đối chiếu vai trò từng đầu vào với item, kỳ và đơn vị "
                "của Goal. Lập final_step từ các đầu vào cần thiết rồi chỉ giữ prior_steps tạo ra "
                "những đầu vào đó. Nếu chỉ có một prior_step thì final_step chỉ có R1 và các E đã cấp. "
                "prior_steps đánh số từ 1: phần tử đầu tạo R1, phần tử hai tạo R2. "
                "Chỉ dùng R sau khi bước tạo R đã được khai trong cùng action. Khi kết quả cuối "
                "kết hợp hai kết quả trung gian, inputs của final_step phải trỏ đúng hai R theo "
                "thứ tự yêu cầu. Không thay R bằng SourceFact. Mỗi action formula_id hoặc indexed "
                "là một quyết định độc lập, không tạo R cho action khác. Chỉ dùng index nguyên "
                "từ available_operands khi một phép tính là đủ. Đối chiếu nhãn, kỳ và đơn vị. "
                "Với dạng indexed, có thể bỏ period_relation để runtime xác định theo metadata. "
                "Toán tử: add cộng; subtract(a,b)=a-b giữ đơn vị, dùng cho chênh lệch tuyệt đối. "
                "relative_difference=(a-b)/b cho ratio; percentage_change=(a-b)/b×100 và "
                "percentage_of=a/b×100 cho percent; divide/ratio=a/b. percentage_of và "
                "percentage_change đã trả %, không thêm bước nhân 100. Hiệu hai tỷ trọng % "
                "là chênh lệch điểm phần trăm, dùng subtract. "
                "sum/mean nhận nhiều inputs; multiply cần một toán hạng ratio. "
                "greater/less/equal trả boolean. Với chương trình nhiều bước, dùng same khi cùng kỳ "
                "và across_periods khi khác kỳ, kể cả hai ngày đầu/cuối cùng năm. "
                "Giữ chiều operands và đơn vị; phép chia cần mẫu khác 0. "
                "Bước đầu chỉ dùng E hoặc handle R:T... thực có trong parent_results. "
                "Dùng handle cha thay cho tính lại; steps của cha là proof để đọc. "
                "Nếu khai evidence_ids, chỉ liệt kê E thực dùng. Không tự đặt handle hoặc dùng số literal. "
                "direct chọn E cho giá trị báo cáo. interpret dùng statement và evidence_ids hoặc steps. "
                "document dùng D và cụm query nguyên văn. Mở S từ inventory/additional_sources bằng "
                "get_financial_fact, đọc bảng qua get_evidence_item, hoặc request_work khi thiếu nguồn. "
                "Nếu không đủ dữ kiện hoặc không biểu diễn được bằng toán tử có sẵn, trả action=need_more "
                "với missing_information. M6 kiểm chứng claim và EO độc lập."
            )
        if not self.graph_enabled:
            prompt["tools"].pop("get_graph_context")
        if self.composition is None or self.document_repository is None:
            prompt["tools"].pop("search_document_evidence")
            prompt["tools"].pop("get_evidence_item")
            prompt["tools"].pop("find_document_evidence")
        if (
            task.specialist != "retrieval"
            or not self._hybrid_tool.available
            or self.composition is None
            or self.document_repository is None
            or self.composition.financial_snapshot.source_kind != "json"
        ):
            prompt["tools"].pop("search_hybrid_evidence")
        action_schema = prompt["response_schema"]
        action_tools = {
            name: signature
            for name, signature in prompt["tools"].items()
            if name in SPECIALIST_TOOLS_BY_ROLE[task.specialist]
        }
        last_results = []
        tool_cache = getattr(self, "_request_tool_cache", {})
        cache_scope = (
            (task.need_refs, state["context_queries"]) if task.specialist == "retrieval" else ()
        )
        repeated_turns = 0
        final = None
        if task.specialist == "retrieval":
            if task.need_refs:
                prompt["instruction"] += (
                    " Chỉ truy xuất các EO trong assigned_evidence_needs. Dùng Goal và câu hỏi "
                    "làm ngữ cảnh, giữ đúng chỉ tiêu hoặc điều kiện được giao."
                )
            prompt["assigned_evidence_needs"] = {
                ref: text
                for ref, (_, text) in _assigned_needs(requirements, task.need_refs).items()
            }
        question_level = any(isinstance(r, QuestionRequirement) for r in requirements)
        question_reasoning = question_level and task.specialist == "reasoning"
        indexed = question_reasoning and self.simplified_reasoning
        if question_level and self.workspace.question_understanding:
            prompt["question_understanding"] = self.workspace.question_understanding
        if question_reasoning:
            prompt["instruction"] = (
                "Trả lời từng yêu cầu trong question gốc. Trong requirement_mapping, ghi nhãn "
                "ngắn cho mỗi vế answer, mỗi operand và condition cần thiết. Gắn E của đúng chỉ "
                "tiêu, kỳ, đơn vị và dấu, hoặc D của bảng/đoạn thực sự có nguồn. Dùng [] khi thiếu "
                "nguồn. Đọc đủ các vế và điều kiện từ question kể cả khi đang recovery. "
                "Nếu evidence có đúng chỉ tiêu và kỳ, trả ngay action direct với E đó. "
                "hydrated_selectors nối S với E đã có. Chỉ mở S chưa có E; nếu chưa thấy ô, dùng find_financial_facts với "
                "canonical_item_id hoặc source_label, period và statement_type khi biết; "
                "hoặc request_work ghi rõ chỉ tiêu/bảng cần tìm.\n"
                "Với phép tính, ghi từng khoản đầu vào thành một operand riêng trước actions. "
                "Gồm mọi khoản nguồn và mọi khoản sử dụng được nêu; mỗi khoản đúng một E. "
                "Dùng calculate.steps; bước đầu tạo R1. Ví dụ cộng các giá trị cùng kỳ theo "
                'dấu nguồn: {"operator":"sum","inputs":["E1","E2","E3"],"period_relation":"same"}. '
                "Dùng add, subtract, divide với hai đầu vào; subtract(A,B)=A−B. Các khoản chi "
                "đã mang dấu âm được cộng vào tiền có sẵn; chỉ trừ nếu đã chuyển thành độ lớn "
                "dương. Không lấy khoản gần tên hoặc nhập số literal. Thiếu E thì mở nguồn trước.\n"
                "Với câu nhiều vế, phân biệt điều phải trả lời với tiền đề. Đối chiếu đúng đối "
                "tượng và header số đầu kỳ, tăng, giảm, số cuối kỳ giữa các bảng. "
                "Dùng document với D và query là nhãn dòng/đoạn nguyên văn của nguồn: ưu tiên "
                "một dòng chứa tên, số trong kỳ và số dư cùng đối tượng. Giữ dấu gạch nguồn. "
                "Đừng dùng số dư của khoản mục khác hoặc số tổng thay cho số dư đối tượng. "
                "Tách action theo vế. Mệnh đề có số phải dùng direct, calculate hoặc trích "
                "đúng hàng nguồn bằng document. interpret chỉ diễn giải quan hệ định tính "
                "và không tự chép số từ các chỉ tiêu khác. Nếu thiếu một vế, ghi phần thiếu. "
                "D preview có thể mở bằng get_evidence_item. M6 sẽ xác minh độc lập."
            )
        elif question_level:
            prompt["instruction"] += (
                " Dùng objective của request_work và câu hỏi gốc để tìm phần nguồn còn thiếu."
            )
        recovery = state.get("answer_recovery") or next(
            (
                self.workspace.tasks[tid]["answer_recovery"]
                for tid in dependencies
                if "answer_recovery" in self.workspace.tasks[tid]
            ),
            None,
        )
        if recovery:
            prompt["answer_recovery"] = {
                key: value for key, value in recovery.items() if key != "context_delta"
            }
        retrieval_attempted = False
        proof_key = None
        for turn in range(getattr(self.gateway, "max_calls", 16)):
            if repeated_turns:
                break  # No extra generation merely to close a repeated tool action.
            dependency_handles = [
                row["handle"]
                for tid in dependencies
                for row in self.workspace.task_results[tid].get("source_context", [])
            ]
            if task.specialist == "reasoning":
                dependency_handles.extend(
                    handle
                    for handle in self._document_views
                    if handle in self._initial_refs and handle not in dependency_handles
                )
            if recovery:
                expanded = set(recovery.get("context_delta", ()))
                dependency_handles.sort(key=lambda h: h not in expanded)
            task_documents = set(dependency_handles) | {
                r["handle"] for r in state.get("source_context", [])
            }
            prompt["turn"] = turn + 1
            prompt["loop_feedback"] = (
                "Đọc evidence/calculations: đúng nguồn thì chốt proposal. Chỉ tìm hoặc tính "
                "thêm cho phần còn thiếu cụ thể."
            )
            prompt["calculations"] = state.get("calculations", [])
            if hasattr(self.gateway, "remaining_generation_calls"):
                prompt["remaining_calls"] = dict(
                    specialists=self.gateway.remaining_generation_calls,
                    verification_reserved=self.gateway.verification_calls,
                )
            result = self._evidence(task, upstream, question)
            facts = {f.reference.observation: f.record for f in upstream.evidence_bundle.facts}
            prompt["evidence"] = [
                dict(
                    id=e.evidence_id,
                    graph_node_id=graph_id("source_fact", e.reference.observation.model_dump())
                    if e.reference.observation
                    else e.calculation.metric_id,
                    label=e.label,
                    value=e.value,
                    unit=e.unit,
                    scale=e.scale,
                    period=e.period,
                    **(
                        dict(
                            statement_type=facts[e.reference.observation].context.statement_type,
                            source_item_code=facts[e.reference.observation].source_item_code,
                            reporting_scope=facts[e.reference.observation].context.reporting_scope,
                        )
                        if question_reasoning and e.reference.observation
                        else {}
                    ),
                    operand_periods=e.operand_periods,
                    source_caveats=e.caveats,
                    **(
                        dict(
                            observation_id=e.reference.observation.local_id,
                            canonical_item_id=e.canonical_item_id,
                        )
                        if task.specialist == "reasoning" and e.reference.observation
                        else {}
                    ),
                    source_context=dict(
                        header=facts[e.reference.observation].raw_header,
                        table_id=facts[e.reference.observation].source_metadata.get("table_id"),
                        row_path=facts[e.reference.observation].source_metadata.get("row_path"),
                        column=facts[e.reference.observation].source_metadata.get("source_column"),
                        bindings=[
                            dict(
                                source=c.source.reference.anchor.page.source_ref,
                                pointer=c.source.reference.source_pointer,
                                provenance_level=c.provenance_level,
                            )
                            for c in e.citations
                            if c.source.reference
                        ],
                    )
                    if e.kind == "fact"
                    else None,
                )
                for e in result.supporting_evidence
            ]
            if indexed:
                cell_titles = {
                    evidence_handle(match): match.record.source_metadata.get("table_title")
                    for match in upstream.evidence_bundle.facts
                    if match.record.source_metadata.get("projection") == "document_cell"
                }
                for row in prompt["evidence"]:
                    if row["id"] in cell_titles:
                        row["source_kind"] = "document_cell"
                        row["source_context"]["title"] = cell_titles[row["id"]]
            preferred = [h for row in last_results for h in row["evidence_refs"]]
            if recovery:
                preferred.extend(recovery.get("context_delta", ()))
            prompt["source_pages"] = {
                c.source.reference.anchor.page.source_ref: c.source.reference.anchor.page.model_dump(
                    mode="json"
                )
                for c in [
                    *upstream.evidence_bundle.citations,
                    *(c for _, hit in self._document_hits.values() for c in hit.evidence.citations),
                ]
                if c.source.reference
            }
            prompt["evidence"].sort(key=lambda row: row["id"] not in preferred)
            available_parents = {}
            parent_scope = False
            additional_sources = {}
            operand_rows = []
            formula_options = []
            single_formulas = []
            prompt.pop("financial_formulas", None)
            if task.specialist == "reasoning":
                visible = {row["id"] for row in prompt["evidence"]}
                bindings = {
                    ref: list(
                        dict.fromkeys(
                            eid
                            for receipt in state.get("need_tool_results", [])
                            if ref in receipt["need_refs"]
                            for eid in receipt["evidence_refs"]
                            if eid in visible
                        )
                        | dict.fromkeys(
                            eid
                            for tid in dependencies
                            for eid in self.workspace.task_results[tid]
                            .get("need_bindings", {})
                            .get(ref, {})
                            .get("evidence_refs", [])
                            if eid in visible
                        )
                    )
                    for ref in task.need_refs
                }
                for row in prompt["evidence"]:
                    row["need_refs"] = [ref for ref, ids in bindings.items() if row["id"] in ids]
                available_parents = (
                    _available_parent_proofs(
                        parent_calculations, result.supporting_evidence, context
                    )
                    if parent_calculations
                    else {}
                )
                prompt["evidence"], additional_sources = _task_evidence_view(
                    task.objective,
                    prompt["evidence"],
                    bindings,
                    available_parents,
                    sources,
                    state.get("tool_evidence_ids", ()),
                )
                visible = {row["id"] for row in prompt["evidence"]}
                if not available_parents and any(r.kind == "metric" for r in requirements):
                    formula_options = _formula_options(
                        (e for e in result.supporting_evidence if e.evidence_id in visible),
                        facts,
                        context,
                    )
                if formula_options:
                    prompt["financial_formulas"] = formula_options
                prompt["assigned_evidence_needs"] = {
                    ref: [eid for eid in eids if eid in visible] for ref, eids in bindings.items()
                }
                prompt["source_need_receipts"] = {
                    tid: receipts
                    for tid in dependencies
                    if (
                        receipts := {
                            ref: binding
                            for ref, binding in self.workspace.task_results[tid]
                            .get("need_bindings", {})
                            .items()
                            if ref in bindings
                            and binding["tool_result_ids"]
                            and binding["evidence_refs"]
                        }
                    )
                }
                prompt["unresolved_evidence_needs"] = [
                    ref
                    for ref, ids in bindings.items()
                    if not ids
                    and not any(
                        ref in receipts for receipts in prompt["source_need_receipts"].values()
                    )
                ]
                parent_scope = _parent_operand_scope(
                    task,
                    requirements,
                    prompt["assigned_evidence_needs"],
                    available_parents,
                    self.workspace.tasks,
                )
                single_formulas = (
                    _single_formula_options(
                        task,
                        requirements,
                        bindings,
                        prompt["assigned_evidence_needs"],
                        formula_options,
                        self.workspace.tasks,
                    )
                    if not parent_calculations
                    else []
                )
                if additional_sources:
                    prompt["additional_sources"] = additional_sources
                else:
                    prompt.pop("additional_sources", None)
                if available_parents:
                    prompt["parent_results"] = {
                        ref: dict(
                            task_id=tid,
                            result_handle=self.workspace.task_results[tid]["handle"],
                            revision=self.workspace.task_results[tid]["revision"],
                            digest=self.workspace.task_results[tid]["digest"],
                            objective=self.workspace.tasks[tid]["objective"],
                            steps=proof["steps"],
                            value=last["result"],
                            unit=last["unit"],
                            periods=last["periods"],
                        )
                        for ref, proof in available_parents.items()
                        for tid in [ref.split(":")[1]]
                        for last in [proof["steps"][-1]]
                    }
                for ref in available_parents:
                    parent = prompt["parent_results"][ref]
                    operand_rows.append(
                        (
                            ref,
                            dict(
                                kind="parent_result",
                                handle=ref,
                                label=parent["objective"],
                                value=parent["value"],
                                unit=parent["unit"],
                                periods=parent["periods"],
                            ),
                        )
                    )
                operand_rows.extend(
                    (
                        row["id"],
                        dict(
                            kind="source_evidence",
                            label=row["label"],
                            value=row["value"],
                            unit=row["unit"],
                            periods=[row["period"]],
                            **({"scale": row["scale"]} if row["scale"] != "1" else {}),
                        ),
                    )
                    for row in prompt["evidence"]
                    if row["source_context"]
                    and (not parent_scope or row["id"] in state.get("tool_evidence_ids", ()))
                )
                if not question_reasoning:
                    prompt["available_operands"] = [
                        dict(index=index, **row) for index, (_, row) in enumerate(operand_rows)
                    ]
            prompt["tool_results"] = [
                {
                    k: v
                    for k, v in row.items()
                    if k != "data"
                    or row.get("error")
                    or row.get("tool") in {"get_graph_context", "get_evidence_sources"}
                }
                for row in last_results
            ]
            prompt["document_sources"] = {
                h: dict(
                    kind=hit.evidence.reference.kind,
                    page=hit.source_page or hit.pdf_page,
                    source_caveats=hit.limitations,
                )
                for h, (search, hit) in self._document_hits.items()
                if h in task_documents
            }
            prompt["document_source_context"] = [
                self._document_views[h]
                for h in dict.fromkeys(
                    [
                        *preferred,
                        *dependency_handles,
                        *(r["handle"] for r in state.get("source_context", [])),
                    ]
                )
                if h in self._document_views
            ]
            visible_sources = (
                set(prompt["inventory"])
                | {
                    handle
                    for view in prompt["document_source_context"]
                    for handle in view.get("numeric_sources", {})
                }
                | additional_sources.keys()
            )
            hydrated_selectors = {}
            if question_reasoning:
                ready = {
                    row["observation_id"]: row["id"]
                    for row in prompt["evidence"]
                    if row.get("observation_id")
                }
                hydrated_selectors = {
                    handle: ready[record.local_observation_id]
                    for handle in sorted(visible_sources)
                    if (source := sources.get(handle)) and source["kind"] == "fact"
                    if len(source["records"]) == 1
                    and (record := source["records"][0]).local_observation_id in ready
                }
                prompt["hydrated_selectors"] = hydrated_selectors
            source_kinds = {sources[h]["kind"] for h in visible_sources if h in sources}
            available_tools = {
                name: signature
                for name, signature in action_tools.items()
                if not (
                    question_reasoning
                    and name in {"calculate_dynamic", "calculate_financial_metric"}
                )
                and (
                    name not in {"get_financial_fact", "calculate_financial_metric"}
                    or ("fact" if name == "get_financial_fact" else "metric") in source_kinds
                )
                and (
                    name != "get_graph_context"
                    or prompt["evidence"]
                    or any(r["tool"] == "get_graph_context" and r.get("data") for r in last_results)
                )
            }
            retrieval_tools = {
                name: signature
                for name, signature in available_tools.items()
                if name
                in {
                    "search_hybrid_evidence",
                    "search_document_evidence",
                    "find_document_evidence",
                    "get_evidence_item",
                    "get_financial_fact",
                    "find_financial_facts",
                    "get_evidence_sources",
                    "get_graph_context",
                }
                and (
                    name != "get_financial_fact"
                    or any(s["kind"] == "fact" for s in sources.values())
                )
                and (name != "get_evidence_item" or self._document_hits)
                and (
                    name not in {"get_evidence_sources", "get_graph_context"} or prompt["evidence"]
                )
            }
            # Cold Retrieval acquires sources; Reasoning may report missing inputs.
            retrieval_required = (
                task.specialist == "retrieval"
                and not retrieval_attempted
                and not prompt["evidence"]
                and not prompt["document_sources"]
                and bool(retrieval_tools)
            )
            prompt["phase"] = "tool_or_proposal"
            prompt["response_schema"] = action_schema
            prompt["tools"] = available_tools
            prompt["retrieval_phase"] = "shared_tools"
            if retrieval_required:
                prompt["phase"] = "retrieval_required"
                prompt["tools"] = retrieval_tools
                prompt["loop_feedback"] = (
                    "Task chưa thực hiện truy xuất và chưa có nguồn đã nạp. "
                    "Chọn retrieval Tool phù hợp objective/assigned_requirements cho phần thiếu. "
                    "Chỉ trả tool_calls; không sinh missing_information hoặc lời giải thích. "
                    "Không tự dựng nguồn; bỏ argument tùy chọn không có giá trị."
                )
            if task.specialist == "retrieval":
                prompt["loop_feedback"] += (
                    " Tool call chỉ có tool và args; runtime gắn refs. Khi cần đọc bảng hoặc chưa biết "
                    "định danh chỉ tiêu, dùng search_document_evidence (evidence_type=table) hoặc "
                    "search_hybrid_evidence với cụm nhãn và tên bảng. Reasoning sẽ chọn dòng/cột. "
                    "Chỉ lookup exact khi có selector hoặc mã khớp nhãn chắc chắn."
                )
            prompt["response_schema"] = bind_specialist_schema(
                prompt["response_schema"],
                proposal,
                prompt["evidence"],
                {h: row for h, row in self._document_hits.items() if h in task_documents},
                prompt["tools"],
                need_refs=task.need_refs,
                role=task.specialist,
                operand_ids=[row["id"] for row in prompt["evidence"] if row["source_context"]],
                parent_operands=available_parents,
                parent_decision=parent_scope,
                operand_count=len(operand_rows),
                formulas=formula_options,
                requirements=requirements,
                input_results=[self.workspace.task_results[tid]["handle"] for tid in dependencies],
            )
            if retrieval_required:
                bound = prompt["response_schema"]
                branches = [
                    branch
                    for branch in bound["oneOf"]
                    if "tool_calls" in branch.get("properties", {})
                    or "request_work" in branch.get("properties", {})
                ]
                prompt["response_schema"] = dict(
                    type="object",
                    **{"$defs": bound["$defs"]},
                    **(dict(oneOf=branches) if len(branches) > 1 else branches[0]),
                )
            bound = prompt["response_schema"]
            action = bound["oneOf"][0] if "oneOf" in bound else bound
            calls = action.get("properties", {}).get("tool_calls")
            prompt["tools"] = (
                {
                    variant["properties"]["tool"]["enum"][0]: prompt["tools"][
                        variant["properties"]["tool"]["enum"][0]
                    ]
                    for variant in calls["items"]["oneOf"]
                    if calls
                }
                if calls
                else {}
            )
            aliases = {e["id"]: f"E{i}" for i, e in enumerate(prompt["evidence"], 1)}
            indexed_operands = tuple(
                (aliases.get(handle, handle), tuple(row["periods"])) for handle, row in operand_rows
            )
            atomic = (
                task.specialist == "reasoning"
                and not formula_options
                and _atomic_calculation_ready(
                    task, self.workspace, len(indexed_operands), prompt["assigned_evidence_needs"]
                )
            )
            if indexed:
                draft = self.workspace.question_understanding
                options, bindings = indexed_reasoning.evidence_options(
                    prompt, self._document_hits, question, draft, self._document_views
                )
                wire_schema = indexed_reasoning.selection_schema(len(bindings))
                previous = (recovery or {}).get("feedback", {})
                covered = {
                    slot["slot_id"]
                    for slot in previous.get("completion", {}).get("Q1", {}).get("slots", [])
                    if slot.get("candidate_ids")
                }
                obligations = [
                    {k: v for k, v in row.items() if v and k != "derivation"}
                    for row in (self.workspace.expected_answers or {}).get("requirements", [])
                    if row["requirement_id"] not in covered
                ]
                projected = dict(
                    instruction=(
                        "Giải quyết từng requirement còn thiếu theo câu hỏi gốc. "
                        "Với phép tính, chọn index trong cells cho từng toán hạng theo đúng kỳ, "
                        "phạm vi và vai trò: a đứng trước b trong a/b, a-b và (a-b)/b. "
                        "Chọn đủ hai index khi hai kỳ nằm cùng financial_row. "
                        "numeric_indices trên hàng trích dẫn tới các ô có thể dùng để tính. "
                        "Với giá trị trực tiếp hoặc tên thực thể, dùng operator=none và chọn ô "
                        "hoặc hàng trực tiếp chứng minh vế hỏi. Với câu nhiều nguồn, tìm tên bên, "
                        "khoản mục và kỳ nối các bằng chứng trước khi kết luận. "
                        "Số bằng nhau chưa xác nhận cùng khoản mục. Giữ nguyên dấu gạch. "
                        "Chỉ chọn evidence làm đáp án cho vế hỏi. Giữ fact trung gian làm tiền đề. "
                        "Ghi missing cho toán hạng, liên kết hoặc vế thực sự chưa có."
                    ),
                    requirements=obligations or draft.get("requirements", []),
                    options=options,
                    feedback=(
                        dict(
                            focus=recovery["objective"],
                            missing=previous.get("missing_evidence", [])[:4],
                            verification=(
                                previous.get("numeric", []) + previous.get("documents", [])
                            )[:3],
                        )
                        if recovery
                        else None
                    ),
                )
            elif single_formulas:
                wire_schema = _map_evidence_handles(
                    formula_decision_schema(single_formulas), aliases
                )
                goal = prompt["assigned_requirements"][0]
                operand_ids = {
                    eid for formula in single_formulas for eid in formula["operands"].values()
                }
                projected = _map_evidence_handles(
                    dict(
                        instruction=(
                            "Chọn đúng một công thức và gắn E vào từng vai trò để hoàn thành "
                            "objective hiện tại. Câu hỏi gốc cho biết mục tiêu chung. "
                            "Trả một object JSON với formula_id và bindings."
                        ),
                        objective=task.objective,
                        role=task.specialist,
                        scope=prompt["scope"],
                        goal={
                            key: goal[key]
                            for key in (
                                "requirement_id",
                                "evidence_needs",
                                "verification_requirements",
                            )
                            if key in goal
                        },
                        assigned_evidence_needs={
                            ref: [eid for eid in eids if eid in operand_ids]
                            for ref, eids in prompt["assigned_evidence_needs"].items()
                        },
                        evidence=[row for row in prompt["evidence"] if row["id"] in operand_ids],
                        financial_formulas=single_formulas,
                    ),
                    aliases,
                )
            elif atomic:
                wire_schema = indexed_calculation_schema(len(indexed_operands))
                projected = dict(
                    objective=task.objective,
                    available_operands=prompt["available_operands"],
                    instruction=(
                        "Chọn operator theo objective và đơn vị kết quả. "
                        "inputs là các chỉ số trong available_operands theo thứ tự [A,B,...]; "
                        "đối chiếu nhãn, kỳ và đơn vị. Với hai đầu vào, A đứng trước B. "
                        "period_relation có thể bỏ qua hoặc khai same/across_periods khớp kỳ nguồn. "
                        "add: A+B; subtract: A−B (hiệu có dấu). sum: tổng; mean: trung bình "
                        "(2–16 đầu vào). Bốn phép này giữ nguyên đơn vị. "
                        "divide/ratio: A/B; relative_difference: (A−B)/B. Cả hai dạng cho tỷ số "
                        "không đơn vị. percentage_of: (A/B)×100; percentage_change: ((A−B)/B)×100. "
                        "Hai phép này cho %, lấy B làm mẫu số. multiply: A×B, ít nhất một đầu vào "
                        "là ratio, kết quả theo đơn vị đầu vào kia. "
                        "greater: A>B; less: A<B; equal: A=B, kết quả đúng/sai."
                    ),
                )
            else:
                wire_schema = _map_evidence_handles(bound, aliases)
                projected = _map_evidence_handles(
                    json.loads(self._prompt_wire(prompt, question)), aliases
                )
                if parent_scope:
                    projected["instruction"] = (
                        "Chỉ hoàn thành objective hiện tại. Khi kết hợp kết quả đã bàn giao, "
                        "trả một object JSON có operator và inputs là các handle từ parent_results "
                        "theo đúng thứ tự phép toán. Nếu khai period_relation, giá trị phải khớp kỳ "
                        "của các toán hạng. Giữ chiều theo câu hỏi gốc. "
                        "Nếu objective cần cả dữ kiện nguồn, dùng action calculate với final_step "
                        "và các E/R đã cấp hoặc mở nguồn bằng Tool. "
                        "Nếu chưa đủ căn cứ, dùng need_more với missing_information. "
                        "M6 kiểm chứng claim và EO độc lập."
                    )
                elif (
                    task.specialist == "reasoning"
                    and not question_reasoning
                    and "FinalOperand" in bound.get("$defs", {})
                ):
                    projected["instruction"] += (
                        " Trả một JSON gọn trên một dòng. Sau mỗi giá trị, xuất ngay dấu "
                        "phẩy hoặc dấu đóng tương ứng, không chèn tab, xuống dòng hoặc chuỗi khoảng trắng. "
                        "Điền đủ trường bắt buộc theo schema của request, kể cả assumptions, "
                        "limitations trong action và missing_information, missing_need_inputs "
                        "ngoài actions nếu schema yêu cầu. Theo chỉ dẫn adapter cho trường tùy chọn. "
                        "Đếm prior_steps trước khi đóng final_step; chỉ dùng các R đã tạo. "
                        "Ví dụ một action trong actions: tổng chi phí XYZ 2024 trừ 2023. "
                        "E1,E2 là chi phí A,B của 2024; E3,E4 là chi phí A,B của 2023. "
                        '{"action":"calculate","prior_steps":['
                        '{"operator":"add","inputs":["E1","E2"],"period_relation":"same"},'
                        '{"operator":"add","inputs":["E3","E4"],"period_relation":"same"}],'
                        '"final_step":{"operator":"subtract","inputs":["R1","R2"],'
                        '"period_relation":"across_periods"},"evidence_ids":["E1","E2","E3","E4"],'
                        '"assumptions":[],"limitations":[]}. Đóng toàn bộ object JSON sau metadata.'
                    )
                if formula_options:
                    projected["instruction"] += (
                        " Chỉ dùng formula_id và operands khi một mục trong financial_formulas "
                        "tính trực tiếp toàn bộ objective. Khi công thức là bước trung gian, "
                        "dùng toán tử và E theo đúng vai trò của công thức trong prior_steps."
                    )
            discriminated = task.specialist == "reasoning" and (
                indexed
                or single_formulas
                or atomic
                or any(
                    {"action", "actions"} & branch["properties"].keys()
                    for branch in wire_schema.get("oneOf", [wire_schema])
                )
            )
            wire = json.dumps(
                projected,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if context.model.provider != "qwen" and len(wire) + len(question) > 48000:
                state.setdefault("operation_errors", []).append(
                    dict(operation="specialist", code="CONTEXT_LIMIT")
                )
                break
            if self.gateway is None or context.mode == "deterministic":
                result.missing_evidence.append("specialist_gateway_required")
                break
            begin = perf_counter()
            response = self.gateway.generate(
                LLMRequest(
                    contract_version="llm_gateway_v1",
                    request_id="m5-specialist-" + task.task_id + "-" + uuid4().hex,
                    model=context.model,
                    messages=[
                        Message(role="system", content=wire),
                        Message(role="user", content=question),
                    ],
                    generation=GenerationParameters(
                        temperature=0.0,
                        max_output_tokens=500
                        if indexed
                        else 4000
                        if task.specialist == "reasoning"
                        and any(isinstance(r, QuestionRequirement) for r in requirements)
                        else 2500,
                    ),
                    output_spec=OutputSpec(
                        format="json",
                        json_schema=wire_schema,
                    ),
                    constraints=RequestConstraints(
                        timeout_seconds=context.provider_timeout_seconds
                    ),
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
                latency_ms=(perf_counter() - begin) * 1000,
            )
            output.usage.stages[f"{task.task_id}_turn_{turn + 1}"] = metadata
            result.llm = metadata
            if (
                response.error
                and response.error.origin == "gateway"
                and response.error.category == "quota_exceeded"
            ):
                state["stop_reason"] = "budget_exhausted"
                result.missing_evidence.append("specialist_budget_reserved_for_m6")
                break
            validation_issues = response.error.validation_issues if response.error else []
            try:
                if (
                    isinstance(response.output, JSONOutput)
                    and response.output.validation_status == "invalid_json"
                ):
                    raise ValueError("JSON_PARSE_ERROR")
                if response.status != "success":
                    raise ValueError(
                        "SPECIALIST_SCHEMA_MISMATCH"
                        if response.error and response.error.category == "schema_mismatch"
                        else "CONTRACT_ERROR"
                        if response.error and response.error.category == "structured_output_invalid"
                        else "TRANSPORT_ERROR"
                    )
                wire_response = (
                    response.output.payload if isinstance(response.output, JSONOutput) else None
                )
                if discriminated:
                    validation_issues = schema_issues(wire_schema, wire_response)
                    if validation_issues:
                        raise ValueError("SPECIALIST_SCHEMA_MISMATCH")
                if atomic:
                    wire_response = dict(actions=[dict(action="calculate", **wire_response)])
                actions = wire_response
                if parent_scope and "operator" in wire_response:
                    actions = dict(actions=[{"action": "calculate", **wire_response}])
                elif single_formulas:
                    actions = dict(
                        actions=[
                            dict(
                                action="calculate",
                                formula_id=wire_response["formula_id"],
                                operands=wire_response["bindings"],
                            )
                        ]
                    )
                inverse_aliases = {v: k for k, v in aliases.items()}
                proposal_order = None
                if indexed:
                    state["indexed_selection"] = dict(decision=wire_response, bindings=bindings)
                    raw, proposal_order = indexed_reasoning.bind_selection(
                        wire_response,
                        bindings,
                        {row["id"]: row for row in prompt["evidence"]},
                        draft,
                        task.objective,
                        self._document_views,
                    )
                    if wire_response["operator"] != "none" and not raw["claims"]:
                        indices = indexed_reasoning.available_operand_row(wire_response, options)
                        if indices:
                            state["available_operand_row"] = sorted(bindings[i][0] for i in indices)
                    if (
                        raw["claims"]
                        and isinstance(raw["claims"][0], dict)
                        and (steps := raw["claims"][0].get("steps"))
                    ):
                        proof_key = content_digest(steps)
                        if any(
                            prior.get("indexed_proof_key") == proof_key
                            for prior in self.workspace.tasks.values()
                        ):
                            raw = dict(
                                claims=[], missing_information=["calculator_proof_unchanged"]
                            )
                            proposal_order = ([], [])
                elif discriminated and ("actions" in actions or "action" in actions):
                    raw, proposal_order = project_reasoning_actions(
                        actions,
                        aliases=inverse_aliases,
                        objective=task.objective,
                        parent_calculations=available_parents,
                        indexed_operands=indexed_operands,
                        formulas=single_formulas or formula_options,
                        parent_decision=parent_scope,
                    )
                else:
                    raw = _map_evidence_handles(wire_response, inverse_aliases)
                if question_reasoning and not indexed and "tool_calls" not in wire_response:
                    raw.pop("requirement_mapping", None)
                    mapping = _map_evidence_handles(
                        wire_response["requirement_mapping"], inverse_aliases
                    )
                    state["requirement_mapping"] = mapping
                    check_requirement_mapping(mapping, raw.get("claims", []))
                payload = parse_specialist_output(
                    raw, role=task.specialist, need_refs=task.need_refs
                )
                visible_evidence = {e["id"] for e in prompt["evidence"]}
                visible_nodes = {e["graph_node_id"] for e in prompt["evidence"]}
                visible_nodes.update(v["graph_node_id"] for v in prompt["document_source_context"])
                visible_nodes.update(
                    node["node"]["node_id"]
                    for row in last_results
                    if row.get("tool") == "get_graph_context"
                    for node in [
                        row.get("data", {}).get("start"),
                        *row.get("data", {}).get("matches", []),
                    ]
                    if node
                )
                scoped_refs = {
                    "get_evidence_item": ("source", task_documents),
                    "get_financial_fact": ("source", visible_sources),
                    "calculate_financial_metric": ("source", visible_sources),
                    "get_evidence_sources": ("evidence_id", visible_evidence),
                    "get_graph_context": ("node_id", visible_nodes),
                }
                for call in payload.get("tool_calls", []):
                    name, args = call["tool"], call["args"]
                    if name not in SPECIALIST_TOOLS_BY_ROLE[task.specialist]:
                        raise ValueError("tool_not_allowed_for_role")
                    if task.specialist == "reasoning":
                        if name in scoped_refs:
                            key, owned = scoped_refs[name]
                            if args.get(key) not in owned:
                                raise ValueError("tool_reference_not_owned")
                        if (
                            name == "calculate_dynamic"
                            and set(args.get("evidence_ids", [])) - visible_evidence
                        ):
                            raise ValueError("tool_reference_not_owned")
                if set(payload.get("missing_need_inputs", {})) - set(task.need_refs) or any(
                    set(call.get("need_refs", [])) - set(task.need_refs)
                    for call in payload.get("tool_calls", [])
                ):
                    raise ValueError("need_reference_unknown")
                if (
                    "request_work" not in payload
                    and "tool_calls" not in payload
                    and not (
                        payload["claims"]
                        or payload.get("analyses")
                        or any(reason.strip() for reason in payload["missing_information"])
                        or task.specialist == "retrieval"
                        and (state.get("source_context") or prompt["evidence"])
                    )
                ):
                    raise ValueError("empty_final_outcome")
                if "tool_calls" in payload and any(
                    call["tool"] not in prompt["tools"] for call in payload["tool_calls"]
                ):
                    raise ValueError("tool_not_available_in_phase")
                if (
                    "request_work" not in payload
                    and retrieval_required
                    and (
                        "tool_calls" not in payload
                        or any(
                            call["tool"] not in retrieval_tools for call in payload["tool_calls"]
                        )
                    )
                ):
                    raise ValueError("retrieval_action_required")
                if not discriminated:
                    validation_issues = schema_issues(bound, raw)
                    if validation_issues:
                        raise ValueError("SPECIALIST_SCHEMA_MISMATCH")
            except (ValueError, TypeError, RecursionError) as error:
                # Rejected model output supplies no candidate. It is not a
                # Python execution failure and must remain a controlled abstention.
                state.setdefault(
                    "operation_errors" if str(error) == "TRANSPORT_ERROR" else "reasoning_errors",
                    [],
                ).append(
                    dict(
                        operation="specialist",
                        code="JSON_PARSE_ERROR"
                        if isinstance(error, json.JSONDecodeError)
                        else str(error)
                        if str(error)
                        in {"JSON_PARSE_ERROR", "TRANSPORT_ERROR", "SPECIALIST_SCHEMA_MISMATCH"}
                        else "MODEL_PROTOCOL_ERROR",
                        reason=str(error),
                        **(
                            dict(
                                validation_issues=[
                                    i.model_dump(mode="json") for i in validation_issues
                                ]
                            )
                            if validation_issues
                            else {}
                        ),
                    )
                )
                if retrieval_required:
                    state["stop_reason"] = "retrieval_action_failed"
                    state.setdefault("operation_errors", []).append(
                        dict(operation="specialist", code="RETRIEVAL_ACTION_REQUIRED")
                    )
                    state.setdefault("retrieval_recovery", {})["status"] = "failed"
                    break
                break
            state.setdefault("turns", []).append(dict(response=payload))
            if discriminated:
                state["turns"][-1]["raw_response"] = wire_response
            if "request_work" in payload:
                state["request_work"] = deepcopy(payload["request_work"])
                final = payload
                break
            if "tool_calls" not in payload:
                if (
                    task.specialist == "retrieval"
                    and not retrieval_attempted
                    and (
                        payload["missing_information"]
                        or not (payload["claims"] or payload.get("analyses"))
                    )
                ):
                    state["turns"][-1]["rejected"] = "retrieval_before_missing_information"
                    if not retrieval_tools:
                        state["stop_reason"] = "retrieval_capability_unavailable"
                        state.setdefault("operation_errors", []).append(
                            dict(operation="specialist", code="RETRIEVAL_CAPABILITY_UNAVAILABLE")
                        )
                        break
                    progress = (
                        len(state.get("need_tool_results", ())),
                        len(state.get("tool_evidence_ids", ())),
                        state.get("handoff"),
                    )
                    if state.get("retrieval_recovery", {}).get("progress") == progress:
                        state["stop_reason"] = "retrieval_no_progress"
                        state["retrieval_recovery"]["status"] = "stopped"
                        break
                    state["retrieval_recovery"] = dict(
                        status="requested", rejected_turn=turn + 1, progress=progress
                    )
                    continue
                final = payload
                state["missing_need_inputs"] = deepcopy(payload.get("missing_need_inputs", {}))
                break
            results = []
            reused_calls = 0
            for call_index, call in enumerate(payload["tool_calls"], 1):
                begin = perf_counter()
                trace_start = len(upstream.tool_trace)
                cache_key = json.dumps((call, cache_scope), sort_keys=True, ensure_ascii=False)
                workspace_digest = content_digest(
                    dict(
                        evidence=self.workspace.evidence.model_dump(mode="json"),
                        documents=self._document_views,
                    )
                )
                cached = tool_cache.get(cache_key)
                try:
                    if call["tool"] == "get_financial_fact" and (
                        eid := hydrated_selectors.get(call["args"]["source"])
                    ):
                        tool_result = dict(
                            ok=True,
                            data={},
                            evidence_refs=[eid],
                            error=None,
                            cached=True,
                        )
                        reused_calls += 1
                        state.setdefault("reasoning_errors", []).append(
                            dict(
                                operation="get_financial_fact",
                                code="SOURCE_FACT_ALREADY_HYDRATED",
                                evidence_id=eid,
                                reason=(
                                    "Chọn E đã nạp để tạo direct nếu khớp câu hỏi; "
                                    "nếu chưa đủ, chỉ rõ chỉ tiêu, kỳ hoặc quan hệ còn thiếu."
                                ),
                            )
                        )
                    elif cached and cached[0] == workspace_digest:
                        tool_result = dict(cached[1], cached=True)
                        for handle in tool_result["evidence_refs"]:
                            if handle in self._document_hits:
                                search, hit = self._document_hits[handle]
                                saved_view = self._document_views[handle]
                                self._remember_document(search, hit, state, sources)
                                if call["tool"] == "get_evidence_item":
                                    self._document_views[handle] = saved_view
                        reused_calls += 1
                    else:
                        tool_result = dict(
                            self._tool(
                                call["tool"], call["args"], context, sources, state, upstream
                            ),
                            cached=False,
                        )
                except Exception as error:
                    failure = dict(
                        code="CONTRACT_ERROR"
                        if isinstance(error, (ValueError, TypeError, KeyError))
                        else "TOOL_EXECUTION_ERROR",
                        reason=str(error)
                        if isinstance(error, ValueError) and not hasattr(error, "errors")
                        else type(error).__name__,
                    )
                    tool_result = dict(ok=False, data={}, evidence_refs=[], error=failure)
                    bad_reference = isinstance(error, ValueError) and str(error) in {
                        "source_unknown",
                        "source_ambiguous_or_wrong_kind",
                        "dynamic_operand_unknown",
                    }
                    bad_protocol = isinstance(error, ValueError) and str(error) in {
                        "tool_unknown",
                        "tool_args_invalid",
                    }
                    calculation_rejected = call["tool"] == "calculate_dynamic" and isinstance(
                        error, (ValueError, ArithmeticError)
                    )
                    state.setdefault(
                        "reasoning_errors"
                        if bad_reference or bad_protocol or calculation_rejected
                        else "operation_errors",
                        [],
                    ).append(
                        dict(
                            operation=call["tool"],
                            **failure,
                            category="MODEL_REFERENCE_ERROR"
                            if bad_reference
                            else "MODEL_PROTOCOL_ERROR"
                            if bad_protocol
                            else "CALCULATION_REJECTED"
                            if calculation_rejected
                            else failure["code"],
                            stack=traceback.format_exc(),
                        )
                    )
                results.append(dict(tool_result, tool_call=call))
                self._record_source_receipts(
                    task, state, call, tool_result, context, f"{turn + 1}:{call_index}"
                )
                state["tool_evidence_ids"] = list(
                    dict.fromkeys(
                        [*state.get("tool_evidence_ids", []), *tool_result["evidence_refs"]]
                    )
                )
                if call["tool"] == "calculate_financial_metric" and tool_result["ok"]:
                    metric_id = sources[call["args"]["source"]]["records"][0].metric_id
                    state["tool_metric_ids"] = list(
                        dict.fromkeys([*state.get("tool_metric_ids", []), metric_id])
                    )
                if call["tool"] in retrieval_tools and (
                    not tool_result.get("cached")
                    and tool_result["data"].get("status")
                    in {"found", "not_found", "ambiguous", "conflicted"}
                    or task.specialist == "retrieval"
                    and tool_result["ok"]
                    and tool_result["evidence_refs"]
                ):
                    retrieval_attempted = True
                    state["retrieval_attempted"] = True
                if len(upstream.tool_trace) > trace_start:
                    upstream.tool_trace[-1].latency_ms = (perf_counter() - begin) * 1000
            if (
                task.specialist == "retrieval"
                and task.need_refs
                and not state.get("context_search_attempted")
                and "search_hybrid_evidence" in retrieval_tools
                and not state.get("source_context")
                and any(
                    row["tool_call"]["tool"]
                    in {
                        "get_financial_fact",
                        "find_financial_facts",
                        "search_document_evidence",
                        "find_document_evidence",
                    }
                    for row in results
                )
                and set(task.need_refs)
                - {
                    ref
                    for receipt in state.get("need_tool_results", [])
                    if receipt["evidence_refs"]
                    for ref in receipt["need_refs"]
                }
            ):
                state["context_search_attempted"] = True
                call = dict(
                    tool="search_hybrid_evidence", args=dict(query=question.strip()[:2000], top_k=5)
                )
                begin = perf_counter()
                search = self._tool(call["tool"], call["args"], context, sources, state, upstream)
                upstream.tool_trace[-1].latency_ms = (perf_counter() - begin) * 1000
                results.append(dict(search, tool_call=call))
                self._record_source_receipts(
                    task, state, call, search, context, f"{turn + 1}:context"
                )
                retrieval_attempted = True
            state["turns"][-1]["tool_results"] = results
            if retrieval_required:
                state.setdefault("retrieval_recovery", {})["status"] = (
                    "recovered" if retrieval_attempted else "failed"
                )
                if not retrieval_attempted:
                    state["stop_reason"] = "retrieval_action_failed"
                    state.setdefault("operation_errors", []).append(
                        dict(operation="specialist", code="RETRIEVAL_ACTION_REQUIRED")
                    )
                    break
            for row in results:
                if row["ok"] and "steps" in row["data"]:
                    calculation = dict(
                        evidence_ids=row["tool_call"]["args"]["evidence_ids"],
                        operations=row["tool_call"]["args"]["operations"],
                        steps=row["data"]["steps"],
                    )
                    if calculation not in state.setdefault("calculations", []):
                        state["calculations"].append(calculation)
            workspace_digest = content_digest(
                dict(
                    evidence=self.workspace.evidence.model_dump(mode="json"),
                    documents=self._document_views,
                )
            )
            for row in results:
                if row["ok"]:
                    tool_cache[
                        json.dumps(
                            (row["tool_call"], cache_scope), sort_keys=True, ensure_ascii=False
                        )
                    ] = (
                        workspace_digest,
                        row,
                    )
            if task.specialist == "retrieval" and any(
                row["ok"] and row["evidence_refs"] for row in results
            ):
                state["handoff"] = "tool_batch_sources"
                state["missing_need_inputs"] = {
                    ref: [
                        f"{row['tool_call']['tool']}:{reason}"
                        for row in results
                        if not row["evidence_refs"]
                        and any(
                            receipt["source_result_id"] == row.get("result_id")
                            and ref in receipt["need_refs"]
                            for receipt in state.get("need_tool_results", [])
                        )
                        for reason in row["data"].get("reasons", [row.get("status", "error")])
                    ]
                    for ref in task.need_refs
                }
                final = dict(
                    missing_information=[
                        f"{row['tool_call']['tool']}:{reason}"
                        for row in results
                        if not row["ok"]
                        for reason in row["data"].get("reasons", [row.get("status", "error")])
                    ]
                )
                break
            received = self._evidence(task, upstream, question).supporting_evidence
            last_results = [
                dict(
                    tool=r["tool_call"].get("tool") if isinstance(r["tool_call"], dict) else None,
                    args=deepcopy(r["tool_call"]["args"]),
                    ok=r["ok"],
                    status=r.get("status", "success" if r["ok"] else "error"),
                    reasons=[] if r.get("status") == "candidates" else r["data"].get("reasons", []),
                    cached=r.get("cached", False),
                    message="Dùng E đã nhận để tạo candidate hoặc nêu phần còn thiếu."
                    if r.get("cached")
                    else "Tập ứng viên chưa verified; chọn E phù hợp requirement hoặc truy xuất tiếp."
                    if r.get("status") == "candidates"
                    else "Không có kết quả với filters đã gửi."
                    if r.get("status") == "empty"
                    else "Truy xuất quá rộng, chưa kết luận thiếu nguồn. Thu hẹp args bằng filters có căn cứ từ catalog/context."
                    if r.get("status") == "refine"
                    else "E đã nạp; trả direct nếu khớp chỉ tiêu và kỳ."
                    if question_reasoning
                    and r["tool_call"]["tool"] == "get_financial_fact"
                    and r["evidence_refs"]
                    else "Kết quả tool.",
                    evidence_refs=[
                        e.evidence_id for e in received if e.evidence_id in r["evidence_refs"]
                    ]
                    if r["tool_call"]["tool"] == "find_financial_facts"
                    else r["evidence_refs"],
                    error=r["error"],
                    data=dict(steps=r["data"]["steps"])
                    if "steps" in r["data"]
                    else r["data"]
                    if isinstance(r["tool_call"], dict)
                    and r["tool_call"].get("tool") in {"get_graph_context", "get_evidence_sources"}
                    else dict(
                        evidence=[
                            dict(
                                id=e.evidence_id,
                                label=e.label,
                                value=e.value,
                                period=e.period,
                                unit=e.unit,
                                scale=e.scale,
                                operand_periods=e.operand_periods,
                            )
                            for e in received
                            if e.evidence_id in r["evidence_refs"]
                        ]
                    ),
                )
                for r in results
            ]
            repeated_turns = repeated_turns + 1 if reused_calls == len(results) else 0
        result = self._evidence(task, upstream, question)
        visible_ids = {e.evidence_id for e in result.supporting_evidence}
        state["selected_observations"] = [
            observation(f)
            for f in upstream.evidence_bundle.facts
            if observation(f)["evidence_id"] in visible_ids
        ]
        # Retain receipt sources independently of the bounded, claim-eligible digest.
        # These snapshots grant neither an LLM handle nor candidate eligibility.
        receipt_refs = {
            ref
            for receipt in state.get("need_tool_results", [])
            for ref in receipt["evidence_refs"]
        }
        state["retained_observations"] = list(
            {
                row["evidence_id"]: row
                for fact in upstream.evidence_bundle.facts
                if (row := observation(fact))["evidence_id"] in receipt_refs - visible_ids
            }.values()
        )
        for row in state["selected_observations"] + state["retained_observations"]:
            self.workspace.observations[row["evidence_id"]] = row
        if final is None:
            if repeated_turns:
                state["stop_reason"] = "no_progress"
            result.missing_evidence.append(state.get("stop_reason", "specialist_no_final_claims"))
            result.status = (
                "partial"
                if result.supporting_evidence and not state.get("stop_reason")
                else "abstained"
            )
            return result
        if task.specialist == "retrieval" or "request_work" in final:
            result.missing_evidence.extend(final["missing_information"])
            result.llm = metadata
            result.status = (
                "partial" if result.missing_evidence or "request_work" in final else "generated"
            )
            return result
        by_id = {c["evidence_id"]: c for c in _numeric_proposals(result.supporting_evidence)}
        claims = []
        for choice in final["claims"]:
            if isinstance(choice, str):
                claims.append(by_id.get(choice, choice))
            elif isinstance(choice, dict) and set(choice) == {"source", "query"}:
                if not isinstance(choice["source"], str) or choice["source"] not in task_documents:
                    state.setdefault("reasoning_errors", []).append(
                        dict(
                            operation="document_selection",
                            code="MODEL_REFERENCE_ERROR",
                            original_code="CONTRACT_ERROR",
                            choice=choice,
                            reason="document_source_unknown",
                        )
                    )
                    continue
                try:
                    response, hit = self._document_hits[choice["source"]]
                    requirement = DocumentRequirement(
                        target=choice["query"],
                        label=task.objective,
                        kind="exact_text",
                        query=choice["query"],
                    )
                    operation = document_operations([requirement], self.composition, None)[0]
                    candidates = document_candidates(
                        DocumentEvidenceBundle(
                            operation=operation,
                            result=response.model_copy(update={"matches": [hit]}),
                        ),
                        context.company_id,
                        self.composition,
                    )
                    if not candidates:
                        result.missing_evidence.append("document_source_selection_invalid")
                        state.setdefault("reasoning_errors", []).append(
                            dict(
                                operation="document_selection",
                                choice=choice,
                                reason="document_source_selection_invalid",
                            )
                        )
                        continue
                    output.document_candidates.extend(
                        c for c in candidates if c not in output.document_candidates
                    )
                    state.setdefault("document_candidate_ids", []).extend(
                        c.candidate_id for c in candidates
                    )
                except (KeyError, ValueError, TypeError):
                    state.setdefault("operation_errors", []).append(
                        dict(operation="document_selection", code="CONTRACT_ERROR")
                    )
            else:
                claims.append(choice)

        def render(selected, evidence):
            if selected.meaning == "fact_value" and selected.kind == evidence.kind == "fact":
                if selected.period != evidence.period:
                    raise ValueError("wrong_period")
                scale = f" (hệ số đơn vị {evidence.scale})" if evidence.scale != "1" else ""
                return f"{evidence.label} kỳ {evidence.period} là {_number(evidence.value)} {evidence.unit}{scale}."
            if (
                selected.meaning != "metric_value"
                or selected.kind != "approved_metric"
                or evidence.kind != "metric"
                or selected.period != evidence.period
                or not evidence.calculation
            ):
                raise ValueError("kind_or_meaning_mismatch")
            text = f"{evidence.label} kỳ {evidence.period} là {_number(evidence.value)} %."
            if selected.statement not in (None, text):
                raise ValueError("unsupported_or_numeric_prose")
            return text

        generate_candidates(
            gateway=None,
            model=context.model,
            result=result,
            prompt=prompt,
            proposal_type=proposal,
            render=render,
            prefix="m5-specialist-" + task.specialist,
            candidate_payload=dict(final, claims=claims),
            numeric_fallback=False,
            emit_derived=False,
            operation_inputs_only=True,
            proposal_order=proposal_order,
        )
        result.llm = metadata
        state.setdefault("reasoning_errors", []).extend(
            dict(operation="candidate", code="MODEL_PROTOCOL_ERROR", reason=reason)
            for trace in result.trace
            if trace.outcome == "excluded"
            for reason in trace.reasons
        )
        valid = []
        for candidate in result.candidates:
            try:
                _check_assignment(
                    result.model_copy(update={"candidates": [candidate]}),
                    supporting_references=[e.reference for e in result.supporting_evidence],
                    citations=upstream.evidence_bundle.citations,
                )
                valid.append(candidate)
            except ValueError as error:
                state.setdefault("operation_errors", []).append(
                    dict(operation="candidate_assignment", code=str(error))
                )
        result.candidates = valid
        if proof_key and any(c.reasoning and c.reasoning.calculation for c in valid):
            state["indexed_proof_key"] = proof_key
        # Task-owned source domains and neighbors survive candidate selection.
        return result

    def run(self, *, question, context):
        self._search_tools = None
        self._hybrid_tool = HybridRAGTool()
        self._request_tool_cache = {}
        self._request_graph_tools = None
        self.workspace = IntegrationWorkspace([], question=question)
        self._document_searches, self._document_hits, self._document_views = {}, {}, {}
        self._cell_sources = {}
        self._initial_refs = set()
        self._recovery_searches = set()
        try:
            return self._run(question=question, context=context)
        finally:
            self._close_search()

    def _close_search(self):
        self._hybrid_tool.close()
        if self._search_tools is not None:
            self._search_tools.close_search()
            self._search_tools = None

    def _run(self, *, question, context):
        started = perf_counter()
        output = OrchestrationResult(question=question, context=context.model_copy(deep=True))
        if not all((context.company_id, context.document_id, context.snapshot_id)):
            output.status, output.stop_conditions = (
                "clarification_required",
                ["trusted_context_required"],
            )
            return output
        if self.composition is not None and (
            self.composition.financial_snapshot.document_id,
            self.composition.financial_snapshot.snapshot_id,
        ) != (context.document_id, context.snapshot_id):
            output.status = "clarification_required"
            output.stop_conditions = ["composition_financial_snapshot_mismatch"]
            return output
        sources = self._sources = inventory(
            self.catalog, context.model_copy(update={"period": None})
        )
        self._eo_descriptor = next(
            (
                d
                for d in self.catalog.descriptors
                if d.source_kind == "json"
                and (d.document_id, d.snapshot_id) == (context.document_id, context.snapshot_id)
            ),
            None,
        )
        self._eo_issuer, self._eo_issuer_proof = (
            json_filing_issuer(self.catalog, self._eo_descriptor, context.company_id)
            if self._eo_descriptor
            else (None, None)
        )
        for handle, source in sources.items():
            for fact in source["records"] if source["kind"] == "fact" else []:
                if fact.sources and (ref := fact.sources[0].reference):
                    self._cell_sources.setdefault(
                        (
                            fact.document_id,
                            fact.snapshot_id,
                            ref.anchor.page.model_dump_json(),
                            ref.source_pointer,
                        ),
                        [],
                    ).append(handle)
        upstream = output.supervisor_result = SupervisorResult(
            plan_id=None,
            status="completed",
            initial_validation=PlanValidation(
                structurally_valid=True, execution_eligible=True, disposition="valid"
            ),
        )
        plan, metadata, gaps = self.supervisor.plan(
            question,
            context,
            sources,
            **(
                dict(
                    retrieve=lambda draft=None: self._initial_context(
                        question, context, sources, upstream, output.trace, draft
                    ),
                    trace=output.trace,
                    stages=output.usage.stages,
                    simplified_reasoning=self.simplified_reasoning,
                    simplified_verification=self.simplified_verification,
                )
                if type(self.supervisor) is SupervisorLite
                else {}
            ),
        )
        output.usage.stages["planning"] = metadata
        output.trace.append(
            StageExecution(
                stage="planning",
                outcome="planned" if plan.tasks else "plan_blocked",
                reasons=[plan.model_dump_json(), *gaps],
            )
        )
        self.workspace.requirements = plan.requirements or [
            IntegrationRequirement(requirement_id="G1", text=question, kind="explanation")
        ]
        if any(isinstance(r, QuestionRequirement) for r in plan.requirements):
            # The planning preview budget does not limit already hydrated source facts.
            self._initial_refs.update(
                evidence_handle(m)
                for m in self.workspace.evidence.facts[:20]
                if not context.reporting_scope
                or m.record.context.reporting_scope == context.reporting_scope
            )
        output.caveats.extend(gaps)
        output.errors.extend(OrchestrationError(stage="planning", code=e) for e in gaps)
        output.stop_conditions.extend(gaps if not plan.tasks else ())
        return self._execute_tasks(output, plan, started)

    def _execute_tasks(self, output, plan, started, *, recovery=None):
        question, context = output.question, output.context
        sources, upstream = self._sources, output.supervisor_result
        output.routing_decision = RoutingDecision(
            question=question,
            status="routed",
            selected_roles=list(dict.fromkeys(t.specialist for t in plan.tasks)),
        )
        from .coordinator_plan import schedule_tasks

        ordered, blocked = schedule_tasks(plan.tasks)
        blocked.update(plan.blocked_tasks)
        for task in plan.tasks:
            origin = "coordinator"
            if task.task_id in plan.scheduler_task_ids:
                origin = "scheduler"
            elif plan.projected_task_id is not None and task.task_id == plan.projected_task_id:
                origin = "projection"
            self.workspace.tasks[task.task_id] = dict(
                task_id=task.task_id,
                requirement_ids=task.requirement_ids,
                depends_on=task.depends_on,
                objective=task.objective,
                role=task.specialist,
                assignment_origin=origin,
                **(dict(need_refs=list(task.need_refs)) if task.need_refs else {}),
                revision=1,
                status="pending",
                **(dict(answer_recovery=recovery) if recovery else {}),
            )
        pending = [*ordered, *(t for t in plan.tasks if t.task_id in blocked)]
        while pending:
            ready, invalid = schedule_tasks(pending, completed=self.workspace.task_results)
            blocked.update(invalid)
            task = ready[0] if ready else pending[0]
            pending.remove(task)
            state = self.workspace.tasks[task.task_id]
            execution = SpecialistExecution(
                execution_id=task.task_id,
                role=task.specialist,
                assigned_requirement_ids=task.requirement_ids,
            )
            output.specialist_executions.append(execution)
            if task.task_id in blocked or not self.workspace.dependencies_ready(task):
                state.update(
                    status="blocked",
                    error=blocked.get(task.task_id, "dependency_output_unavailable"),
                )
                state["missing_inputs"] = [state["error"]]
                output.missing_evidence.extend(state["missing_inputs"])
                execution.status = "abstained"
                output.trace.append(
                    StageExecution(
                        stage="specialist_execution",
                        outcome="blocked",
                        role=task.specialist,
                        reasons=[task.task_id, state["error"]],
                    )
                )
                continue
            try:
                state["status"] = "running"
                upstream.execution_order.append(task.task_id)
                result = self._specialist(task, upstream, question, context, sources, output)
                execution.result, execution.llm, execution.status = (
                    result,
                    result.llm,
                    result.status,
                )
                self.workspace.record_result(task, result, retain_sources=True)
                if state.get("request_work"):
                    try:
                        followups = self.workspace.request_work(
                            task, self.gateway, reserved_ids=blocked
                        )
                        pending = [
                            *followups,
                            *[
                                child.model_copy(
                                    update=dict(
                                        depends_on=[
                                            followups[-1].task_id if tid == task.task_id else tid
                                            for tid in child.depends_on
                                        ]
                                    )
                                )
                                for child in pending
                            ],
                        ]
                        for child in pending:
                            self.workspace.tasks[child.task_id]["depends_on"] = list(
                                child.depends_on
                            )
                    except ValueError as error:
                        state.update(status="blocked", error=str(error))
                        result.missing_evidence.append(str(error))
                        output.missing_evidence.extend(result.missing_evidence)
                else:
                    output.missing_evidence.extend(result.missing_evidence)
                for item in result.trace:
                    if item.outcome == "excluded" and item.stage == "generation":
                        state.setdefault("operation_errors", []).append(
                            dict(operation="specialist", code=":".join(item.reasons))
                        )
            except Exception as error:
                state.update(
                    status="technical_error",
                    error=type(error).__name__,
                    stack=traceback.format_exc(),
                )
                state.setdefault("operation_errors", []).append(
                    dict(operation="specialist", code=type(error).__name__)
                )
                execution.status = "failed"
            output.errors.extend(
                OrchestrationError(
                    stage="specialist_execution",
                    role=task.specialist,
                    code=e["operation"] + ":" + e["code"],
                )
                for e in state.get("operation_errors", [])
            )
            output.trace.append(
                StageExecution(
                    stage="specialist_execution",
                    outcome=execution.status,
                    role=task.specialist,
                    reasons=[task.task_id, task.objective],
                )
            )
        output.candidates, output.conflicts = aggregate_candidates(output.specialist_executions)
        output.integration_context = self.workspace.export(output.candidates)
        output.status = (
            "partial"
            if output.errors
            or output.missing_evidence
            or any(
                e.status != "generated"
                and not self.workspace.tasks[e.execution_id].get("work_request_key")
                for e in output.specialist_executions
            )
            else "completed"
        )
        if not plan.tasks:
            output.status = "blocked"
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

    def recover(self, prior, feedback, seen, round_number):
        """Route one repair over the same pinned sources and task workspace."""
        started = perf_counter()
        event = dict(round=round_number, feedback=feedback, outcome="budget_exhausted")
        if (
            self.gateway.remaining_generation_calls < 2
            or self.gateway.exhausted
            or self.gateway.failure_category
            or perf_counter() >= self.gateway.generation_deadline
        ):
            return None, event
        question, context = prior.question, prior.context
        expected = self.workspace.expected_answers
        suggestion = (
            feedback.get("completion", {}).get("Q1", {}).get("suggested_missing_requirement")
        )
        if (
            expected is not None
            and suggestion
            and not any(
                normalize_search(r["text"]) == normalize_search(suggestion)
                for r in expected["requirements"]
            )
        ):
            start_calls = len(self.gateway.events)
            request_id, added = indexed_reasoning.confirm_missing_answer(
                self.gateway, context, question, expected["requirements"], suggestion
            )
            event.update(
                coordinator_request_id=request_id,
                provider_calls=[e["request_id"] for e in self.gateway.events[start_calls:]],
                outcome="requirement_unresolved",
            )
            if not added:
                return None, event
            revised = expected_answer_set(
                self.workspace.requirements[0].model_dump(mode="json"),
                [added],
                expected["reporting_scope"],
                previous=expected["requirements"],
            )
            if revised["revision"] == expected["revision"]:
                return None, event
            self.workspace.expected_answers = revised
            event.update(outcome="requirement_revised", requirement_revision=revised["revision"])
            return prior.model_copy(
                update={
                    "integration_context": dict(
                        prior.integration_context, expected_answers=revised
                    ),
                    "usage": prior.usage.model_copy(update={"stages": {}}),
                }
            ), event
        upstream = prior.supervisor_result
        self._initial_refs.update(
            ref
            for step in upstream.tool_trace
            if step.final_state == "completed"
            and step.operation in {"get_financial_fact", "find_financial_facts"}
            for ref in step.output_evidence_ids
        )
        tools_before = len(upstream.tool_trace)
        calls_before = len(self.gateway.events)
        sources_before = self._initial_refs | {
            ref
            for step in upstream.tool_trace
            for ref in step.output_evidence_ids
            if not step.step_id.startswith("initial-tool-")
        }
        views_before = {h: content_digest(v) for h, v in self._document_views.items()}
        context_rows = []
        remaining = 14000
        for match in self.workspace.evidence.facts:
            row = observation(match)
            view = {key: row[key] for key in ("evidence_id", "label", "value", "unit", "context")}
            size = len(json.dumps(view, ensure_ascii=False)) + 1
            if size > remaining:
                break
            context_rows.append(view)
            remaining -= size
        documents = [
            dict(
                handle=h,
                title=v.get("table_title"),
                page=v.get("source_page"),
                headers=v.get("headers"),
                preview=v.get("text", "")[:160],
            )
            for h, v in self._document_views.items()
        ]
        fact_labels = {
            h: f"{s['label']} {s['item'] or ''}"
            for h, s in self._sources.items()
            if s["kind"] == "fact"
        }
        catalog = [
            {key: self._sources[h][key] for key in ("item", "label", "period")}
            for h in rank_search_candidates(fact_labels, [question], top_k=12)
        ]
        payload = dict(
            question=question,
            scope=self.workspace.requirements[0].source_scope,
            feedback={
                key: value[:4] if isinstance(value, list) else value
                for key, value in feedback.items()
            },
            documents=documents[:15],
            evidence=context_rows,
            financial_catalog=catalog,
            tried=[list(pair) for pair in sorted(self._recovery_searches)],
        )
        wire = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        while len(wire) > 20000 and (payload["evidence"] or payload["documents"]):
            (payload["evidence"] or payload["documents"]).pop()
            wire = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(wire) > 20000:
            event["outcome"] = "coordinator_context_limit"
            return None, event
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="m5-coordinator-answer-recovery-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(
                    role="system",
                    content=(
                        "Xét từng slot chưa có candidate_ids trong feedback.completion. "
                        "Dùng reason nếu các nguồn đúng đã có và selection hoặc kết luận cần sửa. "
                        "Nếu thiếu liên kết, dùng document và objective ngắn cho khoản mục hoặc bên "
                        "còn thiếu. Dùng financial khi thiếu ô số, objective chỉ là nhãn chỉ tiêu, "
                        "filters gồm canonical_item_id từ financial_catalog nếu có, statement_type, "
                        "period nếu xác định được. Runtime tra nguồn trong filing đã pin rồi tìm bảng "
                        "theo nhãn nếu chưa có fact mới. document cho bảng hoặc đoạn định tính, "
                        "search cho Hybrid, read mở D bằng source. Dùng objective ngắn, tránh lặp "
                        "truy vấn đã thử. stop nếu không còn hướng. Không suy ra số liệu."
                    ),
                ),
                Message(role="user", content=wire),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=400),
            output_spec=OutputSpec(
                format="json",
                json_schema=dict(
                    type="object",
                    properties=dict(
                        action=dict(
                            type="string",
                            enum=["reason", "financial", "search", "document", "read", "stop"],
                        ),
                        objective=dict(type="string"),
                        source=dict(type="string"),
                        filters=dict(
                            type="object",
                            additionalProperties=False,
                            properties=dict(
                                canonical_item_id=dict(type="string"),
                                statement_type=dict(
                                    type="string", enum=["B01", "B02", "B03", "B09"]
                                ),
                                period=dict(type="string"),
                            ),
                        ),
                    ),
                    required=["action", "objective", "source"],
                    additionalProperties=False,
                ),
            ),
            constraints=RequestConstraints(timeout_seconds=30),
        )
        last = next(reversed(self.workspace.tasks.values()), {})
        if (
            self.simplified_reasoning
            and (available := last.get("available_operand_row"))
            and not any(
                task.get("answer_recovery", {}).get("selection_retry") == available
                for task in self.workspace.tasks.values()
            )
        ):
            action = dict(
                action="reason",
                objective="Kiểm lại vai trò và chọn đủ các ô số của hàng đã có.",
                source="",
            )
            event["selection_retry"] = available
        else:
            response = self.gateway.generate(request)
            event["coordinator_request_id"] = request.request_id
            event["provider_calls"] = [e["request_id"] for e in self.gateway.events[calls_before:]]
            if response.status != "success" or not isinstance(response.output, JSONOutput):
                event["outcome"] = "coordinator_unavailable"
                return None, event
            action = response.output.payload
        event["assignment"] = action
        route, objective = action["action"], action["objective"].strip()[:600]
        if route == "stop" or not objective:
            event["outcome"] = "no_supported_revision"
            return None, event
        task_id = f"T{max(int(tid[1:]) for tid in self.workspace.tasks) + 1}"
        if route != "reason":
            source = action["source"]
            document = ("search_document_evidence", dict(query=objective, top_k=12))
            if route == "financial":
                filters = {k: v for k, v in action.get("filters", {}).items() if v}
                item = filters.pop("canonical_item_id", None)
                searches = (
                    [("find_financial_facts", dict(filters, canonical_item_id=item))]
                    if item
                    else []
                )
                searches.extend(
                    [
                        ("find_financial_facts", dict(filters, source_label=objective)),
                        ("search_document_evidence", dict(document[1], evidence_type="table")),
                    ]
                )
            elif route == "read":
                searches = (
                    [("get_evidence_item", dict(source=source))]
                    if source in self._document_hits
                    else []
                )
            elif route == "search" and self._hybrid_tool.available:
                searches = [("search_hybrid_evidence", document[1])]
            else:
                searches = [document]
            state = dict(
                task_id=f"recovery-{round_number}",
                role="retrieval",
                fact_needs={},
                context_queries=[objective, question],
            )
            delta = set()
            event["retrieval_attempts"] = []
            event["tool_calls"] = []
            try:
                for tool, args in searches:
                    strategy = (
                        tool,
                        json.dumps(args, sort_keys=True)
                        if route == "financial"
                        else source
                        if route == "read"
                        else normalize_search(objective),
                    )
                    if strategy in self._recovery_searches:
                        continue
                    self._recovery_searches.add(strategy)
                    result = self._tool(tool, args, context, self._sources, state, upstream)
                    event["retrieval_attempts"].append(
                        dict(
                            tool=tool,
                            args=args,
                            status=result["status"],
                            sources=result["evidence_refs"],
                        )
                    )
                    event["tool_calls"].append(result["result_id"])
                    self._initial_refs.update(result["evidence_refs"])
                    delta = (self._initial_refs - sources_before) | {
                        h
                        for h, view in self._document_views.items()
                        if content_digest(view) != views_before.get(h)
                    }
                    if delta:
                        break
            except (ImportError, OSError, RuntimeError, SQLiteError, ValueError) as error:
                event.update(outcome="retrieval_unavailable", error=type(error).__name__)
                return None, event
            finally:
                self._close_search()
            event["context_delta"] = sorted(delta)
            if not delta:
                event["outcome"] = (
                    "retrieval_no_progress" if event["tool_calls"] else "repeated_or_unknown_source"
                )
                return None, event

        task = LiteTask(
            task_id=task_id,
            specialist="reasoning",
            objective=question[:600],
            requirement_ids=[r.requirement_id for r in self.workspace.requirements],
        )
        output = OrchestrationResult(question=question, context=context, supervisor_result=upstream)
        plan = LitePlan(tasks=[task], requirements=self.workspace.requirements)
        try:
            output = self._execute_tasks(
                output,
                plan,
                started,
                recovery=dict(
                    objective=objective,
                    feedback=payload["feedback"],
                    selection_retry=event.get("selection_retry"),
                    context_delta=event.get("context_delta", []),
                ),
            )
        finally:
            self._close_search()
        output.candidates = [c for c in output.candidates if c.candidate_id not in seen]
        output.document_candidates = [
            c for c in output.document_candidates if c.candidate_id not in seen
        ]
        candidates = [*output.candidates, *output.document_candidates]
        tools = upstream.tool_trace[tools_before:]
        event["context_delta"] = sorted(
            (self._initial_refs - sources_before)
            | {
                ref
                for step in tools
                for ref in step.output_evidence_ids
                if ref not in sources_before
            }
            | {
                h
                for h, v in self._document_views.items()
                if content_digest(v) != views_before.get(h)
            }
        )
        event.update(
            outcome="reverify"
            if candidates
            else "context_progress"
            if event.get("context_delta")
            else "no_progress",
            provider_calls=[e["request_id"] for e in self.gateway.events[calls_before:]],
            tool_calls=[step.step_id for step in tools],
            proof_delta=[c.candidate_id for c in candidates],
            candidate_feedback=output.missing_evidence,
        )
        return output, event
