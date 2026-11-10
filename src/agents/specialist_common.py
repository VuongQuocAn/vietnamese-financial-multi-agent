"""Shared M5 evidence contracts and bounded grounding/Gateway functions.

Only provenance mechanics live here; each specialist owns its domain and prose.
"""

import json
import re
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, ValidationError, model_serializer

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
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from ..tools.financial_calculator import FinancialCalculationResponse
from .contracts import RiskSignal
from .planner_contracts import PlannerLLMMetadata

ClaimKind = Literal["fact", "approved_metric", "supported_interpretation"]


class SpecialistEvidence(FinancialModel):
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


class SpecialistCandidate(FinancialModel):
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
    analysis_premises: list[str] = Field(default_factory=list, max_length=16)
    status: Literal["candidate", "insufficient_evidence"] = "candidate"
    financial_fact_verified: Literal[False] = False

    @model_serializer(mode="wrap")
    def serialize_candidate(self, handler):
        wire = handler(self)
        if not wire.get("analysis_premises"):
            wire.pop("analysis_premises", None)
        return wire


class AnalysisProposal(FinancialModel):
    statement: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=16)
    limitations: list[str] = Field(default_factory=list, max_length=8)


class SpecialistTrace(FinancialModel):
    stage: Literal["selection", "generation", "grounding"]
    outcome: str
    evidence_id: str | None = None
    proposal_index: int | None = None
    reasons: list[str] = Field(default_factory=list)


