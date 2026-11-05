"""Verified retrieval → deterministic sections → bounded permutation → local gate.

This module never runs M4/M5 or selects a filing/snapshot on behalf of a caller.
"""

import hashlib
import json
import re
from datetime import date
from uuid import uuid4

from pydantic import ValidationError

from ..accounting.item_mapping import ITEM_CATALOG
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_gateway import SharedLLMGateway
from ..tools.question_understanding import normalize
from ..verification.ledger import VerifiedClaimLedger
from ..verification.ledger_contracts import VerifiedClaimQuery
from .qa_composer import (
    LEDGER_LIMIT,
    SCOPE_CAVEAT,
    _assertion_signature,
    _citations,
    _segments,
    _unique,
    claim_scope,
)
from .qa_contracts import QAValidationResult
from .report_outline_contracts import (
    GroundedReportOutline,
    ReportClaimSlot,
    ReportOutlineProposal,
    ReportOutlineRequest,
    ReportOutlineScope,
    ReportOutlineSection,
)

# Catalog is presentation taxonomy, never a financial interpretation or formula.
SECTION_CATALOG = {
    "scope": (
        "Thông tin và phạm vi báo cáo",
        "Nêu đúng nguồn, snapshot, kỳ và phạm vi được xác nhận.",
    ),
    "overview": (
        "Tổng quan các số liệu đã xác minh",
        "Liên kết các claim đã xác minh; chưa viết kết luận tổng hợp.",
    ),
    "profitability": (
        "Khả năng sinh lời",
        "Trình bày nguyên văn các claim về kết quả kinh doanh đã xác minh.",
    ),
    "financial_position": (
        "Tình hình tài chính và cơ cấu nợ",
        "Trình bày các claim tài sản, nợ và vốn đã xác minh; không suy khả năng thanh toán.",
    ),
    "cash_flow": (
        "Dòng tiền và chất lượng lợi nhuận",
        "Trình bày các claim dòng tiền đã xác minh; chỉ dùng nhận định đã ACCEPT.",
    ),
    "verified_unclassified": (
        "Thông tin đã xác minh chưa phân nhóm",
        "Giữ nội dung đã xác minh khi chưa có ánh xạ chủ đề an toàn.",
    ),
    "limitations": (
        "Hạn chế dữ liệu và phạm vi diễn giải",
        "Giữ mọi caveat, giới hạn nguồn và phần chưa đủ bằng chứng.",
    ),
}
REPORT_TITLES = {
    "general_financial_analysis": "Dàn ý phân tích tài chính từ các claim đã xác minh",
    "profitability": "Dàn ý về khả năng sinh lời",
    "liquidity_and_leverage": "Dàn ý về tình hình tài chính và cơ cấu nợ",
    "cash_flow_and_earnings_quality": "Dàn ý về dòng tiền và chất lượng lợi nhuận",
    "focused_analysis": "Dàn ý theo các mục được yêu cầu",
}
DOMAINS = ["profitability", "financial_position", "cash_flow"]
DEFAULT_SECTIONS = {
    "general_financial_analysis": ["overview", *DOMAINS, "verified_unclassified"],
    "profitability": ["profitability"],
    "liquidity_and_leverage": ["financial_position"],
    "cash_flow_and_earnings_quality": ["cash_flow"],
    "focused_analysis": [],
}
FORMULA_SECTIONS = {
    "gross_margin": "profitability",
    "revenue_yoy": "profitability",
    "debt_to_assets": "financial_position",
}
ITEM_SECTIONS = {
    item.canonical_item_id: {
        "B01": "financial_position",
        "B02": "profitability",
        "B03": "cash_flow",
    }[item.statement_type]
    for item in ITEM_CATALOG
}
WRITER_LIMIT = "Dàn ý chỉ cho phép sử dụng nội dung ACCEPT trong từng slot; không tạo nhận định hoặc phép tính mới."


def classify_claim(entry):
    """Use typed metric identity first; never categorize a metric from its operands."""
    claim = entry.accepted_claim
    if claim.calculation:
        return FORMULA_SECTIONS.get(claim.calculation.formula_id, "verified_unclassified")
    targets = {
        ITEM_SECTIONS.get(e.canonical_item_id, "verified_unclassified")
        for e in claim.supporting_evidence
    }
    return next(iter(targets)) if len(targets) == 1 else "verified_unclassified"


def _target(entry):
    claim = entry.accepted_claim
    return (
        entry.identity.kind,
        claim.calculation.formula_id
        if claim.calculation
        else tuple(
            sorted(
                {
                    e.canonical_item_id or e.reference.model_dump_json()
                    for e in claim.supporting_evidence
                }
            )
        ),
    )


