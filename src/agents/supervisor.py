"""Bounded EvidencePlan execution; M4 owns financial policy, M6 owns verification."""

from time import perf_counter
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from ..evidence.snapshots import MetricSnapshotClosure, SnapshotCatalog, SnapshotSelection
from ..tools.evidence_retrieval import EvidenceRetrievalTools, EvidenceToolResponse
from ..tools.financial_calculator import FinancialCalculationResponse, FinancialCalculator
from ..tools.financial_retrieval import (
    FinancialFactMatch,
    FinancialRetrievalTools,
    FinancialToolResponse,
)
from .contracts import (
    TOOL_CONTRACTS,
    EvidencePlan,
    EvidenceRequirement,
    ExecutionState,
    PlanValidation,
    RiskSignal,
    StopCondition,
    bind_step_request,
    validate_plan,
)

SUPPORTED_TOOLS = frozenset(
    {
        "find_financial_facts",
        "get_evidence_sources",
        "calculate_financial_metric",
        "get_metric_evidence_lineage",
    }
)


class ExecutionEvidenceBundle(FinancialModel):
    facts: list[FinancialFactMatch] = Field(default_factory=list)
    # None preserves standalone M5-04/05/06 behavior. Projections explicitly
    # distinguish requested facts from operands retained only for metric closure.
    claim_fact_references: list[RetrievalReference] | None = None
    calculations: list[FinancialCalculationResponse] = Field(default_factory=list)
    sources_and_lineage: list[EvidenceToolResponse] = Field(default_factory=list)
    snapshots: list[SnapshotSelection] = Field(default_factory=list)
    compatibility: list[MetricSnapshotClosure] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    resolved_requirement_ids: list[str] = Field(default_factory=list)
    missing_requirement_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    complete: bool = False
    financial_fact_verified: Literal[False] = False


ToolResponse = FinancialToolResponse | FinancialCalculationResponse | EvidenceToolResponse
StepResponse = ToolResponse | SnapshotSelection | MetricSnapshotClosure | ExecutionEvidenceBundle


class StepExecutionResult(FinancialModel):
    execution_kind: str = "DETERMINISTIC_COMPONENT_EXECUTED"
    step_id: str
    operation: str
    initial_state: ExecutionState = "pending"
    final_state: ExecutionState = "pending"
    transitions: list[ExecutionState] = Field(default_factory=lambda: ["pending"])
    # Chính request M4 đã bind/revalidate, JSON đủ replay qua registry.
    bound_request: dict | None = None
    response: StepResponse | None = None
    output_evidence_ids: list[str] = Field(default_factory=list)
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class SupervisorResult(FinancialModel):
    plan_id: str | None
    status: Literal["completed", "partial", "blocked", "failed"]
    initial_validation: PlanValidation
    final_plan_state: EvidencePlan | None = None
    step_results: list[StepExecutionResult] = Field(default_factory=list)
    resolved_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    missing_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    triggered_stop_conditions: list[StopCondition] = Field(default_factory=list)
    tool_trace: list[StepExecutionResult] = Field(default_factory=list)
    evidence_bundle: ExecutionEvidenceBundle = Field(default_factory=ExecutionEvidenceBundle)
    executed_steps: int = 0
    execution_order: list[str] = Field(default_factory=list)
    skipped_steps: int = 0
    latency_ms: float = 0.0
    financial_fact_verified: Literal[False] = False


def _unique(values):
    return list({v.model_dump_json(): v for v in values}.values())


def _schedule(plan):
    """Topological order includes evidence edges, not only explicit step edges."""
    producers = {}
    for step in plan.steps:
        for key in step.output_evidence_ids:
            if key in producers:
                raise ValueError("multiple_evidence_producers")
            producers[key] = step.step_id
    requirements = {r.requirement_id: r for r in plan.requirements}
    steps = {s.step_id: s for s in plan.steps}
    ordered, visited = [], set()

    def evidence_producers(key):
        return ([producers[key]] if key in producers else []) + [
            p
            for dependency in requirements[key].dependencies
            for p in evidence_producers(dependency)
        ]

    def visit(key):
        if key in visited:
            return
        visited.add(key)
        step = steps[key]
        dependencies = list(step.prerequisite_step_ids)
        for requirement in step.required_evidence_ids:
            dependencies.extend(evidence_producers(requirement))
        for output in step.output_evidence_ids:
            for requirement in requirements[output].dependencies:
                dependencies.extend(evidence_producers(requirement))
        for dependency in dependencies:
            if dependency != key:
                visit(dependency)
        ordered.append(key)

    for step in plan.steps:
        visit(step.step_id)
    return ordered


