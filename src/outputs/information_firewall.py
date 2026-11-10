"""Final deterministic release gate over trusted M6 ledger and original requests.

The injected ledger is an admitted, read-only authority. This gate never replays
M6 admission, calls a composer/writer/model, retrieves raw facts or calculates.
"""

import hashlib

from pydantic import ValidationError

from ..tools.question_understanding import understand
from ..verification.ledger import VerifiedClaimLedger
from ..verification.validation_contracts import verification_input_digest
from .citation_contracts import RenderedCitationOutput
from .citation_renderer import _digest, validate_rendered_citations
from .firewall_contracts import FirewallCheckResult, FirewallDecision, ValidatedOutput
from .firewall_qa_binding import validate_qa_request_binding
from .grounded_report_writer import _retrieve, validate_grounded_report
from .qa_composer import _unique, claim_scope, retrieve_qa_claims, validate_qa_response
from .qa_contracts import QAValidationResult, VietnameseQARequest, VietnameseQAResponse
from .report_outline_planner import validate_report_outline
from .report_writer_contracts import GroundedFinancialReport, GroundedReportRequest

BLOCK_MESSAGE = (
    "Không thể cung cấp kết quả vì nội dung chưa vượt qua kiểm tra nguồn và tính nhất quán."
)
CLARIFY_MESSAGE = (
    "Cần xác định rõ yêu cầu, tài liệu, snapshot, kỳ hoặc phạm vi báo cáo trước khi tiếp tục."
)


def _typed(value, kind):
    if not isinstance(value, kind):
        raise ValueError("typed_input_required")
    return kind.model_validate_json(value.model_dump_json())


class _BoundedLookup:
    """One request-scoped retrieval; check exact filters before B01 selection."""

    def __init__(self, ledger):
        self.ledger = ledger
        self.queries = 0
        self.errors = []

    def find_claims(self, query):
        self.queries += 1
        matches = self.ledger.find_claims(query)
        for entry in matches.claims:
            if query.kind == "document" and (
                entry.identity.kind != "document"
                or entry.identity.composition_id != query.composition_id
                or entry.identity.composition_sha256 != query.composition_sha256
            ):
                self.errors.append("ledger_composition_context_mismatch")
            if any(
                getattr(query, field) is not None
                and getattr(entry.identity, field) != getattr(query, field)
                for field in ("company_id", "document_id", "snapshot_id", "period")
            ):
                self.errors.append("ledger_query_context_mismatch")
        return matches


def _entry_errors(entries):
    authority, integrity = [], []
    for entry in entries:
        identity, claim = entry.identity, entry.accepted_claim
        if entry.verification_status != "verified" or entry.decision.decision != "ACCEPT":
            authority.append("ledger_entry_not_verified_accept")
        if (
            any(
                getattr(identity, field) != getattr(claim, field)
                for field in ("company_id", "document_id", "snapshot_id", "period", "kind")
            )
            or identity.accepted_candidate_id != claim.candidate_id
            or identity.content_sha256 != hashlib.sha256(entry.content.encode()).hexdigest()
            or identity.final_decision_sha256 != verification_input_digest(entry.decision)
        ):
            integrity.append("ledger_identity_content_or_kind_mismatch")
        source_document = (
            claim.source_document_id if identity.kind == "document" else identity.document_id
        )
        if not entry.citations or any(
            (c.document_id, c.snapshot_id, c.source.document_id, c.source.snapshot_id)
            != (source_document, identity.snapshot_id) * 2
            for c in entry.citations
        ):
            integrity.append("ledger_citation_source_conflict")
        if any(
            (e.company_id, e.document_id, e.snapshot_id)
            != (identity.company_id, identity.document_id, identity.snapshot_id)
            or e.period != identity.period
            and not (
                getattr(claim, "reasoning", None)
                and claim.reasoning.calculation
                and any(
                    s.operation.period_relation == "across_periods"
                    for s in claim.reasoning.calculation.steps
                )
                and e.period in {p for s in claim.reasoning.calculation.steps for p in s.periods}
            )
            for e in (claim.supporting_evidence if identity.kind != "document" else [])
        ):
            integrity.append("ledger_evidence_context_mismatch")
    return _unique(authority), _unique(integrity)


