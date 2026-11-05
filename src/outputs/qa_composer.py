"""Read-only M7 QA: catalog matching → verified retrieval → protected text slots.

The model can reorder selected slots, never write financial prose. This local
gate covers this composer only, not the general M7-05 Information Firewall.
"""

import json
import re
from uuid import uuid4

from pydantic import ValidationError

from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_gateway import SharedLLMGateway
from ..tools.question_understanding import (
    EXTRA_ALIASES,
    FORMULA_ALIASES,
    ITEM_RULES,
    normalize,
    understand,
)
from ..verification.ledger import VerifiedClaimLedger
from ..verification.ledger_contracts import VerifiedClaim, VerifiedClaimQuery
from .qa_contracts import (
    GroundedAnswerPlan,
    GroundedSegment,
    QAClaimContext,
    QACompositionProposal,
    QARequirement,
    QAValidationResult,
    VietnameseQARequest,
    VietnameseQAResponse,
)

INTRODUCTIONS = {
    "verified": "Theo các nội dung đã được xác minh trong ledger:",
    "by_requirement": "Các nội dung có căn cứ cho từng yêu cầu:",
}
STATUS_TEXT = {
    "answered": "",
    "partial": "Chỉ trả lời được một phần; các ý còn lại chưa có đủ claim đã xác minh.",
    "clarification_required": "Cần làm rõ chỉ tiêu, tài liệu, snapshot hoặc kỳ báo cáo.",
    "abstained": "Chưa có đủ claim đã xác minh cho yêu cầu này trong ledger.",
    "unsupported": "Yêu cầu vượt quá khả năng QA đã được hỗ trợ.",
}
SCOPE_CAVEAT = "Phạm vi báo cáo chưa được xác nhận trong claim đã chọn."
LEDGER_LIMIT = "Thiếu claim trong ledger không có nghĩa là số liệu không tồn tại trong PDF."


def _unique(values):
    return list(dict.fromkeys(values))


def _citations(values):
    return list({c.model_dump_json(): c for c in values}.values())


def claim_scope(entry: VerifiedClaim):
    """Only use the accepted calculation's source-backed scope resolution.

    Caller intent/batch context and a document year do not confirm filing scope.
    Fact-only claims without an embedded resolution retain unknown scope.
    """
    calc = entry.accepted_claim.calculation
    scope = calc.evidence.reporting_scope if calc and calc.evidence else None
    if (
        scope
        and scope.status == "resolved"
        and scope.evidence_status == "confirmed"
        and (scope.document_id, scope.snapshot_id)
        == (entry.identity.document_id, entry.identity.snapshot_id)
    ):
        return scope.reporting_scope
    return None


def _segment(entry):
    claim, decision = entry.accepted_claim, entry.decision
    scope = claim_scope(entry)
    caveats = _unique(
        entry.caveats
        + claim.caveats
        + [c for e in claim.supporting_evidence for c in e.caveats]
        + [c for citation in entry.citations for c in citation.limitations]
        + ([SCOPE_CAVEAT] if scope is None else [])
    )
    return GroundedSegment(
        segment_id=entry.identity.verified_claim_id,
        content=entry.content,
        verified_claim_ids=[entry.identity.verified_claim_id],
        citations=entry.citations,
        context=QAClaimContext(
            **{
                k: getattr(entry.identity, k)
                for k in ("company_id", "document_id", "snapshot_id", "period")
            },
            reporting_scope=scope,
        ),
        caveats=caveats,
        limitations=_unique(
            decision.limitations + decision.unresolved_blockers + claim.missing_information
        ),
    )


def _segments(entries):
    """Coalesce identical display text; retain every selected identity and caveat."""
    grouped = {}
    for entry in entries:
        slot = _segment(entry)
        key = (slot.content, slot.context.model_dump_json())
        if key not in grouped:
            grouped[key] = slot
        else:
            existing = grouped[key]
            existing.verified_claim_ids += slot.verified_claim_ids
            existing.citations = _citations(existing.citations + slot.citations)
            existing.caveats = _unique(existing.caveats + slot.caveats)
            existing.limitations = _unique(existing.limitations + slot.limitations)
    return list(grouped.values())


