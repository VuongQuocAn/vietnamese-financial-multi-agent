"""Planner proposals là nhu cầu phân tích, không là evidence hoặc approval."""

from typing import Any, Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import (
    Cost,
    GatewayError,
    ModelIdentity,
    ResponseProvenance,
    Usage,
)
from ..evidence.contracts import Identity
from ..evidence.snapshots import SnapshotDescriptor
from .contracts import EvidencePlan, PlanValidation, QuerySpecification, RiskSignal


class PlannerOperation(FinancialModel):
    operation_id: Identity
    operation: Literal[
        "find_financial_facts",
        "calculate_financial_metric",
        "get_evidence_sources",
        "get_metric_evidence_lineage",
        "prepare_bundle",
    ]
    canonical_item_id: Identity | None = None
    formula_id: Identity | None = None
    dependencies: list[Identity] = Field(default_factory=list, max_length=32)


class PlannerProposal(FinancialModel):
    intent: Literal[
        "direct_fact",
        "calculated_metric",
        "multi_step_analysis",
        "evidence_explanation",
        "unsupported",
        "ambiguous",
    ]
    company_alias: Identity | None = None
    reporting_years: list[int] = Field(default_factory=list, max_length=8)
    reporting_scope: Literal["separate", "consolidated"] | None = None
    # Chỉ explicit date/period trong câu hỏi; null cho câu hỏi chỉ có năm.
    period: Identity | None = None
    snapshot_origin: Literal["original_extraction", "recovery"] | None = None
    required_indicators: list[Identity] = Field(default_factory=list, max_length=32)
    formula_ids: list[Identity] = Field(default_factory=list, max_length=8)
    evidence_needs: list[
        Literal[
            "fact", "formula", "compatibility", "metric", "lineage", "citations", "analysis_bundle"
        ]
    ] = Field(default_factory=list)
    operations: list[PlannerOperation] = Field(default_factory=list, max_length=32)
    cross_document_comparison: bool = False
    missing_information: list[Identity] = Field(default_factory=list)
    unsupported_capabilities: list[Identity] = Field(default_factory=list)
    reasons: list[Identity] = Field(default_factory=list)


class PlannerContext(FinancialModel):
    document_id: Identity | None = None
    company_id: Identity | None = None
    snapshot_id: Identity | None = None
    reporting_year: int | None = Field(default=None, ge=1900, le=2200)
    reporting_scope: Literal["separate", "consolidated"] | None = None
    period: Identity | None = None
    mode: Literal["gemini", "deterministic"] = "gemini"
    model: ModelIdentity = Field(
        default_factory=lambda: ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)
    )


class PlannerLLMMetadata(FinancialModel):
    calls: int = 0
    status: str = "not_called"
    model: ModelIdentity | None = None
    provenance: ResponseProvenance | None = None
    usage: Usage | None = None
    cost: Cost | None = None
    latency_ms: float | None = None
    error: GatewayError | None = None


class PlannerTrace(FinancialModel):
    stage: Literal[
        "understanding", "proposal_schema", "catalog_resolution", "materialization", "validation"
    ]
    outcome: Identity
    reasons: list[str] = Field(default_factory=list)


class PlannerResult(FinancialModel):
    version: Literal["evidence_aware_planner_v1"] = "evidence_aware_planner_v1"
    question: Identity
    query: QuerySpecification
    raw_proposal: Any = None
    proposal: PlannerProposal | None = None
    plan: EvidencePlan | None = None
    validation: PlanValidation | None = None
    status: Literal["planned", "blocked", "clarification_required", "unsupported", "failed"]
    missing_information: list[str] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    snapshot_candidates: list[SnapshotDescriptor] = Field(default_factory=list)
    llm: PlannerLLMMetadata = Field(default_factory=PlannerLLMMetadata)
    trace: list[PlannerTrace] = Field(default_factory=list)
    latency_ms: float = 0.0
    financial_fact_verified: Literal[False] = False
