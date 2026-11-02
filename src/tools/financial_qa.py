"""Single-agent tool baseline M4-05; chỉ tools cung cấp số liệu và nguồn."""

import json
import re
from copy import deepcopy
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import (
    Cost,
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    ModelIdentity,
    OutputSpec,
    RequestConstraints,
    Usage,
)
from ..core.llm_gateway import SharedLLMGateway
from ..evidence.retrieval import EvidenceCitation
from ..evidence.snapshots import SnapshotCatalog, SnapshotDescriptor
from .evidence_retrieval import (
    EvidenceRetrievalTools,
    EvidenceToolResponse,
    GetEvidenceSourcesRequest,
    GetMetricEvidenceLineageRequest,
)
from .financial_calculator import (
    CalculateFinancialMetricRequest,
    FinancialCalculationResponse,
    FinancialCalculator,
)
from .financial_retrieval import (
    FinancialFactMatch,
    FinancialRetrievalTools,
    FinancialToolResponse,
    FindFinancialFactsRequest,
    ListFinancialMetricsRequest,
)
from .question_understanding import (
    FORMULA_LABELS,
    ITEM_RULES,
    QAUnderstanding,
    normalize,
    understand,
)


class QADocument(FinancialModel):
    """Caller bind metadata đã biết; không suy filing year từ các operand periods."""

    document_id: str
    company_id: str
    company_aliases: list[str] = Field(min_length=1)
    reporting_year: int = Field(ge=1900, le=2200)


class QAContext(FinancialModel):
    document_id: str | None = None
    company_id: str | None = None
    snapshot_id: str | None = None
    reporting_year: int | None = Field(default=None, ge=1900, le=2200)
    period: str | None = None
    reporting_scope: Literal["separate", "consolidated"] | None = None
    # Cho câu hỏi tiếp nối; caller bind target từ response trước, không memory ngầm.
    canonical_item_id: str | None = None
    formula_id: str | None = None
    allow_gateway: bool = False
    model: ModelIdentity = Field(
        default_factory=lambda: ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)
    )


class QALLMMetadata(FinancialModel):
    calls: int = 0
    status: str = "not_called"
    model: ModelIdentity | None = None
    usage: Usage | None = None
    cost: Cost | None = None
    latency_ms: float | None = None
    parsing_method: Literal["deterministic", "gateway"] = "deterministic"
    generation_method: Literal["deterministic_tool_rendering"] = "deterministic_tool_rendering"


class QAToolStep(FinancialModel):
    tool: str
    request: dict
    status: str


class QAResponse(FinancialModel):
    version: Literal["financial_qa_v1"] = "financial_qa_v1"
    baseline_type: Literal["single_agent_tool_baseline"] = "single_agent_tool_baseline"
    question: str
    parsed: QAUnderstanding
    status: Literal["answered", "partial", "clarification_required", "abstained", "unsupported"]
    answer_vi: str
    document_id: str | None = None
    snapshot_id: str | None = None
    period: str | None = None
    numerical_result: str | None = None
    unit: str | None = None
    facts: list[FinancialFactMatch] = Field(default_factory=list)
    retrieval: FinancialToolResponse | None = None
    calculation: FinancialCalculationResponse | None = None
    evidence: list[EvidenceToolResponse] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    snapshot_candidates: list[SnapshotDescriptor] = Field(default_factory=list)
    document_candidates: list[QADocument] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    tool_trace: list[QAToolStep] = Field(default_factory=list)
    llm: QALLMMetadata = Field(default_factory=QALLMMetadata)
    financial_fact_verified: Literal[False] = False


def number_vi(value: str) -> str:
    """Chỉ format chuỗi, không tính lại số, đổi scale hoặc làm tròn."""
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return value
    whole, dot, fraction = value.partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return sign + ".".join(groups) + ("," + fraction if dot else "")


