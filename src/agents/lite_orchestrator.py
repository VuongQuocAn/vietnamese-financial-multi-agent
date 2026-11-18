"""One Supervisor plan, independent specialist executions, ordinary M6 candidates."""

import json
import re
from time import perf_counter
from uuid import uuid4

from pydantic import Field, model_validator

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.prompt_payload import compact_prompt
from ..evidence.graph import graph_id
from ..evidence.retrieval import RetrievalReference
from ..tools.evidence_retrieval import EvidenceRetrievalTools, GetEvidenceSourcesRequest
from ..tools.financial_calculator import CalculateFinancialMetricRequest, FinancialCalculator
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest
from ..tools.graph_retrieval import (
    GetGraphContextRequest,
    GetSnapshotGraphContextRequest,
    GraphContextResponse,
    GraphRetrievalTools,
)
from . import cash_flow_earnings_quality_specialist as cash
from . import liquidity_leverage_specialist as liquidity
from . import profitability_specialist as profit
from .contracts import PlanValidation, SpecialistRole
from .document_qa import document_candidates, document_operations
from .document_qa_contracts import DocumentRequirement
from .integration_workspace import (
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
from .orchestrator import _check_assignment, aggregate_candidates
from .planner_contracts import PlannerLLMMetadata
from .python_agent import PythonAgent, PythonRequirement
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
    """Unwrap typed analysis proposals without changing their content or limitations."""
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
    return dict(payload, claims=remaining, analyses=[*analyses, *moved]) if moved else payload


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
    python_requirement: PythonRequirement | None = None
    resolve_inputs: bool = False
    document_search: DocumentRequirement | None = None


class LitePlan(FinancialModel):
    tasks: list[LiteTask] = Field(default_factory=list, max_length=6)
    requirements: list[IntegrationRequirement] = Field(default_factory=list, max_length=16)
    blocked_tasks: dict[str, str] = Field(default_factory=dict, exclude=True)


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
            key = ("fact", fact.canonical_item_id, fact.context.period)
            entry = entries.setdefault(
                key,
                dict(
                    kind="fact",
                    item=fact.canonical_item_id,
                    period=fact.context.period,
                    label=fact.context.raw_item_label or fact.canonical_item_id,
                    roles=[role] if role else [],
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


class SupervisorLite:
    def __init__(self, gateway=None):
        self.gateway = gateway

    def plan(self, question, context, sources):
        if self.gateway is None or context.mode == "deterministic":
            return (
                LitePlan(),
                PlannerLLMMetadata(status="not_executed"),
                ["coordinator_gateway_required"],
            )
        from .coordinator_plan import PlanProposal, adapt_plan

        prompt = dict(
            instruction=(
                "Bạn là Coordinator. Lập một kế hoạch JSON có goals và tasks. "
                "Mỗi goal ghi một đầu ra được hỏi, giữ đối tượng, kỳ và điều kiện. "
                "Mỗi goal phải có ít nhất một task trong goal_indexes; tasks không được rỗng. "
                "Một yêu cầu tra cứu đơn giản chỉ cần một goal và một task. "
                "Tách các đầu ra tài chính và thuyết minh độc lập thành goals riêng. "
                "Các bước trung gian phục vụ goal hiện có. Ghi công việc cụ thể trong objective. "
                "after liệt kê các task cần hoàn tất trước; task độc lập dùng []. "
                "goal_indexes và after dùng index từ 0. Không tạo vòng lặp. "
                "Specialist tự chọn công cụ và nguồn. Chỉ trả kế hoạch."
            ),
            output_schema=PlanProposal.model_json_schema(),
            example={
                "goals": [{"text": "Chỉ tiêu và kỳ người dùng yêu cầu"}],
                "tasks": [
                    {
                        "goal_indexes": [0],
                        "role": "profitability",
                        "objective": "Tra chỉ tiêu đúng kỳ",
                        "after": [],
                    }
                ],
            },
            context={k: getattr(context, k) for k in ("company_id", "period", "reporting_scope")},
            conversation_context=context.conversation_context,
        )
        payload = json.dumps(compact_prompt(prompt), ensure_ascii=False, separators=(",", ":"))
        if len(payload) + len(question) > 48000:
            return LitePlan(), PlannerLLMMetadata(), ["supervisor_payload_limit"]
        response = self.gateway.generate(
            LLMRequest(
                contract_version="llm_gateway_v1",
                request_id="m5-coordinator-plan-" + uuid4().hex,
                model=context.model,
                messages=[
                    Message(role="system", content=payload),
                    Message(role="user", content=question),
                ],
                generation=GenerationParameters(temperature=0.0, max_output_tokens=2500),
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
        if response.status != "success" or not isinstance(response.output, JSONOutput):
            return LitePlan(), metadata, ["supervisor_provider_failure"]
        plan, errors = adapt_plan(response.output.payload)
        return plan, metadata, errors


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
    ):
        self.catalog, self.gateway = catalog, gateway
        self.supervisor = supervisor or SupervisorLite(gateway)
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

    def reset_request(self):
        pass

    def _specialist(self, task, upstream, question, context):
        module, proposal = DOMAINS[task.specialist]
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
        roles.update(gross_margin="revenue", revenue_yoy="current_revenue", debt_to_assets="assets")
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
        if task.python_requirement:
            record, result.llm = PythonAgent(self.gateway).run(
                objective=task.objective,
                requirement=task.python_requirement,
                matches=upstream.evidence_bundle.facts,
                context=context,
                repair_available=not self.workspace.repair_used,
            )
            state = self.workspace.tasks[task.task_id]
            state["python_candidate"] = record
            state["repair_used"] = record["calls"] > 1
            self.workspace.repair_used |= state["repair_used"]
            state["computation_route"] = "python"
            result.status = "partial"
            result.limitations.append("python_candidate_requires_M6-PY-01")
            if record["execution_status"] != "success":
                result.missing_evidence.append(record["execution_status"])
            # Keep this proof out of the v1 claim adapter/ledger. M6-PY-01 owns admission.
            return result
        self.workspace.tasks[task.task_id]["computation_route"] = "calculator"
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
                "operator: sum,subtract,ratio,percentage_of,percentage_change,mean,greater,less,equal; period_relation "
                "Biên/tỷ trọng theo phần trăm dùng percentage_of inputs=[tử số,mẫu số], tính tử/mẫu*100; "
                "không dùng ratio (lần) hoặc percentage_change (biến động) để trả lời phần trăm tỷ trọng. "
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
        prompt["assigned_requirements"] = [
            r.model_dump(mode="json")
            for r in self.workspace.requirements
            if r.requirement_id in task.requirement_ids
        ]
        prompt["document_source_context"] = self.workspace.tasks[task.task_id].get(
            "source_context", []
        )
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
        prompt["dependency_sources"] = {
            tid: {
                key: self.workspace.task_results[tid][key]
                for key in ("handle", "digest", "source_context")
            }
            for tid in self.workspace.dependency_ids(task)
            if self.workspace.task_results[tid]["source_context"]
        }
        prompt["verification_feedback"] = self.workspace.tasks[task.task_id].get(
            "repair_feedback", []
        )
        if prompt["verification_feedback"]:
            prompt["repair_instruction"] = (
                "Sửa đúng lỗi M6 trong feedback, đối chiếu assigned_requirements và evidence. "
                "Đề xuất claim/phép tính có căn cứ; thiếu evidence thì giữ missing_information. "
                "Không tự cấp ACCEPT hoặc supported_requirement_ids."
            )
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
        prompt["instruction"] = (
            "Bạn là Specialist. Làm đúng objective cho assigned_requirements, với evidence, "
            "shared_tasks và document context. Trả JSON theo response_schema. "
            "Tra trực tiếp: chọn evidence_id trong numeric_choices. "
            "Tính toán: analysis có evidence_ids là facts đầu vào, operations theo schema. "
            "Calculator thực hiện phép tính; dùng percentage_of cho tỷ trọng và "
            "percentage_change với [kỳ mới,kỳ gốc] cho biến động. "
            "Khi task phụ thuộc cần đối chiếu hai số dư, dùng greater hoặc less trên hai "
            "facts cùng kỳ để lưu proof; statement viết kết luận tương ứng. "
            "Phân tích: viết các nhận định độc lập dưới analyses, mỗi nhận định dẫn đủ evidence_ids. "
            "Không tự tính số hoặc bịa nguồn. Kết quả dependency là đề xuất chưa verified; "
            "dùng lại facts và replay phép tính từ nguồn khi cần. M6 kiểm chứng mọi claim."
        )
        prompt["response_schema"]["properties"]["analyses"]["maxItems"] = 8
        deterministic = self.gateway is None or context.mode == "deterministic"
        assigned = [
            r for r in self.workspace.requirements if r.requirement_id in task.requirement_ids
        ]
        if self.workspace.tasks[task.task_id].get("coordination", {}).get("selection"):
            # Selection is already computed from the declared source domain.
            # Emit the selected scalar as an unverified premise, not an LLM-authored extremum claim.
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
            result.supporting_evidence = [
                e
                for e in result.supporting_evidence
                if any(
                    r.target_id
                    == (e.canonical_item_id if e.kind == "fact" else e.calculation.formula_id)
                    and (not r.period or r.period == e.period)
                    for r in assigned
                )
            ]
        if (
            len(json.dumps(compact_prompt(prompt), ensure_ascii=False, separators=(",", ":")))
            + len(question)
            > 48000
        ):
            if not deterministic:
                result.status = "abstained"
                result.limitations.append("specialist_payload_limit")
                return result
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
            normalize_payload=normalize_candidate_envelope,
            operation_inputs_only=True,
            numeric_fallback=False,
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
        workspace = None
        targets = {}
        requirements = plan.requirements or [
            IntegrationRequirement(requirement_id="R-unresolved", text=question, kind="unsupported")
        ]
        workspace = self.workspace = IntegrationWorkspace(requirements)
        workspace.targets = targets
        workspace.question = question
        from .coordinator_plan import schedule_tasks

        ordered, blocked = schedule_tasks(plan.tasks)
        plan.blocked_tasks.update(blocked)
        for task in plan.tasks:
            workspace.tasks[task.task_id] = dict(
                requirement_ids=task.requirement_ids,
                depends_on=task.depends_on,
                objective=task.objective,
                role=task.specialist,
                revision=1,
                status="blocked" if task.task_id in plan.blocked_tasks else "pending",
            )
        for tid, reason in plan.blocked_tasks.items():
            workspace.tasks.setdefault(
                tid, dict(requirement_ids=[], depends_on=[], revision=1, status="blocked")
            )
            workspace.tasks[tid]["error"] = reason
        plan.tasks = [*ordered, *(t for t in plan.tasks if t.task_id in blocked)]
        if gaps:
            output.errors.append(
                OrchestrationError(stage="planning", code="integration_plan_incomplete")
            )
            output.stop_conditions.extend(gaps)
        self._active_plan = plan
        self._last_output = self._run_tasks(question, context, sources, plan, output, gaps)
        self._last_output.latency_ms = (perf_counter() - started) * 1000
        return self._last_output

    def _run_tasks(self, question, context, sources, plan, output, gaps, repair_ids=None):
        started = perf_counter()
        workspace = self.workspace
        tools = FinancialRetrievalTools(self.catalog)
        calculator = FinancialCalculator(self.catalog)
        evidence_tools = EvidenceRetrievalTools(self.catalog)
        graph_tools, graph_error = (None, None)
        graph_initialized = False

        def prepare_graph():
            nonlocal graph_tools, graph_error, graph_initialized
            if graph_initialized:
                return
            graph_initialized = True
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
        if repair_ids is not None:
            all_upstream = output.supervisor_result
            all_upstream.evidence_bundle = workspace.evidence
        output.supervisor_result = all_upstream
        output.routing_decision = RoutingDecision(
            question=question,
            status="routed",
            selected_roles=list(dict.fromkeys(t.specialist for t in plan.tasks)),
        )
        for index, task in enumerate(plan.tasks):
            if repair_ids is not None and task.task_id not in repair_ids:
                continue
            execution = SpecialistExecution(
                execution_id=task.task_id or f"m5-lite-{index}",
                role=task.specialist,
                assigned_requirement_ids=task.requirement_ids,
            )
            output.specialist_executions.append(execution)
            state = workspace.tasks[execution.execution_id]
            if execution.execution_id in plan.blocked_tasks or not workspace.dependencies_ready(
                task
            ):
                state.update(
                    status="blocked", error=state.get("error", "dependency_output_unavailable")
                )
                execution.status = "abstained"
                execution.missing_requirement_ids = task.requirement_ids
                output.trace.append(
                    StageExecution(
                        stage="specialist_execution",
                        outcome="blocked",
                        role=task.specialist,
                        reasons=[task.task_id, state["error"]],
                    )
                )
                continue
            state["status"] = "ready"
            all_upstream.execution_order.append(task.task_id)
            workspace.tasks.setdefault(
                execution.execution_id,
                dict(requirement_ids=task.requirement_ids, depends_on=task.depends_on),
            )
            workspace.tasks[execution.execution_id]["status"] = "running"
            bundle = ExecutionEvidenceBundle()

            def call(operation, request, function, execution=execution):
                begin = perf_counter()
                step_id = f"lite-tool-{len(all_upstream.tool_trace)}"
                step_id = execution.execution_id + "-" + step_id
                workspace.tasks[execution.execution_id].setdefault("tool_step_ids", []).append(
                    step_id
                )
                try:
                    response = function(request)
                except Exception as error:
                    all_upstream.tool_trace.append(
                        StepExecutionResult(
                            step_id=step_id,
                            operation=operation,
                            bound_request=request.model_dump(mode="json"),
                            final_state="failed",
                            reasons=["tool_execution_error", type(error).__name__],
                            latency_ms=(perf_counter() - begin) * 1000,
                        )
                    )
                    raise
                event = StepExecutionResult(
                    step_id=step_id,
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

            def lookup(source, bundle=bundle):
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

            try:
                selected = task.sources
                for handle in dict.fromkeys(selected):
                    resolved = handle
                    source = sources.get(resolved)
                    if source is None:
                        bundle.limitations.append("unknown_or_foreign_source:" + handle)
                        continue
                    lookup(source)
                try:
                    self._coordinate_evidence(task, bundle, sources, context, output, lookup)
                except ValueError as error:
                    bundle.limitations.append(str(error))
                if task.document_search:
                    try:
                        self._search_document(task, context, output, call)
                    except ValueError as error:
                        bundle.limitations.append(str(error))
                bundle.claim_fact_references = [f.reference for f in bundle.facts]
                if self.graph_enabled and task.use_graph:
                    prepare_graph()
                    starts = [c.metric_id for c in bundle.calculations if c.metric_id]
                    starts.extend(
                        graph_id("source_fact", f.record.observation_identity().model_dump())
                        for f in bundle.facts
                    )
                    starts.extend(
                        graph_id("source_fact", row["reference"]["observation"])
                        for tid in workspace.dependency_ids(task)
                        for row in workspace.task_results[tid]["selected_observations"]
                    )
                    if task.document_search and self.composition is not None:
                        starts.extend(
                            graph_id(hit["reference"]["kind"], hit["reference"]["evidence"])
                            for hit in workspace.tasks[task.task_id].get("source_context", [])
                        )
                    starts = list(dict.fromkeys(starts))[:6]
                    if not starts and (not task.depends_on):
                        bundle.limitations.append("graph_no_valid_starting_nodes")
                    for node_id in starts:
                        request = (
                            GetGraphContextRequest(
                                document_id=self.composition.logical_document_id,
                                composition_id=self.composition.composition_id,
                                node_id=node_id,
                                depth=2,
                                limit=8,
                                relations=[
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
                                ],
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
                workspace.tasks[task.task_id]["graph_requests"] = [
                    g.request.model_dump_json() for g in bundle.graph_contexts
                ]
                workspace.merge(bundle)
                all_upstream.evidence_bundle = workspace.evidence
                self._execute_task(task, execution, bundle, all_upstream, context, output)
                continue
            except Exception as error:
                execution.status = "failed"
                execution.error = OrchestrationError(
                    stage="specialist_execution",
                    code="specialist_execution_failed",
                    error_type=type(error).__name__,
                    role=task.specialist,
                )
                output.errors.append(execution.error)
                workspace.tasks[execution.execution_id]["status"] = "technical_error"
            output.trace.append(
                StageExecution(
                    stage="specialist_execution",
                    outcome=execution.status,
                    role=task.specialist,
                    reasons=[task.objective, *bundle.limitations],
                )
            )
        all_upstream.evidence_bundle = workspace.evidence
        output.candidates, output.conflicts = aggregate_candidates(output.specialist_executions)
        if repair_ids is not None:
            renamed = {}
            for candidate in output.candidates:
                if any(o.execution_id in repair_ids for o in candidate.origins):
                    renamed[candidate.candidate_id] = candidate.candidate_id + ":r2"
                    candidate.candidate_id = renamed[candidate.candidate_id]
            for conflict in output.conflicts:
                conflict.candidate_ids = [renamed.get(cid, cid) for cid in conflict.candidate_ids]
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
            if output.candidates or output.document_candidates
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
        output.latency_ms = (output.latency_ms if repair_ids is not None else 0) + (
            perf_counter() - started
        ) * 1000
        return output

    def _search_document(self, task, context, output, call):
        manifest = self.composition
        if manifest is None or self.document_repository is None:
            raise ValueError("document_composition_unavailable")
        requirement = task.document_search
        tools = EvidenceRetrievalTools.from_composition(
            manifest,
            self.document_repository,
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )
        pinned_snapshot = (
            context.snapshot_id if manifest.financial_snapshot.source_kind == "json" else None
        )
        operation = document_operations([requirement], manifest, pinned_snapshot)[0]
        try:
            result = call(operation.operation, operation.request, tools.search_document_evidence)
        finally:
            tools.close_search()
        if result.status != "found":
            raise ValueError("document_search_" + result.status)
        from .document_qa_contracts import DocumentEvidenceBundle
        from .evidence_coordination import content_digest

        state = self.workspace.tasks[task.task_id]
        state["source_context"] = [
            dict(
                handle="D-" + content_digest(hit.evidence.reference.model_dump(mode="json"))[:20],
                text=hit.snippet,
                reference=hit.evidence.reference.model_dump(mode="json"),
                citations=[c.model_dump(mode="json") for c in hit.evidence.citations],
                cells=[cell.model_dump(mode="json") for cell in hit.cells],
            )
            for hit in result.matches
        ]
        goal_id = state.get("document_goal")
        if goal_id is None and not task.resolve_inputs:
            goal_id = next(
                (
                    r.requirement_id
                    for r in self.workspace.requirements
                    if r.requirement_id in task.requirement_ids and r.kind == "document"
                ),
                None,
            )
        if goal_id:
            candidates = document_candidates(
                DocumentEvidenceBundle(operation=operation, result=result),
                context.company_id,
                manifest,
            )
            state["document_goal"] = goal_id
            state["document_candidate_ids"] = [c.candidate_id for c in candidates]
            output.document_candidates.extend(
                c for c in candidates if c not in output.document_candidates
            )

    def _coordinate_evidence(self, task, bundle, sources, context, output, lookup):
        from .evidence_coordination import (
            join_observations,
            observation,
            propose,
            resolve_demand_batches,
            select_observations,
        )

        workspace = self.workspace
        state = workspace.tasks[task.task_id]
        for match in [*workspace.evidence.facts, *bundle.facts]:
            row = observation(match)
            workspace.observations[row["evidence_id"]] = row
        current = [observation(f) for f in bundle.facts]
        state["selected_observations"] = current
        if not task.resolve_inputs:
            return
        try:
            proposal, _ = propose(self.gateway, context, task, workspace, sources)
            task.use_graph |= proposal.use_graph
            search = proposal.document_search
            if search:
                goal = next(
                    (
                        r
                        for r in workspace.requirements
                        if r.requirement_id == search.goal_id
                        and r.requirement_id in task.requirement_ids
                    ),
                    None,
                )
                task.document_search = DocumentRequirement(
                    target=search.query,
                    label=goal.text if goal else task.objective,
                    kind=search.kind,
                    query=search.query,
                    selection_period=search.selection_period,
                )
                if goal:
                    goal.kind = "document"
                    state["document_goal"] = goal.requirement_id
                elif search.goal_id is not None:
                    bundle.limitations.append("document_goal_reference_unknown")
            handles, lineage = resolve_demand_batches(
                proposal, state.get("retrieval_batches", []), task, workspace, sources
            )
            state["coordination"] = dict(
                proposal=proposal.model_dump(mode="json"),
                retrieval_lineage=lineage,
                selected_handles=handles,
                joins=[],
                retrieval_batches=state.get("retrieval_batches", []),
            )
            if proposal.selection:
                # Demand-retrieve the entire declared domain rather than ranking a truncated prompt.
                handles.extend(
                    h
                    for h, s in sources.items()
                    if s["kind"] == "fact"
                    and s["item"] == proposal.selection.item
                    and s["period"] in proposal.selection.periods
                )
            known_facts = {
                f.reference.observation.model_dump_json() for f in workspace.evidence.facts
            }
            reused = set()
            for handle in dict.fromkeys(handles):
                source = sources[handle]
                if source["kind"] == "fact":
                    reused.update(
                        f.observation_identity().model_dump_json() for f in source["records"]
                    )
                    source = source | {
                        "records": [
                            f
                            for f in source["records"]
                            if f.observation_identity().model_dump_json() not in known_facts
                        ]
                    }
                lookup(source)
            current = [observation(f) for f in bundle.facts]
            for row in current:
                workspace.observations[row["evidence_id"]] = row
            current = [
                row
                for row in workspace.observations.values()
                if row in current
                or json.dumps(row["reference"]["observation"], separators=(",", ":")) in reused
            ]
            if proposal.selection:
                current, record = select_observations(
                    proposal.selection, list(workspace.observations.values()), sources
                )
                state["coordination"]["selection"] = record
            demands = [d for batch in state.get("retrieval_batches", []) for d in batch]
            for tid in dict.fromkeys(
                d["period_from_task"]
                for d in demands
                if d.get("period_from_task") and d["source"] in sources
            ):
                record = join_observations(workspace.task_results[tid], current)
                state["coordination"]["joins"].append(record)
                if record["status"] != "matched":
                    raise ValueError("join_" + record["status"])
            state["selected_observations"] = current
        finally:
            if "coordination_usage" in state:
                output.usage.stages[
                    task.task_id + ("_repair" if workspace.repair_used else "") + "_evidence_demand"
                ] = PlannerLLMMetadata.model_validate(state["coordination_usage"])

    def _execute_task(self, task, execution, bundle, all_upstream, context, output):
        state = self.workspace.tasks[execution.execution_id]
        try:
            upstream = all_upstream.model_copy(deep=True)
            dependencies = self.workspace.dependency_ids(task)
            from .evidence_coordination import observation

            permitted = {
                row["evidence_id"]
                for record in [
                    state,
                    *(self.workspace.task_results[tid] for tid in dependencies),
                ]
                for row in record.get("selected_observations", [])
            }
            upstream.evidence_bundle.facts = [
                f
                for f in upstream.evidence_bundle.facts
                if observation(f)["evidence_id"] in permitted
            ]
            metric_ids = {c.metric_id for c in bundle.calculations}
            for tid in dependencies:
                metric_ids.update(self.workspace.tasks[tid].get("metric_ids", ()))
            upstream.evidence_bundle.calculations = [
                c for c in self.workspace.evidence.calculations if c.metric_id in metric_ids
            ]
            graph_requests = set(state.get("graph_requests", ()))
            for tid in dependencies:
                graph_requests.update(self.workspace.tasks[tid].get("graph_requests", ()))
            upstream.evidence_bundle.graph_contexts = [
                g
                for g in self.workspace.evidence.graph_contexts
                if g.request.model_dump_json() in graph_requests
            ]
            upstream.status = "partial" if bundle.limitations else "completed"
            state["metric_ids"] = [c.metric_id for c in bundle.calculations]
            assigned = [
                r for r in self.workspace.requirements if r.requirement_id in task.requirement_ids
            ]
            if task.document_search and assigned and all(r.kind == "document" for r in assigned):
                result = SpecialistResult(
                    question=task.objective,
                    role=task.specialist,
                    upstream_status=upstream.status,
                    status="generated" if state.get("document_candidate_ids") else "abstained",
                )
            else:
                result = self._specialist(task, upstream, task.objective, context)
            _check_assignment(
                result,
                supporting_references=[f.reference for f in upstream.evidence_bundle.facts]
                + [
                    RetrievalReference(kind="metric", record_id=c.metric_id)
                    for c in upstream.evidence_bundle.calculations
                ],
                citations=upstream.evidence_bundle.citations,
            )
            execution.result, execution.llm = result, result.llm
            execution.status = result.status
            if state.get("revision", 1) > 1:
                previous = state.get("previous_candidate_ids", [])
                state["candidate_revisions"] = [
                    dict(
                        candidate_id=c.candidate_id,
                        parent_candidate_ids=previous,
                        revision=state["revision"],
                    )
                    for c in result.candidates
                ]
            self.workspace.record_result(task, result, retain_sources=True)
            output.usage.stages[
                execution.execution_id + ("_repair" if self.workspace.repair_used else "")
            ] = result.llm
            output.missing_evidence.extend(
                result.missing_evidence + result.limitations + bundle.limitations
            )
            if "specialist_processing_failure" in result.limitations:
                state.update(status="failed", error="specialist_output_invalid")
                output.errors.append(
                    OrchestrationError(
                        stage="specialist_execution",
                        code="specialist_output_invalid",
                        role=task.specialist,
                    )
                )
        except Exception as error:
            state.update(status="failed", error="specialist_execution_failed")
            execution.status = "failed"
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
                reasons=[task.task_id, task.objective, *bundle.limitations],
            )
        )
