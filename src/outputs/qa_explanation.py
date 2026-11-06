"""Bounded presentation of admitted calculations; no lookup or arithmetic."""

from ..evidence.compatibility import FinancialOperand
from ..evidence.preparation_policy import check_metric_formula_policy
from ..tools.question_understanding import ITEM_RULES
from .qa_contracts import QAExplanationOperand, QAMetricExplanation


def metric_explanation(entry, aspects):
    claim = entry.accepted_claim
    calc = claim.calculation
    if (
        entry.verification_status != "verified"
        or entry.decision.decision != "ACCEPT"
        or entry.identity.kind != "approved_metric"
        or not calc
        or calc.status != "computed"
        or calc.result is None
        or not calc.trace
        or not calc.evidence
    ):
        return None
    trace, evidence = calc.trace, calc.evidence
    policy = trace.formula
    if (
        (calc.formula_id, calc.formula_version, calc.formula_digest)
        != (policy.formula_id, policy.version, policy.definition_digest())
        or (calc.document_id, calc.snapshot_id)
        != (entry.identity.document_id, entry.identity.snapshot_id)
        or calc.metric_id != evidence.record.metric_id
        or calc.output_unit != policy.output_unit
    ):
        return None
    facts, projected = [], []
    if len(trace.operands) != len(policy.operands) or len(evidence.operands) != len(
        policy.operands
    ):
        return None
    for spec in policy.operands:
        operands = [o for o in trace.operands if o.role == spec.role]
        bindings = [o for o in evidence.operands if o.binding.role == spec.role]
        if len(operands) != 1 or len(bindings) != 1 or len(bindings[0].facts.matches) != 1:
            return None
        operand, binding = operands[0], bindings[0]
        match = binding.facts.matches[0]
        fact = match.record
        if (
            match.reference.kind != "fact"
            or binding.binding.status != "bound"
            or operand.observation != binding.binding.observation
            or operand.observation != fact.observation_identity()
            or operand.source_fact_node_id != binding.binding.source_fact_node_id
            or fact.value.normalized_value is None
            or operand.value != str(fact.value.normalized_value)
            or operand.unit != fact.value.unit
            or operand.context != fact.context
            or operand.company_id != fact.company_id
            or fact.company_id != entry.identity.company_id
            or (operand.observation.document_id, operand.observation.snapshot_id)
            != (entry.identity.document_id, entry.identity.snapshot_id)
            or spec.canonical_item_id not in ITEM_RULES
        ):
            return None
        citations = [
            c for c in entry.citations if c in match.citations and c.source in fact.sources
        ]
        if not citations:
            return None
        facts.append(FinancialOperand(role=spec.role, fact=fact))
        projected.append(
            QAExplanationOperand(
                label=ITEM_RULES[spec.canonical_item_id].aliases[0],
                operand=operand,
                citations=citations,
            )
        )
    approval = check_metric_formula_policy(
        policy, evidence.record.definition, facts, [trace.approval]
    )
    if not approval["execution_approved"] or approval["blockers"]:
        return None
    # Expression has passed the existing approved policy check. Replace whole role tokens only.
    expression = policy.expression
    for row in sorted(projected, key=lambda r: len(r.operand.role), reverse=True):
        expression = expression.replace(row.operand.role, row.label)
    return QAMetricExplanation(
        metric_id=calc.metric_id,
        formula_id=calc.formula_id,
        formula_version=calc.formula_version,
        formula_digest=calc.formula_digest,
        result=calc.result,
        output_unit=calc.output_unit,
        formula=f"({expression}) × {policy.output_multiplier}%" if "formula" in aspects else None,
        operands=projected if "operands" in aspects else [],
    )


def explanation_text(explanation):
    parts = []
    if explanation.formula:
        parts.append("Công thức: " + explanation.formula + ".")
    if explanation.operands:
        parts.append("Số liệu sử dụng trong phép tính đã xác minh:")
        for row in explanation.operands:
            o = row.operand
            parts.append(
                f"- {row.label} ({o.role}): {o.value} {o.unit}; "
                f"hệ số đơn vị {o.context.scale}; kỳ {o.context.period}."
            )
    return "\n".join(parts)