class FinancialQABaseline:
    """Caller hydrate SnapshotCatalog và filing metadata; không I/O, OCR hoặc agents.

    Optional gateway chỉ parse một lần khi rules chưa nhận diện target. Outputs
    của model không chứa IDs tài liệu/snapshot, giá trị hay citations.
    """

    def __init__(
        self, catalog: SnapshotCatalog, documents=(), *, gateway: SharedLLMGateway | None = None
    ):
        self._catalog = deepcopy(catalog)
        self._documents = [QADocument.model_validate(d).model_copy(deep=True) for d in documents]
        known = {d.document_id for d in catalog.descriptors}
        if any(d.document_id not in known for d in self._documents):
            raise ValueError("QA document not in snapshot catalog")
        if len({d.document_id for d in self._documents}) != len(self._documents):
            raise ValueError("Duplicate QA document metadata")
        self._financial = FinancialRetrievalTools(catalog)
        self._calculator = FinancialCalculator(catalog)
        self._evidence = EvidenceRetrievalTools(catalog)
        self._gateway = gateway
        self._selections = {}

    def _select(self, document, snapshot):
        key = document, snapshot
        if key not in self._selections:
            self._selections[key] = self._catalog.select(document, snapshot)
        return self._selections[key].model_copy(deep=True)

    @staticmethod
    def _call(response, tool, request):
        result = tool(request)
        response.tool_trace.append(
            QAToolStep(
                tool=request.tool,
                request=request.model_dump(mode="json"),
                status=result.status,
            )
        )
        response.caveats.extend(result.caveats)
        response.reasons.extend(result.reasons)
        return result

    def _parse_gateway(self, question, context, response):
        meta = response.llm
        if not context.allow_gateway or self._gateway is None:
            meta.status = "disabled" if not context.allow_gateway else "gateway_unavailable"
            return
        catalog = {key: list(rule.aliases) for key, rule in ITEM_RULES.items()}
        prompt = {
            "instruction": "Chỉ phân loại câu hỏi đơn mục tiêu. Không trả số liệu, nguồn hoặc IDs. "
            "Không đổi câu hỏi không hỗ trợ thành chỉ tiêu gần giống. Thiếu dữ kiện dùng null. "
            "intent=unsupported cho chỉ số ngoài allowlist, dự báo, nhiều mục tiêu/so sánh.",
            "schema": QAUnderstanding.model_json_schema(),
            "canonical_catalog": catalog,
            "approved_formulas": FORMULA_LABELS,
            "company_aliases": sorted({a for d in self._documents for a in d.company_aliases}),
        }
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id="qa-" + uuid4().hex,
            model=context.model,
            messages=[
                Message(role="system", content=json.dumps(prompt, ensure_ascii=False)),
                Message(role="user", content=question),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=600),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=30.0),
        )
        start = perf_counter()
        result = self._gateway.generate(request)
        meta.calls, meta.model = 1, context.model
        meta.latency_ms = (perf_counter() - start) * 1000
        meta.status, meta.usage, meta.cost = result.status, result.usage, result.cost
        if result.status != "success" or not isinstance(result.output, JSONOutput):
            response.reasons.append("gateway_unavailable_or_invalid_output")
            return
        try:
            parsed = QAUnderstanding.model_validate(result.output.payload)
        except ValidationError:
            meta.status = "invalid_intent_schema"
            response.reasons.append("invalid_gateway_intent")
            return
        # Chặn model phát minh năm/công ty ngoài câu hỏi; target được kiểm allowlist tiếp.
        if parsed.reporting_year is not None and str(parsed.reporting_year) not in question:
            response.reasons.append("gateway_invented_reporting_year")
            return
        if parsed.company_alias is not None and (
            not any(
                normalize(parsed.company_alias) == normalize(a)
                for d in self._documents
                for a in d.company_aliases
            )
            or normalize(parsed.company_alias) not in normalize(question)
        ):
            response.reasons.append("gateway_unknown_company")
            return
        if parsed.reporting_scope != response.parsed.reporting_scope:
            response.reasons.append("gateway_changed_explicit_scope")
            return
        if parsed.period is not None and parsed.period != response.parsed.period:
            response.reasons.append("gateway_invented_period")
            return
        parsed.period = response.parsed.period
        parsed.reporting_year = response.parsed.reporting_year or parsed.reporting_year
        response.parsed = parsed
        meta.parsing_method = "gateway"

    def answer(self, question: str, context: QAContext | None = None) -> QAResponse:
        context = QAContext.model_validate_json((context or QAContext()).model_dump_json())
        parsed, errors = understand(question)
        response = QAResponse(
            question=question,
            parsed=parsed,
            status="unsupported",
            answer_vi="Câu hỏi chưa được hỗ trợ trong baseline này.",
            reasons=errors,
        )
        if not question.strip():
            return self._stop(response, "clarification_required", "Cần nhập câu hỏi.", "question")
        if errors:
            if errors == ["cross_document_comparison_blocked_D03_B10"]:
                response.answer_vi = (
                    "Chưa hỗ trợ so sánh liên tài liệu: D03-B10 còn chặn khi phạm vi báo cáo "
                    "chưa được xác nhận tương thích. Có thể hỏi từng filing riêng."
                )
            elif "multiple_or_ambiguous_targets" in errors or "ambiguous_reporting_scope" in errors:
                return self._stop(
                    response,
                    "clarification_required",
                    "Cần chọn một chỉ tiêu/phạm vi rõ ràng.",
                    "target",
                )
            return response
        if not (parsed.canonical_item_id or parsed.formula_id):
            if parsed.intent == "evidence_explanation" and (
                context.canonical_item_id or context.formula_id
            ):
                parsed.canonical_item_id, parsed.formula_id = (
                    context.canonical_item_id,
                    context.formula_id,
                )
            else:
                self._parse_gateway(question, context, response)
                parsed = response.parsed
        if parsed.intent == "unsupported":
            response.reasons.append("unsupported_question")
            return response
        if bool(parsed.canonical_item_id) == bool(parsed.formula_id):
            return self._stop(
                response,
                "clarification_required",
                "Cần chỉ rõ chỉ tiêu hoặc công thức muốn hỏi.",
                "target",
            )
        if (parsed.canonical_item_id and parsed.canonical_item_id not in ITEM_RULES) or (
            parsed.formula_id and parsed.formula_id not in FORMULA_LABELS
        ):
            response.reasons.append("target_outside_allowlist")
            return response
        if (parsed.intent == "direct_fact" and parsed.formula_id) or (
            parsed.intent == "calculated_metric" and parsed.canonical_item_id
        ):
            response.reasons.append("intent_target_mismatch")
            return response
        if (
            parsed.reporting_year
            and context.reporting_year
            and parsed.reporting_year != context.reporting_year
        ):
            return self._stop(
                response,
                "clarification_required",
                "Năm trong câu hỏi khác năm caller đã chọn.",
                "reporting_year",
            )
        parsed.reporting_year = parsed.reporting_year or context.reporting_year
        if parsed.period and context.period and parsed.period != context.period:
            return self._stop(
                response, "clarification_required", "Kỳ trong câu hỏi khác kỳ đã chọn.", "period"
            )
        context.period = parsed.period or context.period
        if context.period:
            year_match = re.fullmatch(r"((?:19|20|21)\d{2})(?:-\d{2}-\d{2})?", context.period)
            if not year_match or (
                parsed.reporting_year and int(year_match[1]) != parsed.reporting_year
            ):
                return self._stop(
                    response,
                    "clarification_required",
                    "Kỳ đã chọn không khớp năm hoặc chưa được hỗ trợ.",
                    "period",
                )
            parsed.reporting_year = int(year_match[1])
        if (
            parsed.reporting_scope
            and context.reporting_scope
            and parsed.reporting_scope != context.reporting_scope
        ):
            return self._stop(
                response,
                "clarification_required",
                "Phạm vi trong câu hỏi khác phạm vi đã chọn.",
                "reporting_scope",
            )
        parsed.reporting_scope = parsed.reporting_scope or context.reporting_scope
        if parsed.reporting_year is None:
            return self._stop(
                response, "clarification_required", "Cần chọn năm/kỳ báo cáo.", "reporting_year"
            )
        document = self._resolve_document(question, context, response)
        if document is None:
            return response
        response.document_id = document
        selection = self._select(document, context.snapshot_id)
        # Exact snapshot trong câu hỏi phải thuộc catalog và AND với caller selection.
        mentioned = {d.snapshot_id for d in self._catalog.descriptors if d.snapshot_id in question}
        if mentioned:
            if len(mentioned) != 1 or (
                context.snapshot_id and context.snapshot_id not in mentioned
            ):
                return self._stop(
                    response,
                    "clarification_required",
                    "Lựa chọn snapshot mâu thuẫn.",
                    "snapshot_id",
                )
            selection = self._select(document, next(iter(mentioned)))
        text = normalize(question)
        original = "ban goc" in text or "snapshot goc" in text
        recovery = "ban recovery" in text or "snapshot recovery" in text
        explicit_snapshot = re.search(
            r"\bsnapshot\s+(?:id\s+)?([^\s?,;]+)", question, re.IGNORECASE
        )
        if explicit_snapshot and not (mentioned or original or recovery):
            response.reasons.append("unknown_snapshot_in_question")
            return self._stop(
                response, "abstained", "Snapshot được hỏi không có trong catalog.", "snapshot_id"
            )
        if original or recovery:
            choices = [
                d
                for d in self._catalog.descriptors
                if d.document_id == document and (d.origin == "recovery") == recovery
            ]
            if original and recovery or len(choices) != 1:
                return self._stop(
                    response, "clarification_required", "Cần chọn exact snapshot ID.", "snapshot_id"
                )
            chosen = choices[0].snapshot_id
            if (context.snapshot_id and context.snapshot_id != chosen) or (
                mentioned and chosen not in mentioned
            ):
                return self._stop(
                    response,
                    "clarification_required",
                    "Lựa chọn snapshot mâu thuẫn.",
                    "snapshot_id",
                )
            selection = self._select(document, chosen)
        response.snapshot_candidates = [e.descriptor for e in selection.candidates]
        if selection.status != "selected":
            response.reasons.extend(selection.reasons)
            return self._stop(
                response,
                "clarification_required" if selection.status == "ambiguous" else "abstained",
                "Cần chọn snapshot hợp lệ; không tự chọn bản mới nhất hoặc trộn bản gốc/recovery.",
                "snapshot_id",
            )
        descriptor = selection.candidates[0].descriptor
        response.snapshot_id = descriptor.snapshot_id
        scope = self._catalog.get_reporting_scope(document, descriptor.snapshot_id)
        if parsed.reporting_scope and (
            scope.status != "resolved" or scope.reporting_scope != parsed.reporting_scope
        ):
            response.reasons.extend(["requested_reporting_scope_unavailable", *scope.reasons])
            return self._stop(
                response, "abstained", "Chưa có nguồn xác nhận phạm vi báo cáo được yêu cầu."
            )
        if scope.status != "resolved":
            response.caveats.append("reporting_scope_unresolved")
        if parsed.canonical_item_id:
            self._direct(response, context)
        else:
            self._analytical(response, context)
        response.caveats = sorted(set(response.caveats))
        response.reasons = sorted(set(response.reasons))
        return response.model_copy(deep=True)

    @staticmethod
    def _stop(response, status, message, missing=None):
        response.status, response.answer_vi = status, message
        if missing:
            response.missing_information.append(missing)
        return response

    def _resolve_document(self, question, context, response):
        text = normalize(question)
        alias_companies = {
            d.company_id
            for d in self._documents
            for alias in d.company_aliases
            if re.search(r"(?<!\w)" + re.escape(normalize(alias)) + r"(?!\w)", text)
        }
        if response.parsed.company_alias:
            alias_companies.update(
                d.company_id
                for d in self._documents
                if normalize(response.parsed.company_alias)
                in {normalize(a) for a in d.company_aliases}
            )
        if context.company_id:
            if alias_companies and alias_companies != {context.company_id}:
                self._stop(
                    response,
                    "clarification_required",
                    "Công ty trong câu hỏi khác lựa chọn caller.",
                    "company_id",
                )
                return None
            alias_companies = {context.company_id}
        if context.document_id:
            known = {d.document_id for d in self._catalog.descriptors}
            metadata = [d for d in self._documents if d.document_id == context.document_id]
            companies = {
                f.company_id for f in self._catalog.facts if f.document_id == context.document_id
            }
            if context.document_id not in known or (
                alias_companies and not alias_companies <= companies
            ):
                self._stop(response, "abstained", "Không tìm thấy tài liệu đúng định danh/công ty.")
                response.reasons.append("document_company_not_found")
                return None
            response.document_candidates = metadata
            return context.document_id
        if not alias_companies:
            self._stop(
                response,
                "clarification_required",
                "Cần chọn công ty hoặc tài liệu cụ thể.",
                "company_id_or_document_id",
            )
            return None
        candidates = [
            d
            for d in self._documents
            if d.company_id in alias_companies
            and d.reporting_year == response.parsed.reporting_year
        ]
        response.document_candidates = candidates
        if len(candidates) != 1:
            self._stop(
                response,
                "clarification_required" if candidates else "abstained",
                "Không xác định được duy nhất filing phù hợp; cần chọn document ID.",
                "document_id",
            )
            return None
        return candidates[0].document_id

    def _direct(self, response, context):
        parsed = response.parsed
        rule = ITEM_RULES[parsed.canonical_item_id]
        response.period = context.period or (
            f"{parsed.reporting_year}-12-31"
            if rule.statement_type == "B01"
            else str(parsed.reporting_year)
        )
        result = self._call(
            response,
            self._financial.find_financial_facts,
            FindFinancialFactsRequest(
                document_id=response.document_id,
                snapshot_id=response.snapshot_id,
                canonical_item_id=parsed.canonical_item_id,
                statement_type=rule.statement_type,
                period=response.period,
                period_type=rule.period_types[0],
                reporting_scope=parsed.reporting_scope,
            ),
        )
        response.retrieval = result
        if result.status != "found" or len(result.matches) != 1:
            self._stop(
                response,
                "clarification_required" if result.status == "ambiguous" else "abstained",
                "Chưa có một số liệu duy nhất đủ căn cứ cho chỉ tiêu/kỳ đã chọn.",
            )
            return
        fact = result.matches[0]
        response.facts = [fact]
        sources = self._call(
            response,
            self._evidence.get_evidence_sources,
            GetEvidenceSourcesRequest(
                reference=fact.reference,
                document_id=response.document_id,
                snapshot_id=response.snapshot_id,
            ),
        )
        response.evidence = [sources]
        if (
            sources.status != "found"
            or not sources.matches
            or fact.display_status != "display_with_caveat"
            or fact.record.value.normalized_value is None
        ):
            response.reasons.append("fact_or_source_not_usable")
            self._stop(
                response,
                "abstained",
                "Số liệu hoặc nguồn chưa đủ điều kiện để trả lời; không suy đoán giá trị.",
            )
            return
        response.citations = sources.matches[0].citations
        response.numerical_result = str(fact.record.value.normalized_value)
        response.unit = fact.record.value.unit
        label = fact.record.context.raw_item_label or rule.aliases[0]
        scope_note = (
            ""
            if fact.record.context.scale in (None, 1)
            else f" (hệ số đơn vị gốc {fact.record.context.scale})"
        )
        response.answer_vi = (
            f"{label}{self._company_text(response)} kỳ {response.period} là {number_vi(response.numerical_result)} "
            f"{response.unit or '(chưa rõ đơn vị)'}{scope_note}. "
            f"Báo cáo {rule.statement_type}; {self._sources_text(response.citations)}. "
            + self._quality_text(response)
        )
        response.status = "answered"

    def _analytical(self, response, context):
        parsed = response.parsed
        response.period = context.period or (
            f"{parsed.reporting_year}-12-31"
            if parsed.formula_id == "debt_to_assets"
            else str(parsed.reporting_year)
        )
        retrieved = self._call(
            response,
            self._financial.list_financial_metrics,
            ListFinancialMetricsRequest(
                document_id=response.document_id,
                snapshot_id=response.snapshot_id,
                formula_id=parsed.formula_id,
            ),
        )
        response.retrieval = retrieved
        current_role = {
            "gross_margin": "revenue",
            "debt_to_assets": "assets",
            "revenue_yoy": "current_revenue",
        }[parsed.formula_id]
        matches = [
            m
            for m in retrieved.matches
            if m.record.request.operand_periods.get(current_role) == response.period
        ]
        if retrieved.status != "found" or len(matches) != 1:
            self._stop(
                response,
                "clarification_required" if len(matches) > 1 else "abstained",
                "Chưa có duy nhất metric được phê duyệt cho kỳ/snapshot đã chọn.",
            )
            response.reasons.append("approved_metric_not_unique_or_missing")
            return
        metric = matches[0]
        calculated = self._call(
            response,
            self._calculator.calculate_financial_metric,
            CalculateFinancialMetricRequest(
                metric_id=metric.record.metric_id,
                document_id=response.document_id,
                snapshot_id=response.snapshot_id,
            ),
        )
        response.calculation = calculated
        lineage = self._call(
            response,
            self._evidence.get_metric_evidence_lineage,
            GetMetricEvidenceLineageRequest(
                metric_id=metric.record.metric_id,
                document_id=response.document_id,
                snapshot_id=response.snapshot_id,
            ),
        )
        response.evidence = [lineage]
        if (
            calculated.status != "computed"
            or calculated.trace is None
            or calculated.evidence is None
        ):
            self._stop(
                response,
                "abstained",
                "Chưa đủ điều kiện thực thi công thức; không tự tính hoặc ghép hai PDF.",
            )
            return
        if (
            lineage.status != "found"
            or len(lineage.metric_matches) != 1
            or not lineage.metric_matches[0].citations
        ):
            self._stop(
                response, "abstained", "Chưa có lineage và nguồn đầy đủ để trả kết quả có căn cứ."
            )
            return
        response.citations = lineage.metric_matches[0].citations
        response.numerical_result, response.unit = calculated.result, calculated.output_unit
        response.facts = [
            FinancialFactMatch(
                **f.model_dump(),
                source_review=o.source_review,
                reporting_scope=calculated.evidence.reporting_scope,
            )
            for o in calculated.evidence.operands
            for f in o.facts.matches
        ]
        role_labels = {
            "gross_profit": "lợi nhuận gộp",
            "revenue": "doanh thu thuần",
            "assets": "tổng tài sản",
            "liabilities": "nợ phải trả",
            "current_revenue": "doanh thu thuần kỳ hiện tại",
            "prior_revenue": "doanh thu thuần kỳ trước",
        }
        expression = re.sub(
            r"[a-z_]+", lambda m: role_labels.get(m[0], m[0]), calculated.trace.formula.expression
        )
        operands = "; ".join(
            f"{role_labels.get(o.role, o.role)}: {number_vi(o.value)} {o.unit}, kỳ {o.context.period}"
            for o in calculated.trace.operands
        )
        response.answer_vi = (
            f"{FORMULA_LABELS[parsed.formula_id]}{self._company_text(response)} kỳ {response.period} là "
            f"{number_vi(calculated.result)}%. Công thức: ({expression}) × "
            f"{calculated.trace.formula.output_multiplier}. "
            f"Số liệu gốc: {operands}. {self._sources_text(response.citations)}. "
            + self._quality_text(response)
        )
        response.status = "answered"

    @staticmethod
    def _company_text(response):
        return (
            " của " + response.document_candidates[0].company_aliases[0]
            if response.document_candidates
            else ""
        )

    @staticmethod
    def _sources_text(citations):
        pages = sorted({c.pdf_page for c in citations if c.pdf_page is not None})
        return (
            "Nguồn PDF, trang " + ", ".join(map(str, pages))
            if pages
            else "Nguồn chưa xác định trang PDF"
        )

    @staticmethod
    def _quality_text(response):
        caveats = ""
        if any(c.provenance_level == "page" for c in response.citations):
            caveats += "Dẫn nguồn ở cấp trang, chưa xác định ô/bbox. "
        if "reporting_scope_unresolved" in response.caveats:
            caveats += "Phạm vi báo cáo chưa được xác nhận. "
        reviews = {v.status for f in response.facts for v in f.source_review.matches}
        if response.parsed.intent == "evidence_explanation" and reviews:
            labels = {
                "value_row_verified": "đã đối chiếu giá trị/dòng với PDF",
                "page_resolved": "đã xác định trang nguồn",
                "unverified": "chưa đối chiếu giá trị với PDF",
                "source_inconsistent": "nguồn có mâu thuẫn",
                "source_missing": "thiếu nguồn",
            }
            caveats += "Trạng thái nguồn: " + ", ".join(labels[r] for r in sorted(reviews)) + ". "
        return (
            caveats
            + "Có nguồn hoặc tính toán thành công chưa phải xác minh độc lập số liệu tài chính."
        )
