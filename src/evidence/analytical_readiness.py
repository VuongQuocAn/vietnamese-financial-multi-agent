"""D-02 source review và approved preparation profile; không sửa M3-01/facts."""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from ..accounting.automated_extraction import parse_vietnamese_number
from ..accounting.contracts import FinancialModel
from .compatibility import FinancialOperand, OperationCompatibilitySpec, assess_compatibility
from .contracts import CanonicalFinancialFact, EvidenceAnchor, Identity, ObservationIdentity
from .preparation_policy import (
    PROFILE,
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
    check_formula_policy,
)


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
    *,
    approval: PreparationApproval | None = None,
    formula_policy: PreparedFormulaPolicy | None = None,
    formula_approvals: Sequence[FormulaExecutionApproval] = (),
) -> dict:
    """Explicit Tech Lead record chỉ approve analytical preparation đúng profile.

    Global assessment được trả nguyên vẹn. Chỉ waive unknown scope trong cùng
    statement/document/snapshot khi mọi operand được review và không known conflict.
    Formula approval và financial claims nằm ngoài profile này.
    """
    if approval is not None:
        # Revalidate selected mutable record, không chấp nhận đổi version/purpose ngầm.
        approval = PreparationApproval.model_validate_json(approval.model_dump_json())
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
    profile_status = (
        candidate if approval is not None else ("incompatible" if incompatible else "undetermined")
    )
    preparation_ready = approval is not None and profile_status == "compatible"
    formula = check_formula_policy(formula_policy, spec, operands, formula_approvals)
    eligibility_blockers = list(blockers) + formula["blockers"]
    if approval is None:
        eligibility_blockers.append("compatibility_profile_not_approved")
    if not formula["execution_approved"]:
        eligibility_blockers.append("formula_policy_not_approved")
    if original.status != "compatible":
        # Preparation-only approval không tự cấp exception cho execution.
        eligibility_blockers.append("global_execution_compatibility_not_established")
    return dict(
        profile=PROFILE,
        policy_status="approved_analytical_preparation"
        if approval
        else "experimental_pending_tech_lead",
        global_compatibility=original.model_dump(mode="json"),
        approved_profile_compatibility=dict(
            profile=PROFILE,
            purpose="analytical_preparation",
            status=profile_status,
            approval_reference=approval.decision_reference if approval else None,
            reasons=sorted(set(blockers))
            + ([] if approval else ["compatibility_profile_not_approved"]),
        ),
        preparation_ready=preparation_ready,
        formula_policy=formula,
        # Legacy alias của global assessment, giữ cho consumers baseline D-02.
        approved_compatibility=original.model_dump(mode="json"),
        candidate_compatibility=candidate,
        source_status=source_status,
        context_issues={
            o.role: [i.model_dump() for i in o.fact.resolution_issues] for o in operands
        },
        candidate_blockers=sorted(set(blockers)),
        preparation_source_ready=candidate == "compatible",
        calculation_eligible=preparation_ready
        and formula["execution_approved"]
        and not eligibility_blockers,
        eligibility_blockers=sorted(set(eligibility_blockers)),
        financial_fact_verified=False,
    )
