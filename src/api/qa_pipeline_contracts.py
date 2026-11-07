"""Application E2E contracts; technical trace is separate from released prose."""

from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..outputs.citation_contracts import CitationReference
from ..outputs.qa_contracts import QARequirement, VietnameseQARequest


class FinancialQARequest(VietnameseQARequest):
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    force_refresh: bool = False


class PipelineStage(FinancialModel):
    status: str = "NOT_EXECUTED"
    latency_ms: float = 0
    reasons: list[str] = Field(default_factory=list)


class CandidateOutcome(FinancialModel):
    candidate_id: str
    initial_decision: str
    final_decision: str
    reasons: list[str] = Field(default_factory=list)
    admission_status: str = "NOT_EXECUTED"
    verified_claim_id: str | None = None
    validation: dict[str, str] = Field(default_factory=dict)
    evidence_status: str | None = None
    logic_statuses: list[str] = Field(default_factory=list)


class PipelineTrace(FinancialModel):
    request_id: str
    document_id: str | None = None
    snapshot_id: str | None = None
    company_id: str | None = None
    stages: dict[str, PipelineStage] = Field(
        default_factory=lambda: {
            name: PipelineStage()
            for name in (
                "context",
                "ledger_lookup",
                "m5",
                "m6",
                "m6_validators",
                "m6_evidence",
                "m6_logic",
                "m6_judge_revision",
                "admission",
                "ledger_reload",
                "composer",
                "citations",
                "firewall",
            )
        }
    )
    planner_status: str | None = None
    planner_intent: str | None = None
    selected_agents: list[str] = Field(default_factory=list)
    executed_agents: list[str] = Field(default_factory=list)
    agent_stages: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    composition_id: str | None = None
    document_candidates: list[dict] = Field(default_factory=list)
    document_release: dict = Field(default_factory=dict)
    candidate_count: int = 0
    outcomes: list[CandidateOutcome] = Field(default_factory=list)
    native_decisions: dict[str, int] = Field(default_factory=dict)
    provider_calls: int = 0
    known_total_tokens: int = 0
    calls_with_unknown_tokens: int = 0
    provider_errors: list[str] = Field(default_factory=list)
    provider_stages: list[dict] = Field(default_factory=list)
    m7_status: str | None = None
    firewall_decision: str | None = None
    unanswered_requirements: list[QARequirement] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    total_latency_ms: float = 0


class FinancialQAResponse(FinancialModel):
    status: Literal[
        "completed",
        "completed_with_caveats",
        "partial_verified_coverage",
        "clarification_required",
        "unsupported",
        "verification_blocked",
        "provider_unavailable",
        "firewall_blocked",
        "internal_error",
    ] = "verification_blocked"
    mode: Literal[
        "CACHE_HIT",
        "FRESH_M5_M6_M7",
        "PARTIAL_REUSE_AND_REFRESH",
        "PARTIAL_REUSE_ONLY",
        "CLARIFICATION_REQUIRED",
        "BLOCKED",
        "PROVIDER_FAILURE",
    ] = "BLOCKED"
    answer_vi: str = "Chưa có đủ claim đã xác minh để trả lời yêu cầu."
    citations: list[CitationReference] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    used_verified_claim_ids: list[str] = Field(default_factory=list)
    reused_claims: int = 0
    newly_accepted_claims: int = 0
    rejected_claims: int = 0
    deferred_claims: int = 0
    trace: PipelineTrace
