"""Request-local task/evidence bookkeeping; no storage or verification authority."""

import ast
import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

from ..outputs.qa_composer import INTERPRETATION_TERMS, matches_financial_target
from ..outputs.qa_contracts import QARequirement
from ..tools.question_understanding import normalize
from .supervisor import ExecutionEvidenceBundle


class IntegrationRequirement(QARequirement):
    requested_unit: str | None = None
    answer_goal: Literal["value", "analysis", "synthesis", "limitation"] = "value"


def evidence_handle(evidence):
    return "E-" + hashlib.sha256(evidence.reference.model_dump_json().encode()).hexdigest()[:20]


def _matches_metric_expression(claim, source):
    """Bind a dynamic proof to the inventory formula, including ordered operands.

    Structural matching only: M6 still independently replays values and sources.
    A correct quotient of other indicators is not this accounting metric.
    """
    proof = claim.reasoning
    if (
        not proof
        or not proof.calculation
        or proof.claim_type != "derived_fact"
        or proof.assumptions
    ):
        return False
    metric = source["records"][0]
    roles = {
        operand.role: (operand.canonical_item_id, metric.request.operand_periods[operand.role])
        for operand in metric.definition.compatibility.operands
    }

    def expression(node):
        if isinstance(node, ast.Name):
            return roles[node.id]
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Sub, ast.Div, ast.Add, ast.Mult)
        ):
            return (type(node.op).__name__, expression(node.left), expression(node.right))
        raise ValueError("unsupported_formula_expression")

    values = {}
    for key, operand in proof.calculation.operands.items():
        matches = [s for s in claim.supporting_evidence if s.reference == operand.reference]
        if len(matches) != 1:
            return False
        values[key] = (matches[0].canonical_item_id, operand.period)
    try:
        for step in proof.calculation.steps:
            operation = step.operation
            args = [values[key] for key in operation.inputs]
            if operation.operator in {"divide", "ratio"}:
                value = ("Div", *args)
            elif operation.operator in {"percentage_change", "relative_difference"}:
                value = ("Div", ("Sub", *args), args[1])
            elif operation.operator == "subtract":
                value = ("Sub", *args)
            else:
                return False
            values[operation.operation_id] = value
        return values[proof.calculation.steps[-1].operation.operation_id] == expression(
            ast.parse(metric.definition.expression, mode="eval").body
        )
    except (KeyError, ValueError, SyntaxError, IndexError):
        return False


def matches_requirement(claim, requirement, source=None):
    """Typed target matching only. Interpretation relevance is confirmed by M6."""
    if requirement.answer_goal != "value":
        proof = claim.reasoning
        # Proposed relevance still needs M6 semantic truth and goal coverage.
        # A scalar or pure arithmetic proof cannot satisfy commentary.
        return bool(
            claim.kind == "supported_interpretation"
            and proof
            and proof.claim_type == "reasoned_conclusion"
            and normalize(proof.goal) == normalize(requirement.text)
            and set(requirement.required_indicators)
            <= {s.canonical_item_id for s in claim.supporting_evidence if s.kind == "fact"}
        )
    if requirement.kind in {"unsupported", "ambiguous", "document", "limitations"}:
        return False
    if not requirement.target_id:
        return False
    matched = matches_financial_target(claim, requirement)
    if not matched and source and source["kind"] == "metric":
        text = normalize(requirement.text)
        numeric_goal = re.match(r"^(?:tinh|tim|neu)\b", text) and not any(
            term in text for term in INTERPRETATION_TERMS
        )
        matched = (
            numeric_goal
            and (not requirement.period or requirement.period == claim.period)
            and set(requirement.required_indicators)
            <= {s.canonical_item_id for s in claim.supporting_evidence}
            and (
                not requirement.reasoning_periods
                or set(requirement.reasoning_periods)
                == {s.period for s in claim.supporting_evidence}
            )
            and _matches_metric_expression(claim, source)
        )
    if not matched:
        return False
    if requirement.requested_unit:
        proof = claim.reasoning
        units = (
            {s.unit for s in proof.calculation.steps[-1:]}
            if proof and proof.calculation
            else {s.unit for s in claim.supporting_evidence}
        )
        if requirement.requested_unit not in units:
            return False
    return True


def answer_coverage(context, entries):
    """Project request-local M6 bindings onto admitted and rendered claim identities."""
    supported = context.get("supported_requirements", {})
    rows = []
    technical = context.get("technical_errors", [])
    for requirement in context.get("requirements", []):
        rid = requirement["requirement_id"]
        matches = [
            entry.identity.verified_claim_id
            for entry in entries
            if rid
            in context.get("verified_requirements", {}).get(
                entry.identity.verified_claim_id,
                supported.get(entry.identity.accepted_candidate_id, []),
            )
        ]
        rows.append(
            dict(
                requirement_id=rid,
                text=requirement["text"],
                required=requirement.get("required", True),
                verified_claim_ids=matches,
                status="satisfied" if matches else "technical_error" if technical else "unverified",
            )
        )
    return dict(
        complete=bool(rows)
        and not technical
        and all(not row["required"] or row["verified_claim_ids"] for row in rows),
        requirements=rows,
    )


@dataclass
class IntegrationWorkspace:
    requirements: list[IntegrationRequirement]
    question: str = ""
    evidence: ExecutionEvidenceBundle = field(default_factory=ExecutionEvidenceBundle)
    tasks: dict[str, dict] = field(default_factory=dict)
    targets: dict[str, dict] = field(default_factory=dict)

    def merge(self, bundle):
        for key in ("facts", "calculations", "citations", "sources_and_lineage", "graph_contexts"):
            target = getattr(self.evidence, key)
            for value in getattr(bundle, key):
                if value not in target:
                    target.append(value)
        self.evidence.claim_fact_references = [f.reference for f in self.evidence.facts]

    def export(self, candidates):
        by_id = {r.requirement_id: r for r in self.requirements}
        bindings = {}
        for claim in candidates:
            assigned = {
                requirement_id
                for origin in claim.origins
                for requirement_id in self.tasks[origin.execution_id]["requirement_ids"]
            }
            bindings[claim.candidate_id] = [
                key
                for key in by_id
                if key in assigned and matches_requirement(claim, by_id[key], self.targets.get(key))
            ]
        return dict(
            version="integration_v2",
            requirements=[r.model_dump(mode="json") for r in self.requirements],
            tasks=self.tasks,
            candidate_requirements=bindings,
            evidence_references=[f.reference.model_dump(mode="json") for f in self.evidence.facts],
        )