def _request_problem(request):
    if request.language != "vi":
        return "unsupported", ["language_vi_only"]
    text = normalize(request.title or "")
    for label, scope in (("hop nhat", "consolidated"), ("rieng", "separate")):
        if label in text and request.reporting_scope != scope:
            return "clarification_required", ["explicit_reporting_scope_binding_required"]
    if re.search(
        r"\b(?:roe|roa|ebitda|current ratio|quick ratio|cash ratio|debt to equity)\b", text
    ):
        return "unsupported", ["unsupported_metric_request"]
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", text))
    if len(years) > 1 or any(
        w in text
        for w in (
            "so sanh",
            "nhieu nam",
            "lien tai lieu",
            "cross-document",
            "multi-year",
            "xu huong nhieu",
        )
    ):
        return "unsupported", ["D03-B10_cross_document_or_multi_year_not_approved"]
    if any(
        w in text
        for w in (
            "tinh them",
            "tinh lai",
            "du bao",
            "nguyen nhan",
            "chung minh",
            "an toan",
            "tang truong manh",
        )
    ):
        return "unsupported", ["unsupported_analytical_objective"]
    missing = [
        key
        for key in ("company_id", "document_id", "snapshot_id", "period")
        if not getattr(request, key)
    ]
    if missing:
        return "clarification_required", missing
    try:
        if not re.fullmatch(r"[0-9]{4}", request.period):
            date.fromisoformat(request.period)
    except ValueError:
        return "unsupported", ["single_exact_period_required"]
    if years and years != {request.period[:4]}:
        return "clarification_required", ["title_period_mismatch"]
    if request.report_type == "focused_analysis" and not request.requested_sections:
        return "clarification_required", ["requested_sections"]
    return None


def _retrieval_valid(request, entries):
    seen = set()
    for entry in entries:
        identity, claim = entry.identity, entry.accepted_claim
        if (
            identity.verified_claim_id in seen
            or entry.verification_status != "verified"
            or entry.decision.decision != "ACCEPT"
        ):
            return False
        seen.add(identity.verified_claim_id)
        for field in ("company_id", "document_id", "snapshot_id", "period"):
            if getattr(identity, field) != getattr(request, field) or getattr(
                claim, field
            ) != getattr(identity, field):
                return False
        if identity.kind != claim.kind or not entry.citations:
            return False
        if any(
            (c.document_id, c.snapshot_id, c.source.document_id, c.source.snapshot_id)
            != (request.document_id, request.snapshot_id) * 2
            for c in entry.citations
        ):
            return False
        if any(
            (e.company_id, e.document_id, e.snapshot_id, e.period)
            != (request.company_id, request.document_id, request.snapshot_id, request.period)
            for e in claim.supporting_evidence
        ):
            return False
    return True


def _empty(request, status, reasons):
    return GroundedReportOutline(
        report_type=request.report_type,
        report_title=REPORT_TITLES[request.report_type],
        status=status,
        scope=ReportOutlineScope(
            **{
                k: getattr(request, k)
                for k in ("company_id", "document_id", "snapshot_id", "period")
            },
            requested_reporting_scope=request.reporting_scope,
        ),
        reasons=reasons,
        missing_information=reasons if status == "clarification_required" else [],
        limitations=[LEDGER_LIMIT, WRITER_LIMIT],
    )


def _slots(entries):
    kind = entries[0].identity.kind
    return [
        ReportClaimSlot(
            slot_id="slot:" + hashlib.sha256("|".join(s.verified_claim_ids).encode()).hexdigest(),
            verified_claim_ids=s.verified_claim_ids,
            accepted_content=s.content,
            claim_kind=kind,
            claim_context=s.context,
            citations=s.citations,
            caveats=s.caveats,
            limitations=s.limitations,
            suggested_role={
                "fact": "key_fact",
                "approved_metric": "approved_metric",
                "supported_interpretation": "verified_interpretation",
            }[kind],
        )
        for s in _segments(entries)
    ]


