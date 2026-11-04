"""Financial reasoning annotations; never verification decisions or new financial facts."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..agents.orchestration_contracts import CandidateConflict
from ..agents.planner_contracts import PlannerLLMMetadata
from ..evidence.retrieval import RetrievalReference
from .evidence_contracts import EvidenceSupportFinding
from .validation_contracts import ValidationCheck

LogicStatus = Literal["consistent", "inconsistent", "insufficient_context", "not_applicable"]
PremiseKind = Literal[
    "numeric_context",
    "sign_context",
    "comparison",
    "causal_evidence",
    "liquidity_context",
    "earnings_quality_context",
    "financial_context",
]
SemanticLogicReason = Literal[
    "bounded_interpretation",
    "contradiction",
    "missing_premises",
    "no_reasoning",
]


class SemanticLogicFinding(FinancialModel):
    assertion_id: str
    status: LogicStatus
    reason: SemanticLogicReason
    required_premises: list[PremiseKind]
    missing_evidence: list[PremiseKind]
    # IDs address only input checks and fully supported evidence assertions.
    premise_ids: list[str]
    evidence_ids: list[str]
    limitations: list[
        Literal[
            "source_quality_limited",
            "scope_unresolved",
            "causality_unproven",
            "comparison_unavailable",
            "bounded_to_supplied_evidence",
        ]
    ]


class SemanticLogicAssessment(FinancialModel):
    candidate_id: str
    assertions: list[SemanticLogicFinding] = Field(min_length=1, max_length=16)


class FinancialLogicError(FinancialModel):
    stage: Literal["consistency", "deterministic", "semantic"]
    code: str
    candidate_id: str | None = None


class LogicFinding(FinancialModel):
    candidate_id: str
    assertion_id: str
    content: str
    status: LogicStatus = "insufficient_context"
    reason_codes: list[str] = Field(default_factory=list)
    references: list[RetrievalReference] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    support_findings: list[EvidenceSupportFinding] = Field(default_factory=list)
    required_premises: list[PremiseKind] = Field(default_factory=list)
    missing_evidence: list[PremiseKind] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    method: Literal["deterministic", "gemini"] = "deterministic"


class FinancialLogicTrace(FinancialModel):
    deterministic_latency_ms: float = 0
    semantic_latency_ms: float = 0
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    semantic_response: SemanticLogicAssessment | None = None


class ClaimLogicAssessment(FinancialModel):
    candidate_id: str
    content: str
    assertions: list[LogicFinding] = Field(default_factory=list)
    conflict_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    errors: list[FinancialLogicError] = Field(default_factory=list)
    trace: FinancialLogicTrace = Field(default_factory=FinancialLogicTrace)
    financial_fact_verified: Literal[False] = False


class FinancialLogicCriticResult(FinancialModel):
    version: Literal["financial_logic_critic_v1"] = "financial_logic_critic_v1"
    source_result_sha256: str
    verification_input_sha256: str
    validation_result_sha256: str
    evidence_result_sha256: str
    claims: list[ClaimLogicAssessment] = Field(default_factory=list)
    conflicts: list[CandidateConflict] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    errors: list[FinancialLogicError] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False
