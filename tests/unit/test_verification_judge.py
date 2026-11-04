"""Decision policy and bounded re-verification; synthetic fixtures, no live calls."""

import pytest
from vietnamese_financial_multi_agent.agents.orchestration_contracts import CandidateConflict
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification import (
    BoundedVerificationLoop,
    DeterministicFinancialValidator,
    EvidenceCritic,
    FinancialLogicCritic,
    VerificationDecisionResult,
    VerificationJudge,
    VerificationLoopResult,
)
from vietnamese_financial_multi_agent.verification.validation_contracts import (
    validation_result_digest,
    verification_input_digest,
)

from .test_financial_validators import batch_for
from .test_m4_execution import fixture


def passes(data, batch):
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    evidence = EvidenceCritic(catalog).assess(batch, validation)
    logic = FinancialLogicCritic().assess(batch, validation, evidence)
    return validation, evidence, logic


def case(*, metric=False, tail="", numeric_fail=False):
    data = fixture()
    batch = batch_for(data, metric=metric)
    if numeric_fail:
        content = batch.claims[0].content
        batch.claims[0].content = (
            content[: content.index(" là ")] + " là 999,00" + ("%." if metric else " VND.")
        )
    if tail:
        batch.claims[0].kind = "supported_interpretation"
        batch.claims[0].content += " " + tail
    return data, batch, *passes(data, batch)


@pytest.mark.parametrize("metric", [False, True])
def test_positive_numeric_acceptance_is_deterministic_read_only_with_caveats(metric):
    _, batch, validation, evidence, logic = case(metric=metric)
    before = [x.model_dump_json() for x in (batch, validation, evidence, logic)]
    judge = VerificationJudge()
    result = judge.decide(batch, validation, evidence, logic)
    record = result.claims[0]
    assert record.decision == "ACCEPT", record
    assert all(a.status == "not_applicable" for a in logic.claims[0].assertions)
    assert record.caveats and record.original_claim == batch.claims[0]
    assert record.validation == validation.claims[0] and record.evidence == evidence.claims[0]
    assert record.logic == logic.claims[0] and record.supporting_citations
    assert result == judge.decide(batch, validation, evidence, logic)
    assert VerificationDecisionResult.model_validate_json(result.model_dump_json()) == result
    assert [x.model_dump_json() for x in (batch, validation, evidence, logic)] == before


@pytest.mark.parametrize("metric", [False, True])
def test_exact_numeric_mismatch_revises_without_replacing_sources(metric):
    _, batch, validation, evidence, logic = case(metric=metric, numeric_fail=True)
    record = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert record.decision == "REVISE", record
    assert record.revision.reason_codes == ["exact_canonical_numeric_correction"]
    assert "999" not in record.revision.content
    assert record.original_claim.content == batch.claims[0].content
    assert record.revision.required_reruns == ["M6-02", "M6-03", "M6-04"]


@pytest.mark.parametrize(
    "tail",
    [
        "Hiệu quả kinh doanh cải thiện rõ rệt.",
        "Do chi phí giảm nên lợi nhuận tăng.",
        "CFO dương chứng tỏ chất lượng lợi nhuận cao.",
    ],
)
def test_unassessed_or_unsupported_conclusion_keeps_only_supported_prefix(tail):
    _, batch, validation, evidence, logic = case(metric=True, tail=tail)
    record = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert record.decision == "REVISE", record
    assert tail in record.revision.unsupported_portions
    assert tail not in record.revision.content
    assert record.revision.kind == "approved_metric"
    assert not record.original_claim.decision


@pytest.mark.parametrize(
    "mutation",
    [
        "batch",
        "validation",
        "evidence",
        "logic_digest",
        "source",
        "candidate_ids",
        "logic_content",
        "assertion_id",
        "assertion_checks",
        "reasoning_not_applicable",
    ],
)
def test_stale_or_malformed_identity_never_accepts_and_returns_structured_error(mutation):
    _, batch, validation, evidence, logic = case()
    if mutation == "batch":
        batch.claims[0].content += " changed"
    elif mutation == "validation":
        validation.claims[0].checks[0].reason_code = "changed"
    elif mutation == "evidence":
        evidence.claims[0].content += " changed"
    elif mutation == "logic_digest":
        logic.evidence_result_sha256 = "bad"
    elif mutation == "source":
        batch.source_result_sha256 = "bad"
    elif mutation == "candidate_ids":
        logic.claims[0].candidate_id = "other"
    elif mutation == "logic_content":
        logic.claims[0].content = "other"
    elif mutation == "assertion_id":
        logic.claims[0].assertions[0].assertion_id = "other"
    elif mutation == "assertion_checks":
        logic.claims[0].assertions[0].validation_checks = []
    else:
        _, batch, validation, evidence, logic = case(metric=True, tail="Doanh thu tăng.")
        logic.claims[0].assertions[-1].status = "not_applicable"
        logic.claims[0].errors = []
    record = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert record.decision == "INVESTIGATE" and record.errors


def test_legacy_requires_original_pairing_and_never_modifies_artifacts():
    _, batch, validation, evidence, _ = case()
    validation.verification_input_sha256 = None
    evidence.verification_input_sha256 = None
    evidence.validation_result_sha256 = None
    pairing = dict(validated_batch=batch, evidence_batch=batch, evidence_validation=validation)
    logic = FinancialLogicCritic().assess(batch, validation, evidence, **pairing)
    judge = VerificationJudge()
    assert judge.decide(batch, validation, evidence, logic).claims[0].decision == "INVESTIGATE"
    record = judge.decide(batch, validation, evidence, logic, **pairing).claims[0]
    assert record.decision == "ACCEPT" and record.trace.legacy_pairing
    assert (
        validation.verification_input_sha256 is None and evidence.validation_result_sha256 is None
    )


