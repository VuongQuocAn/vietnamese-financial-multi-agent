"""Request-local task/evidence bookkeeping; no storage or verification authority."""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

from pydantic import Field, model_serializer

from ..accounting.contracts import FinancialModel
from ..outputs.qa_contracts import QARequirement
from ..tools.financial_calculator import DynamicOperation
from .supervisor import ExecutionEvidenceBundle


class GoalCalculationIntent(FinancialModel):
    """Declared N/R graph, with period and unit constraints in EO ordinal order."""

    steps: list[DynamicOperation]
    operand_constraints: list[dict[str, str]]


class IntegrationRequirement(QARequirement):
    requested_unit: str | None = None
    answer_goal: Literal["value", "analysis", "synthesis", "limitation"] = "value"
    evidence_needs: list[str] = Field(default_factory=list, max_length=8)
    verification_requirements: list[str] = Field(default_factory=list, max_length=8)
    calculation_intent: GoalCalculationIntent | None = None

    @property
    def need_refs(self):
        return [f"{self.requirement_id}.need[{i}]" for i in range(len(self.evidence_needs))]

    @model_serializer(mode="wrap")
    def serialize_requirement(self, handler):
        wire = super().serialize_requirement(handler)
        for key in ("evidence_needs", "verification_requirements", "calculation_intent"):
            if not wire.get(key):
                wire.pop(key, None)
        return wire


class QuestionRequirement(IntegrationRequirement):
    """The original request is the criterion for semantic verification."""

    kind: Literal["question"] = "question"
    requirement_id: Literal["Q1"] = "Q1"
    source_scope: dict[str, str | None]

    @classmethod
    def from_request(cls, question, context):
        scope = {
            key: getattr(context, key)
            for key in ("company_id", "document_id", "snapshot_id", "period", "reporting_scope")
        }
        if not question.strip() or not all(
            scope[k] for k in ("company_id", "document_id", "snapshot_id")
        ):
            raise ValueError("question_requirement_scope_missing")
        return cls(text=question, source_scope=scope)

    @classmethod
    def matches_request(cls, requirement, question, context):
        try:
            return requirement == cls.from_request(question, context).model_dump(mode="json")
        except ValueError:
            return False

    @model_serializer(mode="wrap")
    def serialize_requirement(self, handler):
        return {
            k: v
            for k, v in handler(self).items()
            if k in {"requirement_id", "text", "kind", "source_scope"}
        }


def expected_answers_for_verification(expected):
    """Omit the predicted derivation from semantic input and revision identity."""
    if not expected:
        return expected
    return dict(
        expected,
        requirements=[
            {key: value for key, value in row.items() if key != "derivation"}
            if "answer_type" in row
            else row
            for row in expected["requirements"]
        ],
    )


def expected_answer_set(question_requirement, proposals, scope, previous=()):
    """Assign IDs before candidates exist. Appending preserves existing IDs."""
    from ..evidence.composition import payload_sha256

    rows = list(previous)
    for proposal in proposals:
        if not proposal["text"].strip() or any(
            proposal["text"].strip().casefold() == row["text"].strip().casefold() for row in rows
        ):
            continue
        rows.append(dict(proposal, requirement_id=f"R{len(rows) + 1}"))
    expected = dict(requirements=rows, reporting_scope=scope)
    identity = expected_answers_for_verification(expected)["requirements"]
    return dict(expected, revision=payload_sha256([question_requirement, scope, identity]))


def bind_need_results(
    need_refs, tool_results, missing_inputs, missing_need_inputs=None, *, owned_refs=None
):
    """Acquisition associations only; never infer relevance or EO completion."""
    return {
        ref: dict(
            tool_result_ids=[r["result_id"] for r in tool_results if ref in r["need_refs"]],
            evidence_refs=list(
                dict.fromkeys(
                    key
                    for r in tool_results
                    if ref in r["need_refs"]
                    for key in r["evidence_refs"]
                    if owned_refs is None or key in owned_refs
                )
            ),
            # Unscoped final notes remain explicitly task-wide, not semantic assignments.
            missing_inputs=list((missing_need_inputs or {}).get(ref, missing_inputs)),
            missing_scope="need" if ref in (missing_need_inputs or {}) else "task",
        )
        for ref in need_refs
    }


def evidence_handle(evidence):
    return "E-" + hashlib.sha256(evidence.reference.model_dump_json().encode()).hexdigest()[:20]


