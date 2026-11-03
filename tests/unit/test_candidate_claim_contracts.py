"""Synthetic handoff controls; persisted BBS conversion is evaluated separately."""

from copy import deepcopy
from typing import get_args

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.agents import PlannerContext, aggregate_candidates
from vietnamese_financial_multi_agent.agents.specialist_common import SpecialistCandidate
from vietnamese_financial_multi_agent.verification import (
    CandidateClaim,
    FindingKind,
    VerificationDecision,
    VerificationFinding,
    VerificationInput,
    to_verification_input,
)

from .test_orchestrator import inputs, metric_specialist, pipeline


@pytest.fixture(scope="module")
def original_result():
    p, s = inputs()
    instance, _, _, _ = pipeline(p, s, {"profitability": metric_specialist([])})
    return instance.run(question=p.question, context=PlannerContext(mode="deterministic"))


def test_metric_payload_roundtrip_pending_and_no_shared_mutation(original_result):
    source = original_result.model_copy(deep=True)
    before = source.model_dump_json()
    batch = to_verification_input(source)
    assert batch == to_verification_input(source)
    assert VerificationInput.model_validate_json(batch.model_dump_json()) == batch
    assert not batch.issues
    assert batch.source_plan_id == source.planner_result.plan.plan_id
    claim, original = batch.claims[0], source.candidates[0]
    assert claim.candidate_id == claim.provenance.m5_candidate_id == original.candidate_id
    assert claim.model_dump(include=set(SpecialistCandidate.model_fields)) == original.model_dump(
        include=set(SpecialistCandidate.model_fields)
    )
    assert claim.provenance.origins == original.origins
    assert claim.supporting_evidence == original.supporting_evidence
    assert claim.provenance.supporting_references == original.supporting_references
    # M5 fact_references include metric operands; retain them without making fact claims.
    assert len(batch.claims) == 1 and claim.kind == "approved_metric"
    assert all(e.kind == "metric" for e in claim.supporting_evidence)
    assert len(claim.calculation.trace.operands) == 2
    assert claim.calculation == original.calculation
    assert (
        claim.calculation.evidence.reviewed_lineage
        == original.calculation.evidence.reviewed_lineage
    )
    assert claim.verification_status == batch.verification_status == "pending"
    assert claim.decision is None and claim.findings == [] and not claim.financial_fact_verified
    batch.context.company_id = "consumer-edit"
    claim.provenance.origins[0].supporting_evidence[0].caveats.append("consumer-edit")
    claim.calculation.trace.operands.clear()
    assert source.model_dump_json() == before


def test_partial_multiple_origins_with_local_ids_and_conflicts_preserved(original_result):
    source = original_result.model_copy(deep=True)
    first = source.specialist_executions[0]
    duplicate = first.model_copy(deep=True)
    duplicate.execution_id, duplicate.role = "other-execution", "liquidity_and_leverage"
    duplicate.result.candidates[0].candidate_id = "other-local-candidate"
    duplicate.result.supporting_evidence[0].evidence_id = "E099"
    duplicate.result.candidates[0].supporting_evidence_ids = ["E099"]
    competing = first.model_copy(deep=True)
    competing.execution_id = "competing-execution"
    competing.result.candidates[0].content = "Synthetic conflicting proposition"
    source.specialist_executions = [first, duplicate, competing]
    source.candidates, source.conflicts = aggregate_candidates(source.specialist_executions)
    source.status, source.missing_evidence = "partial", ["missing-CFO"]
    source.caveats = ["reporting_scope_unresolved", "usable_with_caveat", "D03-B10"]
    before = deepcopy(source)
    batch = to_verification_input(source)
    assert batch.orchestration_status == "partial" and len(batch.claims) == 2
    assert batch.conflicts == source.conflicts and len(batch.conflicts) == 1
    assert batch.missing_evidence == source.missing_evidence
    assert batch.caveats == source.caveats and not batch.issues
    origins = batch.claims[0].provenance.origins
    assert len(origins) == 2
    assert origins[1].candidate_id == "other-local-candidate"
    assert origins[1].supporting_evidence[0].evidence_id == "E099"
    assert origins[0].supporting_evidence[0].evidence_id != "E099"
    assert batch.conflicts[0].candidate_ids == [c.candidate_id for c in batch.claims]
    assert all(c.decision is None and c.provenance.conflict_ids for c in batch.claims)
    assert source == before


@pytest.mark.parametrize(
    "status", ["blocked", "failed", "abstained", "unsupported", "clarification_required", "partial"]
)
def test_no_claims_are_manufactured_from_upstream_steps(status, original_result):
    source = original_result.model_copy(deep=True)
    source.status, source.candidates, source.conflicts = status, [], []
    source.missing_evidence, source.stop_conditions = ["missing-evidence"], ["stop"]
    batch = to_verification_input(source)
    assert batch.claims == [] and batch.orchestration_status == status
    assert batch.missing_evidence == ["missing-evidence"] and batch.stop_conditions == ["stop"]
    assert not batch.financial_fact_verified


def test_incomplete_evidence_retained_as_issues_and_malformed_contract_rejected(original_result):
    source = original_result.model_copy(deep=True)
    original = source.candidates[0]
    original.citations = []
    original.supporting_evidence[0].citations[0].anchor_id = None
    original.supporting_evidence[0].citations[0].pdf_page = 999
    original.supporting_evidence[0].calculation.trace = None
    original.calculation = None
    original.conflict_ids.append("missing-conflict")
    before = source.model_dump_json()
    batch = to_verification_input(source)
    assert batch.claims[0].citations == [] and batch.claims[0].calculation is None
    assert batch.claims[0].supporting_evidence == original.supporting_evidence
    assert {issue.code for issue in batch.issues} >= {
        "missing_citations",
        "missing_calculation",
        "incomplete_citation_metadata",
        "inconsistent_citation_metadata",
        "incomplete_calculation_payload",
        "unresolved_conflict_reference",
    }
    assert source.model_dump_json() == before
    original.supporting_evidence[0].reference.record_id = None
    with pytest.raises(ValidationError, match="Reference kind/identity mismatch"):
        to_verification_input(source)


def test_finding_decision_and_claim_kind_are_distinct(original_result):
    claim = to_verification_input(original_result).claims[0]
    for decision in get_args(VerificationDecision):
        with pytest.raises(ValidationError):
            CandidateClaim.model_validate({**claim.model_dump(), "decision": decision})
    for field, value in [("financial_fact_verified", True), ("verification_status", "verified")]:
        with pytest.raises(ValidationError):
            CandidateClaim.model_validate({**claim.model_dump(), field: value})
    for kind in get_args(FindingKind):
        finding = VerificationFinding(
            finding_id="finding-1", candidate_ids=[claim.candidate_id], kind=kind, message=kind
        )
        assert VerificationFinding.model_validate_json(finding.model_dump_json()) == finding
        with pytest.raises(ValidationError):
            CandidateClaim.model_validate({**claim.model_dump(), "kind": kind})
    with pytest.raises(ValidationError, match="candidate_identity_must_match_m5"):
        CandidateClaim.model_validate({**claim.model_dump(), "candidate_id": "new-random-id"})
