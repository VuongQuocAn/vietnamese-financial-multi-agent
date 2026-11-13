"""Request-local task/evidence bookkeeping; no storage or verification authority."""

import hashlib
from dataclasses import dataclass, field

from ..outputs.qa_composer import matches_financial_target
from ..outputs.qa_contracts import QARequirement
from .supervisor import ExecutionEvidenceBundle


class IntegrationRequirement(QARequirement):
    requested_unit: str | None = None


def evidence_handle(evidence):
    return "E-" + hashlib.sha256(evidence.reference.model_dump_json().encode()).hexdigest()[:20]


def matches_requirement(claim, requirement):
    """Typed target matching only. Interpretation relevance is confirmed by M6."""
    if requirement.kind in {"unsupported", "ambiguous", "document", "limitations"}:
        return False
    if not requirement.target_id:
        return False
    if not matches_financial_target(claim, requirement):
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
    evidence: ExecutionEvidenceBundle = field(default_factory=ExecutionEvidenceBundle)
    tasks: dict[str, dict] = field(default_factory=dict)

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
                key for key in by_id if key in assigned and matches_requirement(claim, by_id[key])
            ]
        return dict(
            version="integration_v2",
            requirements=[r.model_dump(mode="json") for r in self.requirements],
            tasks=self.tasks,
            candidate_requirements=bindings,
            evidence_references=[f.reference.model_dump(mode="json") for f in self.evidence.facts],
        )
