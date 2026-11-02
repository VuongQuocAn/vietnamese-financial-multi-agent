"""Source-backed scope overlay; không sửa facts hoặc cấp cross-document authority."""

from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.context_resolution import (
    ContextEvidence,
    ContextResolution,
    resolve_financial_context,
)
from ..accounting.contracts import FinancialModel
from .contracts import EvidenceAnchor, Identity


class ReportingScopeReview(FinancialModel):
    version: Literal["reporting_scope_review_v1"] = "reporting_scope_review_v1"
    document_id: Identity
    snapshot_id: Identity
    pdf_sha256: Identity
    pdf_page: int = Field(ge=1)
    source_quote: Identity
    evidence_role: Literal["filing_scope", "other_entity", "inspected_context"]
    reporting_scope: Literal["separate", "consolidated"] | None
    evidence: ContextEvidence
    sources: list[EvidenceAnchor] = Field(min_length=1)
    method: Literal["controlled_original_pdf_visual_read"]
    review_image_sha256: Identity
    verification_reference: Identity
    inspection_reference: Identity


class ReportingScopeResolution(FinancialModel):
    version: Literal["reporting_scope_resolution_v1"] = "reporting_scope_resolution_v1"
    document_id: Identity
    snapshot_id: Identity
    reporting_scope: Literal["separate", "consolidated"] | None = None
    status: Literal["resolved", "unresolved", "ambiguous", "conflicted"]
    evidence_status: Literal["confirmed", "insufficient", "ambiguous", "conflicted"]
    reasons: list[str]
    reviews: list[ReportingScopeReview]
    context_resolution: ContextResolution | None = None
    # Overlay có scope không tự là approval cho phép so sánh/thực thi liên tài liệu.
    cross_document_execution_approved: Literal[False] = False
    financial_fact_verified: Literal[False] = False


def resolve_reporting_scope(descriptor, reviews=()) -> ReportingScopeResolution:
    """Resolve đúng một explicit document/snapshot/PDF, không latest/parent fallback.

    Review là controlled reading do caller persist sau khi kiểm original PDF và
    cache selector. Runtime revalidate binding, quote, inferred scope và giữ cả
    hai nguồn khi conflict; không sửa global M3 hoặc original FinancialContext.
    """
    selected = [
        r.model_copy(deep=True)
        for r in reviews
        if (r.document_id, r.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
    ]
    reasons = []
    if descriptor.document_id != "sha256:" + descriptor.pdf_sha256:
        reasons.append("scope_document_hash_mismatch")
    if not selected:
        reasons.append("scope_review_missing_for_selected_snapshot")
    for record in selected:
        try:
            ReportingScopeReview.model_validate_json(record.model_dump_json())
        except ValidationError:
            reasons.append("scope_review_contract_invalid")
        if (
            record.document_id != "sha256:" + record.pdf_sha256
            or record.pdf_sha256 != descriptor.pdf_sha256
            or record.source_quote != record.evidence.raw_text
            or [s.reference for s in record.sources] != record.evidence.provenance
            or any(
                s.reference is None
                or (s.document_id, s.snapshot_id) != (record.document_id, record.snapshot_id)
                or s.reference.anchor.page.source_ref != record.document_id
                or s.reference.anchor.page.page != record.pdf_page
                or not s.reference.anchor.page.image.strip()
                or not s.reference.source_pointer
                for s in record.sources
            )
        ):
            reasons.append("scope_source_binding_or_quote_mismatch")
        individual = resolve_financial_context(
            [record.evidence] if record.evidence_role == "filing_scope" else []
        )
        if individual.context.reporting_scope != record.reporting_scope:
            reasons.append("scope_review_value_mismatch")
    context = resolve_financial_context(
        [r.evidence for r in selected if r.evidence_role == "filing_scope"]
    )
    field = context.reporting_scope
    if "conflicting_candidates" in field.issues:
        status, evidence_status = "conflicted", "conflicted"
        reasons.append("reporting_scope_conflicting_evidence")
    elif reasons:
        status, evidence_status = "unresolved", "insufficient"
    elif field.status == "resolved":
        status, evidence_status = "resolved", "confirmed"
    elif field.candidates:
        status, evidence_status = "ambiguous", "ambiguous"
        reasons.extend(["reporting_scope_ambiguous_evidence", *field.issues])
    else:
        status, evidence_status = "unresolved", "insufficient"
        reasons.append("reporting_scope_source_insufficient")
    return ReportingScopeResolution(
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        reporting_scope=context.context.reporting_scope if status == "resolved" else None,
        status=status,
        evidence_status=evidence_status,
        reasons=sorted(set(reasons)),
        reviews=[r.model_copy(deep=True) for r in selected],
        context_resolution=context,
    )
