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


class LitePlan(FinancialModel):
    tasks: list[LiteTask] = Field(default_factory=list, max_length=6)


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
        if context.reporting_scope and fact.context.reporting_scope != context.reporting_scope:
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
    for metric in catalog.metrics:
        if (metric.request.document_id, metric.request.snapshot_id) != (
            context.document_id,
            context.snapshot_id,
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
    def __init__(self, gateway=None):
        self.gateway = gateway

    def plan(self, question, context, sources):
        metadata = PlannerLLMMetadata(status="deterministic")
        if self.gateway is None or context.mode == "deterministic":
            return fallback_plan(question, sources), metadata, []
        prompt = dict(
            instruction=(
                "Supervisor tài chính. Chọn ít Specialist thực sự cần thiết từ roles trong nguồn. "
                "Chỉ lập kế hoạch MỘT lần. JSON {tasks:[{specialist,objective,sources:[S1,...],use_graph:false}]}. "
                "Đặt use_graph=true khi cần truy vết nguồn, thành phần metric, phân tích nhiều bước, "
                "kết hợp bảng/thuyết minh hoặc kiểm tra ngữ cảnh phép tính. Tra một giá trị đơn giản "
                "không cần graph. Graph chỉ cung cấp structural/contextual relations, không chứng minh claim. "
                "objective là công việc ngắn tiếng Việt; sources là handles phù hợp trong inventory. "
                "Không DAG, approval, coverage hoặc suy đoán identities. Câu hỏi đơn giản một role; "
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
            generation=GenerationParameters(temperature=0.0, max_output_tokens=900),
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
            return fallback_plan(question, sources), metadata, ["supervisor_provider_failure"]
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

    def run_document(self, *args, **kwargs):
        raise ValueError("m5_lite_financial_scope_only")

    def reset_request(self):
        pass

    def _specialist(self, task, upstream, question, context):
        module, proposal = DOMAINS[task.specialist]
        result = SpecialistResult(
            question=question, role=task.specialist, upstream_status=upstream.status
        )
        roles = {
            "profitability": {"gross_margin": "revenue", "revenue_yoy": "current_revenue"},
            "liquidity_and_leverage": {"debt_to_assets": "assets"},
        }.get(task.specialist, {})
        select_evidence(
            upstream,
            result,
            item_labels=module.ITEM_LABELS,
            metric_labels=getattr(module, "METRIC_LABELS", {}),
            period_roles=roles,
            balance_sheet=task.specialist == "liquidity_and_leverage",
        )
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
        deterministic = self.gateway is None or context.mode == "deterministic"
        if len(json.dumps(prompt, ensure_ascii=False)) + len(question) > 48000:
            deterministic = True
            result.limitations.append("specialist_payload_limit_numeric_fallback")
        generate_candidates(
            gateway=self.gateway,
            model=context.model,
            result=result,
            prompt=prompt,
            proposal_type=LiteProposal,
            render=module._render,
            prefix="m5-lite-" + task.specialist,
            deterministic=deterministic,
            emit_derived=True,
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
                execution_id=f"m5-lite-{index}", role=task.specialist, assigned_requirement_ids=[]
            )
            output.specialist_executions.append(execution)
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
                    source = sources.get(handle)
                    if source is None or task.specialist not in source["roles"]:
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
            output.trace.append(
                StageExecution(
                    stage="specialist_execution",
                    outcome=execution.status,
                    role=task.specialist,
                    reasons=[task.objective, *bundle.limitations],
                )
            )
        output.candidates, output.conflicts = aggregate_candidates(output.specialist_executions)
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
