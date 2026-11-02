"""M5 candidate generation; bounded arithmetic prose, never M6 claim verification."""

import json
import re
import unicodedata
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    ModelIdentity,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_gateway import SharedLLMGateway
from ..evidence.graph import graph_id
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from ..tools.financial_calculator import FinancialCalculationResponse
from ..tools.question_understanding import normalize
from .contracts import SPECIALIST_BOUNDARIES, RiskSignal
from .planner_contracts import PlannerLLMMetadata
from .supervisor import SupervisorResult

ITEM_LABELS = {
    "b02.net_revenue": "Doanh thu thuần",
    "b02.cost_of_sales": "Giá vốn hàng bán",
    "b02.gross_profit": "Lợi nhuận gộp",
    "b02.profit_before_tax": "Lợi nhuận trước thuế",
    "b02.profit_after_tax": "Lợi nhuận sau thuế",
}
METRIC_LABELS = {"gross_margin": "Biên lợi nhuận gộp", "revenue_yoy": "Tăng trưởng doanh thu"}
ClaimKind = Literal["fact", "approved_metric", "supported_interpretation"]
Meaning = Literal["fact_value", "metric_value", "gross_profit_per_100_revenue", "revenue_change"]


class ProfitabilityEvidence(FinancialModel):
    evidence_id: str
    kind: Literal["fact", "metric"]
    reference: RetrievalReference
    company_id: str
    document_id: str
    snapshot_id: str
    period: str
    operand_periods: dict[str, str] = Field(default_factory=dict)
    label: str
    value: str
    unit: str
    scale: str = "1"
    canonical_item_id: str | None = None
    citations: list[EvidenceCitation]
    caveats: list[str]
    # Full accepted execution includes formula/version, operands, lineage and reviews.
    calculation: FinancialCalculationResponse | None = None


class ProfitabilityCandidate(FinancialModel):
    """Temporary M5 contract; M6-01 owns the eventual CandidateClaim."""

    candidate_id: str
    kind: ClaimKind
    content: str
    company_id: str
    document_id: str
    snapshot_id: str
    period: str
    fact_references: list[RetrievalReference] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str]
    citations: list[EvidenceCitation]
    calculation: FinancialCalculationResponse | None = None
    caveats: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    status: Literal["candidate", "insufficient_evidence"] = "candidate"
    financial_fact_verified: Literal[False] = False


class SpecialistTrace(FinancialModel):
    stage: Literal["selection", "generation", "grounding"]
    outcome: str
    evidence_id: str | None = None
    proposal_index: int | None = None
    reasons: list[str] = Field(default_factory=list)