class SpecialistResult(FinancialModel):
    version: Literal[
        "profitability_specialist_v1",
        "liquidity_leverage_specialist_v1",
        "cash_flow_earnings_quality_specialist_v1",
    ] = "profitability_specialist_v1"
    role: Literal["profitability", "liquidity_and_leverage", "cash_flow_and_earnings_quality"] = (
        "profitability"
    )
    question: str
    upstream_status: Literal["completed", "partial", "blocked", "failed"]
    candidates: list[SpecialistCandidate] = Field(default_factory=list)
    supporting_evidence: list[SpecialistEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    status: Literal["generated", "partial", "abstained", "failed"] = "abstained"
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    raw_output: Any = None
    trace: list[SpecialistTrace] = Field(default_factory=list)
    latency_ms: float = 0.0
    financial_fact_verified: Literal[False] = False


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


def select_evidence(
    upstream, result, *, item_labels, metric_labels, period_roles, balance_sheet=False
):
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
        if record.canonical_item_id not in item_labels:
            continue
        if (
            bundle.claim_fact_references is not None
            and fact.reference not in bundle.claim_fact_references
        ):
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
            SpecialistEvidence(
                evidence_id="",
                kind="fact",
                reference=fact.reference,
                company_id=record.company_id,
                document_id=record.document_id,
                snapshot_id=record.snapshot_id,
                period=record.context.period,
                label=item_labels[record.canonical_item_id],
                canonical_item_id=record.canonical_item_id,
                value=str(record.value.normalized_value),
                unit=record.value.unit,
                scale=str(record.context.scale),
                citations=fact.citations,
                caveats=sorted(set(caveats)),
            )
        )
    for calc in bundle.calculations:
        if calc.formula_id not in metric_labels:
            continue
        error = _metric_error(calc, bundle)
        if calc.trace and any(o.observation in rejected_observations for o in calc.trace.operands):
            error = "metric_operand_conflicted"
        if error:
            result.missing_evidence.append(error)
            result.trace.append(
                SpecialistTrace(stage="selection", outcome="excluded", reasons=[error])
            )
            continue
        periods = {o.role: o.context.period for o in calc.trace.operands}
        period = periods[period_roles[calc.formula_id]]
        result.supporting_evidence.append(
            SpecialistEvidence(
                evidence_id="",
                kind="metric",
                reference=RetrievalReference(kind="metric", record_id=calc.metric_id),
                company_id=calc.trace.operands[0].company_id,
                document_id=calc.document_id,
                snapshot_id=calc.snapshot_id,
                period=period,
                operand_periods=periods,
                label=metric_labels[calc.formula_id],
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
            e
            for e in result.supporting_evidence
            if (e.period[:4] if balance_sheet else e.period) in years
        ]
    # Planner permits 32 indicators and 8 approved metrics. A larger digest must
    # not discard every independently usable source.
    if len(result.supporting_evidence) > 40:
        result.missing_evidence.append("evidence_digest_limit_exceeded")
        result.supporting_evidence = result.supporting_evidence[:40]
    for index, evidence in enumerate(result.supporting_evidence, 1):
        evidence.evidence_id = f"E{index:03d}"


def with_assignment(prompt, upstream):
    """Scope a projected call without rewriting the original user question."""
    if upstream.evidence_bundle.claim_fact_references is None:
        return prompt
    query = upstream.final_plan_state.query
    reasoning = any(c.startswith("PLANNER_TASK:") for c in upstream.evidence_bundle.limitations)
    if reasoning:
        prompt = dict(
            prompt,
            analysis_schema=AnalysisProposal.model_json_schema(),
            instruction=prompt["instruction"]
            + (
                " NHIỆM VỤ PHÂN TÍCH: đọc PLANNER_TASK và PRIOR_AGENT_RESULTS trong limitations. "
                "Ngoài claims số liệu theo schema cũ, thêm analyses:[{statement,evidence_ids,limitations}] "
                "để diễn giải quan hệ giữa evidence được giao, trả lời mục tiêu thực tế. "
                "Statement do bạn suy luận, không bị giới hạn vào grammar mẫu số học cũ; "
                "mọi tiền đề phải có evidence_ids, không tính ratio mới hoặc đoán nguyên nhân. "
                "analyses.statement chỉ là diễn giải KHÔNG chứa chữ số hoặc tỷ lệ; số và kỳ đã có "
                "trong numeric claims, dùng 'trong kỳ này' khi cần. "
                "Ưu tiên một analysis ngắn trực tiếp đáp ứng task; không lặp các giới hạn thành nhiều claims. "
                "limitations tối đa 8 ý; backend đã giữ source caveats nên không chép toàn bộ flags vào đây. "
                "statement chỉ mô tả quan hệ có căn cứ giữa những facts được giao. Điều chưa thể kết luận "
                "hoặc nguyên nhân chưa biết ghi riêng trong limitations, không ghép thành claim thiếu nguồn. "
                "Không biến việc agent này chưa được giao một chỉ tiêu thành claim rằng toàn hệ thống thiếu "
                "chỉ tiêu đó. Nếu task vượt phạm vi evidence được giao, ghi giới hạn trong missing_information; "
                "giữ facts hợp lệ, không tạo analysis kết luận về toàn câu hỏi từ chỉ một chỉ tiêu. "
                "Nhận định là candidate_pending_M6, không tự phê duyệt. Thiếu evidence nêu missing_information. "
                "Không dùng prior agent claim làm nguồn thay cho evidence gốc."
            ),
        )
    return dict(
        prompt,
        orchestration_assignment=dict(
            roles=upstream.final_plan_state.specialist_roles,
            assigned_fact_targets=query.required_indicators,
            assigned_formula_targets=query.requested_formula_ids,
        ),
        instruction=prompt["instruction"]
        + (
            " CÂU HỎI GỐC được giữ đầy đủ cho context; bạn CHỈ thực hiện targets trong "
            "orchestration_assignment bằng evidence digest được giao. Các targets thuộc "
            "Specialist khác KHÔNG phải missing_information của bạn. Supporting operands "
            "của metric không phải factual claims độc lập. Không báo thiếu dữ liệu cho "
            "phân tích sâu, so sánh kỳ khác hoặc ratio không được giao. Giữ caveats nguồn "
            "nhưng không tự mở rộng workload."
        ),
    )


def _numeric_proposals(evidence):
    return [
        dict(
            evidence_id=e.evidence_id,
            kind="approved_metric" if e.calculation else "fact",
            meaning="metric_value" if e.calculation else "fact_value",
            period=e.period,
        )
        for e in evidence
    ]


def generate_candidates(
    *, gateway, model, result, prompt, proposal_type, render, prefix, deterministic=False
):
    if deterministic:
        # Existing typed numeric renderers; no model, interpretation or new calculation.
        result.llm.status = "deterministic"
        payload = {
            "claims": _numeric_proposals(result.supporting_evidence),
            "missing_information": [],
        }
    else:
        executions = [
            dict(
                evidence_id=e.evidence_id,
                status=e.calculation.status,
                formula_id=e.calculation.formula_id,
                calculation_eligible=e.calculation.evidence.closure.calculation_eligible,
                formula_approval=e.calculation.trace.approval.model_dump(mode="json"),
                verification_status="candidate_pending_M6",
            )
            for e in result.supporting_evidence
            if e.calculation
        ]
        if executions:
            prompt = dict(
                prompt,
                current_metric_executions=executions,
                instruction=prompt["instruction"]
                + (
                    " current_metric_executions là trạng thái M4 hiện tại của evidence đã được "
                    "kiểm tra và giao. status=computed cùng calculation_eligible=true cho phép "
                    "đề xuất numeric metric_value, chưa phải claim ACCEPT. Các caveats nguồn "
                    "được giữ nguyên, có thể là annotations lịch sử; không suy lại rằng metric "
                    "chưa approved chỉ từ annotation cũ khi current execution đã computed. "
                    "Không bỏ numeric candidate hợp lệ vì thiếu điều kiện diễn giải. "
                    "M6 vẫn kiểm chứng độc lập mọi candidate."
                ),
            )
        request = LLMRequest(
            contract_version="llm_gateway_v1",
            request_id=prefix + "-" + uuid4().hex,
            model=model,
            messages=[
                Message(role="system", content=json.dumps(prompt, ensure_ascii=False)),
                Message(role="user", content=result.question),
            ],
            generation=GenerationParameters(temperature=0.0, max_output_tokens=2500),
            output_spec=OutputSpec(format="json"),
            constraints=RequestConstraints(timeout_seconds=60.0),
        )
        result.llm.calls, result.llm.model = 1, model
        actual_events = getattr(gateway, "events", None)
        events_before = len(actual_events) if isinstance(actual_events, list) else None
        call_start = perf_counter()
        response = gateway.generate(request)
        if events_before is not None:
            result.llm.calls = len(actual_events) - events_before
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
            result.trace.append(
                SpecialistTrace(
                    stage="generation", outcome="excluded", reasons=["gateway_response_failed"]
                )
            )
            payload = {
                "claims": _numeric_proposals(result.supporting_evidence),
                "missing_information": [],
            }
        else:
            payload = result.raw_output
    if (
        set(payload)
        not in ({"claims", "missing_information"}, {"claims", "missing_information", "analyses"})
        or not isinstance(payload["claims"], list)
        or len(payload["claims"]) > 32
    ):
        result.trace.append(
            SpecialistTrace(
                stage="generation", outcome="excluded", reasons=["invalid_proposal_envelope"]
            )
        )
        # Only local, selected source facts are rendered; malformed model text
        # supplies no claim. These candidates still require ordinary native M6.
        payload = {
            "claims": _numeric_proposals(result.supporting_evidence),
            "missing_information": [],
        }
    missing = payload["missing_information"]
    if not isinstance(missing, list) or any(not isinstance(m, str) for m in missing):
        result.trace.append(
            SpecialistTrace(
                stage="generation", outcome="excluded", reasons=["invalid_missing_information"]
            )
        )
        missing = []
    if not deterministic and not payload["claims"] and not missing and result.supporting_evidence:
        # An unexplained empty model response supplies no rejection reason. Reuse
        # the existing numeric pathway only after source/metric selection gates;
        # keep the original model payload and send all candidates through M6.
        payload = dict(payload, claims=_numeric_proposals(result.supporting_evidence))
        result.trace.append(
            SpecialistTrace(
                stage="generation",
                outcome="deterministic_numeric_fallback",
                reasons=["empty_model_claims_without_missing_information"],
            )
        )
    # Model limitations are untrusted annotations, never financial claims.
    result.missing_evidence.extend(missing)
    evidence_by_id = {e.evidence_id: e for e in result.supporting_evidence}
    analyses = payload.get("analyses", [])
    if not isinstance(analyses, list) or len(analyses) > 8:
        result.trace.append(
            SpecialistTrace(
                stage="generation", outcome="excluded", reasons=["invalid_analysis_envelope"]
            )
        )
        analyses = []
    for raw in analyses:
        try:
            analysis = AnalysisProposal.model_validate(raw)
            if set(analysis.evidence_ids) - evidence_by_id.keys():
                raise ValueError("analysis_unknown_evidence")
            sources = [evidence_by_id[key] for key in dict.fromkeys(analysis.evidence_ids)]
            if re.search(r"\d|%", analysis.statement) or any(s.calculation for s in sources):
                result.trace.append(
                    SpecialistTrace(
                        stage="grounding",
                        outcome="excluded",
                        reasons=["analysis_requires_number_free_fact_premises"],
                    )
                )
                continue
            owner = sources[0]
            if any(
                (s.company_id, s.document_id, s.snapshot_id, s.period)
                != (owner.company_id, owner.document_id, owner.snapshot_id, owner.period)
                for s in sources
            ):
                raise ValueError("analysis_context_mismatch")
            result.candidates.append(
                SpecialistCandidate(
                    candidate_id=prefix + "-analysis-" + uuid4().hex,
                    kind="supported_interpretation",
                    content=analysis.statement,
                    company_id=owner.company_id,
                    document_id=owner.document_id,
                    snapshot_id=owner.snapshot_id,
                    period=owner.period,
                    fact_references=_unique([s.reference for s in sources if not s.calculation]),
                    metric_ids=[s.calculation.metric_id for s in sources if s.calculation],
                    supporting_evidence_ids=analysis.evidence_ids,
                    analysis_premises=[
                        f"{s.label} kỳ {s.period} là {_number(s.value)} {s.unit}"
                        + (f" (hệ số đơn vị {s.scale})" if s.scale != "1" else "")
                        + "."
                        for s in sources
                    ],
                    citations=_unique([c for s in sources for c in s.citations]),
                    caveats=sorted(
                        set(analysis.limitations + [c for s in sources for c in s.caveats])
                    ),
                )
            )
        except (ValidationError, ValueError) as error:
            result.trace.append(
                SpecialistTrace(
                    stage="grounding",
                    outcome="excluded",
                    reasons=[
                        "invalid_analysis_schema"
                        if isinstance(error, ValidationError)
                        else str(error)
                    ],
                )
            )
    seen = set()
    for index, raw in enumerate(payload["claims"]):
        try:
            proposal = proposal_type.model_validate(raw)
            if proposal.evidence_id not in evidence_by_id:
                raise ValueError("unknown_evidence_id")
            evidence = evidence_by_id[proposal.evidence_id]
            content = render(proposal, evidence)
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
                SpecialistCandidate(
                    candidate_id=prefix + "-" + uuid4().hex,
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
            reason = "invalid_claim_schema" if isinstance(error, ValidationError) else str(error)
            result.trace.append(
                SpecialistTrace(
                    stage="grounding",
                    outcome="excluded",
                    proposal_index=index,
                    reasons=[reason],
                )
            )
    rejected = any(t.outcome == "excluded" for t in result.trace)
    if any(
        reason
        in {
            "gateway_response_failed",
            "invalid_proposal_envelope",
            "invalid_missing_information",
            "invalid_analysis_envelope",
        }
        for trace in result.trace
        for reason in trace.reasons
    ):
        result.limitations.append("specialist_processing_failure")
    result.status = (
        "partial"
        if result.candidates
        and (result.upstream_status == "partial" or result.missing_evidence or rejected)
        else "generated"
        if result.candidates
        else "abstained"
    )
