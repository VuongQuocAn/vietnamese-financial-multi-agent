"""M5 orchestration wire outputs; candidates remain unverified inputs to future M6."""

from typing import Literal

from pydantic import Field, model_serializer

from ..accounting.contracts import FinancialModel
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from .contracts import RiskSignal, SpecialistRole
from .planner_contracts import PlannerContext, PlannerLLMMetadata, PlannerResult
from .routing_contracts import RoutingDecision, RoutingRequirement
from .specialist_common import SpecialistCandidate, SpecialistEvidence, SpecialistResult
from .supervisor import SupervisorResult

Stage = Literal[
    "planning",
    "supervisor",
    "routing",
    "context_projection",
    "specialist_execution",
    "candidate_aggregation",
    "finalization",
]


class OrchestrationError(FinancialModel):
    stage: Stage
    code: str
    error_type: str | None = None
    role: SpecialistRole | None = None


class StageExecution(FinancialModel):
    stage: Stage
    outcome: str
    role: SpecialistRole | None = None
    reasons: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class EvidenceProjection(FinancialModel):
    role: SpecialistRole
    source_plan_id: str
    assigned_requirement_ids: list[str]
    dependency_requirement_ids: list[str]
    assigned_items: list[str]
    assigned_formulas: list[str]
    claim_fact_references: list[RetrievalReference]
    supporting_operand_references: list[RetrievalReference]
    metric_ids: list[str]
    citations: list[EvidenceCitation]
    source_step_ids: list[str]
    # Exact context delivered to analyze; full upstream execution lives once on result.
    supervisor_result: SupervisorResult


class SpecialistExecution(FinancialModel):
    execution_id: str
    role: SpecialistRole
    assigned_requirement_ids: list[str]
    covered_requirement_ids: list[str] = Field(default_factory=list)
    missing_requirement_ids: list[str] = Field(default_factory=list)
    status: Literal["generated", "partial", "abstained", "failed"] = "failed"
    projection: EvidenceProjection | None = None
    result: SpecialistResult | None = None
    error: OrchestrationError | None = None
    latency_ms: float = 0.0
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    usage_unknown: bool = False


class CandidateOrigin(FinancialModel):
    role: SpecialistRole
    execution_id: str
    candidate_id: str
    original_content: str
    supporting_evidence: list[SpecialistEvidence]


class AggregatedCandidate(SpecialistCandidate):
    origins: list[CandidateOrigin]
    origin_roles: list[SpecialistRole]
    supporting_evidence: list[SpecialistEvidence]
    supporting_references: list[RetrievalReference]
    conflict_ids: list[str] = Field(default_factory=list)


class CandidateConflict(FinancialModel):
    conflict_id: str
    candidate_ids: list[str]
    reason: Literal["value_or_context_disagreement"] = "value_or_context_disagreement"
    financial_fact_verified: Literal[False] = False


class GeminiUsageSummary(FinancialModel):
    calls: int = 0
    calls_with_unknown_tokens: int = 0
    executions_with_unknown_usage: int = 0
    # None means unavailable, never a fabricated zero cost/token count.
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    stages: dict[str, PlannerLLMMetadata] = Field(default_factory=dict)


class OrchestrationResult(FinancialModel):
    version: Literal["financial_multi_agent_orchestration_v1"] = (
        "financial_multi_agent_orchestration_v1"
    )
    question: str
    context: PlannerContext
    status: Literal[
        "completed",
        "partial",
        "blocked",
        "failed",
        "clarification_required",
        "unsupported",
        "abstained",
    ] = "failed"
    planner_result: PlannerResult | None = None
    supervisor_result: SupervisorResult | None = None
    routing_decision: RoutingDecision | None = None
    specialist_executions: list[SpecialistExecution] = Field(default_factory=list)
    candidates: list[AggregatedCandidate] = Field(default_factory=list)
    conflicts: list[CandidateConflict] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    uncovered_requirements: list[RoutingRequirement] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    errors: list[OrchestrationError] = Field(default_factory=list)
    trace: list[StageExecution] = Field(default_factory=list)
    usage: GeminiUsageSummary = Field(default_factory=GeminiUsageSummary)
    stage_latency_ms: dict[str, float] = Field(default_factory=dict)
    latency_ms: float = 0.0
    financial_fact_verified: Literal[False] = False
    integration_context: dict = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def serialize_integration(self, handler):
        wire = handler(self)
        if not self.integration_context:
            wire.pop("integration_context", None)
        return wire