class SpecialistResult(FinancialModel):
    version: Literal["profitability_specialist_v1"] = "profitability_specialist_v1"
    role: Literal["profitability"] = "profitability"
    question: str
    upstream_status: Literal["completed", "partial", "blocked", "failed"]
    candidates: list[ProfitabilityCandidate] = Field(default_factory=list)
    supporting_evidence: list[ProfitabilityEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    status: Literal["generated", "partial", "abstained", "failed"] = "abstained"
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    raw_output: Any = None
    trace: list[SpecialistTrace] = Field(default_factory=list)
    latency_ms: float = 0.0
    financial_fact_verified: Literal[False] = False


class ProfitabilityProposal(FinancialModel):
    evidence_id: str
    kind: ClaimKind
    meaning: Meaning
    period: str
    # Facts/metrics may request exact backend rendering. Interpretations require prose.
    statement: str | None = Field(default=None, max_length=700)


def _unique(values):
    return list({v.model_dump_json(): v for v in values}.values())


def _number(value):
    # Display only; never calculate a new financial metric or silently change scale.
    return format(Decimal(value), ",f").translate(str.maketrans({",": ".", ".": ","}))


def _citations_valid(citations, document, snapshot, sources, bundle):
    return bool(citations) and all(
        c in bundle.citations
        and c.document_id == c.source.document_id == document
        and c.snapshot_id == c.source.snapshot_id == snapshot
        and c.source in sources
        and c.source.source_key() is not None
        and c.anchor_id == graph_id("anchor", c.source.source_key())
        and c.source.reference is not None
        and c.pdf_page == c.source.reference.anchor.page.page
        and c.provenance_level == c.source.reference.provenance_level
        for c in citations
    )


def _fact_error(match, bundle):
    fact = match.record
    decisions = [q.decision for q in fact.quality_context if q.task_type == "direct_qa"]
    if (
        not fact.company_id
        or not fact.context.period
        or not fact.context.scale
        or not fact.value.unit
        or fact.value.status != "resolved"
        or fact.value.normalized_value is None
        or match.reference.observation != fact.observation_identity()
    ):
        return "fact_context_or_identity_missing"
    if (
        match.display_status == "blocked"
        or not decisions
        or any(d in {"insufficient", "conflicted"} for d in decisions)
        or match.source_review.status != "found"
        or not match.source_review.matches
        or any(
            v.observation != fact.observation_identity()
            or v.original_sources != fact.sources
            or v.status in {"source_inconsistent", "source_missing"}
            for v in match.source_review.matches
        )
    ):
        return "fact_conflicted_or_unusable"
    if not _citations_valid(
        match.citations, fact.document_id, fact.snapshot_id, fact.sources, bundle
    ):
        return "fact_citations_missing_or_mismatched"
    return None


def _metric_error(calc, bundle):
    evidence, trace = calc.evidence, calc.trace
    if (
        calc.status != "computed"
        or calc.result is None
        or evidence is None
        or trace is None
        or not evidence.closure.calculation_eligible
        or evidence.closure.status != "closed"
        or evidence.reviewed_lineage.status != "found"
        or evidence.reviewed_lineage.lineage is None
        or evidence.reviewed_lineage.lineage.completeness != "complete"
    ):
        return "metric_trace_or_lineage_incomplete"
    if (
        calc.metric_id != evidence.record.metric_id
        or calc.document_id != evidence.record.request.document_id
        or calc.snapshot_id != evidence.record.request.snapshot_id
        or calc.formula_id != evidence.record.definition.name
        or calc.formula_id != trace.formula.formula_id
        or calc.formula_id != trace.approval.formula_id
        or calc.formula_version != trace.formula.version
        or calc.formula_version != trace.approval.version
        or calc.formula_digest != trace.formula.definition_digest()
        or calc.formula_digest != trace.approval.definition_sha256
    ):
        return "metric_formula_binding_mismatch"
    if (
        evidence.closure.metric_id != calc.metric_id
        or evidence.reviewed_lineage.lineage.metric_id != calc.metric_id
        or evidence.reviewed_lineage.lineage.request != evidence.record.request
        or Decimal(calc.result) != Decimal(trace.scaled_value).quantize(Decimal("0.01"))
    ):
        return "metric_result_or_lineage_binding_mismatch"
    operands = trace.operands
    if len(operands) != 2 or len({o.role for o in operands}) != 2:
        return "metric_operand_missing"
    for operand in operands:
        facts = [f for f in bundle.facts if f.reference.observation == operand.observation]
        bindings = [b for b in evidence.record.operands if b.role == operand.role]
        if (
            len(facts) != 1
            or len(bindings) != 1
            or bindings[0].observation != operand.observation
            or bindings[0].source_fact_node_id != operand.source_fact_node_id
            or evidence.record.request.operand_periods.get(operand.role) != operand.context.period
            or _fact_error(facts[0], bundle)
            or operand.observation.document_id != calc.document_id
            or operand.observation.snapshot_id != calc.snapshot_id
            or operand.value != str(facts[0].record.value.normalized_value)
            or operand.unit != facts[0].record.value.unit
            or operand.context != facts[0].record.context
            or operand.company_id != facts[0].record.company_id
        ):
            return "metric_operand_binding_mismatch"
    if len({o.company_id for o in operands}) != 1:
        return "metric_company_mismatch"
    if not _citations_valid(
        evidence.citations,
        calc.document_id,
        calc.snapshot_id,
        [
            s
            for f in bundle.facts
            if f.reference.observation in {o.observation for o in operands}
            for s in f.record.sources
        ],
        bundle,
    ):
        return "metric_citations_missing_or_mismatched"
    return None


# Full-match semantic grammar, NOT a blacklist: no extra clauses, invented causes,
# industry judgments, periods, numbers or citations can survive. Gemini chooses the
# proposition and writes Vietnamese within these bounded arithmetic paraphrases.
GROSS_PROSE = (
    r"(?:trong ky \{period\},? )?"
    r"(?:cu|voi moi|tren moi) 100 dong doanh thu thuan "
    r"(?:tuong ung|tao ra|doanh nghiep thu duoc)(?: khoang)? "
    r"\{value\} dong loi nhuan gop[.]?"
)
YOY_PROSE = (
    r"(?:trong cung (?:mot )?bao cao,? )?doanh thu thuan "
    r"(?:ky|nam) \{period\} \{direction\} \{value\}% "
    r"so voi (?:ky|nam) \{prior_period\}[.]?"
)


def _render(proposal, evidence):
    if proposal.period != evidence.period:
        raise ValueError("wrong_period")
    value = _number(evidence.value)
    if proposal.meaning == "fact_value" and proposal.kind == evidence.kind == "fact":
        text = f"{evidence.label} kỳ {evidence.period} là {value} {evidence.unit}"
        if evidence.scale != "1":
            text += f" (hệ số đơn vị {evidence.scale})"
        text += "."
    elif (
        proposal.meaning == "metric_value"
        and proposal.kind == "approved_metric"
        and evidence.calculation
    ):
        text = f"{evidence.label} kỳ {evidence.period} đạt {value}%."
    elif proposal.kind == "supported_interpretation" and evidence.calculation:
        calc = evidence.calculation
        statement = unicodedata.normalize("NFC", proposal.statement or "")
        if proposal.meaning == "gross_profit_per_100_revenue" and calc.formula_id == "gross_margin":
            pattern = GROSS_PROSE
        elif proposal.meaning == "revenue_change" and calc.formula_id == "revenue_yoy":
            pattern = YOY_PROSE
        else:
            raise ValueError("unsupported_interpretation")
        replacements = {"period": evidence.period, "value": value}
        if proposal.meaning == "revenue_change":
            replacements.update(
                value=_number(abs(Decimal(evidence.value))),
                direction="tăng"
                if Decimal(evidence.value) > 0
                else "giảm"
                if Decimal(evidence.value) < 0
                else "không đổi ở mức",
                prior_period=evidence.operand_periods["prior_revenue"],
            )
        # Both placeholders and exact accepted numbers are safe. A literal value
        # mismatch cannot match the grammar and is never repaired by guessing.
        for key, replacement in replacements.items():
            options = ["{" + key + "}", replacement]
            if key == "value":
                options.append(
                    str(abs(Decimal(evidence.value)))
                    if proposal.meaning == "revenue_change"
                    else evidence.value
                )
            alternatives = "|".join(
                re.escape(normalize(v) if key == "direction" and v == replacement else v)
                for v in options
            )
            pattern = pattern.replace(re.escape("{" + key + "}"), f"(?P<{key}>{alternatives})")
        folded = unicodedata.normalize("NFD", statement.casefold().replace("đ", "d"))
        folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
        matched = re.fullmatch(pattern, folded)
        if not matched:
            raise ValueError("unsupported_or_numeric_prose")
        text = statement
        for key in sorted(replacements, key=lambda k: matched.start(k), reverse=True):
            start, end = matched.span(key)
            if start >= 0:
                text = text[:start] + replacements[key] + text[end:]
        return text
    else:
        raise ValueError("kind_or_meaning_mismatch")
    if proposal.statement not in (None, text):
        # A structured fact/metric lets the backend render exact values; never fix
        # a conflicting Gemini numeric statement by guessing its intended number.
        raise ValueError("fact_or_metric_text_mismatch")
    return text


class ProfitabilitySpecialist:
    boundary = next(b for b in SPECIALIST_BOUNDARIES if b.role == "profitability")

    def __init__(self, gateway: SharedLLMGateway, *, model: ModelIdentity | None = None):
        self._gateway = gateway
        self._model = model or ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)

    def _select(self, upstream, result):
        bundle = upstream.evidence_bundle

        # Conflicts within the same observation or same financial context block all
        # variants, rather than picking the first record.
        def key(f):
            r = f.record
            return (
                r.document_id,
                r.snapshot_id,
                r.company_id,
                r.canonical_item_id,
                (
                    r.context.period,
                    r.context.period_type,
                    r.context.reporting_scope,
                    r.context.currency,
                    str(r.context.scale),
                ),
                r.value.unit,
            )

        groups = {}
        for fact in bundle.facts:
            groups.setdefault(key(fact), set()).add(fact.record.model_dump_json())
        rejected_observations = set()
        for fact in bundle.facts:
            record = fact.record
            if record.canonical_item_id not in ITEM_LABELS:
                continue
            error = _fact_error(fact, bundle)
            if len(groups[key(fact)]) > 1:
                error = "conflicting_fact_variants"
            if error:
                rejected_observations.add(fact.reference.observation)
                result.missing_evidence.append(error)
                result.trace.append(
                    SpecialistTrace(stage="selection", outcome="excluded", reasons=[error])
                )
                continue
            caveats = [
                *fact.issues,
                *fact.reporting_scope.reasons,
                *[c for view in fact.source_review.matches for c in view.quality_caveats],
                *[i.code for i in record.resolution_issues],
                *[c for q in record.quality_context for c in [q.decision, *q.caveats]],
                *[c for cite in fact.citations for c in cite.limitations],
            ]
            result.supporting_evidence.append(
                ProfitabilityEvidence(
                    evidence_id="",
                    kind="fact",
                    reference=fact.reference,
                    company_id=record.company_id,
                    document_id=record.document_id,
                    snapshot_id=record.snapshot_id,
                    period=record.context.period,
                    label=ITEM_LABELS[record.canonical_item_id],
                    canonical_item_id=record.canonical_item_id,
                    value=str(record.value.normalized_value),
                    unit=record.value.unit,
                    scale=str(record.context.scale),
                    citations=fact.citations,
                    caveats=sorted(set(caveats)),
                )
            )
        for calc in bundle.calculations:
            if calc.formula_id not in METRIC_LABELS:
                continue
            error = _metric_error(calc, bundle)
            if calc.trace and any(
                o.observation in rejected_observations for o in calc.trace.operands
            ):
                error = "metric_operand_conflicted"
            if error:
                result.missing_evidence.append(error)
                result.trace.append(
                    SpecialistTrace(stage="selection", outcome="excluded", reasons=[error])
                )
                continue
            periods = {o.role: o.context.period for o in calc.trace.operands}
            period = (
                periods["current_revenue"]
                if calc.formula_id == "revenue_yoy"
                else periods["revenue"]
            )
            result.supporting_evidence.append(
                ProfitabilityEvidence(
                    evidence_id="",
                    kind="metric",
                    reference=RetrievalReference(kind="metric", record_id=calc.metric_id),
                    company_id=calc.trace.operands[0].company_id,
                    document_id=calc.document_id,
                    snapshot_id=calc.snapshot_id,
                    period=period,
                    operand_periods=periods,
                    label=METRIC_LABELS[calc.formula_id],
                    value=calc.result,
                    unit="percent",
                    citations=calc.evidence.citations,
                    caveats=sorted(
                        set(
                            calc.caveats
                            + [c for cite in calc.evidence.citations for c in cite.limitations]
                        )
                    ),
                    calculation=calc,
                )
            )
        result.supporting_evidence = _unique(result.supporting_evidence)
        years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", result.question))
        if years:
            result.supporting_evidence = [
                e for e in result.supporting_evidence if e.period in years
            ]
        if len(result.supporting_evidence) > 24:
            result.missing_evidence.append("evidence_digest_limit_exceeded")
            result.supporting_evidence = []
        for index, evidence in enumerate(result.supporting_evidence, 1):
            evidence.evidence_id = f"E{index:03d}"

    def _prompt(self, result):
        digest = []
        for evidence in result.supporting_evidence:
            item = evidence.model_dump(exclude={"citations", "calculation", "reference"})
            if evidence.calculation:
                calc = evidence.calculation
                item.update(
                    formula_id=calc.formula_id,
                    formula_version=calc.formula_version,
                    expression=calc.trace.formula.expression,
                    operands=[
                        dict(role=o.role, value=o.value, unit=o.unit, period=o.context.period)
                        for o in calc.trace.operands
                    ],
                )
            digest.append(item)
        return {
            "instruction": (
                "Bạn là Profitability Specialist. Phân tích câu hỏi và chỉ chọn evidence liên quan. "
                "Xuất JSON {claims: [...], missing_information: [string]}. Mỗi claim theo schema. "
                "fact/fact_value và approved_metric/metric_value: statement=null để backend render "
                "số chính xác. Không viết citations hoặc IDs ngoài evidence_id input. "
                "Nếu metric phù hợp, PHẢI thêm supported_interpretation ngoài metric_value. "
                "Diễn giải bằng tiếng Việt trong NGỮ PHÁP SỐ HỌC GIỚI HẠN sau, ưu tiên giữ literal "
                "{period}, {value}, {direction}, {prior_period}; backend thay từ evidence. "
                "gross_profit_per_100_revenue: [Trong kỳ {period}, ] + (cứ|với mỗi|trên mỗi) "
                "100 đồng doanh thu thuần + (tương ứng|tạo ra|doanh nghiệp thu được) + [khoảng ] "
                "+ {value} đồng lợi nhuận gộp. revenue_change: [Trong cùng báo cáo, ] "
                "+ Doanh thu thuần kỳ {period} {direction} {value}% so với kỳ {prior_period}. "
                "Các dấu [] biểu thị thành phần tùy chọn, không in dấu ngoặc. "
                "Chọn cách diễn đạt phù hợp, viết thành câu hoàn chỉnh. Không thêm mệnh đề khác. "
                "Ví dụ câu HOÀN CHỈNH hợp lệ: 'Trong kỳ {period}, với mỗi 100 đồng doanh thu "
                "thuần tương ứng khoảng {value} đồng lợi nhuận gộp.' Chỉ chọn MỘT động từ, "
                "không ghép 'tạo ra doanh nghiệp thu được'. Có thể dùng số thực từ evidence "
                "nhưng phải khớp chính xác. Với câu hỏi nhiều chỉ tiêu, MỖI chỉ tiêu có "
                "evidence phải có fact candidate. Nhánh doanh thu thiếu/conflicted KHÔNG chặn "
                "các facts giá vốn và lợi nhuận gộp độc lập đang có trong digest. "
                "Không nhận xét cao/thấp/tốt/xấu, so ngành, nguyên nhân, hoặc ROE/ROA/NPM "
                "chưa approved. Không tính mới, không comparison liên tài liệu D03-B10. "
                "Thiếu dữ liệu ghi missing_information; không biến thành financial claim. "
                "Không tự xác minh hoặc phê duyệt claims."
            ),
            "schema": ProfitabilityProposal.model_json_schema(),
            "boundary": self.boundary.model_dump(),
            "evidence": digest,
            "upstream_status": result.upstream_status,
            "missing_evidence": result.missing_evidence,
            "limitations": result.limitations,
        }

    def analyze(self, *, question: str, supervisor_result: SupervisorResult) -> SpecialistResult:
        start = perf_counter()
        upstream = SupervisorResult.model_validate_json(supervisor_result.model_dump_json())
        result = SpecialistResult(
            question=question,
            upstream_status=upstream.status,
            risks=upstream.risk_signals,
            limitations=list(upstream.evidence_bundle.limitations),
            missing_evidence=list(upstream.evidence_bundle.missing_requirement_ids),
        )
        try:
            plan = upstream.final_plan_state
            if upstream.status in {"blocked", "failed"}:
                result.missing_evidence.append("upstream_" + upstream.status)
                return result
            if (plan and plan.query.cross_document_comparison) or any(
                r.code == "cross_document_compatibility_unresolved" and r.blocking
                for r in result.risks
            ):
                result.missing_evidence.append("D03-B10_cross_document_blocked")
                return result
            question_text = normalize(question)
            unsupported = re.findall(
                r"\b(?:roe|roa|net profit margin|operating margin|bien loi nhuan rong|bien loi nhuan hoat dong)\b",
                question_text,
            )
            result.missing_evidence.extend("unsupported_capability:" + name for name in unsupported)
            independent = re.search(
                r"doanh thu thuan|gia von|loi nhuan gop|loi nhuan truoc thue|loi nhuan sau thue|gross margin|revenue yoy|tang truong doanh thu",
                question_text,
            )
            if not unsupported or independent:
                self._select(upstream, result)
            if not result.supporting_evidence:
                result.missing_evidence.append("no_usable_profitability_evidence")
            request = LLMRequest(
                contract_version="llm_gateway_v1",
                request_id="profitability-" + uuid4().hex,
                model=self._model,
                messages=[
                    Message(
                        role="system", content=json.dumps(self._prompt(result), ensure_ascii=False)
                    ),
                    Message(role="user", content=question),
                ],
                generation=GenerationParameters(temperature=0.0, max_output_tokens=2500),
                output_spec=OutputSpec(format="json"),
                constraints=RequestConstraints(timeout_seconds=60.0),
            )
            result.llm.calls, result.llm.model = 1, self._model
            call_start = perf_counter()
            response = self._gateway.generate(request)
            result.llm.latency_ms = (perf_counter() - call_start) * 1000
            result.llm.status, result.llm.usage, result.llm.cost = (
                response.status,
                response.usage,
                response.cost,
            )
            result.llm.provenance, result.llm.error = response.provenance, response.error
            if isinstance(response.output, JSONOutput):
                result.raw_output = response.output.payload
            if response.status != "success" or not isinstance(result.raw_output, dict):
                result.status = "failed"
                result.trace.append(
                    SpecialistTrace(
                        stage="generation", outcome="failed", reasons=["gateway_response_failed"]
                    )
                )
                return result
            payload = result.raw_output
            if (
                set(payload) != {"claims", "missing_information"}
                or not isinstance(payload["claims"], list)
                or len(payload["claims"]) > 32
            ):
                raise ValueError("invalid_proposal_envelope")
            missing = payload["missing_information"]
            if not isinstance(missing, list) or any(not isinstance(m, str) for m in missing):
                raise ValueError("invalid_missing_information")
            # Model limitations are untrusted annotations, never financial claims.
            result.missing_evidence.extend(missing)
            evidence_by_id = {e.evidence_id: e for e in result.supporting_evidence}
            seen = set()
            for index, raw in enumerate(payload["claims"]):
                try:
                    proposal = ProfitabilityProposal.model_validate(raw)
                    if proposal.evidence_id not in evidence_by_id:
                        raise ValueError("unknown_evidence_id")
                    evidence = evidence_by_id[proposal.evidence_id]
                    content = _render(proposal, evidence)
                    key = (proposal.evidence_id, proposal.meaning)
                    if key in seen:
                        raise ValueError("duplicate_proposition")
                    seen.add(key)
                    calc = evidence.calculation
                    facts = (
                        [
                            RetrievalReference(kind="fact", observation=o.observation)
                            for o in calc.trace.operands
                        ]
                        if calc
                        else [evidence.reference]
                    )
                    result.candidates.append(
                        ProfitabilityCandidate(
                            candidate_id="profitability-" + uuid4().hex,
                            kind=proposal.kind,
                            content=content,
                            company_id=evidence.company_id,
                            document_id=evidence.document_id,
                            snapshot_id=evidence.snapshot_id,
                            period=evidence.period,
                            fact_references=facts,
                            metric_ids=[calc.metric_id] if calc else [],
                            supporting_evidence_ids=[evidence.evidence_id],
                            citations=evidence.citations,
                            calculation=calc,
                            caveats=evidence.caveats,
                        )
                    )
                    result.trace.append(
                        SpecialistTrace(
                            stage="grounding",
                            outcome="candidate",
                            evidence_id=proposal.evidence_id,
                            proposal_index=index,
                        )
                    )
                except (ValidationError, ValueError) as error:
                    reason = (
                        "invalid_claim_schema" if isinstance(error, ValidationError) else str(error)
                    )
                    result.trace.append(
                        SpecialistTrace(
                            stage="grounding",
                            outcome="excluded",
                            proposal_index=index,
                            reasons=[reason],
                        )
                    )
            rejected = any(t.outcome == "excluded" for t in result.trace)
            result.status = (
                "partial"
                if result.candidates
                and (upstream.status == "partial" or result.missing_evidence or rejected)
                else "generated"
                if result.candidates
                else "abstained"
            )
        except (ValueError, ValidationError):
            result.status = "failed"
            result.trace.append(
                SpecialistTrace(
                    stage="generation", outcome="failed", reasons=["invalid_proposal_schema"]
                )
            )
        finally:
            result.missing_evidence = sorted(set(result.missing_evidence))
            result.latency_ms = (perf_counter() - start) * 1000
        return result
