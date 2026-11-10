"""Planner proposals là nhu cầu phân tích, không là evidence hoặc approval."""

from typing import Any, Literal

from pydantic import Field, field_validator, model_serializer, model_validator

from ..accounting.contracts import FinancialModel
from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import (
    Cost,
    GatewayError,
    ModelIdentity,
    ResponseProvenance,
    Usage,
)
from ..core.llm_gateway import GatewayAttempt
from ..evidence.contracts import Identity
from ..evidence.snapshots import SnapshotDescriptor
from .contracts import EvidencePlan, PlanValidation, QuerySpecification, RiskSignal


class SpecialistAssignment(FinancialModel):
    role: Literal["profitability", "liquidity_and_leverage", "cash_flow_and_earnings_quality"]
    task: str = Field(min_length=1, max_length=1500)
    indicators: list[Identity] = Field(default_factory=list, max_length=32)
    formulas: list[Identity] = Field(default_factory=list, max_length=8)
    depends_on: list[Identity] = Field(default_factory=list, max_length=35)

    @field_validator("depends_on")
    @classmethod
    def unique_dependencies(cls, references):
        if len(references) != len(set(references)):
            raise ValueError("duplicate_specialist_dependency")
        return references


class PlannerOperation(FinancialModel):
    operation_id: Identity
    period: Identity | None = None
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


class UserRequestedTarget(FinancialModel):
    """Answer goals, independent of the execution DAG and its supporting operands."""

    kind: Literal["fact", "metric", "explanation", "limitations"]
    target_id: Identity | None = None
    period: Identity | None = None
    interpretation: bool = False
    interpretation_topic: (
        Literal["metric_meaning", "earnings_quality", "dynamic_calculation", "unbounded"] | None
    ) = None
    required_indicators: list[Identity] = Field(default_factory=list, max_length=16)
    aspect: Literal["value", "formula", "operands"] = "value"
    reasoning_operations: list[str] = Field(default_factory=list, max_length=12)
    reasoning_periods: list[str] = Field(default_factory=list, max_length=16)

    @model_serializer(mode="wrap")
    def serialize_target(self, handler):
        wire = handler(self)
        for key in ("reasoning_operations", "reasoning_periods"):
            if not wire.get(key):
                wire.pop(key, None)
        return wire


class ReasoningPlanStep(FinancialModel):
    step_id: Identity
    operation: Literal[
        "retrieve_facts",
        "retrieve_evidence",
        "compare",
        "calculate",
        "interpret",
        "evaluate_alternatives",
        "assess_limitations",
        "conclude",
    ]
    inputs: list[Identity] = Field(default_factory=list, max_length=16)
    dependencies: list[Identity] = Field(default_factory=list, max_length=16)
    goal: str = Field(min_length=1, max_length=1000)
    expected_output: str = Field(min_length=1, max_length=1000)


class PlannerProposal(FinancialModel):
    reasoning_steps: list[ReasoningPlanStep] = Field(default_factory=list, max_length=16)
    user_requested_targets: list[UserRequestedTarget] = Field(default_factory=list, max_length=32)
    reasoning_required: bool = False
    selection_reason: str = ""
    assignments: list[SpecialistAssignment] = Field(default_factory=list, max_length=3)
    completion_conditions: list[str] = Field(default_factory=list, max_length=8)
    stop_reason: str | None = None
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

    def ordered_specialist_roles(self) -> list[str]:
        """Validate the bounded operation/role DAG before any dispatch."""
        operations = {op.operation_id: op for op in self.operations}
        assignments = {assignment.role: assignment for assignment in self.assignments}
        if len(operations) != len(self.operations):
            raise ValueError("duplicate_proposal_operation")
        if len(assignments) != len(self.assignments):
            raise ValueError("duplicate_specialist_role")
        if operations.keys() & assignments.keys():
            raise ValueError("ambiguous_dependency_reference")
        graph = {key: op.dependencies for key, op in operations.items()}
        for references in graph.values():
            if len(references) != len(set(references)):
                raise ValueError("duplicate_operation_dependency")
            if set(references) - operations.keys():
                raise ValueError("unknown_proposal_dependency")
        graph.update({role: assignment.depends_on for role, assignment in assignments.items()})
        ordered, active, visited = [], set(), set()

        def visit(key):
            if key not in graph:
                raise ValueError("unknown_specialist_dependency")
            if key in active:
                raise ValueError("proposal_dependency_cycle")
            if key in visited:
                return
            references = graph[key]
            if len(references) > 35 or len(references) != len(set(references)):
                raise ValueError("invalid_dependency_references")
            active.add(key)
            for reference in references:
                visit(reference)
            active.remove(key)
            visited.add(key)
            if key in assignments:
                ordered.append(key)

        for key in graph:
            visit(key)
        return ordered

    @model_validator(mode="after")
    def dependency_graph(self):
        self.ordered_specialist_roles()
        known = set()
        for step in self.reasoning_steps:
            if step.step_id in known or set(step.dependencies) - known:
                raise ValueError("reasoning_plan_dependency_invalid")
            known.add(step.step_id)
        return self

    @model_serializer(mode="wrap")
    def serialize_proposal(self, handler):
        wire = handler(self)
        if not wire.get("user_requested_targets"):
            wire.pop("user_requested_targets", None)
        if not wire.get("reasoning_steps"):
            wire.pop("reasoning_steps", None)
        return wire


class PlannerContext(FinancialModel):
    document_id: Identity | None = None
    company_id: Identity | None = None
    snapshot_id: Identity | None = None
    reporting_year: int | None = Field(default=None, ge=1900, le=2200)
    reporting_scope: Literal["separate", "consolidated"] | None = None
    period: Identity | None = None
    mode: Literal["auto", "gemini", "deterministic"] = "gemini"
    feedback: dict | None = None
    previous_proposal: PlannerProposal | None = None
    reusable_results: list[dict] = Field(default_factory=list)
    conversation_context: list[dict] = Field(default_factory=list, max_length=8)
    provider_attempt_limit: int = Field(default=2, ge=1, le=2)
    provider_timeout_seconds: float = Field(default=60.0, gt=0, le=60)
    model: ModelIdentity = Field(
        default_factory=lambda: ModelIdentity(provider="gemini", model=DEFAULT_GEMINI_MODEL)
    )

    @model_serializer(mode="wrap")
    def serialize_context(self, handler):
        wire = handler(self)
        for key in ("feedback", "previous_proposal", "reusable_results", "conversation_context"):
            if not wire.get(key):
                wire.pop(key, None)
        return wire


class PlannerLLMMetadata(FinancialModel):
    calls: int = 0
    status: str = "not_called"
    model: ModelIdentity | None = None
    provenance: ResponseProvenance | None = None
    usage: Usage | None = None
    cost: Cost | None = None
    latency_ms: float | None = None
    error: GatewayError | None = None
    attempts: list[GatewayAttempt] = Field(default_factory=list)


class PlannerTrace(FinancialModel):
    stage: Literal[
        "understanding",
        "proposal_schema",
        "semantic_policy",
        "catalog_resolution",
        "materialization",
        "validation",
    ]
    outcome: Identity
    reasons: list[str] = Field(default_factory=list)


class PlannerResult(FinancialModel):
    version: Literal["evidence_aware_planner_v1"] = "evidence_aware_planner_v1"
    question: Identity
    query: QuerySpecification
    raw_proposal: Any = None
    proposal: PlannerProposal | None = None
    # Original proposal stays intact; consumers use this only after semantic policy.
    effective_proposal: PlannerProposal | None = None
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