def _deterministic(request, retrieved):
    problem = _request_problem(request)
    if problem:
        return _empty(request, *problem)
    if not _retrieval_valid(request, retrieved):
        return _empty(request, "abstained", ["retrieval_context_or_source_mismatch"])
    requested = request.requested_sections or DEFAULT_SECTIONS[request.report_type]
    content_types = [s for s in requested if s not in ("scope", "limitations")]
    if not content_types:
        return _empty(request, "clarification_required", ["requested_content_sections"])
    groups, conflicts, scope_missing = {}, [], False
    for entry in sorted(retrieved, key=lambda e: e.identity.verified_claim_id):
        category = classify_claim(entry)
        if category not in content_types and "overview" not in content_types:
            continue
        if request.reporting_scope and claim_scope(entry) != request.reporting_scope:
            scope_missing = True
            continue
        groups.setdefault(_target(entry), []).append(entry)
    buckets = {s: [] for s in content_types}
    for entries in groups.values():
        if len({_assertion_signature(e) for e in entries}) > 1:
            conflicts.extend(e.identity.verified_claim_id for e in entries)
            continue
        category = classify_claim(entries[0])
        destination = category if category in buckets else "overview"
        buckets[destination].extend(_slots(entries))
    # Overview is an index of the other sections via their IDs, not duplicate financial slots.
    if "overview" in buckets and not buckets["overview"] and any(buckets.values()):
        overview_supported = True
    else:
        overview_supported = bool(buckets.get("overview"))
    supported = [s for s in content_types if buckets[s] or (s == "overview" and overview_supported)]
    missing = [s for s in content_types if s not in supported]
    # Default unclassified is optional when there is nothing unclassified to present.
    if not request.requested_sections and "verified_unclassified" in missing:
        missing.remove("verified_unclassified")
    if not supported:
        reason = (
            "conflicting_verified_claims"
            if conflicts
            else "requested_scope_unconfirmed"
            if scope_missing
            else "no_verified_support"
        )
        return _empty(
            request,
            "clarification_required" if conflicts or scope_missing else "abstained",
            [reason],
        )
    result = _empty(request, "partial" if missing or conflicts or scope_missing else "ready", [])
    result.missing_information = ["verified_claims:" + s for s in missing]
    result.reasons = (["conflicting_verified_claims"] if conflicts else []) + (
        ["requested_scope_unconfirmed"] if scope_missing else []
    )
    if conflicts:
        result.missing_information.append("resolve_conflicts:" + ",".join(sorted(conflicts)))
    selected_slots = [slot for s in content_types for slot in buckets[s]]
    result.used_verified_claim_ids = sorted(
        key for slot in selected_slots for key in slot.verified_claim_ids
    )
    result.citations = _citations(
        c for slot in sorted(selected_slots, key=lambda s: s.slot_id) for c in slot.citations
    )
    result.caveats = _unique(
        c for slot in sorted(selected_slots, key=lambda s: s.slot_id) for c in slot.caveats
    )
    result.limitations = _unique(
        [WRITER_LIMIT, LEDGER_LIMIT]
        + [v for slot in sorted(selected_slots, key=lambda s: s.slot_id) for v in slot.limitations]
    )
    scopes = {slot.claim_context.reporting_scope for slot in selected_slots}
    result.scope.reporting_scope = next(iter(scopes)) if len(scopes) == 1 else None
    if result.scope.reporting_scope is None:
        result.caveats = _unique(result.caveats + [SCOPE_CAVEAT])
    result.omitted_sections = [
        s for s in SECTION_CATALOG if s not in ("scope", "limitations") and s not in supported
    ]
    section_types = [
        "scope",
        *[s for s in content_types if s in supported or s in missing],
        "limitations",
    ]
    for index, section_type in enumerate(section_types, 1):
        slots = buckets.get(section_type, [])
        result.sections.append(
            ReportOutlineSection(
                section_id=section_type,
                section_type=section_type,
                title_vi=SECTION_CATALOG[section_type][0],
                purpose=SECTION_CATALOG[section_type][1],
                order=index,
                status="context"
                if section_type in ("scope", "limitations")
                else "supported"
                if section_type in supported
                else "insufficient_evidence",
                claim_slots=slots,
                linked_section_ids=[s for s in supported if s != "overview"]
                if section_type == "overview"
                else [],
                caveats=result.caveats
                if section_type == "limitations"
                else _unique(c for slot in slots for c in slot.caveats),
                limitations=result.limitations
                if section_type == "limitations"
                else _unique(c for slot in slots for c in slot.limitations),
                missing_information=result.missing_information
                if section_type == "limitations"
                else ["verified_claims:" + section_type]
                if section_type in missing
                else [],
            )
        )
    return result


def _protected(response):
    wire = response.model_dump(mode="json", exclude={"llm_metadata", "validation_result"})
    for section in wire["sections"]:
        section.pop("order")
        section["claim_slots"].sort(key=lambda slot: slot["slot_id"])
    wire["sections"].sort(key=lambda section: section["section_id"])
    return wire


def validate_report_outline(response, retrieved, request):
    """Reconstruct the full allowed selection/projection, permitting order only."""
    errors = []
    try:
        response = GroundedReportOutline.model_validate_json(response.model_dump_json())
        expected = _deterministic(request, retrieved)
        if _protected(response) != _protected(expected):
            errors.append("protected_outline_or_coverage_mismatch")
        if [s.order for s in response.sections] != list(range(1, len(response.sections) + 1)):
            errors.append("invalid_section_order")
        if response.sections and (
            response.sections[0].section_id != "scope"
            or response.sections[-1].section_id != "limitations"
        ):
            errors.append("scope_and_limitations_position_mismatch")
    except (ValidationError, ValueError, AttributeError, KeyError):
        errors.append("invalid_outline_contract")
    return QAValidationResult(valid=not errors, errors=errors)


