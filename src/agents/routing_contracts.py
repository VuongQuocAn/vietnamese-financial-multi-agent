"""Routing wire contracts; evidence references only, never financial verification."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from .contracts import RiskSignal, SpecialistRole

Eligibility = Literal["eligible", "partially_eligible", "blocked", "unsupported", "not_relevant"]


class RoutingRequirement(FinancialModel):
    requirement_id: str
    kind: Literal["fact", "metric", "capability"]
    target_id: str
    importance: Literal["required", "optional"] = "required"
    status: Literal["covered", "missing", "blocked", "unsupported"] = "missing"
    supporting_references: list[RetrievalReference] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class SpecialistRoute(FinancialModel):
    role: SpecialistRole
    eligibility: Eligibility = "not_relevant"
    assigned_items: list[str] = Field(default_factory=list)
    assigned_formulas: list[str] = Field(default_factory=list)
    covered_requirement_ids: list[str] = Field(default_factory=list)
    required_requirement_ids: list[str] = Field(default_factory=list)
    missing_requirement_ids: list[str] = Field(default_factory=list)
    supporting_references: list[RetrievalReference] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    selection_reason: str = "no_requested_capability"
    execution_eligible: bool = False


class RoutingTrace(FinancialModel):
    stage: Literal["intent", "capability", "evidence", "risk", "decision"]
    outcome: str
    requirement_id: str | None = None
    role: SpecialistRole | None = None
    reasons: list[str] = Field(default_factory=list)


class RoutingDecision(FinancialModel):
    version: Literal["adaptive_specialist_router_v1"] = "adaptive_specialist_router_v1"
    question: str
    planner_plan_id: str | None = None
    supervisor_plan_id: str | None = None
    planner_status: str | None = None
    supervisor_status: str | None = None
    status: Literal[
        "routed", "partial", "blocked", "unsupported", "clarification_required", "incomplete"
    ] = "incomplete"
    selected_roles: list[SpecialistRole] = Field(default_factory=list)
    skipped_roles: list[SpecialistRole] = Field(default_factory=list)
    routes: list[SpecialistRoute] = Field(default_factory=list)
    requirements: list[RoutingRequirement] = Field(default_factory=list)
    covered_requirement_ids: list[str] = Field(default_factory=list)
    uncovered_requirement_ids: list[str] = Field(default_factory=list)
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    trace: list[RoutingTrace] = Field(default_factory=list)
    stop_reasons: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False
