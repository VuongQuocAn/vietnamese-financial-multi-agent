"""Synthetic policy/repository tests. Real-source coverage belongs to the evaluator."""

import json

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.verification import (
    BoundedVerificationLoop,
    LedgerConflict,
    VerificationHistory,
    VerificationProofContext,
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)

from .test_verification_judge import case, passes


def history_for(*, metric=False, revise=False):
    data, batch, validation, evidence, logic = case(metric=metric, numeric_fail=revise)
    context = VerificationProofContext(
        batch=batch, validation=validation, evidence=evidence, logic=logic
    )
    loop = BoundedVerificationLoop()
    outcome = loop.start(
        batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
    )
    contexts = [context]
    if revise:
        revision = loop.propose(outcome)
        validation, evidence, logic = passes(data, revision.batch)
        contexts.append(
            VerificationProofContext(
                batch=revision.batch, validation=validation, evidence=evidence, logic=logic
            )
        )
        outcome = loop.submit(outcome, revision, validation, evidence, logic)
    return VerificationHistory(contexts=contexts, outcome=outcome)


@pytest.mark.parametrize("metric,revise", [(False, False), (True, False), (True, True)])
def test_admission_restart_exact_provenance_and_read_only_queries(tmp_path, metric, revise):
    history = history_for(metric=metric, revise=revise)
    original = history.model_dump_json()
    repository = VerifiedClaimRepository(tmp_path)
    result = repository.admit(history)
    assert result.status == "stored"
    assert repository.admit(history).status == "idempotent"
    restarted = VerifiedClaimRepository(tmp_path)
    entry = restarted.get(result.verified_claim_id)
    assert entry.history == history and history.model_dump_json() == original
    assert entry.accepted_claim == history.outcome.final.original_claim
    assert entry.accepted_claim.verification_status == "pending"
    assert entry.verification_status == "verified"
    assert entry.caveats == history.outcome.final.caveats and entry.caveats
    assert entry.citations == history.outcome.final.supporting_citations
    claim = entry.accepted_claim
    query = VerifiedClaimQuery(
        company_id=claim.company_id,
        document_id=claim.document_id,
        snapshot_id=claim.snapshot_id,
        period=claim.period,
        kind=claim.kind,
        reference=claim.fact_references[0],
        metric_id=claim.metric_ids[0] if metric else None,
        canonical_item_id=claim.supporting_evidence[0].canonical_item_id,
    )
    ledger = VerifiedClaimLedger(restarted)
    assert ledger.find_claims(query).claims == [entry]
    if metric:
        lineage = claim.calculation.evidence.reviewed_lineage.lineage
        item_id = lineage.operands[0].observations[0].canonical_item_id
        assert ledger.find_claims(VerifiedClaimQuery(canonical_item_id=item_id)).claims == [entry]
    assert ledger.find_claims(VerifiedClaimQuery(canonical_item_id="absent")).status == "empty"
    assert restarted.list_by_document(claim.document_id, claim.snapshot_id) == [entry]
    assert ledger.find_claims(VerifiedClaimQuery(snapshot_id="absent")).status == "empty"
    assert restarted.get("missing") is None
    # Retrieval returns detached objects; caller mutation cannot alter persistence.
    entry.accepted_claim.content = "changed"
    assert (
        restarted.get(result.verified_claim_id).content
        == history.outcome.final.original_claim.content
    )
    if revise:
        stored = restarted.list_all()
        assert len(stored) == 1 and stored[0].identity.parent_candidate_id
        assert stored[0].identity.accepted_candidate_id != stored[0].identity.original_candidate_id
        assert stored[0].history.outcome.attempts[0].decision == "REVISE"


