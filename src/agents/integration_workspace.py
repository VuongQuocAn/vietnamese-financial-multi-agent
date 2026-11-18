"""Request-local task/evidence bookkeeping; no storage or verification authority."""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Literal

from ..outputs.qa_contracts import QARequirement
from .supervisor import ExecutionEvidenceBundle


class IntegrationRequirement(QARequirement):
    requested_unit: str | None = None
    answer_goal: Literal["value", "analysis", "synthesis", "limitation"] = "value"


def evidence_handle(evidence):
    return "E-" + hashlib.sha256(evidence.reference.model_dump_json().encode()).hexdigest()[:20]


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
                if (context.get("goal_errors", {}).get(rid))
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

    def record_result(self, task, result, *, retain_sources=False):
        """Immutable revision-1 proposal refs; source/proof closure still goes to M6."""
        state = self.tasks[task.task_id]
        state.update(
            status="source_only"
            if not result.candidates
            and (
                state.get("source_context") or retain_sources and state.get("selected_observations")
            )
            else "completed"
            if result.status == "generated"
            else result.status,
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
            if retain_sources or result.candidates or state.get("coordination", {}).get("selection")
            else [],
            coordination=state.get("coordination", {}),
            source_context=state.get("source_context", []),
            document_candidate_ids=state.get("document_candidate_ids", []),
        )
        if state.get("python_candidate"):
            record["python_candidate"] = state["python_candidate"]
        record["digest"] = hashlib.sha256(
            json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.task_results[task.task_id] = record
        state["result_handle"] = record["handle"]
        state["input_results"] = inputs

    def dependencies_ready(self, task):
        return all(
            self.tasks.get(tid, {}).get("status") in {"completed", "partial", "source_only"}
            and (
                self.task_results.get(tid, {}).get("candidate_ids")
                or self.task_results.get(tid, {}).get("selected_observations")
                or self.task_results.get(tid, {}).get("source_context")
                or self.task_results.get(tid, {}).get("document_candidate_ids")
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
        bindings = {
            claim.candidate_id: list(
                dict.fromkeys(
                    rid
                    for origin in claim.origins
                    for rid in self.tasks[origin.execution_id]["requirement_ids"]
                    if rid in by_id
                )
            )
            for claim in candidates
        }
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
