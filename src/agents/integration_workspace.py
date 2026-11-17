"""Request-local task/evidence bookkeeping; no storage or verification authority."""

import ast
import hashlib
import json
import re
from copy import deepcopy
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
            if operation.operator in {"divide", "ratio", "percentage_of"}:
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
            and set(requirement.required_indicators)
            <= {s.canonical_item_id for s in claim.supporting_evidence if s.kind == "fact"}
        )
    if requirement.kind in {"unsupported", "ambiguous", "document", "limitations"}:
        return False
    if (
        requirement.reason == "goal_context_unresolved"
        and requirement.interpretation_topic == "dynamic_calculation"
    ):
        # Only a proposed binding: the existing M6 dynamic-goal semantic pass
        # must confirm the operation actually answers this unresolved value goal.
        return bool(claim.reasoning and claim.reasoning.calculation)
    if not requirement.target_id and not (
        requirement.interpretation_topic == "dynamic_calculation"
        and requirement.required_indicators
        and requirement.reason in {None, "source_unknown"}
    ):
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
            {s.unit for s in proof.calculation.steps}
            if proof
            and proof.calculation
            and requirement.interpretation_topic == "dynamic_calculation"
            else {s.unit for s in proof.calculation.steps[-1:]}
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
                status="satisfied"
                if matches
                else "technical_error"
                if (
                    context.get("goal_errors", {}).get(rid)
                    if context.get("adaptive_coordinator")
                    else technical
                )
                else "unverified",
            )
        )
    return dict(
        complete=bool(rows)
        and (not technical or context.get("adaptive_coordinator", False))
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
    task_results: dict[str, dict] = field(default_factory=dict)
    observations: dict[str, dict] = field(default_factory=dict)
    expansion_used: bool = False
    repair_used: bool = False

    def dependency_ids(self, task):
        """Keep transitive input closure even if a consumer names only its direct parent."""
        pending, found = list(task.depends_on), []
        while pending:
            tid = pending.pop(0)
            if tid in found or tid not in self.task_results:
                continue
            found.append(tid)
            pending.extend(r["task_id"] for r in self.task_results[tid]["input_results"])
        return found

    def record_result(self, task, result):
        """Immutable revision-1 proposal refs; source/proof closure still goes to M6."""
        state = self.tasks[task.task_id]
        state.update(
            status="completed" if result.status == "generated" else result.status,
            candidate_statements=[c.content for c in result.candidates],
            candidate_evidence_ids=list(
                dict.fromkeys(k for c in result.candidates for k in c.supporting_evidence_ids)
            ),
            candidate_proofs=[
                c.reasoning.model_dump(mode="json")
                for c in result.candidates
                if c.reasoning and c.reasoning.calculation
            ],
            missing_inputs=result.missing_evidence,
        )
        candidates = [c.model_dump(mode="json") for c in result.candidates]
        inputs = [
            {k: self.task_results[tid][k] for k in ("handle", "task_id", "revision", "digest")}
            for tid in task.depends_on
        ]
        revision = state.get("revision", 1)
        record = dict(
            handle=f"result:{task.task_id}:v{revision}",
            task_id=task.task_id,
            revision=revision,
            input_results=inputs,
            candidate_ids=[c.candidate_id for c in result.candidates],
            evidence_ids=state["candidate_evidence_ids"],
            # Full candidates keep source identities, citations and replayable proofs.
            candidates=candidates,
            evidence=[
                e.model_dump(mode="json")
                for e in result.supporting_evidence
                if e.evidence_id in state["candidate_evidence_ids"]
            ],
            verification="unverified_candidates",
            selected_observations=state.get("selected_observations", [])
            if result.candidates or state.get("coordination", {}).get("selection")
            else [],
            coordination=state.get("coordination", {}),
        )
        record["digest"] = hashlib.sha256(
            json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.task_results[task.task_id] = record
        state["result_handle"] = record["handle"]
        state["input_results"] = inputs

    def dependencies_ready(self, task):
        return all(
            self.tasks.get(tid, {}).get("status") in {"completed", "partial"}
            and (
                self.task_results.get(tid, {}).get("candidate_ids")
                or self.task_results.get(tid, {}).get("selected_observations")
            )
            for tid in task.depends_on
        )

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
                if (key in assigned or by_id[key].answer_goal == "value")
                and (
                    key in assigned
                    and bool(self.task_results)
                    or matches_requirement(claim, by_id[key], self.targets.get(key))
                )
            ]
        adaptive = self.task_results or any("revision" in t for t in self.tasks.values())
        goal_errors = {}
        if adaptive:
            for rid in by_id:
                owners = [t for t in self.tasks.values() if rid in t["requirement_ids"]]
                if not owners:
                    goal_errors[rid] = ["goal_owner_unresolved"]
                elif all(t["status"] in {"failed", "blocked", "technical_error"} for t in owners):
                    goal_errors[rid] = [t.get("error", t["status"]) for t in owners]
        return dict(
            version="integration_v2",
            requirements=[r.model_dump(mode="json") for r in self.requirements],
            tasks=deepcopy(self.tasks),
            candidate_requirements=bindings,
            evidence_references=[f.reference.model_dump(mode="json") for f in self.evidence.facts],
            **(
                {
                    "task_results": deepcopy(self.task_results),
                    "adaptive_coordinator": True,
                    "goal_errors": goal_errors,
                    "observations": deepcopy(self.observations),
                }
                if adaptive
                else {}
            ),
        )
