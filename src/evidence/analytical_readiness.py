"""D-02 source review overlay và experimental readiness; không sửa M3-01/facts."""

from typing import Literal

from pydantic import Field

from ..accounting.automated_extraction import parse_vietnamese_number
from ..accounting.contracts import FinancialModel
from .compatibility import FinancialOperand, OperationCompatibilitySpec, assess_compatibility
from .contracts import CanonicalFinancialFact, EvidenceAnchor, Identity, ObservationIdentity

PROFILE = "D-02/document-statement-v1"


class SourceReview(FinancialModel):
    """Controlled original-PDF reading, không phải independent human gold.

    Caller phải resolve PDF/render/selector trước khi persist. Records chỉ có hiệu
    lực cho đúng observation và toàn bộ anchors; không áp dụng sang snapshot khác.
    """

    observation: ObservationIdentity
    sources: list[EvidenceAnchor] = Field(min_length=1)
    pdf_sha256: Identity
    pdf_page: int = Field(ge=1)
    review_image_sha256: Identity
    review_reference: Identity
    method: Literal["controlled_original_pdf_visual_read"]
    level: Literal["page_resolved", "value_row_verified"]
    value_selector: Identity
    label_selector: Identity
    header_selector: Identity
    raw_value: str
    raw_label: str
    raw_header: str
    period: Identity
    statement_type: Identity
    # Không có cell_verified: chưa có exact cell geometry independent evidence.


class AccountingBasisReview(FinancialModel):
    document_id: Identity
    snapshot_id: Identity
    pdf_sha256: Identity
    pdf_page: int = Field(ge=1)
    review_image_sha256: Identity
    review_reference: Identity
    method: Literal["controlled_original_pdf_visual_read"]
    source_quote: Identity
    basis: Literal["VAS/TT200/accrual-historical-cost"]
    statement_types: list[Literal["B01", "B02"]] = Field(min_length=1)


def source_review_status(fact: CanonicalFinancialFact, reviews: list[SourceReview]) -> str:
    if not fact.sources or any(s.reference is None for s in fact.sources):
        return "source_missing"
    selected = [r for r in reviews if r.observation == fact.observation_identity()]
    if not selected:
        return "unverified"
    if len(selected) != 1:
        return "source_inconsistent"
    r = selected[0]
    if r.sources != fact.sources or fact.document_id != "sha256:" + r.pdf_sha256:
        return "source_inconsistent"
    for s in fact.sources:
        a = s.reference.anchor
        if (
            s.document_id != fact.document_id
            or s.snapshot_id != fact.snapshot_id
            or a.page.source_ref != fact.document_id
            or a.page.page != r.pdf_page
        ):
            return "source_inconsistent"
    pointers = {s.reference.source_pointer for s in fact.sources}
    if not {r.value_selector, r.label_selector, r.header_selector} <= pointers:
        return "source_inconsistent"
    if r.level == "page_resolved":
        return "page_resolved"
    if (
        not all((r.raw_label.strip(), r.raw_header.strip(), r.raw_value.strip()))
        or r.raw_value != fact.value.raw_value
        or r.raw_label != fact.context.raw_item_label
        or r.raw_header != fact.raw_header
        or r.period != fact.context.period
        or r.statement_type != fact.context.statement_type
        or parse_vietnamese_number(r.raw_value) != fact.value.normalized_value
    ):
        return "source_inconsistent"
    return "value_row_verified"


def assess_analytical_readiness(
    spec: OperationCompatibilitySpec,
    operands: list[FinancialOperand],
    reviews: list[SourceReview],
    bases: list[AccountingBasisReview],
) -> dict:
    """Candidate profile luôn pending review; không có tham số tự approve.

    Global assessment được trả nguyên vẹn. Chỉ waive unknown scope trong cùng
    statement/document/snapshot khi mọi operand được review và không known conflict.
    Formula approval và financial claims nằm ngoài profile này.
    """
    original = assess_compatibility(spec, operands)
    facts = [o.fact for o in operands]
    blockers = []
    source_status = {o.role: source_review_status(o.fact, reviews) for o in operands}
    same_context = (
        len(facts) == 2
        and len({f.document_id for f in facts}) == 1
        and len({f.snapshot_id for f in facts}) == 1
        and len({f.context.statement_type for f in facts}) == 1
        and all(f.document_id and f.snapshot_id and f.context.statement_type for f in facts)
    )
    if not same_context:
        blockers.append("document_statement_snapshot_not_shared")
    all_reviewed = bool(facts) and all(v == "value_row_verified" for v in source_status.values())
    for o in operands:
        f = o.fact
        if source_status[o.role] != "value_row_verified":
            blockers.append(f"{o.role}:source_{source_status[o.role]}")
        # Direct-QA usable không đủ để approve calculation; blocked vẫn veto.
        if not f.quality_context or any(
            q.decision in {"insufficient", "conflicted"} for q in f.quality_context
        ):
            blockers.append(f"{o.role}:quality_not_eligible")
        if f.value.normalized_value is None or f.value.status != "resolved" or f.value.issues:
            blockers.append(f"{o.role}:numeric_value_unresolved")
        for issue in f.resolution_issues:
            if issue.code != "missing_reporting_scope":
                blockers.append(f"{o.role}:context:{issue.code}:{issue.detail}")
        bound = [
            b
            for b in bases
            if b.document_id == f.document_id
            and b.snapshot_id == f.snapshot_id
            and b.document_id == "sha256:" + b.pdf_sha256
            and f.context.statement_type in b.statement_types
        ]
        if len(bound) != 1:
            blockers.append(f"{o.role}:accounting_basis_unknown_or_ambiguous")
    scope_exception = same_context and all_reviewed
    for reason in original.reasons:
        if reason.code == "source_reference_uncertain" and all_reviewed:
            continue
        if reason.code == "missing_reporting_scope" and scope_exception:
            continue
        if reason.code == "unresolved_operand_context":
            # Exact issues were expanded above; missing_scope only can be waived.
            if not scope_exception:
                blockers.append("missing_reporting_scope")
            continue
        blockers.append(reason.code)
    incompatible = original.status == "incompatible" or any(
        status == "source_inconsistent" for status in source_status.values()
    )
    candidate = "incompatible" if incompatible else "undetermined" if blockers else "compatible"
    return dict(
        profile=PROFILE,
        policy_status="experimental_pending_tech_lead",
        approved_compatibility=original.model_dump(mode="json"),
        candidate_compatibility=candidate,
        source_status=source_status,
        context_issues={
            o.role: [i.model_dump() for i in o.fact.resolution_issues] for o in operands
        },
        candidate_blockers=sorted(set(blockers)),
        preparation_source_ready=candidate == "compatible",
        calculation_eligible=False,
        eligibility_blockers=["compatibility_profile_not_approved", "formula_policy_not_approved"],
        financial_fact_verified=False,
    )