def _assertion_signature(entry):
    """Compare typed accepted premises, never interpret/paraphrase the claim text.

    Different wording of numeric-only ACCEPTs is allowed only for the same exact
    value/unit/scale, source references, calculation identity, period and scope.
    Interpretations still require verbatim content equality.
    """
    claim = entry.accepted_claim
    calc = claim.calculation
    return json.dumps(
        dict(
            context=_segment(entry).context.model_dump(mode="json"),
            kind=entry.identity.kind,
            interpretation=entry.content
            if entry.identity.kind == "supported_interpretation"
            else None,
            evidence=[
                dict(
                    kind=e.kind,
                    reference=e.reference.model_dump(mode="json"),
                    value=e.value,
                    unit=e.unit,
                    scale=e.scale,
                    item=e.canonical_item_id,
                    period=e.period,
                )
                for e in claim.supporting_evidence
            ],
            metric=dict(
                id=calc.metric_id,
                formula=calc.formula_id,
                digest=calc.formula_digest,
                result=calc.result,
                unit=calc.output_unit,
            )
            if calc
            else None,
        ),
        sort_keys=True,
    )


def _targets(text):
    """Longest non-overlapping matches over the existing public catalog/aliases."""
    aliases = [("metric", key, names) for key, names in FORMULA_ALIASES.items()]
    aliases += [
        ("fact", key, (*rule.aliases, key, *EXTRA_ALIASES.get(key, ())))
        for key, rule in ITEM_RULES.items()
    ]
    spans = []
    for kind, key, names in aliases:
        for name in names:
            for match in re.finditer(r"(?<!\w)" + re.escape(normalize(name)) + r"(?!\w)", text):
                spans.append((match.start(), match.end(), kind, key))
    return _unique(
        (kind, key)
        for start, end, kind, key in sorted(spans)
        if not any(a <= start and end <= b and b - a > end - start for a, b, _, _ in spans)
    )


def understand_requirements(question):
    requirements = []
    # Split only requests, not evidence or numeric values from claims.
    for clause in re.split(r"\s+và\s+|[,;\n]+|\s+đồng thời\s+", question, flags=re.I):
        if not clause.strip():
            continue
        text = normalize(clause)
        parsed, issues = understand(clause)
        interpretation = any(w in text for w in ("nhan dinh", "dien giai", "phan tich"))
        targets = _targets(text)
        if any(w in text for w in ("han che", "gioi han", "caveat")):
            requirements.append(QARequirement(requirement_id="", text=clause, kind="limitations"))
        # Guard unsupported questions before mapping a mentioned operand/nearby metric.
        unsafe = any(
            w in text
            for w in (
                "vi sao",
                "tai sao",
                "nguyen nhan",
                "do dau",
                "chung to",
                "nen dau tu",
                "tot hay xau",
                "du bao",
                "du doan",
                "tang bao nhieu",
                "giam bao nhieu",
                "gap doi",
                "gap ba",
                "cao hon",
                "thap hon",
                "tot khong",
                "an toan",
                "lanh manh",
            )
        )
        if unsafe or (issues and issues != ["multiple_or_ambiguous_targets"]):
            requirements.append(
                QARequirement(
                    requirement_id="",
                    text=clause,
                    kind="unsupported",
                    reason=issues[0] if issues else "unsupported_inference",
                )
            )
        elif targets:
            for kind, key in targets:
                requirements.append(
                    QARequirement(
                        requirement_id="",
                        text=clause,
                        kind=kind,
                        target_id=key,
                        interpretation=interpretation,
                    )
                )
        elif not any(w in text for w in ("han che", "gioi han", "caveat")):
            requirements.append(
                QARequirement(
                    requirement_id="",
                    text=clause,
                    kind="ambiguous"
                    if any(w in text for w in ("loi nhuan", "sinh loi", "co cau no"))
                    else "unsupported",
                    reason="specify_catalog_target"
                    if parsed.intent != "unsupported"
                    or "loi nhuan" in text
                    or "sinh loi" in text
                    or "co cau no" in text
                    else "unsupported_question",
                )
            )
    for index, requirement in enumerate(requirements):
        requirement.requirement_id = f"r{index + 1}"
    return requirements


def _matches_target(entry, requirement):
    claim = entry.accepted_claim
    expected_kind = (
        "supported_interpretation"
        if requirement.interpretation
        else ("fact" if requirement.kind == "fact" else "approved_metric")
    )
    if entry.identity.kind != expected_kind:
        return False
    if requirement.kind == "fact":
        return any(
            e.kind == "fact" and e.canonical_item_id == requirement.target_id
            for e in claim.supporting_evidence
        )
    return bool(claim.calculation and claim.calculation.formula_id == requirement.target_id)


