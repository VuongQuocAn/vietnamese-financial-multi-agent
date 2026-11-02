"""M4 bounded execution assessment; không tính toán hoặc thay global M3/facts."""

from typing import Literal

from pydantic import ValidationError

from ..accounting.contracts import FinancialModel
from .analytical_readiness import AccountingBasisReview, SourceReview, assess_analytical_readiness
from .compatibility import CompatibilityAssessment
from .contracts import Identity
from .preparation_policy import check_formula_policy

EXECUTION_PROFILE = "M4/same-document-execution-v1"


class ExecutionCompatibilityApproval(FinancialModel):
    version: Literal["execution_compatibility_approval_v1"] = "execution_compatibility_approval_v1"
    profile: Literal["M4/same-document-execution-v1"]
    purpose: Literal["formula_execution_compatibility"]
    authority: Literal["Tech Lead"]
    decision_reference: Identity


class ExecutionCompatibilityDecision(FinancialModel):
    profile: Literal["M4/same-document-execution-v1"] = EXECUTION_PROFILE
    purpose: Literal["formula_execution_compatibility"] = "formula_execution_compatibility"
    status: Literal["compatible", "undetermined", "incompatible"]
    approval_reference: str | None = None
    reasons: list[str]


class ExecutionCompatibilityAssessment(FinancialModel):
    version: Literal["execution_compatibility_assessment_v1"] = (
        "execution_compatibility_assessment_v1"
    )
    global_compatibility: CompatibilityAssessment
    approved_execution_compatibility: ExecutionCompatibilityDecision
    execution_profile_approved: bool
    execution_blockers: list[str]
    # Compatibility riêng chưa chứng minh snapshot closed/formula approved.
    calculation_eligible: Literal[False] = False
    financial_fact_verified: Literal[False] = False


def assess_execution_compatibility(
    spec, operands, reviews, bases, *, approval=None, formula_policy=None
):
    """Reuse M3 + D-02 checks; approval không là preparation/candidate status flag.

    Invalid mutable records bị revalidate; caller phải dùng SnapshotCatalog cho
    eligibility cuối cùng. Không nhận boolean snapshot_closed từ caller.
    """
    baseline = assess_analytical_readiness(spec, operands, reviews, bases)
    original = CompatibilityAssessment.model_validate(baseline["global_compatibility"])
    blockers = list(baseline["candidate_blockers"])
    # Spec do caller cung cấp chưa đủ authority cho roles/statement/period semantics.
    # Formula approval vẫn là gate riêng tại catalog; ở đây chỉ reuse preflight.
    blockers.extend(check_formula_policy(formula_policy, spec, operands, ())["blockers"])
    approved = None
    if approval is not None:
        try:
            approved = ExecutionCompatibilityApproval.model_validate_json(
                approval.model_dump_json()
            )
        except (ValidationError, AttributeError):
            blockers.append("execution_approval_invalid")
    if approved is None:
        blockers.append("execution_profile_not_approved")
    if spec.document_relation != "same":
        blockers.append("execution_requires_same_document_rule")
    facts = [o.fact for o in operands]
    if len(facts) != 2:
        blockers.append("execution_requires_two_operands")
    elif (facts[0].context.reporting_scope is None) != (facts[1].context.reporting_scope is None):
        blockers.append("mixed_known_unknown_reporting_scope")
    for operand in operands:
        fact = operand.fact
        if fact.context.currency != fact.value.unit:
            blockers.append(f"{operand.role}:currency_unit_conflict")
        if (
            fact.context.mapped_item_code is not None
            and fact.context.mapped_item_code != fact.canonical_item_id
        ):
            blockers.append(f"{operand.role}:canonical_context_conflict")
        if not any(
            q.task_type == "direct_qa" and q.decision in {"usable", "usable_with_caveat"}
            for q in fact.quality_context
        ):
            blockers.append(f"{operand.role}:direct_qa_decision_missing")
        bound = [
            b
            for b in bases
            if (b.document_id, b.snapshot_id) == (fact.document_id, fact.snapshot_id)
            and fact.context.statement_type in b.statement_types
        ]
        if any(b.reused_from_snapshot and not b.verification_reference for b in bound):
            blockers.append(f"{operand.role}:accounting_basis_reverification_missing")
    identities = {f.observation_identity() for f in facts}
    contexts = {(f.document_id, f.snapshot_id) for f in facts}
    for model, records, code in (
        (
            SourceReview,
            [r for r in reviews if r.observation in identities],
            "source_review_contract_invalid",
        ),
        (
            AccountingBasisReview,
            [b for b in bases if (b.document_id, b.snapshot_id) in contexts],
            "accounting_basis_contract_invalid",
        ),
    ):
        for record in records:
            try:
                model.model_validate_json(record.model_dump_json())
            except ValidationError:
                blockers.append(code)
    status = (
        "incompatible"
        if original.status == "incompatible"
        or any(s == "source_inconsistent" for s in baseline["source_status"].values())
        else "undetermined"
        if blockers
        else "compatible"
    )
    blockers = sorted(set(blockers))
    return ExecutionCompatibilityAssessment(
        global_compatibility=original,
        approved_execution_compatibility=ExecutionCompatibilityDecision(
            status=status,
            approval_reference=approved.decision_reference if approved else None,
            reasons=blockers,
        ),
        execution_profile_approved=approved is not None,
        execution_blockers=blockers,
    )