class ReportOutlinePlanner:
    def __init__(self, ledger: VerifiedClaimLedger, gateway: SharedLLMGateway | None = None):
        self._ledger, self._gateway = ledger, gateway

    def plan(self, request: ReportOutlineRequest) -> GroundedReportOutline:
        request = ReportOutlineRequest.model_validate_json(request.model_dump_json())
        retrieved = []
        if not _request_problem(request):
            try:
                retrieved = self._ledger.find_claims(
                    VerifiedClaimQuery(
                        **{
                            key: getattr(request, key)
                            for key in ("company_id", "document_id", "snapshot_id", "period")
                        }
                    )
                ).claims
            except (ValueError, OSError):
                result = _empty(request, "abstained", ["ledger_read_failed"])
                result.validation_result = QAValidationResult(valid=True)
                return result
        result = _deterministic(request, retrieved)
        result.validation_result = validate_report_outline(result, retrieved, request)
        if not result.validation_result.valid:
            failure = _empty(request, "abstained", result.validation_result.errors)
            failure.validation_result = QAValidationResult(
                valid=False, errors=result.validation_result.errors
            )
            return failure
        if request.allow_gateway and result.used_verified_claim_ids:
            result = self._propose(request, result, retrieved)
        return GroundedReportOutline.model_validate_json(result.model_dump_json())

    def _propose(self, request, baseline, retrieved):
        result = baseline.model_copy(deep=True)
        metadata = result.llm_metadata
        metadata.status = "fallback"
        if self._gateway is None:
            metadata.reason = "gateway_unavailable"
            return result
        prompt = json.dumps(
            dict(
                instruction="Chỉ trả JSON theo schema. sections là hoán vị đầy đủ section_id; slot_order là hoán vị đầy đủ slot_id trong đúng mục. Giữ scope đầu, limitations cuối. Không thêm prose, claims, tiêu đề, citations, mục hoặc phép tính.",
                schema=ReportOutlineProposal.model_json_schema(),
                report_type=request.report_type,
                sections=[
                    dict(
                        section_id=s.section_id,
                        title_vi=s.title_vi,
                        slots=[
                            dict(
                                slot_id=slot.slot_id,
                                kind=slot.claim_kind,
                                accepted_content=slot.accepted_content,
                            )
                            for slot in s.claim_slots
                        ],
                    )
                    for s in result.sections
                ],
            ),
            ensure_ascii=False,
        )
        if len(prompt.encode("utf-8")) > 24000:
            metadata.reason = "projection_budget_exceeded"
            return result
        metadata.calls, metadata.model = 1, request.model
        response = self._gateway.generate(
            LLMRequest(
                contract_version="llm_gateway_v1",
                request_id=str(uuid4()),
                model=request.model,
                messages=[Message(role="user", content=prompt)],
                generation=GenerationParameters(temperature=0, max_output_tokens=1600),
                output_spec=OutputSpec(format="json"),
                constraints=RequestConstraints(timeout_seconds=45),
            )
        )
        metadata.usage, metadata.cost = response.usage, response.cost
        metadata.provenance, metadata.error = response.provenance, response.error
        try:
            if response.status != "success" or not isinstance(response.output, JSONOutput):
                raise ValueError("provider_or_structured_output_failure")
            proposal = ReportOutlineProposal.model_validate(response.output.payload)
            sections = {s.section_id: s for s in result.sections}
            if len(proposal.sections) != len(sections) or {
                s.section_id for s in proposal.sections
            } != set(sections):
                raise ValueError("invalid_section_permutation")
            ordered = []
            for order, item in enumerate(proposal.sections, 1):
                section = sections[item.section_id]
                slots = {slot.slot_id: slot for slot in section.claim_slots}
                if len(item.slot_order) != len(slots) or set(item.slot_order) != set(slots):
                    raise ValueError("invalid_slot_permutation")
                section.claim_slots = [slots[key] for key in item.slot_order]
                section.order = order
                ordered.append(section)
            result.sections = ordered
            result.validation_result = validate_report_outline(result, retrieved, request)
            if not result.validation_result.valid:
                raise ValueError("local_outline_validation_failed")
        except (ValidationError, ValueError):
            fallback = baseline.model_copy(deep=True)
            fallback.llm_metadata = metadata
            metadata.reason = "invalid_outline_proposal"
            return fallback
        metadata.status, metadata.reason = "accepted", None
        return result
