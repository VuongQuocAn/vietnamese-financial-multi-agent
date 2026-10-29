"""Binary operation metadata contract; accounting rules do caller/M4 phê duyệt."""

from typing import Literal

from pydantic import Field, model_validator
from vietnamese_financial_multi_agent.accounting.contracts import FinancialModel

from .contracts import CanonicalFinancialFact, Identity, ObservationIdentity


class OperandRequirement(FinancialModel):
    role: Identity
    canonical_item_id: Identity
    semantic_role: Identity
    statement_type: Literal["B01", "B02", "B03", "B09"]


class PeriodPair(FinancialModel):
    """Cặp kỳ đã xác nhận theo thứ tự operands, không suy năm từ PDF."""

    left: Identity
    right: Identity
    period_type: Identity

    @model_validator(mode="after")
    def distinct_periods(self):
        if self.left == self.right:
            raise ValueError("Ordered comparison requires distinct periods")
        return self


class OperationCompatibilitySpec(FinancialModel):
    operation_id: Identity
    # Reference tới policy/example được caller chọn; không là chứng nhận approval.
    rule_reference: Identity
    operands: list[OperandRequirement] = Field(min_length=2, max_length=2)
    period_relation: Literal["same", "ordered_pair"]
    period_pairs: list[PeriodPair] = Field(default_factory=list)
    document_relation: Literal["same", "any"]

    @model_validator(mode="after")
    def coherent_spec(self):
        if self.operands[0].role == self.operands[1].role:
            raise ValueError("Operand roles must be distinct")
        if self.period_relation == "same" and self.period_pairs:
            raise ValueError("Same-period rule cannot declare ordered pairs")
        return self


class FinancialOperand(FinancialModel):
    role: Identity
    fact: CanonicalFinancialFact


class OperandReference(FinancialModel):
    role: Identity
    observation: ObservationIdentity | None


class CompatibilityReason(FinancialModel):
    code: str
    operand_roles: list[str]
    outcome: Literal["incompatible", "undetermined"]


class CompatibilityAssessment(FinancialModel):
    operation_id: Identity
    rule_reference: Identity
    status: Literal["compatible", "incompatible", "undetermined"]
    operands: list[OperandReference]
    reasons: list[CompatibilityReason]
    financial_fact_verified: Literal[False] = False


def assess_compatibility(
    spec: OperationCompatibilitySpec, operands: list[FinancialOperand]
) -> CompatibilityAssessment:
    """Không tính giá trị; khác scale/unit giữ undetermined, không ngầm convert."""
    reasons = []
    roles = [r.role for r in spec.operands]

    def reason(code, outcome="undetermined", affected=None):
        reasons.append(
            CompatibilityReason(code=code, outcome=outcome, operand_roles=affected or roles)
        )

    supplied = [o.role for o in operands]
    if len(supplied) != len(set(supplied)) or set(supplied) - set(roles):
        reason("operand_role_mismatch", "incompatible", supplied)
    if set(roles) - set(supplied):
        reason("missing_operand", affected=sorted(set(roles) - set(supplied)))
    # Không bỏ âm thầm duplicate role bằng dict rồi trả compatible.
    if len(operands) == 2 and set(supplied) == set(roles) and len(set(supplied)) == 2:
        facts = [next(o.fact for o in operands if o.role == r) for r in roles]
        for requirement, f in zip(spec.operands, facts, strict=True):
            if f.observation_identity() is None:
                reason("missing_observation_identity", affected=[requirement.role])
            if f.resolution_issues:
                reason("unresolved_operand_context", affected=[requirement.role])
            for field in ("canonical_item_id", "semantic_role", "statement_type"):
                actual = getattr(f.context if field == "statement_type" else f, field)
                if not actual:
                    reason(f"missing_{field}", affected=[requirement.role])
                elif actual != getattr(requirement, field):
                    reason(f"{field}_mismatch", "incompatible", [requirement.role])
        left, right = facts
        for field in ("company_id", "document_id"):
            a, b = getattr(left, field), getattr(right, field)
            if not a or not b:
                reason(f"missing_{field}")
            elif a != b and (field == "company_id" or spec.document_relation == "same"):
                reason(f"{field}_mismatch", "incompatible")
        for field in ("reporting_scope", "period_type", "currency", "scale", "unit"):
            a = getattr(left.value if field == "unit" else left.context, field)
            b = getattr(right.value if field == "unit" else right.context, field)
            if a is None or b is None or a == "" or b == "":
                reason(f"missing_{field}")
            elif field == "scale" and (a <= 0 or b <= 0):
                reason("invalid_scale")
            elif a != b:
                outcome = "undetermined" if field in {"unit", "scale"} else "incompatible"
                reason(f"{field}_mismatch", outcome)
        a, b = left.context.period, right.context.period
        if not a or not b:
            reason("missing_period")
        elif spec.period_relation == "same":
            if a != b:
                reason("period_mismatch", "incompatible")
        elif not spec.period_pairs:
            reason("period_relation_not_defined")
        elif (
            left.context.period_type
            and right.context.period_type
            and not any(
                (p.left, p.right, p.period_type) == (a, b, left.context.period_type)
                for p in spec.period_pairs
            )
        ):
            reason("period_relation_mismatch", "incompatible")
    status = (
        "incompatible"
        if any(r.outcome == "incompatible" for r in reasons)
        else "undetermined"
        if reasons
        else "compatible"
    )
    return CompatibilityAssessment(
        operation_id=spec.operation_id,
        rule_reference=spec.rule_reference,
        status=status,
        operands=[
            OperandReference(role=o.role, observation=o.fact.observation_identity())
            for o in operands
        ],
        reasons=reasons,
    )
