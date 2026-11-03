"""Deterministic read-only M5 → M6 handoff; no tools, LLM or financial policy."""

import hashlib
import json

from ..agents.orchestration_contracts import OrchestrationResult
from ..agents.specialist_common import SpecialistCandidate
from .contracts import CandidateClaim, ClaimProvenance, ConversionIssue, VerificationInput


def to_verification_input(result: OrchestrationResult) -> VerificationInput:
    """Copy/revalidate the wire contract, preserving incomplete evidence as issues.

    Invalid typed payloads raise Pydantic ValidationError (including mutated models).
    Structurally parseable missing references remain intact for later investigation.
    No orchestration status is interpreted as a verification decision.
    """
    source_wire = result.model_dump_json()
    source = OrchestrationResult.model_validate_json(source_wire)
    canonical = json.dumps(json.loads(source_wire), sort_keys=True, ensure_ascii=False)
    batch = VerificationInput(
        source_version=source.version,
        source_result_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        source_plan_id=source.planner_result.plan.plan_id
        if source.planner_result and source.planner_result.plan
        else None,
        question=source.question,
        context=source.context,
        orchestration_status=source.status,
        conflicts=source.conflicts,
        caveats=source.caveats,
        risks=source.risks,
        missing_evidence=source.missing_evidence,
        uncovered_requirements=source.uncovered_requirements,
        stop_conditions=source.stop_conditions,
        errors=source.errors,
    )

    def issue(code, path, candidate_id=None):
        batch.issues.append(ConversionIssue(code=code, path=path, candidate_id=candidate_id))

    def citations_issues(citations, path, candidate_id):
        if not citations:
            issue("missing_citations", path, candidate_id)
        for i, citation in enumerate(citations):
            if (
                citation.source.source_key() is None
                or citation.anchor_id is None
                or citation.pdf_page is None
                or citation.provenance_level is None
            ):
                issue("incomplete_citation_metadata", [*path, i], candidate_id)
            reference = citation.source.reference
            if (
                (citation.document_id, citation.snapshot_id)
                != (citation.source.document_id, citation.source.snapshot_id)
                or reference is not None
                and (citation.pdf_page, citation.provenance_level)
                != (reference.anchor.page.page, reference.provenance_level)
            ):
                issue("inconsistent_citation_metadata", [*path, i], candidate_id)

    def calculation_issues(calculation, path, candidate_id):
        if calculation is not None and (
            calculation.trace is None
            or calculation.evidence is None
            or calculation.evidence.reviewed_lineage.lineage is None
        ):
            issue("incomplete_calculation_payload", path, candidate_id)

    candidate_ids = [c.candidate_id for c in source.candidates]
    conflict_ids = {c.conflict_id for c in source.conflicts}
    executions = {e.execution_id: e for e in source.specialist_executions}
    if len(set(candidate_ids)) != len(candidate_ids):
        issue("duplicate_candidate_id", ["candidates"])
    if source.candidates and source.status not in {"completed", "partial"}:
        # Preserve supplied candidates, but flag inconsistent upstream state. Never
        # manufacture candidates by mining SpecialistResult or SupervisorResult.
        issue("candidates_in_stopped_orchestration", ["status"])
    for i, candidate in enumerate(source.candidates):
        cid, path = candidate.candidate_id, ["candidates", i]
        batch.claims.append(
            CandidateClaim(
                **{name: getattr(candidate, name) for name in SpecialistCandidate.model_fields},
                provenance=ClaimProvenance(
                    m5_candidate_id=cid,
                    origins=candidate.origins,
                    origin_roles=candidate.origin_roles,
                    supporting_references=candidate.supporting_references,
                    conflict_ids=candidate.conflict_ids,
                ),
                supporting_evidence=candidate.supporting_evidence,
            )
        )
        citations_issues(candidate.citations, [*path, "citations"], cid)
        if not candidate.supporting_evidence:
            issue("missing_supporting_evidence", [*path, "supporting_evidence"], cid)
        if not candidate.origins:
            issue("missing_candidate_origins", [*path, "origins"], cid)
        for j, evidence in enumerate(candidate.supporting_evidence):
            ep = [*path, "supporting_evidence", j]
            citations_issues(evidence.citations, [*ep, "citations"], cid)
            calculation_issues(evidence.calculation, [*ep, "calculation"], cid)
            if evidence.kind == "metric" and evidence.calculation is None:
                issue("missing_calculation", [*ep, "calculation"], cid)
            if evidence.reference not in candidate.supporting_references:
                issue("missing_supporting_reference", [*ep, "reference"], cid)
        if candidate.kind == "approved_metric" and candidate.calculation is None:
            issue("missing_calculation", [*path, "calculation"], cid)
        calculation_issues(candidate.calculation, [*path, "calculation"], cid)
        for j, origin in enumerate(candidate.origins):
            op = [*path, "origins", j]
            execution = executions.get(origin.execution_id)
            originals = (
                [c for c in execution.result.candidates if c.candidate_id == origin.candidate_id]
                if execution and execution.result
                else []
            )
            if len(originals) != 1 or execution.role != origin.role:
                issue("unresolved_candidate_origin", op, cid)
            # Evidence IDs are execution-local. Never match them globally or against
            # only the first origin's supporting_evidence_ids after M5 dedup.
            if originals and execution and execution.result:
                local = {e.evidence_id: e for e in execution.result.supporting_evidence}
                if any(
                    key not in local or local[key] not in origin.supporting_evidence
                    for key in originals[0].supporting_evidence_ids
                ):
                    issue("unresolved_origin_evidence", [*op, "supporting_evidence"], cid)
            for k, evidence in enumerate(origin.supporting_evidence):
                citations_issues(
                    evidence.citations, [*op, "supporting_evidence", k, "citations"], cid
                )
                calculation_issues(
                    evidence.calculation, [*op, "supporting_evidence", k, "calculation"], cid
                )
        for j, conflict_id in enumerate(candidate.conflict_ids):
            if conflict_id not in conflict_ids:
                issue("unresolved_conflict_reference", [*path, "conflict_ids", j], cid)
    for i, conflict in enumerate(source.conflicts):
        for j, cid in enumerate(conflict.candidate_ids):
            if cid not in candidate_ids:
                issue("unresolved_conflict_candidate", ["conflicts", i, "candidate_ids", j], cid)
    return batch