@pytest.mark.parametrize(
    "mutation",
    [
        "decision",
        "content",
        "source",
        "snapshot",
        "caveat",
        "stale",
        "metric",
        "parent",
        "revision_source",
        "missing_final",
        "parent_decision",
        "attempt",
    ],
)
def test_tampered_or_stale_proof_cannot_store(tmp_path, mutation):
    revised = mutation in {
        "parent",
        "revision_source",
        "missing_final",
        "parent_decision",
        "attempt",
    }
    history = history_for(metric=True, revise=revised)
    final = history.outcome.final
    if mutation == "decision":
        history = history_for(metric=True, revise=True)
        history.contexts = history.contexts[:1]
        history.outcome.attempts = history.outcome.attempts[:1]
        history.outcome.final.decision = "ACCEPT"
    elif mutation == "content":
        final.original_claim.content += " altered"
    elif mutation == "source":
        ref = final.original_claim.fact_references[0]
        ref.observation = ref.observation.model_copy(update={"local_id": "other"})
    elif mutation == "snapshot":
        final.original_claim.snapshot_id = "other"
    elif mutation == "caveat":
        final.caveats = []
    elif mutation == "stale":
        history.contexts[0].logic.evidence_result_sha256 = "0" * 64
    elif mutation == "metric":
        final.original_claim.calculation.formula_digest = "altered"
    elif mutation == "parent":
        history.outcome.revision_input.parent_candidate_id = "other"
    elif mutation == "revision_source":
        history.contexts[1].batch.claims[0].snapshot_id = "other"
    elif mutation == "missing_final":
        history.contexts.pop()
    elif mutation == "parent_decision":
        history.outcome.attempts[0].caveats = []
    elif mutation == "attempt":
        final.iteration_index = 0
    repository = VerifiedClaimRepository(tmp_path)
    assert repository.admit(history).status == "rejected"
    assert repository.list_all() == []


def test_unfinished_revise_rejected_and_missing_context_is_contract_error(tmp_path):
    history = history_for(revise=True)
    history.contexts = history.contexts[:1]
    history.outcome.attempts = history.outcome.attempts[:1]
    history.outcome.revision_input = None
    history.outcome.stopped = False
    history.outcome.stop_reason = None
    assert VerifiedClaimRepository(tmp_path).admit(history).status == "rejected"
    with pytest.raises(ValidationError):
        VerificationHistory(contexts=[], outcome=history.outcome)


def test_same_identity_different_payload_conflict_never_overwrites(tmp_path):
    history = history_for()
    repository = VerifiedClaimRepository(tmp_path)
    result = repository.admit(history)
    before = (tmp_path / "verified-claims.json").read_bytes()
    # Redundant pairing does not change a modern Judge decision, but changes proof payload.
    context = history.contexts[0]
    context.validated_batch = context.batch.model_copy(deep=True)
    with pytest.raises(LedgerConflict):
        repository.admit(history)
    assert (tmp_path / "verified-claims.json").read_bytes() == before
    assert repository.get(result.verified_claim_id)


def test_atomic_batch_mixed_decisions_duplicates_and_conflict(tmp_path):
    valid = history_for(metric=True)
    pending = history_for(revise=True)
    pending.contexts = pending.contexts[:1]
    pending.outcome.attempts = pending.outcome.attempts[:1]
    pending.outcome.revision_input = None
    pending.outcome.stopped, pending.outcome.stop_reason = False, None
    repository = VerifiedClaimRepository(tmp_path)
    results = repository.admit_many([valid, pending, valid])
    assert [r.status for r in results] == ["stored", "rejected", "idempotent"]
    before = (tmp_path / "verified-claims.json").read_bytes()
    altered = valid.model_copy(deep=True)
    altered.contexts[0].validated_batch = altered.contexts[0].batch.model_copy(deep=True)
    with pytest.raises(LedgerConflict):
        repository.admit_many([history_for(), altered])
    assert (tmp_path / "verified-claims.json").read_bytes() == before


@pytest.mark.parametrize("mutation", ["duplicate", "payload", "malformed", "forged_rehashed"])
def test_malformed_or_tampered_snapshot_fails_closed(tmp_path, mutation):
    history = history_for()
    repository = VerifiedClaimRepository(tmp_path)
    repository.admit(history)
    path = tmp_path / "verified-claims.json"
    wire = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "duplicate":
        wire["entries"].append(wire["entries"][0])
    elif mutation == "payload":
        wire["entries"][0]["payload_sha256"] = "0" * 64
    elif mutation == "malformed":
        wire["version"] = "unknown"
    else:
        # Even recomputing the non-secret checksum cannot replace decision replay.
        from vietnamese_financial_multi_agent.verification import VerifiedClaim
        from vietnamese_financial_multi_agent.verification.validation_contracts import (
            verification_input_digest,
        )

        entry = VerifiedClaim.model_validate_json(json.dumps(wire["entries"][0]))
        entry.decision.original_claim.content = "forged"
        entry.payload_sha256 = ""
        entry.payload_sha256 = verification_input_digest(entry)
        wire["entries"][0] = entry.model_dump(mode="json")
    path.write_text(json.dumps(wire), encoding="utf-8")
    # Reusing a repository must not let its validated digest cache hide tampering.
    with pytest.raises(ValueError):
        repository.list_all()
    with pytest.raises(ValueError):
        VerifiedClaimLedger(VerifiedClaimRepository(tmp_path)).find_claims(VerifiedClaimQuery())
