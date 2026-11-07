"""Coordinate existing M6 checks and bounded revision on a fresh typed batch."""

from time import perf_counter

from .contracts import VerificationInput
from .evidence_critic import EvidenceCritic
from .financial_logic_critic import FinancialLogicCritic
from .ledger_contracts import VerificationHistory, VerificationProofContext
from .validators import DeterministicFinancialValidator
from .verification_loop import BoundedVerificationLoop


class VerificationRuntime:
    def __init__(self, catalog, gateway=None, *, model=None):
        self.validator = DeterministicFinancialValidator(catalog)
        self.evidence = EvidenceCritic(catalog, gateway, model=model)
        self.logic = FinancialLogicCritic(gateway, model=model)
        self.provider_metadata = []
        self.stage_latency_ms = {}

    @staticmethod
    def verify_document(candidates, builder, manifest, company_id, snapshot_id):
        from .document_verification import verify_document_claim

        return [
            verify_document_claim(c, builder, manifest, company_id, snapshot_id) for c in candidates
        ]

    def _checks(self, batch):
        def timed(name, call):
            start = perf_counter()
            value = call()
            self.stage_latency_ms[name] = (
                self.stage_latency_ms.get(name, 0) + (perf_counter() - start) * 1000
            )
            return value

        validation = timed("validators", lambda: self.validator.validate(batch))
        evidence = timed("evidence", lambda: self.evidence.assess(batch, validation))
        logic = timed("logic", lambda: self.logic.assess(batch, validation, evidence))
        for name, output in (("evidence", evidence), ("logic", logic)):
            for claim in output.claims:
                self.provider_metadata.append((name, claim.trace.llm))
        return VerificationProofContext(
            batch=batch, validation=validation, evidence=evidence, logic=logic
        )

    def verify(self, batch):
        batch = VerificationInput.model_validate_json(batch.model_dump_json())
        initial = self._checks(batch)
        histories = []
        loop = BoundedVerificationLoop()
        for claim in batch.claims:
            start = perf_counter()
            outcome = loop.start(
                batch,
                initial.validation,
                initial.evidence,
                initial.logic,
                candidate_id=claim.candidate_id,
            )
            contexts = [initial]
            if not outcome.stopped:
                revision = loop.propose(outcome)
                child = self._checks(revision.batch)
                contexts.append(child)
                outcome = loop.submit(
                    outcome, revision, child.validation, child.evidence, child.logic
                )
            self.stage_latency_ms["judge_revision"] = (
                self.stage_latency_ms.get("judge_revision", 0) + (perf_counter() - start) * 1000
            )
            histories.append(VerificationHistory(contexts=contexts, outcome=outcome))
        return histories