def answer_coverage(context, entries):
    """Project M6 goal completion; a related ACCEPT claim alone never completes a goal."""
    from ..verification.evidence_obligations import question_grants
    from ..verification.lite_contracts import question_completion

    supported = context.get("supported_requirements", {})
    rows = []
    technical = context.get("technical_errors", [])
    for requirement in context.get("requirements", []):
        rid = requirement["requirement_id"]
        completion = context.get("goal_completion", {}).get(rid, {})
        if requirement.get("kind") == "question":
            resolved = context.get("verified_question_bindings", {})
            eligible = {
                entry.identity.verified_claim_id: grants
                for entry in entries
                if (grants := question_grants(resolved.get(entry.identity.verified_claim_id, {})))
            }
            projected = question_completion(
                completion,
                released_bindings=[grant for grants in eligible.values() for grant in grants],
            )
            rows.append(
                dict(
                    requirement_id=rid,
                    text=requirement["text"],
                    required=requirement.get("required", True),
                    slots=[
                        dict(slot, status="satisfied" if slot["bindings"] else "unverified")
                        for slot in projected.get("slots", [])
                    ],
                    verified_claim_ids=list(eligible),
                    status=projected["status"]
                    if completion.get("status") != "technical_error"
                    else "technical_error",
                )
            )
            continue
        completed_ids = set(completion.get("candidate_ids", []))
        bound_entries = [
            entry
            for entry in entries
            if rid
            in context.get("verified_requirements", {}).get(
                entry.identity.verified_claim_id,
                supported.get(entry.identity.accepted_candidate_id, []),
            )
        ]
        released_ids = {entry.identity.accepted_candidate_id for entry in bound_entries}
        satisfied = (
            completion.get("status") == "satisfied"
            and bool(completed_ids)
            and completed_ids <= released_ids
        )
        matches = [entry.identity.verified_claim_id for entry in bound_entries]
        rows.append(
            dict(
                requirement_id=rid,
                text=requirement["text"],
                required=requirement.get("required", True),
                verified_claim_ids=matches,
                status="satisfied"
                if satisfied
                else "technical_error"
                if completion.get("status") == "technical_error"
                or context.get("goal_errors", {}).get(rid)
                else "unverified",
            )
        )
    return dict(
        complete=bool(rows)
        and (not technical or context.get("adaptive_coordinator", False))
        and all(not row["required"] or row["status"] == "satisfied" for row in rows),
        requirements=rows,
    )


