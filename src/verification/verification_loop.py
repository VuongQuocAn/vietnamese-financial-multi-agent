"""One revision per original candidate; fresh upstream passes are supplied by caller."""

from copy import deepcopy

from .decision_contracts import RevisionInput, VerificationLoopResult
from .judge import VerificationJudge
from .validation_contracts import verification_input_digest


class BoundedVerificationLoop:
    """No providers, hidden rechecks, persistence or automatic recursive repairs.

    start -> proposal -> caller runs M6-02/03/04 -> submit -> terminal result.
    A rejected/stale submission consumes the single attempt and cannot ACCEPT.
    """

    def __init__(self):
        self._judge = VerificationJudge()
        self._consumed: set[tuple[str, str]] = set()

    def start(self, batch, validation, evidence, logic, *, candidate_id, **pairing):
        if (
            candidate_id.startswith("revision:")
            or (batch.source_result_sha256, candidate_id) in self._consumed
        ):
            raise ValueError("revision_budget_exhausted")
        result = self._judge.decide(batch, validation, evidence, logic, **pairing)
        matches = [c for c in result.claims if c.candidate_id == candidate_id]
        if len(matches) != 1:
            raise ValueError("one_original_candidate_required")
        record = matches[0]
        return VerificationLoopResult(
            parent_candidate_id=candidate_id,
            initial_input=deepcopy(batch),
            attempts=[record],
            stopped=record.decision != "REVISE",
            stop_reason=None if record.decision == "REVISE" else "initial_decision_terminal",
        )

    @staticmethod
    def propose(history):
        if history.stopped or len(history.attempts) != 1 or not history.final.revision:
            raise ValueError("revision_not_available_or_budget_exhausted")
        parent = history.final
        if (
            parent.candidate_id != history.parent_candidate_id
            or parent.trace.verification_input_sha256
            != verification_input_digest(history.initial_input)
            or parent.original_claim not in history.initial_input.claims
        ):
            raise ValueError("original_history_identity_mismatch")
        batch = history.initial_input.model_copy(deep=True)
        claim = parent.original_claim.model_copy(deep=True)
        proposal = parent.revision
        # Identity depends on original full input, exact proposal and policy trace.
        suffix = verification_input_digest(parent)[:24]
        claim.candidate_id = f"revision:{suffix}"
        claim.provenance.m5_candidate_id = claim.candidate_id
        claim.content, claim.kind = proposal.content, proposal.kind
        batch.claims = [claim]
        return RevisionInput(
            parent_candidate_id=parent.candidate_id,
            parent_decision_sha256=verification_input_digest(parent),
            batch=batch,
        )

    def submit(self, history, revision, validation, evidence, logic):
        key = (history.initial_input.source_result_sha256, history.parent_candidate_id)
        if history.stopped or len(history.attempts) != 1 or key in self._consumed:
            raise ValueError("revision_budget_exhausted")
        expected = self.propose(history)
        self._consumed.add(key)
        output = history.model_copy(deep=True)
        # Exact proposal equality protects source/snapshot/formula/caveats and
        # parent linkage without inventing a second source-validation layer.
        if revision != expected:
            checked = self._judge.decide(revision.batch, validation, evidence, logic)
            final = checked.claims[0] if checked.claims else history.final.model_copy(deep=True)
            final.decision = "ABSTAIN"
            final.reason_codes = ["revision_source_parent_or_proposal_mismatch"]
            final.unresolved_blockers.append(final.reason_codes[0])
            final.revision = None
            final.iteration_index = 1
            final.parent_candidate_id = history.parent_candidate_id
            output.attempts.append(final)
            output.revision_input = deepcopy(revision)
            output.stopped, output.stop_reason = True, "invalid_revision_submission"
            return output
        result = self._judge.decide(revision.batch, validation, evidence, logic)
        final = result.claims[0]
        final.iteration_index = 1
        final.parent_candidate_id = history.parent_candidate_id
        if final.decision == "REVISE":
            final.decision = "ABSTAIN"
            final.reason_codes.append("revision_budget_exhausted")
            final.unresolved_blockers.append("revision_budget_exhausted")
            final.revision = None
        output.attempts.append(final)
        output.revision_input = deepcopy(revision)
        output.stopped = True
        output.stop_reason = (
            "revised_claim_accepted" if final.decision == "ACCEPT" else "revision_budget_exhausted"
        )
        return output