def _answer_text(response):
    parts = [INTRODUCTIONS[response.introduction]] if response.grounded_segments else []
    for segment in response.grounded_segments:
        # Separate context and text: no rewriting or numerical formatting of accepted content.
        ctx = segment.context
        parts.append(f"Kỳ {ctx.period} — {segment.content}")
    if STATUS_TEXT[response.status]:
        parts.append(STATUS_TEXT[response.status])
    if response.unanswered_requirements:
        # Reflect requirement labels only; never echo untrusted financial assertions.
        parts.append(
            "Các yêu cầu chưa đáp ứng: "
            + ", ".join(r.requirement_id for r in response.unanswered_requirements)
            + "."
        )
    if response.caveats:
        parts.append("Lưu ý: " + "; ".join(response.caveats))
    if response.limitations:
        parts.append("Giới hạn: " + "; ".join(response.limitations))
    return "\n".join(parts)


def validate_qa_response(response, retrieved):
    """Compare complete protected slots, not numeric regex or model attestations."""
    entries = {e.identity.verified_claim_id: e for e in retrieved}
    errors = []
    ids = response.used_verified_claim_ids
    if len(set(ids)) != len(ids) or any(key not in entries for key in ids):
        errors.append("invalid_verified_claim_reference")
    if [key for s in response.grounded_segments for key in s.verified_claim_ids] != ids:
        errors.append("segment_selection_mismatch")
    if all(key in entries for key in ids):
        if response.grounded_segments != _segments([entries[key] for key in ids]):
            errors.append("protected_slot_mismatch")
    for segment in response.grounded_segments:
        ctx = segment.context
        if any(
            (c.document_id, c.snapshot_id) != (ctx.document_id, ctx.snapshot_id)
            or (c.source.document_id, c.source.snapshot_id) != (ctx.document_id, ctx.snapshot_id)
            for c in segment.citations
        ):
            errors.append("citation_context_mismatch")
    if response.citations != _citations(c for s in response.grounded_segments for c in s.citations):
        errors.append("citation_projection_mismatch")
    if response.caveats != _unique(c for s in response.grounded_segments for c in s.caveats):
        errors.append("caveat_projection_mismatch")
    expected_limits = _unique(c for s in response.grounded_segments for c in s.limitations)
    if response.unanswered_requirements:
        expected_limits = _unique(expected_limits + [LEDGER_LIMIT])
    if response.limitations != expected_limits:
        errors.append("limitation_projection_mismatch")
    answered = [r for r in response.plan.requirements if r.verified_claim_ids]
    unanswered = [r for r in response.plan.requirements if not r.verified_claim_ids]
    if (
        response.answered_requirements != answered
        or response.unanswered_requirements != unanswered
        or set(ids) != {key for r in answered for key in r.verified_claim_ids}
        or set(ids) != set(response.plan.selected_verified_claim_ids)
    ):
        errors.append("requirement_coverage_mismatch")
    for requirement in answered:
        if (
            len(
                {
                    _assertion_signature(entries[key])
                    for key in requirement.verified_claim_ids
                    if key in entries
                }
            )
            > 1
            and requirement.kind != "limitations"
        ):
            errors.append("conflicting_requirement_assertions")
        for key in requirement.verified_claim_ids:
            if key not in entries or (
                requirement.kind != "limitations" and not _matches_target(entries[key], requirement)
            ):
                errors.append("requirement_target_mismatch")
    if ids and response.status != ("partial" if unanswered else "answered"):
        errors.append("status_coverage_mismatch")
    if not ids and response.status in ("answered", "partial"):
        errors.append("empty_answer")
    contexts = {
        (s.context.company_id, s.context.document_id, s.context.snapshot_id)
        for s in response.grounded_segments
    }
    if len(contexts) > 1:
        errors.append("mixed_contexts")
    if len({s.context.period[:4] for s in response.grounded_segments}) > 1:
        errors.append("mixed_reporting_years")
    if response.answer_vi != _answer_text(response):
        errors.append("unapproved_display_text")
    return QAValidationResult(valid=not errors, errors=_unique(errors))


