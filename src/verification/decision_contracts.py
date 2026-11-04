"""Source-bound verification decisions; no ledger or changes to pending claims."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.orchestration_contracts import CandidateConflict
from ..agents.specialist_common import ClaimKind
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from .contracts import CandidateClaim, VerificationDecision, VerificationInput
from .evidence_contracts import ClaimEvidenceAssessment
from .logic_contracts import ClaimLogicAssessment
from .validation_contracts import ClaimValidationResult

DECISION_POLICY_VERSION = "verification_decisions_v1"
RERUN_CHECKS = ["M6-02", "M6-03", "M6-04"]


class DecisionError(FinancialModel):
    code: str
    candidate_id: str | None = None


class RevisionProposal(FinancialModel):
    parent_candidate_id: str
    reason_codes: list[str]
    supported_portions: list[str]
    unsupported_portions: list[str]
    content: str
    kind: ClaimKind
    required_reruns: list[str] = Field(default_factory=lambda: list(RERUN_CHECKS))


class InvestigationRequirement(FinancialModel):
    reason_code: str
    action: str
    recheck_condition: str
    references: list[RetrievalReference] = Field(default_factory=list)


class VerificationDecisionTrace(FinancialModel):
    source_result_sha256: str
    verification_input_sha256: str
    validation_result_sha256: str
    evidence_result_sha256: str
    logic_result_sha256: str
    policy_version: Literal["verification_decisions_v1"] = DECISION_POLICY_VERSION
    required_checks: list[str] = Field(default_factory=list)
    passed_gates: list[str] = Field(default_factory=list)
    legacy_pairing: bool = False


class VerificationDecisionRecord(FinancialModel):
    candidate_id: str
    original_claim: CandidateClaim
    decision: VerificationDecision
    reason_codes: list[str]
    supporting_references: list[RetrievalReference] = Field(default_factory=list)
    supporting_citations: list[EvidenceCitation] = Field(default_factory=list)
    validation: ClaimValidationResult | None = None
    evidence: ClaimEvidenceAssessment | None = None
    logic: ClaimLogicAssessment | None = None
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    unresolved_blockers: list[str] = Field(default_factory=list)
    revision: RevisionProposal | None = None
    investigations: list[InvestigationRequirement] = Field(default_factory=list)
    errors: list[DecisionError] = Field(default_factory=list)
    trace: VerificationDecisionTrace
    iteration_index: Literal[0, 1] = 0
    parent_candidate_id: str | None = None


class VerificationDecisionResult(FinancialModel):
    version: Literal["verification_decision_result_v1"] = "verification_decision_result_v1"
    trace: VerificationDecisionTrace
    claims: list[VerificationDecisionRecord] = Field(default_factory=list)
    conflicts: list[CandidateConflict] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    errors: list[DecisionError] = Field(default_factory=list)


class RevisionInput(FinancialModel):
    """Child identity/parent link outside the accepted M6-01 input contract.

    The child has a new candidate ID; the original M5 provenance remains in
    attempt 0, and origins/references are preserved in the child input.
    """

    parent_candidate_id: str
    parent_decision_sha256: str
    batch: VerificationInput


class VerificationLoopResult(FinancialModel):
    parent_candidate_id: str
    initial_input: VerificationInput
    attempts: list[VerificationDecisionRecord] = Field(min_length=1, max_length=2)
    revision_input: RevisionInput | None = None
    stopped: bool = False
    stop_reason: str | None = None

    @property
    def final(self) -> VerificationDecisionRecord:
        return self.attempts[-1]