@dataclass
class IntegrationWorkspace:
    requirements: list[IntegrationRequirement]
    question: str = ""
    question_understanding: dict = field(default_factory=dict)
    expected_answers: dict | None = None
    evidence: ExecutionEvidenceBundle = field(default_factory=ExecutionEvidenceBundle)
    tasks: dict[str, dict] = field(default_factory=dict)
    targets: dict[str, dict] = field(default_factory=dict)
    task_results: dict[str, dict] = field(default_factory=dict)
    observations: dict[str, dict] = field(default_factory=dict)

    def dependency_ids(self, task):
        """Keep transitive input closure even if a consumer names only its direct parent."""
        pending, found = list(task["depends_on"] if isinstance(task, dict) else task.depends_on), []
        while pending:
            tid = pending.pop(0)
            if tid in found or tid not in self.task_results:
                continue
            found.append(tid)
            pending.extend(r["task_id"] for r in self.task_results[tid]["input_results"])
        return found

    def record_result(self, task, result, *, retain_sources=False):
        """Immutable revision-1 proposal refs; source/proof closure still goes to M6."""
        if task.task_id in self.task_results:
            raise ValueError("task_result_already_recorded")
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
            tool_evidence_ids=list(state.get("tool_evidence_ids", [])),
            tool_metric_ids=list(state.get("tool_metric_ids", [])),
            missing_inputs=list(result.missing_evidence),
            # Full candidates keep source identities, citations and replayable proofs.
            candidates=candidates,
            evidence=[
                e.model_dump(mode="json")
                for e in result.supporting_evidence
                if e.evidence_id in state["candidate_evidence_ids"]
            ],
            verification="unverified_candidates",
            selected_observations=deepcopy(state.get("selected_observations", []))
            if retain_sources or result.candidates or state.get("coordination", {}).get("selection")
            else [],
            coordination=state.get("coordination", {}),
            calculations=deepcopy(state.get("calculations", [])),
            source_context=deepcopy(state.get("source_context", [])),
            document_candidate_ids=state.get("document_candidate_ids", []),
        )
        if state.get("retained_observations"):
            record["retained_observations"] = deepcopy(state["retained_observations"])
        if task.need_refs:
            owned = {
                row["evidence_id"]
                for row in record["selected_observations"] + record.get("retained_observations", [])
            } | {row["handle"] for row in record["source_context"]}
            receipts = deepcopy(state.get("need_tool_results", []))
            diagnostics = state.pop("need_source_issues", {})
            cells = {}
            for receipt in receipts:
                if cell := receipt.get("source_cell"):
                    source = cell["provenance"][0]
                    key = (source["anchor"]["page"]["source_ref"], cell["source_pointer"])
                    for ref in receipt["need_refs"]:
                        cells.setdefault(ref, set()).add(key)
            for ref, locations in cells.items():
                if len(locations) > 1:
                    diagnostics.setdefault(ref, []).append("source_ambiguous")
                    for receipt in receipts:
                        if ref in receipt["need_refs"]:
                            receipt["need_refs"].remove(ref)
            unresolved = sorted({ref for r in receipts for ref in r["evidence_refs"]} - owned)
            if unresolved:
                record["unresolved_evidence_refs"] = unresolved
                record["missing_inputs"].append("source_closure_unresolved")
                state["missing_inputs"] = list(record["missing_inputs"])
            record.update(
                need_refs=list(task.need_refs),
                tool_results=receipts,
                missing_need_inputs=deepcopy(state.get("missing_need_inputs", {})),
                need_bindings=bind_need_results(
                    task.need_refs,
                    receipts,
                    record["missing_inputs"],
                    state.get("missing_need_inputs", {}),
                    owned_refs=owned,
                ),
            )
            if task.specialist == "retrieval":
                record["need_diagnostics"] = {
                    ref: next(
                        (
                            reason
                            for reason in (
                                "source_ambiguous",
                                "issuer_mismatch",
                                "period_unresolved",
                                "provenance_insufficient",
                                "canonical_mapping_missing",
                                "item_mismatch",
                            )
                            if reason in diagnostics.get(ref, ())
                        ),
                        "tool_no_match" if receipts else "retrieval_not_executed",
                    )
                    for ref, binding in record["need_bindings"].items()
                    if not binding["evidence_refs"]
                }
        if state.get("python_candidate"):
            record["python_candidate"] = state["python_candidate"]
        if state.get("request_work"):
            record["request_work"] = deepcopy(state["request_work"])
        record["digest"] = hashlib.sha256(
            json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.task_results[task.task_id] = record
        state["result_handle"] = record["handle"]
        state["input_results"] = inputs

    def dependencies_ready(self, task):
        ready = all(
            (result := self.task_results.get(tid))
            and self.tasks[tid]["status"] in {"completed", "partial", "source_only"}
            and (
                result["candidate_ids"]
                or result["document_candidate_ids"]
                or result.get("request_work")
                or self.tasks[tid]["role"] == "retrieval"
                and (result["selected_observations"] or result["source_context"])
            )
            for tid in task.depends_on
        )
        if (
            ready
            and task.specialist == "reasoning"
            and any(self.tasks[tid]["role"] == "reasoning" for tid in task.depends_on)
        ):
            return self._result_inputs_current(
                self.task_results[tid] for tid in self.dependency_ids(task)
            )
        return ready

    def _result_inputs_current(self, records):
        from .evidence_coordination import content_digest

        return all(
            record["digest"] == content_digest({k: v for k, v in record.items() if k != "digest"})
            and all(
                all(
                    parent[k] == self.task_results.get(parent["task_id"], {}).get(k)
                    for k in ("handle", "revision", "digest")
                )
                for parent in record["input_results"]
            )
            for record in records
        )

    def request_work(self, task, gateway, *, reserved_ids=()):
        """Validate one scoped acquisition request; reuse tasks and immutable result inputs."""
        from .coordinator_plan import TaskProposal
        from .evidence_coordination import content_digest
        from .lite_orchestrator import LiteTask

        request = self.task_results[task.task_id]["request_work"]
        if task.specialist != "reasoning" or set(request) != {
            "role",
            "objective",
            "need_refs",
            "input_results",
        }:
            raise ValueError("work_request_invalid")
        assignment = TaskProposal.model_validate(
            {k: request[k] for k in ("role", "objective", "need_refs")}, strict=True
        )
        question_work = any(
            isinstance(r, QuestionRequirement) and r.requirement_id in task.requirement_ids
            for r in self.requirements
        )
        if (
            assignment.role != "retrieval"
            or (not assignment.need_refs and not question_work)
            or set(assignment.need_refs) - set(task.need_refs)
        ):
            raise ValueError("work_request_scope_invalid")
        refs = request["input_results"]
        inputs = {
            self.task_results[tid]["handle"]: self.task_results[tid]
            for tid in self.dependency_ids(task)
        }
        if (
            not isinstance(refs, list)
            or len(refs) > 6
            or any(not isinstance(ref, str) or ref not in inputs for ref in refs)
        ):
            raise ValueError("work_request_input_not_owned")
        if not self._result_inputs_current([self.task_results[task.task_id], *inputs.values()]):
            raise ValueError("work_request_input_stale")
        key = content_digest(
            dict(
                role=assignment.role,
                objective=assignment.objective,
                need_refs=sorted(set(assignment.need_refs)),
            )
        )
        if any(s.get("work_request_key") == key for s in self.tasks.values()):
            raise ValueError("work_request_repeated")
        if len(self.tasks) + 2 > 6:
            raise ValueError("work_request_task_cap")
        if (
            getattr(gateway, "remaining_generation_calls", 2) < 2
            or perf_counter() >= getattr(gateway, "generation_deadline", float("inf"))
            or getattr(gateway, "exhausted", False)
            or getattr(gateway, "failure_category", None)
        ):
            raise ValueError("work_request_budget_exhausted")
        index = max(int(tid[1:]) for tid in [*self.tasks, *reserved_ids]) + 1
        acquisition = LiteTask(
            task_id=f"T{index}",
            specialist="retrieval",
            objective=assignment.objective,
            requirement_ids=[
                r.requirement_id
                for r in self.requirements
                if set(r.need_refs) & set(assignment.need_refs)
                or (question_work and r.requirement_id in task.requirement_ids)
            ],
            need_refs=assignment.need_refs,
            depends_on=[task.task_id],
        )
        consumer = task.model_copy(
            deep=True, update=dict(task_id=f"T{index + 1}", depends_on=[acquisition.task_id])
        )
        self.tasks[task.task_id]["work_request_key"] = key
        for child in (acquisition, consumer):
            self.tasks[child.task_id] = dict(
                task_id=child.task_id,
                requirement_ids=child.requirement_ids,
                depends_on=child.depends_on,
                objective=child.objective,
                role=child.specialist,
                need_refs=child.need_refs,
                revision=1,
                status="pending",
            )
        return [acquisition, consumer]

    def merge(self, bundle):
        for key in ("facts", "calculations", "citations", "sources_and_lineage", "graph_contexts"):
            target = getattr(self.evidence, key)
            for value in getattr(bundle, key):
                if value not in target:
                    target.append(value)
        self.evidence.claim_fact_references = [f.reference for f in self.evidence.facts]

    def export(self, candidates):
        by_id = {r.requirement_id: r for r in self.requirements}
        tasks = deepcopy(self.tasks)
        for tid, task in tasks.items():
            if (
                task.get("role") == "retrieval"
                and tid not in self.task_results
                and task.get("need_refs")
            ):
                task["need_diagnostics"] = dict.fromkeys(
                    task["need_refs"], "retrieval_not_executed"
                )
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
            **(
                {"question_understanding": deepcopy(self.question_understanding)}
                if self.question_understanding
                else {}
            ),
            requirements=[r.model_dump(mode="json") for r in self.requirements],
            **(
                {"expected_answers": deepcopy(self.expected_answers)}
                if self.expected_answers is not None
                else {}
            ),
            tasks=tasks,
            candidate_requirements=bindings,
            **(
                dict(
                    candidate_need_refs={
                        claim.candidate_id: list(
                            dict.fromkeys(
                                ref
                                for origin in claim.origins
                                for tid in [
                                    origin.execution_id,
                                    *self.dependency_ids(self.tasks[origin.execution_id]),
                                ]
                                for ref, binding in self.task_results.get(tid, {})
                                .get("need_bindings", {})
                                .items()
                                if ref in self.tasks[origin.execution_id].get("need_refs", [])
                                if set(binding["evidence_refs"])
                                & set(claim.supporting_evidence_ids)
                            )
                        )
                        for claim in candidates
                    }
                )
                if any(r.evidence_needs for r in self.requirements)
                else {}
            ),
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