def test_partial_mixed_batch_is_decided_per_candidate_and_conflicts_have_no_winner():
    data, batch, *_ = case()
    original = batch.claims[0]
    for cid in ("C2", "C3"):
        child = original.model_copy(deep=True)
        child.candidate_id = child.provenance.m5_candidate_id = cid
        child.provenance.conflict_ids = ["conflict-1"]
        batch.claims.append(child)
    batch.conflicts = [CandidateConflict(conflict_id="conflict-1", candidate_ids=["C2", "C3"])]
    batch.orchestration_status = "partial"
    result = VerificationJudge().decide(batch, *passes(data, batch))
    assert [c.decision for c in result.claims] == ["ACCEPT", "INVESTIGATE", "INVESTIGATE"]
    assert result.conflicts == batch.conflicts


@pytest.mark.parametrize("mutation", ["formula", "numeric", "missing_numeric", "quality"])
def test_all_required_occurrences_must_pass_no_pass_override(mutation):
    _, batch, validation, evidence, _ = case(metric=True)
    if mutation == "missing_numeric":
        validation.claims[0].checks = [
            c for c in validation.claims[0].checks if c.check_id != "numeric"
        ]
    else:
        check = next(c for c in validation.claims[0].checks if c.check_id == mutation).model_copy(
            deep=True
        )
        check.finding_id += "extra"
        check.status = "fail" if mutation != "quality" else "undetermined"
        validation.claims[0].checks.insert(0, check)
    evidence.validation_result_sha256 = validation_result_digest(validation)
    evidence.claims[0].deterministic_findings = validation.claims[0].checks
    logic = FinancialLogicCritic().assess(batch, validation, evidence)
    result = VerificationJudge().decide(batch, validation, evidence, logic)
    assert result.claims[0].decision != "ACCEPT"


def test_no_sources_no_safe_recovery_abstains():
    data, batch, *_ = case()
    claim = batch.claims[0]
    claim.content = "Doanh nghiệp chắc chắn thịnh vượng."
    claim.kind = "supported_interpretation"
    claim.fact_references = claim.provenance.supporting_references = []
    claim.supporting_evidence = []
    claim.supporting_evidence_ids = []
    claim.citations = []
    record = VerificationJudge().decide(batch, *passes(data, batch)).claims[0]
    assert record.decision == "ABSTAIN"


@pytest.mark.parametrize(
    "scenario",
    ["fresh", "stale", "still_failing", "source_change", "parent_change", "caveat_removed"],
)
def test_bounded_revision_requires_fresh_pass_exact_sources_parent_and_caveats(scenario):
    data, batch, validation, evidence, logic = case(
        metric=True, tail="Hiệu quả kinh doanh cải thiện."
    )
    loop = BoundedVerificationLoop()
    history = loop.start(
        batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
    )
    revision = loop.propose(history)
    assert revision.batch.claims[0].candidate_id != history.parent_candidate_id
    assert revision.parent_candidate_id == history.parent_candidate_id
    assert revision.batch.claims[0].provenance.origins == batch.claims[0].provenance.origins
    if scenario == "source_change":
        revision.batch.claims[0].snapshot_id = "other"
    elif scenario == "parent_change":
        revision.parent_candidate_id = "other"
    elif scenario == "caveat_removed":
        revision.batch.claims[0].caveats.append("changed")
    fresh = passes(data, revision.batch)
    if scenario == "stale":
        fresh = (validation, evidence, logic)
    elif scenario == "still_failing":
        # Real new checks from a catalog with a missing fact; no fake PASS reuse.
        data["facts"] = []
        fresh = passes(data, revision.batch)
    final = loop.submit(history, revision, *fresh)
    assert final.stopped and len(final.attempts) == 2
    assert (
        final.final.iteration_index == 1
        and final.final.parent_candidate_id == history.parent_candidate_id
    )
    assert (final.final.decision == "ACCEPT") == (scenario == "fresh")
    assert VerificationLoopResult.model_validate_json(final.model_dump_json()) == final
    assert not history.stopped and len(history.attempts) == 1
    with pytest.raises(ValueError, match="budget_exhausted"):
        loop.submit(final, revision, *fresh)
    with pytest.raises(ValueError, match="budget_exhausted"):
        loop.submit(history, revision, *fresh)
    with pytest.raises(ValueError, match="budget_exhausted"):
        loop.start(batch, validation, evidence, logic, candidate_id=history.parent_candidate_id)


def test_child_digest_is_fresh_even_with_same_source_and_budget_never_recurses():
    data, batch, validation, evidence, logic = case(numeric_fail=True)
    loop = BoundedVerificationLoop()
    history = loop.start(
        batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
    )
    child = loop.propose(history)
    fresh = passes(data, child.batch)
    assert child.batch.source_result_sha256 == batch.source_result_sha256
    assert verification_input_digest(child.batch) != verification_input_digest(batch)
    assert fresh[0].verification_input_sha256 != validation.verification_input_sha256
    result = loop.submit(history, child, *fresh)
    assert result.final.decision == "ACCEPT" and result.final.original_claim != batch.claims[0]
