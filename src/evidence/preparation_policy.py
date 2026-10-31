"""D-02 explicit preparation approval và draft formula preflight; không executor."""

import hashlib
import json
from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from .compatibility import FinancialOperand, OperandRequirement, OperationCompatibilitySpec
from .contracts import Identity

PROFILE = "D-02/document-statement-v1"


class PreparationApproval(FinancialModel):
    profile: Literal["D-02/document-statement-v1"]
    purpose: Literal["analytical_preparation"]
    authority: Literal["Tech Lead"]
    decision_reference: Identity
    # Không dùng record này để approve formula execution/cross-document consistency.


class PreparedFormulaPolicy(FinancialModel):
    formula_id: Literal["gross_margin", "debt_to_assets", "revenue_yoy"]
    version: Identity
    semantics: Identity
    expression: Identity
    operands: list[OperandRequirement] = Field(min_length=2, max_length=2)
    period_relation: Literal["same", "consecutive_fiscal_years_descending"]
    denominator_role: Identity
    denominator_policy: Literal["strictly_positive_else_undefined"]
    nonnegative_roles: list[Identity]
    arithmetic: Literal["Decimal"]
    precision: Literal[34]
    rounding: Literal["ROUND_HALF_EVEN"]
    output_multiplier: Literal["100"]
    output_unit: Literal["percent"]
    output_quantum: Literal["0.01"]
    rounding_stage: Literal["final_output_only"]

    def definition_digest(self):
        wire = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(wire.encode()).hexdigest()


class FormulaExecutionApproval(FinancialModel):
    formula_id: Identity
    version: Identity
    definition_sha256: Identity
    authority: Literal["Tech Lead"]
    purpose: Literal["formula_execution"]
    decision_reference: Identity
    negative_controls_reference: Identity


def check_formula_policy(
    policy: PreparedFormulaPolicy | None,
    spec: OperationCompatibilitySpec,
    operands: list[FinancialOperand],
    approvals: Sequence[FormulaExecutionApproval],
) -> dict:
    """Check semantics/guards only, never divide, scale, quantize or compute a metric."""
    if policy is None:
        return dict(
            execution_approved=False, blockers=["formula_definition_missing"], status="missing"
        )
    blockers = []
    if spec.operation_id != policy.formula_id or spec.operands != policy.operands:
        blockers.append("formula_semantics_or_operands_mismatch")
    expected_expressions = {
        "gross_margin": "gross_profit / revenue",
        "debt_to_assets": "liabilities / assets",
        "revenue_yoy": "(current_revenue - prior_revenue) / prior_revenue",
    }
    if policy.expression != expected_expressions[policy.formula_id]:
        blockers.append("formula_expression_mismatch")
    expected_denominator = {
        "gross_margin": "revenue",
        "debt_to_assets": "assets",
        "revenue_yoy": "prior_revenue",
    }
    expected_nonnegative = {
        "gross_margin": set(),
        "debt_to_assets": {"liabilities"},
        "revenue_yoy": {"current_revenue"},
    }
    if (
        policy.denominator_role != expected_denominator[policy.formula_id]
        or set(policy.nonnegative_roles) != expected_nonnegative[policy.formula_id]
    ):
        blockers.append("formula_guard_role_mismatch")
    roles = [r.role for r in policy.operands]
    supplied = [o.role for o in operands]
    if len(set(supplied)) != 2 or set(supplied) != set(roles):
        blockers.append("formula_operand_roles_mismatch")
    else:
        facts = {o.role: o.fact for o in operands}
        for requirement in policy.operands:
            fact = facts[requirement.role]
            if (
                fact.canonical_item_id != requirement.canonical_item_id
                or fact.semantic_role != requirement.semantic_role
                or fact.context.statement_type != requirement.statement_type
            ):
                blockers.append("formula_fact_semantics_mismatch")
        if any(f.value.normalized_value is None for f in facts.values()):
            blockers.append("formula_numeric_operand_missing")
        expected_period_type = "as_of" if policy.formula_id == "debt_to_assets" else "fiscal_year"
        if any(f.context.period_type != expected_period_type for f in facts.values()):
            blockers.append("formula_period_type_mismatch")
        if policy.denominator_role not in roles or set(policy.nonnegative_roles) - set(roles):
            blockers.append("formula_guard_role_mismatch")
        else:
            denominator = facts[policy.denominator_role].value.normalized_value
            if denominator is None or denominator <= 0:
                blockers.append("denominator_non_positive_or_missing")
            if any(
                facts[r].value.normalized_value is None or facts[r].value.normalized_value < 0
                for r in policy.nonnegative_roles
            ):
                blockers.append("nonnegative_operand_required")
        periods = [facts[r].context.period for r in roles]
        if policy.formula_id == "revenue_yoy":
            if (
                policy.period_relation != "consecutive_fiscal_years_descending"
                or spec.period_relation != "ordered_pair"
                or any(f.context.period_type != "fiscal_year" for f in facts.values())
                or not all(p and len(p) == 4 and p.isascii() and p.isdigit() for p in periods)
                or int(periods[0]) != int(periods[1]) + 1
            ):
                blockers.append("formula_period_relation_mismatch")
        elif (
            policy.period_relation != "same"
            or spec.period_relation != "same"
            or periods[0] != periods[1]
        ):
            blockers.append("formula_period_relation_mismatch")
    matching = [
        a
        for a in approvals
        if (a.formula_id, a.version, a.definition_sha256)
        == (policy.formula_id, policy.version, policy.definition_digest())
    ]
    approved = len(matching) == 1
    return dict(
        formula_id=policy.formula_id,
        version=policy.version,
        definition_sha256=policy.definition_digest(),
        execution_approved=approved,
        status="approved" if approved else "draft_pending_tech_lead",
        approval_reference=matching[0].decision_reference if approved else None,
        blockers=sorted(set(blockers)),
    )
