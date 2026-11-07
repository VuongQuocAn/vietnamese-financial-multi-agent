"""Typed proof bundles and source-bound verified entries for M7."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.specialist_common import ClaimKind
from ..evidence.retrieval import RetrievalReference
from .contracts import VerificationInput
from .decision_contracts import VerificationLoopResult
from .document_verification import DocumentVerificationHistory
from .evidence_contracts import EvidenceCriticResult
from .logic_contracts import FinancialLogicCriticResult
from .validation_contracts import ValidationResult


class VerificationProofContext(FinancialModel):
    """Exact saved inputs to Judge, including explicit legacy pairing when needed."""

    batch: VerificationInput
    validation: ValidationResult
    evidence: EvidenceCriticResult
    logic: FinancialLogicCriticResult
    validated_batch: VerificationInput | None = None
    evidence_batch: VerificationInput | None = None
    evidence_validation: ValidationResult | None = None

    def pairing(self):
        return {
            "validated_batch": self.validated_batch,
            "evidence_batch": self.evidence_batch,
            "evidence_validation": self.evidence_validation,
        }


class VerificationHistory(FinancialModel):
    contexts: list[VerificationProofContext] = Field(min_length=1, max_length=2)
    outcome: VerificationLoopResult


class VerifiedClaimIdentity(FinancialModel):
    verified_claim_id: str
    source_result_sha256: str
    original_candidate_id: str
    accepted_candidate_id: str
    parent_candidate_id: str | None
    company_id: str
    document_id: str
    snapshot_id: str
    period: str
    kind: ClaimKind
    content_sha256: str
    final_decision_sha256: str
    policy_version: str


class VerifiedClaim(FinancialModel):
    version: Literal["verified_claim_v1"] = "verified_claim_v1"
    identity: VerifiedClaimIdentity
    verification_status: Literal["verified"] = "verified"
    history: VerificationHistory
    payload_sha256: str

    @property
    def decision(self):
        return self.history.outcome.final

    @property
    def accepted_claim(self):
        # Preserve the complete typed M6 claim/calculation, with its pending status.
        return self.decision.original_claim

    @property
    def content(self):
        return self.accepted_claim.content

    @property
    def citations(self):
        return self.decision.supporting_citations

    @property
    def caveats(self):
        return self.decision.caveats


class VerifiedDocumentIdentity(VerifiedClaimIdentity):
    period: None = None
    kind: Literal["document"] = "document"
    composition_id: str
    composition_sha256: str


class VerifiedDocumentClaim(VerifiedClaim):
    version: Literal["verified_document_claim_v1"] = "verified_document_claim_v1"
    identity: VerifiedDocumentIdentity
    history: DocumentVerificationHistory

    @property
    def decision(self):
        return self.history.final


LedgerEntry = VerifiedDocumentClaim | VerifiedClaim


class LedgerAdmissionResult(FinancialModel):
    status: Literal["stored", "idempotent", "rejected"]
    verified_claim_id: str | None = None
    reason: str | None = None


class VerifiedClaimLedgerSnapshot(FinancialModel):
    version: Literal["verified_claim_ledger_v1"] = "verified_claim_ledger_v1"
    entries: list[LedgerEntry] = Field(default_factory=list)


class VerifiedClaimQuery(FinancialModel):
    company_id: str | None = None
    document_id: str | None = None
    snapshot_id: str | None = None
    period: str | None = None
    kind: ClaimKind | Literal["document"] | None = None
    composition_id: str | None = None
    composition_sha256: str | None = None
    canonical_item_id: str | None = None
    reference: RetrievalReference | None = None
    metric_id: str | None = None


class VerifiedClaimMatches(FinancialModel):
    status: Literal["matched", "empty"]
    claims: list[LedgerEntry] = Field(default_factory=list)