def _bundle(plan, results):
    bundle = ExecutionEvidenceBundle(limitations=list(plan.evidence_limitations))
    for result in results:
        if result.final_state != "completed":
            continue
        response = result.response
        bundle.limitations.extend(result.caveats)
        if isinstance(response, FinancialToolResponse):
            bundle.facts.extend(m for m in response.matches if isinstance(m, FinancialFactMatch))
        elif isinstance(response, FinancialCalculationResponse):
            bundle.calculations.append(response)
        elif isinstance(response, EvidenceToolResponse):
            bundle.sources_and_lineage.append(response)
        elif isinstance(response, SnapshotSelection):
            bundle.snapshots.append(response)
        elif isinstance(response, MetricSnapshotClosure):
            bundle.compatibility.append(response)
    for requirement in plan.requirements:
        if requirement.resolution == "resolved":
            bundle.resolved_requirement_ids.append(requirement.requirement_id)
            bundle.citations.extend(requirement.citations)
        elif requirement.importance == "required":
            bundle.missing_requirement_ids.append(requirement.requirement_id)
        bundle.limitations.extend(requirement.caveats)
    bundle.complete = not bundle.missing_requirement_ids
    bundle.citations = _unique(bundle.citations)
    bundle.facts = _unique(bundle.facts)
    bundle.limitations = sorted(set(bundle.limitations))
    return bundle


def _failure(status, reasons):
    reason = ";".join(reasons) or "required_output_unavailable"
    if status == "conflicted" or "conflict" in reason:
        return "conflicting_evidence", "conflicting_evidence", reason
    if status == "ambiguous":
        return "ambiguous_snapshot", "unresolved_ambiguity", reason
    if any(t in reason for t in ("unit", "period", "currency", "scale")):
        return "period_unit_mismatch", "compatibility_gate_blocked", reason
    if "formula" in reason or "approval" in reason:
        return "formula_not_approved", "compatibility_gate_blocked", reason
    if "lineage" in reason or "citation" in reason:
        return "incomplete_lineage", "missing_required_inputs", reason
    if "scope" in reason:
        return "reporting_scope_unresolved", "compatibility_gate_blocked", reason
    return "missing_evidence", "missing_required_inputs", reason


