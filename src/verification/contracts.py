"""M6 handoff contracts; representation never certifies a financial claim."""

from typing import Literal

from pydantic import Field, model_validator

from ..accounting.contracts import FinancialModel
from ..agents.contracts import RiskSignal, SpecialistRole
from ..agents.orchestration_contracts import CandidateConflict, CandidateOrigin, OrchestrationError
from ..agents.planner_contracts import PlannerContext
from ..agents.routing_contracts import RoutingRequirement
from ..agents.specialist_common import SpecialistCandidate, SpecialistEvidence
from ..evidence.retrieval import RetrievalReference

# Reuse the full M5 payload, including typed M4 calculation/lineage and source caveats.
VerificationEvidence = SpecialistEvidence

VerificationDecision = Literal["ACCEPT", "REVISE", "INVESTIGATE", "ABSTAIN"]
FindingKind = Literal[
    "numeric_value_mismatch",
    "formula_calculation_mismatch",
    "context_scope_snapshot_mismatch",
    "missing_evidence",
    "unsupported_inference",
    "conflicting_candidates",
    "source_quality_limitation",
]


class VerificationFinding(FinancialModel):
    """Vocabulary for later validators/critics; the adapter produces no findings."""

    finding_id: str
    candidate_ids: list[str]
    kind: FindingKind
    message: str
    references: list[RetrievalReference] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)


class ConversionIssue(FinancialModel):
    """Structural handoff issue, separate from financial findings and decisions."""

    code: str
    path: list[str | int]
    candidate_id: str | None = None


class ClaimProvenance(FinancialModel):
    m5_candidate_id: str
    origins: list[CandidateOrigin]
    origin_roles: list[SpecialistRole]
    supporting_references: list[RetrievalReference]
    conflict_ids: list[str] = Field(default_factory=list)


class CandidateClaim(SpecialistCandidate):
    """Original M5 proposition/status plus explicit pending M6 state."""

    provenance: ClaimProvenance
    supporting_evidence: list[VerificationEvidence]
    verification_status: Literal["pending"] = "pending"
    decision: None = None
    findings: list[VerificationFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def stable_m5_identity(self):
        if not self.candidate_id or self.candidate_id != self.provenance.m5_candidate_id:
            raise ValueError("candidate_identity_must_match_m5")
        return self


class VerificationInput(FinancialModel):
    version: Literal["candidate_claim_batch_v1"] = "candidate_claim_batch_v1"
    source_version: Literal["financial_multi_agent_orchestration_v1"]
    # Digest identifies the exact serialized M5 result; no new random identity.
    source_result_sha256: str
    source_plan_id: str | None = None
    question: str
    context: PlannerContext
    orchestration_status: Literal[
        "completed",
        "partial",
        "blocked",
        "failed",
        "clarification_required",
        "unsupported",
        "abstained",
    ]
    claims: list[CandidateClaim] = Field(default_factory=list)
    conflicts: list[CandidateConflict] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    uncovered_requirements: list[RoutingRequirement] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    errors: list[OrchestrationError] = Field(default_factory=list)
    issues: list[ConversionIssue] = Field(default_factory=list)
    verification_status: Literal["pending"] = "pending"
    financial_fact_verified: Literal[False] = False
