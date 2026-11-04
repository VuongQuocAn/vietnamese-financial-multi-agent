"""Evidence support annotations, independent of later verification decisions."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.orchestration_contracts import CandidateConflict
from ..agents.planner_contracts import PlannerLLMMetadata
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from .validation_contracts import ValidationCheck

SupportStatus = Literal["supported", "partially_supported", "unsupported", "insufficient_evidence"]
SemanticReason = Literal[
    "direct_support", "partial_support", "contradicted", "beyond_evidence", "missing_evidence"
]


class SemanticAssertionAssessment(FinancialModel):
    # No generated prose, financial values, formulas, citations or quality overrides.
    assertion_id: str
    status: SupportStatus
    evidence_ids: list[str]
    reason: SemanticReason
    missing: list[Literal["comparison", "causal_evidence", "source_content", "financial_context"]]


class SemanticEvidenceAssessment(FinancialModel):
    candidate_id: str
    assertions: list[SemanticAssertionAssessment] = Field(min_length=1, max_length=16)


class EvidenceCriticError(FinancialModel):
    stage: Literal["consistency", "retrieval", "semantic", "assessment"]
    code: str
    candidate_id: str | None = None


class EvidenceContext(FinancialModel):
    evidence_id: str
    reference: RetrievalReference
    document_id: str | None
    snapshot_id: str | None
    period: str | None = None
    reporting_scope: str | None = None
    reporting_scope_status: str | None = None
    citations: list[EvidenceCitation]
    # Source-derived projection only, bounded before sending to the Gateway.
    content: dict = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)
    available: bool = False


class EvidenceSupportFinding(FinancialModel):
    assertion_id: str
    content: str
    status: SupportStatus
    evidence_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    check_references: list[str] = Field(default_factory=list)


class EvidenceCriticTrace(FinancialModel):
    deterministic_latency_ms: float = 0
    semantic_latency_ms: float = 0
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    semantic_response: SemanticEvidenceAssessment | None = None


class ClaimEvidenceAssessment(FinancialModel):
    candidate_id: str
    content: str
    status: SupportStatus = "insufficient_evidence"
    method: Literal["deterministic", "gemini", "combined"] = "deterministic"
    assertions: list[EvidenceSupportFinding] = Field(default_factory=list)
    evidence: list[EvidenceContext] = Field(default_factory=list)
    supporting_citations: list[EvidenceCitation] = Field(default_factory=list)
    unsupported_portions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    deterministic_findings: list[ValidationCheck] = Field(default_factory=list)
    errors: list[EvidenceCriticError] = Field(default_factory=list)
    trace: EvidenceCriticTrace = Field(default_factory=EvidenceCriticTrace)
    financial_fact_verified: Literal[False] = False


class EvidenceCriticResult(FinancialModel):
    version: Literal["evidence_critic_v1"] = "evidence_critic_v1"
    source_result_sha256: str
    claims: list[ClaimEvidenceAssessment] = Field(default_factory=list)
    conflicts: list[CandidateConflict] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    errors: list[EvidenceCriticError] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False