class RiskAwareSupervisor:
    def __init__(self, catalog: SnapshotCatalog):
        from ..evidence.snapshots import isolated_catalog

        self._catalog = isolated_catalog(catalog)
        self._financial = FinancialRetrievalTools(self._catalog)
        self._calculator = FinancialCalculator(self._catalog)
        self._evidence = EvidenceRetrievalTools(self._catalog)
        self._request_cache = {}
        self.cache_hits = 0

    def reset_request(self):
        self._request_cache.clear()
        self.cache_hits = 0

    @staticmethod
    def execute_document(operation, tools):
        from .document_qa_contracts import DocumentEvidenceBundle

        return DocumentEvidenceBundle(
            operation=operation, result=tools.search_document_evidence(operation.request)
        )

    def _dispatch(self, operation, request):
        # Explicit capability list; never arbitrary getattr on an LLM tool name.
        dispatch = {
            "find_financial_facts": self._financial.find_financial_facts,
            "get_evidence_sources": self._evidence.get_evidence_sources,
            "calculate_financial_metric": self._calculator.calculate_financial_metric,
            "get_metric_evidence_lineage": self._evidence.get_metric_evidence_lineage,
        }
        key = operation, request.model_dump_json()
        if key in self._request_cache:
            self.cache_hits += 1
            return self._request_cache[key].model_copy(deep=True)
        result = dispatch[operation](request)
        self._request_cache[key] = result.model_copy(deep=True)
        return result

    def _compatibility(self, step, requirements):
        selected = self._catalog.select(step.selector.document_id, step.selector.snapshot_id)
        metrics = [
            m
            for m in self._catalog.metrics
            if m.request.document_id == step.selector.document_id
            and m.request.snapshot_id == step.selector.snapshot_id
            and m.definition.name == step.formula_id
        ]
        if selected.status != "selected" or len(metrics) != 1:
            raise ValueError("metric_binding_missing_or_ambiguous")
        metric = metrics[0]
        closures = [c for c in selected.candidates[0].metrics if c.metric_id == metric.metric_id]
        if len(closures) != 1 or not closures[0].calculation_eligible:
            raise ValueError("compatibility_gate_blocked")
        # Closure chính production, đồng thời inputs thực thi phải là đúng operands.
        references = {
            r.observation.model_dump_json()
            for key in step.required_evidence_ids
            for r in requirements[key].references
            if r.observation
        }
        if any(
            o.observation is None or o.observation.model_dump_json() not in references
            for o in metric.operands
        ):
            raise ValueError("metric_operand_evidence_binding_mismatch")
        return closures[0]

    @staticmethod
    def _resolve(requirement, response):
        """Resolve từ typed payload thực; không dùng status found làm approval."""
        data = requirement.model_dump()
        refs, citations, decisions, caveats = [], [], [], list(requirement.caveats)
        kind = requirement.evidence_type
        if isinstance(response, SnapshotSelection):
            if kind != "snapshot" or response.status != "selected":
                raise ValueError("snapshot_not_selected")
        elif isinstance(response, MetricSnapshotClosure):
            if kind not in {"formula", "compatibility"} or not response.calculation_eligible:
                raise ValueError("compatibility_gate_blocked")
        elif isinstance(response, ExecutionEvidenceBundle):
            if kind != "analysis_bundle":
                raise ValueError("bundle_output_type_mismatch")
            citations = response.citations
            caveats.extend(response.limitations)
        else:
            if response.status not in {"found", "computed"}:
                raise ValueError(";".join(response.reasons) or response.status)
            caveats.extend(response.caveats)
            if isinstance(response, FinancialCalculationResponse):
                if (
                    kind != "metric"
                    or response.trace is None
                    or response.evidence is None
                    or response.result is None
                    or not response.evidence.closure.calculation_eligible
                    or response.evidence.reviewed_lineage.status != "found"
                    or response.evidence.reviewed_lineage.lineage is None
                    or response.evidence.reviewed_lineage.lineage.completeness != "complete"
                    or not response.evidence.citations
                ):
                    raise ValueError("calculation_trace_or_lineage_incomplete")
                if requirement.formula_id and response.formula_id != requirement.formula_id:
                    raise ValueError("metric_formula_mismatch")
                refs = [RetrievalReference(kind="metric", record_id=response.metric_id)]
                citations = response.evidence.citations
            else:
                matches = response.matches
                if not matches:
                    raise ValueError("required_output_unavailable")
                if kind == "fact":
                    if len(matches) != 1 or not isinstance(matches[0], FinancialFactMatch):
                        raise ValueError("fact_missing_or_conflicted")
                    match = matches[0]
                    record = match.record
                    actual = {
                        **record.model_dump(),
                        **record.context.model_dump(),
                        "reporting_scope": match.reporting_scope.reporting_scope,
                    }
                    for field, expected in requirement.selector.model_dump(
                        exclude_none=True
                    ).items():
                        if field == "evidence_type":
                            value = "fact"
                        elif field == "source_page":
                            if not any(c.pdf_page == expected for c in match.citations):
                                raise ValueError("fact_source_page_mismatch")
                            continue
                        else:
                            value = actual.get(field)
                        if value != expected:
                            raise ValueError("fact_selector_mismatch:" + field)
                    if requirement.canonical_item_id not in (None, record.canonical_item_id):
                        raise ValueError("fact_item_mismatch")
                    decisions = [
                        q.decision for q in record.quality_context if q.task_type == "direct_qa"
                    ]
                    if (
                        not decisions
                        or any(q in {"insufficient", "conflicted"} for q in decisions)
                        or match.display_status == "blocked"
                        or match.source_review.status == "conflicted"
                    ):
                        raise ValueError("fact_quality_or_source_conflicted")
                    caveats.extend(c for q in record.quality_context for c in q.caveats)
                elif kind == "lineage":
                    if (
                        not isinstance(response, EvidenceToolResponse)
                        or len(response.metric_matches) != 1
                        or response.metric_matches[0].reviewed_lineage.status != "found"
                        or response.metric_matches[0].reviewed_lineage.lineage is None
                        or response.metric_matches[0].reviewed_lineage.lineage.completeness
                        != "complete"
                        or not response.metric_matches[0].closure.calculation_eligible
                        or not any(m.reference.kind == "lineage" for m in matches)
                    ):
                        raise ValueError("incomplete_lineage")
                elif kind != "citations":
                    raise ValueError("unsupported_output_evidence_type")
                refs = [m.reference for m in matches]
                citations = [c for m in matches for c in m.citations]
            if not citations:
                raise ValueError("citations_unavailable")
        data.update(
            resolution="resolved",
            references=refs,
            citations=citations,
            quality_decisions=decisions,
            caveats=sorted(set(caveats)),
        )
        return EvidenceRequirement.model_validate(data)

    def execute(self, plan: EvidencePlan | dict, max_steps: int = 20) -> SupervisorResult:
        start = perf_counter()
        validation = validate_plan(plan, catalog=self._catalog)
        result = SupervisorResult(
            plan_id=plan.plan_id if isinstance(plan, EvidencePlan) else plan.get("plan_id"),
            status="blocked" if validation.structurally_valid else "failed",
            initial_validation=validation,
            risk_signals=list(validation.risks),
            triggered_stop_conditions=list(validation.triggered_stop_conditions),
        )
        if not validation.structurally_valid:
            result.latency_ms = (perf_counter() - start) * 1000
            return result
        current = EvidencePlan.model_validate_json(
            plan.model_dump_json()
            if isinstance(plan, EvidencePlan)
            else EvidencePlan.model_validate(plan).model_dump_json()
        )
        result.step_results = [
            StepExecutionResult(
                step_id=s.step_id, operation=s.tool or s.step_type, initial_state=s.status
            )
            for s in current.steps
        ]
        steps = {s.step_id: s for s in current.steps}
        requirements = {r.requirement_id: r for r in current.requirements}
        outputs = {}
        budget = (
            min(max_steps, current.execution_limit or max_steps) if type(max_steps) is int else 0
        )
        fresh = current.state == "pending" and all(s.status == "pending" for s in current.steps)
        fresh &= all(
            r.resolution == "unresolved"
            or (r.importance == "optional" and r.resolution in {"missing", "conflicted"})
            for r in current.requirements
        )
        supported = all(s.tool is None or s.tool in SUPPORTED_TOOLS for s in current.steps)
        try:
            schedule = _schedule(current)
        except ValueError:
            schedule, supported = [], False

        def transition(step, trace, state, reason=None):
            step.status = trace.final_state = state
            trace.transitions.append(state)
            step.failure_or_skip_reason = (
                reason if state in {"blocked", "failed", "skipped"} else None
            )
            if reason:
                trace.reasons.append(reason)

        def stop(condition):
            if condition not in result.triggered_stop_conditions:
                result.triggered_stop_conditions.append(condition)

        allowed = (
            validation.execution_eligible
            and fresh
            and supported
            and type(max_steps) is int
            and budget > 0
        )
        if not allowed:
            reason = (
                "preflight_policy_blocked"
                if not validation.execution_eligible
                else "runtime_requires_fresh_plan"
                if not fresh
                else "unsupported_operation"
                if not supported
                else "execution_limit_reached"
            )
            if validation.execution_eligible:
                stop(
                    "unsupported_operation"
                    if not supported or not fresh
                    else "execution_limit_reached"
                )
            for step, trace in zip(current.steps, result.step_results, strict=True):
                transition(step, trace, "skipped", reason)
        else:
            current.state = "running"
            traces = {t.step_id: t for t in result.step_results}
            for step_id in schedule:
                step, trace = steps[step_id], traces[step_id]
                dependencies = [*step.required_evidence_ids]
                dependencies += [
                    d
                    for key in step.output_evidence_ids
                    for d in requirements[key].dependencies
                    if d not in step.output_evidence_ids
                ]
                if any(steps[k].status != "completed" for k in step.prerequisite_step_ids) or any(
                    requirements[k].resolution != "resolved"
                    and (
                        k in step.required_evidence_ids or requirements[k].importance == "required"
                    )
                    for k in dependencies
                ):
                    transition(step, trace, "skipped", "dependency_not_completed")
                    for key in step.output_evidence_ids:
                        requirements[key] = self._missing(
                            requirements[key], "dependency_not_completed"
                        )
                    current.requirements = list(requirements.values())
                    continue
                if result.executed_steps >= budget:
                    stop("execution_limit_reached")
                    transition(step, trace, "skipped", "execution_limit_reached")
                    continue
                transition(step, trace, "ready")
                transition(step, trace, "running")
                result.executed_steps += 1
                result.execution_order.append(step.step_id)
                tick = perf_counter()
                try:
                    if step.step_type == "resolve_snapshot":
                        response = self._catalog.select(
                            step.selector.document_id, step.selector.snapshot_id
                        )
                    elif step.step_type == "check_compatibility":
                        response = self._compatibility(step, requirements)
                    elif step.step_type == "prepare_bundle":
                        response = _bundle(current, result.step_results)
                    else:
                        request = bind_step_request(current, step.step_id, outputs)
                        trace.bound_request = request.model_dump(mode="json")
                        previous_hits = self.cache_hits
                        response = self._dispatch(step.tool, request)
                        trace.execution_kind = (
                            "CACHE_HIT" if self.cache_hits > previous_hits else "TOOL_EXECUTED"
                        )
                        response = TOOL_CONTRACTS[step.tool][1].model_validate_json(
                            response.model_dump_json()
                        )
                        if response.request != request:
                            raise ValueError("tool_response_request_mismatch")
                    trace.response = response
                    trace.caveats = list(getattr(response, "caveats", []))
                    if isinstance(
                        response,
                        (
                            FinancialToolResponse,
                            FinancialCalculationResponse,
                            EvidenceToolResponse,
                            SnapshotSelection,
                        ),
                    ) and response.status not in {
                        "found",
                        "computed",
                        "selected",
                    }:
                        raise ValueError(";".join(response.reasons) or response.status)
                    for key in step.output_evidence_ids:
                        requirements[key] = self._resolve(requirements[key], response)
                        trace.output_evidence_ids.append(key)
                    outputs[step.step_id] = response
                    transition(step, trace, "completed")
                except Exception as error:
                    # Bounded local execution: no retry; independent branches may continue.
                    reasons = getattr(trace.response, "reasons", []) or [
                        "tool_exception:" + type(error).__name__
                        if not isinstance(error, (ValueError, KeyError, ValidationError))
                        else str(error)
                    ]
                    code, condition, reason = _failure(
                        getattr(trace.response, "status", ""), reasons
                    )
                    blocking = not step.output_evidence_ids or any(
                        requirements[k].importance == "required" for k in step.output_evidence_ids
                    )
                    risk = RiskSignal(
                        code=code,
                        reason=reason,
                        blocking=blocking,
                        step_ids=[step.step_id],
                        requirement_ids=step.output_evidence_ids,
                    )
                    trace.risk_signals.append(risk)
                    result.risk_signals.append(risk)
                    if blocking:
                        stop(condition)
                    for key in step.output_evidence_ids:
                        requirements[key] = self._missing(
                            requirements[key], reason, code == "conflicting_evidence"
                        )
                    trace.output_evidence_ids = []
                    transition(
                        step,
                        trace,
                        "blocked" if isinstance(error, (ValueError, KeyError)) else "failed",
                        reason,
                    )
                trace.latency_ms = (perf_counter() - tick) * 1000
                # Commit requirements + step transitions together, then validate whole state.
                current.requirements = list(requirements.values())
                EvidencePlan.model_validate_json(current.model_dump_json())
            current.requirements = list(requirements.values())
            all_required = all(
                r.resolution == "resolved"
                for r in current.requirements
                if r.importance == "required"
            )
            required_work = all(
                s.status == "completed"
                for s in current.steps
                if not s.output_evidence_ids
                or any(requirements[k].importance == "required" for k in s.output_evidence_ids)
            )
            if all_required and required_work:
                result.status = "completed"
                stop("all_required_evidence_resolved")
            elif any(t.output_evidence_ids for t in result.step_results):
                result.status = "partial"
            elif any(t.final_state == "failed" for t in result.step_results):
                result.status = "failed"
            else:
                result.status = "blocked"
        current.state = result.status
        # Optional runtime risks remain nonblocking; initial caveats are preserved.
        current.risks = _unique(result.risk_signals)
        result.final_plan_state = EvidencePlan.model_validate_json(current.model_dump_json())
        result.resolved_requirements = [
            r for r in current.requirements if r.resolution == "resolved"
        ]
        result.missing_requirements = [
            r for r in current.requirements if r.resolution != "resolved"
        ]
        result.evidence_bundle = _bundle(current, result.step_results)
        result.skipped_steps = sum(t.final_state == "skipped" for t in result.step_results)
        traces = {t.step_id: t for t in result.step_results}
        result.tool_trace = [
            traces[k] for k in result.execution_order if traces[k].bound_request is not None
        ]
        result.latency_ms = (perf_counter() - start) * 1000
        return SupervisorResult.model_validate_json(result.model_dump_json())

    @staticmethod
    def _missing(requirement, reason, conflicted=False):
        return EvidenceRequirement.model_validate(
            {
                **requirement.model_dump(),
                "resolution": "conflicted" if conflicted else "missing",
                "reasons": [reason],
            }
        )