class InformationFirewall:
    def __init__(self, ledger: VerifiedClaimLedger):
        self._ledger = ledger

    def evaluate_qa(
        self,
        *,
        request: VietnameseQARequest,
        response: VietnameseQAResponse,
        rendered: RenderedCitationOutput,
    ) -> FirewallDecision:
        return self._evaluate("qa", request, response, rendered)

    def evaluate_report(
        self,
        *,
        request: GroundedReportRequest,
        report: GroundedFinancialReport,
        rendered: RenderedCitationOutput,
    ) -> FirewallDecision:
        return self._evaluate("report", request, report, rendered)

    def _evaluate(self, mode, original_request, original_source, original_rendered):
        checks = []
        ids, segments, citations = [], [], []

        def check(key, reasons=(), *, warning=False, applicable=True):
            reasons = _unique(reasons)
            checks.append(
                FirewallCheckResult(
                    check_id=key,
                    status="not_applicable"
                    if not applicable
                    else ("warning" if reasons and warning else "fail" if reasons else "pass"),
                    severity="warning"
                    if reasons and warning
                    else "critical"
                    if reasons
                    else "info",
                    reason_code=reasons[0]
                    if reasons
                    else "not_applicable"
                    if not applicable
                    else "ok",
                    reasons=reasons,
                    affected_verified_claim_ids=ids.copy() if reasons else [],
                    affected_segment_ids=segments.copy() if reasons else [],
                    affected_citation_ids=citations.copy() if reasons else [],
                )
            )

        lookup = _BoundedLookup(self._ledger)
        stage = "F02"
        try:
            request = _typed(
                original_request, VietnameseQARequest if mode == "qa" else GroundedReportRequest
            )
            stage = "F08"
            source = _typed(
                original_source, VietnameseQAResponse if mode == "qa" else GroundedFinancialReport
            )
            stage = "F09"
            rendered = _typed(original_rendered, RenderedCitationOutput)
        except (ValidationError, ValueError, AttributeError, TypeError):
            check("F01", ["invalid_typed_request_or_output"])
            check(stage, ["required_binding_or_protected_contract_invalid"])
            return self._decision(mode, "unknown", checks, lookup.queries)
        ids = source.used_verified_claim_ids.copy()
        citations = [r.citation_id for r in rendered.references]
        segments = (
            [s.segment_id for s in source.grounded_segments]
            if mode == "qa"
            else [p.paragraph_id for s in source.sections for p in s.paragraphs]
        )
        check("F01")
        try:
            if mode == "qa":
                parsed, _ = understand(request.question)
                entries = (
                    retrieve_qa_claims(lookup, request, parsed)
                    if (request.snapshot_id or request.composition_id)
                    and (request.company_id or request.document_id)
                    else []
                )
            else:
                entries = _retrieve(lookup, request.outline_request)
        except (ValueError, OSError, AttributeError, TypeError):
            check("F03", ["ledger_read_failed"])
            return self._decision(mode, source.status, checks, lookup.queries)

        keys = [e.identity.verified_claim_id for e in entries]
        inventory_errors = lookup.errors.copy()
        if len(keys) != len(set(keys)):
            inventory_errors.append("duplicate_or_ambiguous_ledger_identity")
        if len(ids) != len(set(ids)) or set(ids) - set(keys):
            inventory_errors.append("unknown_or_unverified_claim_reference")
        check("F03", inventory_errors)
        authority, integrity = _entry_errors(entries)
        check("F04", authority)
        check("F05", integrity)

        if mode == "qa":
            binding_errors = validate_qa_request_binding(request, source, entries)
            outline_errors = []
            validation = validate_qa_response(source, entries)
            wanted_scope = request.reporting_scope or parsed.reporting_scope
        else:
            outline_errors = validate_report_outline(
                request.outline, entries, request.outline_request
            ).errors
            binding_errors = outline_errors.copy()
            validation = validate_grounded_report(source, entries, request)
            wanted_scope = request.outline_request.reporting_scope
        check("F02", binding_errors)
        check(
            "F06",
            ["requested_scope_not_confirmed"]
            if wanted_scope
            and any(
                claim_scope(e) != wanted_scope
                for e in entries
                if e.identity.verified_claim_id in ids
                and not (
                    mode == "qa" and request.document_snapshots and e.identity.kind == "document"
                )
            )
            else [],
        )
        check("F07", outline_errors, applicable=mode == "report")
        check("F08", validation.errors)

        # The presentation validator requires a validated source flag. Supply our
        # fresh result on a detached copy, never use a caller's attestation.
        validated_source = source.model_copy(deep=True)
        validated_source.validation_result = validation
        checked_rendered = rendered.model_copy(deep=True)
        checked_rendered.validation_result = QAValidationResult(valid=True)
        citation_validation = validate_rendered_citations(checked_rendered, validated_source)
        check("F09", citation_validation.errors)
        check(
            "F10",
            ["source_output_type_or_status_mismatch"]
            if (rendered.source_output_type != mode or rendered.original_status != source.status)
            else [],
        )
        warnings = []
        if source.caveats:
            warnings.append("required_caveats_disclosed")
        if source.status == "partial":
            warnings.append("partial_coverage_disclosed")
        if any(
            e.identity.kind != "document"
            and e.identity.verified_claim_id in ids
            and claim_scope(e) is None
            for e in entries
        ):
            warnings.append("reporting_scope_unknown")
        if any(r.provenance_level == "page" for r in rendered.references):
            warnings.append("page_level_location")
        if any(r.source_locator.resolution_status != "resolved" for r in rendered.references):
            warnings.append("source_location_unresolved")
        check("F11", warnings, warning=True)
        source_fingerprint = _digest(
            dict(
                request=request.model_dump(mode="json"),
                ledger=[
                    dict(
                        identity=e.identity.model_dump(mode="json"), payload_sha256=e.payload_sha256
                    )
                    for e in sorted(entries, key=lambda e: e.identity.verified_claim_id)
                ],
            )
        )
        output_fingerprint = _digest(
            dict(source=source.model_dump(mode="json"), rendered=rendered.model_dump(mode="json"))
        )
        return self._decision(
            mode,
            source.status,
            checks,
            lookup.queries,
            rendered,
            source_fingerprint,
            output_fingerprint,
        )

    @staticmethod
    def _decision(
        mode,
        status,
        checks,
        queries,
        rendered=None,
        source_fingerprint=None,
        output_fingerprint=None,
    ):
        blockers = _unique(r for c in checks if c.status == "fail" for r in c.reasons)
        warnings = _unique(r for c in checks if c.status == "warning" for r in c.reasons)
        verdict = (
            "BLOCK"
            if blockers
            else "CLARIFICATION_REQUIRED"
            if status == "clarification_required"
            else "ALLOW_WITH_CAVEAT"
            if warnings
            else "ALLOW"
        )
        released = verdict in ("ALLOW", "ALLOW_WITH_CAVEAT")
        release_status = (
            "released"
            if released
            else "blocked"
            if verdict == "BLOCK"
            else "clarification_required"
        )
        view = ValidatedOutput(
            status=status if released else release_status,
            message_vi="" if released else BLOCK_MESSAGE if blockers else CLARIFY_MESSAGE,
        )
        if released:
            view.rendered_text = rendered.rendered_text
            view.references = rendered.references
            view.citation_bindings = rendered.citation_bindings
            view.verified_claim_ids = _unique(
                k for b in rendered.citation_bindings for k in b.verified_claim_ids
            )
            view.caveats = rendered.caveats
            view.limitations = rendered.limitations
        return FirewallDecision(
            output_type=mode,
            decision=verdict,
            original_status=status,
            release_status=release_status,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
            validated_verified_claim_ids=view.verified_claim_ids,
            validated_citation_ids=[r.citation_id for r in view.references],
            limitations=rendered.limitations if released else [],
            source_fingerprint=source_fingerprint,
            output_fingerprint=output_fingerprint,
            validated_output=view,
            validation_result=QAValidationResult(valid=not blockers, errors=blockers),
            ledger_queries=queries,
        )
