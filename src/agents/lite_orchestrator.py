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
from ..tools.evidence_retrieval import EvidenceRetrievalTools, GetEvidenceSourcesRequest
from ..tools.financial_calculator import CalculateFinancialMetricRequest, FinancialCalculator
from ..tools.financial_retrieval import FinancialRetrievalTools, GetFinancialFactRequest
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
    SpecialistResult,
    _numeric_proposals,
    generate_candidates,
    select_evidence,
)
from .supervisor import ExecutionEvidenceBundle, StepExecutionResult, SupervisorResult

DOMAINS = {
    "profitability": (profit, profit.ProfitabilityProposal),
    "liquidity_and_leverage": (liquidity, liquidity.LiquidityLeverageProposal),
    "cash_flow_and_earnings_quality": (cash, cash.CashFlowEarningsQualityProposal),
}


class LiteTask(FinancialModel):
    specialist: SpecialistRole
    objective: str = Field(min_length=1, max_length=600)
    # Optional retrieval handles, never coverage obligations or claim approvals.
    sources: list[str] = Field(default_factory=list, max_length=16)


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
                "Chỉ lập kế hoạch MỘT lần. JSON {tasks:[{specialist,objective,sources:[S1,...]}]}. "
                "objective là công việc ngắn tiếng Việt; sources là handles phù hợp trong inventory. "
                "Không DAG, approval, coverage hoặc suy đoán identities. Câu hỏi đơn giản một role; "
                "nhiều phần chọn các role cần thiết, không gọi tất cả mặc định. "
                "Thiếu dữ liệu vẫn chọn các nguồn độc lập phù hợp; không bịa handles."
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
        if len(payload) + len(question) > 8000:
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
    def __init__(self, catalog, gateway=None, *, supervisor=None):
        self.catalog, self.gateway = catalog, gateway
        self.supervisor = supervisor or SupervisorLite(gateway)

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
                "không tự tính số. analyses tùy chọn [{statement,evidence_ids,goal,operations:[],"
                "assumptions:[],limitations:[],claim_type:reasoned_conclusion}]. "
                "Được phân tích quan hệ, so sánh và nêu giới hạn dựa trên nguồn, không chỉ điền số. "
                "Phép tính mới chỉ khai báo operations để Financial Calculator thực thi: "
                "{operation_id,operator,inputs:[evidence_id hoặc operation_id],period_relation}. "
                "operator: sum,subtract,ratio,percentage_change,mean,greater,less,equal; period_relation "
                "same hoặc across_periods. Không bịa giá trị/nguồn, không ACCEPT claim. "
                "Trả phần có căn cứ khi thiếu phần khác. M6 sẽ xác minh mọi candidate."
            ),
            objective=task.objective,
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
                )
                for e in result.supporting_evidence
            ],
        )
        deterministic = self.gateway is None or context.mode == "deterministic"
        if len(json.dumps(prompt, ensure_ascii=False)) + len(question) > 7500:
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
        )
        return result

    def run(self, *, question, context):
        started = perf_counter()
        output = OrchestrationResult(question=question, context=context.model_copy(deep=True))
        if not all((context.company_id, context.document_id, context.snapshot_id)):
            output.status = "clarification_required"
            output.stop_conditions = ["trusted_context_required"]
            return output
        # Explicit comparative years constrain retrieval within the trusted snapshot.
        years = re.findall(r"\b(?:19|20|21)\d{2}\b", question)
        retrieval_context = (
            context.model_copy(update={"period": " ".join(years)}) if years else context
        )
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