class VietnameseQAComposer:
    def __init__(self, ledger: VerifiedClaimLedger, gateway: SharedLLMGateway | None = None):
        self._ledger, self._gateway = ledger, gateway

    def compose(self, request: VietnameseQARequest) -> VietnameseQAResponse:
        request = VietnameseQARequest.model_validate_json(request.model_dump_json())
        parsed, issues = understand(request.question)
        plan = GroundedAnswerPlan(requirements=understand_requirements(request.question))
        response = VietnameseQAResponse(
            question=request.question, status="abstained", answer_vi="", plan=plan
        )
        # Comparisons cannot be decomposed to circumvent D03-B10.
        if "cross_document_comparison_blocked_D03_B10" in issues:
            plan.reasons.append("cross_document_comparison_blocked_D03_B10")
            return self._finish(response, [], "unsupported")
        if "ambiguous_reporting_scope" in issues:
            plan.reasons.append("ambiguous_reporting_scope")
            return self._finish(response, [], "clarification_required")
        if parsed.period and request.period and parsed.period != request.period:
            plan.missing_information.append("period")
            return self._finish(response, [], "clarification_required")
        if (
            parsed.reporting_year
            and request.period
            and (request.period[:4] != str(parsed.reporting_year))
        ):
            plan.missing_information.append("period")
            return self._finish(response, [], "clarification_required")
        if (
            parsed.reporting_scope
            and request.reporting_scope
            and (parsed.reporting_scope != request.reporting_scope)
        ):
            plan.missing_information.append("reporting_scope")
            return self._finish(response, [], "clarification_required")
        if not any(r.kind in ("fact", "metric", "limitations") for r in plan.requirements):
            return self._finish(
                response,
                [],
                "clarification_required"
                if any(r.kind == "ambiguous" for r in plan.requirements)
                else "unsupported",
            )
        if not request.snapshot_id or not (request.document_id or request.company_id):
            plan.missing_information.extend(
                [
                    field
                    for field, bound in (
                        ("snapshot_id", request.snapshot_id),
                        ("company_id_or_document_id", request.company_id or request.document_id),
                    )
                    if not bound
                ]
            )
            return self._finish(response, [], "clarification_required")
        # Descriptions of origin without a caller binding must never override exact IDs.
        text = normalize(request.question)
        if re.search(r"\bsnapshot\b|\brecovery\b|\bban goc\b|\boriginal\b", text):
            plan.missing_information.append("snapshot_origin_binding")
            return self._finish(response, [], "clarification_required")
        try:
            retrieved = self._ledger.find_claims(
                VerifiedClaimQuery(
                    company_id=request.company_id,
                    document_id=request.document_id,
                    snapshot_id=request.snapshot_id,
                    period=request.period or parsed.period,
                )
            ).claims
        except (ValueError, OSError):
            plan.reasons.append("ledger_read_failed")
            return self._finish(response, [], "abstained")
        # Defend the consumer boundary even if a malformed facade ignores its AND query.
        if any(
            any(
                value is not None and getattr(e.identity, field) != value
                for field, value in (
                    ("company_id", request.company_id),
                    ("document_id", request.document_id),
                    ("snapshot_id", request.snapshot_id),
                    ("period", request.period or parsed.period),
                )
            )
            or e.verification_status != "verified"
            or e.decision.decision != "ACCEPT"
            for e in retrieved
        ):
            plan.reasons.append("retrieval_context_mismatch")
            return self._finish(response, [], "abstained")
        if (
            len(
                {
                    (e.identity.company_id, e.identity.document_id, e.identity.snapshot_id)
                    for e in retrieved
                }
            )
            > 1
        ):
            plan.missing_information.append("document_id")
            return self._finish(response, [], "clarification_required")
        scope = request.reporting_scope or parsed.reporting_scope
        year = parsed.reporting_year
        for requirement in plan.requirements:
            if requirement.kind not in ("fact", "metric"):
                continue
            candidates = [
                e
                for e in retrieved
                if _matches_target(e, requirement)
                and (year is None or e.identity.period[:4] == str(year))
                and (scope is None or claim_scope(e) == scope)
            ]
            signatures = {_assertion_signature(e) for e in candidates}
            if len(signatures) > 1:
                requirement.reason = "ambiguous_verified_claims"
            elif candidates:
                requirement.verified_claim_ids = sorted(
                    e.identity.verified_claim_id for e in candidates
                )
            else:
                requirement.reason = "requested_scope_unconfirmed" if scope else "no_verified_claim"
        selected_ids = _unique(key for r in plan.requirements for key in r.verified_claim_ids)
        # No implicit joining of claims from different reporting years.
        years = {
            e.identity.period[:4] for e in retrieved if e.identity.verified_claim_id in selected_ids
        }
        if len(years) > 1 or len(selected_ids) > 12:
            for requirement in plan.requirements:
                requirement.verified_claim_ids = []
            plan.missing_information.append("period" if len(years) > 1 else "narrower_question")
            return self._finish(response, [], "clarification_required")
        for requirement in plan.requirements:
            if requirement.kind == "limitations":
                requirement.verified_claim_ids = selected_ids.copy()
                if not selected_ids:
                    requirement.reason = "select_claims_for_limitations"
        plan.selected_verified_claim_ids = selected_ids
        if not selected_ids:
            ambiguous = any(r.reason == "ambiguous_verified_claims" for r in plan.requirements)
            return self._finish(
                response, retrieved, "clarification_required" if ambiguous else "abstained"
            )
        order = selected_ids
        if request.allow_gateway:
            order = self._propose(request, response, retrieved)
        response.grounded_segments = _segments(
            [next(e for e in retrieved if e.identity.verified_claim_id == key) for key in order]
        )
        return self._finish(response, retrieved)

    def _propose(self, request, response, retrieved):
        metadata, ids = response.llm_metadata, response.plan.selected_verified_claim_ids
        if self._gateway is None:
            metadata.status, metadata.reason = "fallback", "gateway_unavailable"
            return ids
        projection = [
            dict(
                verified_claim_id=e.identity.verified_claim_id,
                content=e.content,
                context=_segment(e).context.model_dump(mode="json"),
                citation_handles=[c.anchor_id for c in e.citations],
                caveats=_segment(e).caveats,
                limitations=_segment(e).limitations,
                interpretation_boundary="Render accepted content verbatim; no added assertion.",
            )
            for e in retrieved
            if e.identity.verified_claim_id in ids
        ]
        prompt = json.dumps(
            dict(
                instruction="Chỉ sắp xếp các protected slots. Xuất JSON theo schema; claim_order "
                "là hoán vị đầy đủ các verified_claim_id. Không xuất prose, số mới, "
                "citations hay caveats; backend giữ nguyên mọi nội dung và giới hạn.",
                schema=QACompositionProposal.model_json_schema(),
                selected_claims=projection,
            ),
            ensure_ascii=False,
        )
        if len(prompt.encode("utf-8")) > 24000:
            metadata.status, metadata.reason = "fallback", "projection_budget_exceeded"
            return ids
        metadata.calls, metadata.model = 1, request.model
        result = self._gateway.generate(
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
        metadata.usage, metadata.cost = result.usage, result.cost
        metadata.provenance, metadata.error = result.provenance, result.error
        try:
            if result.status != "success" or not isinstance(result.output, JSONOutput):
                raise ValueError("provider_or_structured_output_failure")
            proposal = QACompositionProposal.model_validate(result.output.payload)
            if len(proposal.claim_order) != len(ids) or set(proposal.claim_order) != set(ids):
                raise ValueError("invalid_claim_permutation")
        except (ValidationError, ValueError):
            metadata.status, metadata.reason = "fallback", "invalid_composition_proposal"
            return ids
        metadata.status = "accepted"
        response.introduction = proposal.introduction
        return proposal.claim_order

    @staticmethod
    def _finish(response, retrieved, status=None):
        response.answered_requirements = [
            r for r in response.plan.requirements if r.verified_claim_ids
        ]
        response.unanswered_requirements = [
            r for r in response.plan.requirements if not r.verified_claim_ids
        ]
        response.status = status or ("partial" if response.unanswered_requirements else "answered")
        response.used_verified_claim_ids = [
            key for s in response.grounded_segments for key in s.verified_claim_ids
        ]
        response.citations = _citations(c for s in response.grounded_segments for c in s.citations)
        response.caveats = _unique(c for s in response.grounded_segments for c in s.caveats)
        response.limitations = _unique(c for s in response.grounded_segments for c in s.limitations)
        if response.unanswered_requirements:
            response.limitations = _unique(response.limitations + [LEDGER_LIMIT])
        response.missing_information = response.plan.missing_information.copy()
        response.reasons = _unique(
            response.plan.reasons + [r.reason for r in response.unanswered_requirements if r.reason]
        )
        response.answer_vi = _answer_text(response)
        response.validation_result = validate_qa_response(response, retrieved)
        if not response.validation_result.valid:
            # Retain the failure codes, but expose no financial slots/references.
            errors = response.validation_result.errors
            for r in response.plan.requirements:
                r.verified_claim_ids = []
            response.plan.selected_verified_claim_ids = []
            response.plan.reasons.extend(errors)
            response.grounded_segments = []
            return VietnameseQAComposer._finish(response, [], "abstained")
        return VietnameseQAResponse.model_validate_json(response.model_dump_json())
