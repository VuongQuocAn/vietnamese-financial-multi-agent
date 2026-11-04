"""Admission replays the existing deterministic policy; retrieval never generates facts."""

import hashlib

from .ledger_contracts import (
    VerificationHistory,
    VerifiedClaim,
    VerifiedClaimIdentity,
    VerifiedClaimMatches,
    VerifiedClaimQuery,
)
from .validation_contracts import verification_input_digest
from .verification_loop import BoundedVerificationLoop


class LedgerAdmissionError(ValueError):
    pass


def replay_history(history: VerificationHistory):
    """Reproduce the complete direct/one-child outcome from saved upstream results."""
    history = VerificationHistory.model_validate_json(history.model_dump_json())
    contexts, supplied = history.contexts, history.outcome
    if len(contexts) != len(supplied.attempts):
        raise LedgerAdmissionError("missing_or_extra_verification_context")
    initial = contexts[0]
    loop = BoundedVerificationLoop()
    try:
        expected = loop.start(
            initial.batch,
            initial.validation,
            initial.evidence,
            initial.logic,
            candidate_id=supplied.parent_candidate_id,
            **initial.pairing(),
        )
        if len(contexts) == 2:
            child = contexts[1]
            revision = loop.propose(expected)
            if supplied.revision_input != revision or child.batch != revision.batch:
                raise LedgerAdmissionError("revision_proof_or_source_mismatch")
            # submit uses fresh non-legacy results; no caller pairing overrides.
            if any(value is not None for value in child.pairing().values()):
                raise LedgerAdmissionError("revision_requires_fresh_verification")
            expected = loop.submit(
                expected, revision, child.validation, child.evidence, child.logic
            )
    except ValueError as error:
        raise LedgerAdmissionError(str(error)) from error
    if expected != supplied:
        raise LedgerAdmissionError("decision_history_does_not_match_policy_replay")
    if expected.final.decision != "ACCEPT":
        raise LedgerAdmissionError("final_decision_is_not_accept")
    return history


def build_verified_claim(history: VerificationHistory) -> VerifiedClaim:
    history = replay_history(history)
    outcome = history.outcome
    final, original = outcome.final, outcome.attempts[0]
    claim = final.original_claim
    fields = dict(
        source_result_sha256=original.trace.source_result_sha256,
        original_candidate_id=original.candidate_id,
        accepted_candidate_id=claim.candidate_id,
        parent_candidate_id=final.parent_candidate_id,
        company_id=claim.company_id,
        document_id=claim.document_id,
        snapshot_id=claim.snapshot_id,
        period=claim.period,
        kind=claim.kind,
        content_sha256=hashlib.sha256(claim.content.encode("utf-8")).hexdigest(),
        final_decision_sha256=verification_input_digest(final),
        policy_version=final.trace.policy_version,
    )
    seed = VerifiedClaimIdentity(verified_claim_id="", **fields)
    identity = seed.model_copy(
        update={"verified_claim_id": "verified:" + verification_input_digest(seed)}
    )
    entry = VerifiedClaim(identity=identity, history=history, payload_sha256="")
    entry.payload_sha256 = verification_input_digest(entry)
    return entry


def validate_entry(entry: VerifiedClaim):
    if build_verified_claim(entry.history) != entry:
        raise LedgerAdmissionError("ledger_payload_or_identity_mismatch")


class VerifiedClaimLedger:
    """M7 read-only facade. All matches retain their individual source identities."""

    def __init__(self, repository):
        self._repository = repository

    def find_claims(self, query: VerifiedClaimQuery) -> VerifiedClaimMatches:
        claims = self._repository.query(query)
        return VerifiedClaimMatches(status="matched" if claims else "empty", claims=claims)
