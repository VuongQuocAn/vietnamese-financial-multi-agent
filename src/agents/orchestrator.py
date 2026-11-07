"""Sequential bounded orchestration; Router owns selection, M6 owns verification."""

import hashlib
import json
from time import perf_counter

from .orchestration_contracts import (
    AggregatedCandidate,
    CandidateConflict,
    CandidateOrigin,
    OrchestrationError,
    OrchestrationResult,
    SpecialistExecution,
    StageExecution,
)
from .orchestration_projection import build_specialist_context
from .planner_contracts import PlannerContext, PlannerResult
from .routing_contracts import RoutingDecision
from .specialist_common import SpecialistResult
from .supervisor import SupervisorResult


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _id(prefix, value):
    return prefix + ":" + hashlib.sha256(_json(value).encode()).hexdigest()[:24]


def _unique(models):
    return list({m.model_dump_json(): m for m in models}.values())


def _check_assignment(result, projection, route):
    evidence = {e.evidence_id: e for e in result.supporting_evidence}
    if len(evidence) != len(result.supporting_evidence) or any(
        e.reference not in route.supporting_references for e in evidence.values()
    ):
        raise ValueError("specialist_evidence_outside_assignment")
    for candidate in result.candidates:
        if not candidate.supporting_evidence_ids or any(
            key not in evidence for key in candidate.supporting_evidence_ids
        ):
            raise ValueError("candidate_evidence_identity_missing")
        supports = [evidence[key] for key in candidate.supporting_evidence_ids]
        if any(
            (candidate.company_id, candidate.document_id, candidate.snapshot_id, candidate.period)
            != (e.company_id, e.document_id, e.snapshot_id, e.period)
            for e in supports
        ) or any(c not in projection.citations for c in candidate.citations):
            raise ValueError("candidate_provenance_outside_assignment")


def aggregate_candidates(executions):
    """Exact semantic/provenance dedup; preserve competing versions without a winner."""
    aggregated, keys, groups = [], {}, {}
    for execution in executions:
        result = execution.result
        if result is None or execution.status not in {"generated", "partial"}:
            continue
        for candidate in result.candidates:
            if candidate.status != "candidate":
                continue
            evidence = [
                e
                for e in result.supporting_evidence
                if e.evidence_id in candidate.supporting_evidence_ids
            ]
            if not evidence or len({e.evidence_id for e in evidence}) != len(
                set(candidate.supporting_evidence_ids)
            ):
                raise ValueError("candidate_evidence_identity_missing")
            semantics = sorted(
                {
                    e.canonical_item_id or (e.calculation.formula_id if e.calculation else e.label)
                    for e in evidence
                }
            )
            # Local evidence IDs and random candidate IDs never define identity.
            provenance = sorted(
                [e.model_dump(mode="json", exclude={"evidence_id"}) for e in evidence], key=_json
            )
            identity = dict(
                kind=candidate.kind,
                company=candidate.company_id,
                document=candidate.document_id,
                snapshot=candidate.snapshot_id,
                period=candidate.period,
                semantics=semantics,
                content=candidate.content,
                provenance=provenance,
                references=sorted(
                    [r.model_dump(mode="json") for r in candidate.fact_references], key=_json
                ),
                citations=sorted(
                    [c.model_dump(mode="json") for c in candidate.citations], key=_json
                ),
            )
            key = _json(identity)
            origin = CandidateOrigin(
                role=execution.role,
                execution_id=execution.execution_id,
                candidate_id=candidate.candidate_id,
                original_content=candidate.content,
                supporting_evidence=evidence,
            )
            if key in keys:
                item = keys[key]
                item.origins.append(origin)
                item.origin_roles = list(dict.fromkeys([*item.origin_roles, execution.role]))
                item.caveats = sorted(set(item.caveats + candidate.caveats))
                item.missing_information = sorted(
                    set(item.missing_information + candidate.missing_information)
                )
                continue
            item = AggregatedCandidate(
                **dict(candidate.model_dump(), candidate_id=_id("candidate", identity)),
                origins=[origin],
                origin_roles=[execution.role],
                supporting_evidence=evidence,
                supporting_references=_unique(
                    [e.reference for e in evidence] + candidate.fact_references
                ),
            )
            keys[key] = item
            aggregated.append(item)
            # Interpretations with different wording/meaning are separate propositions.
            if candidate.kind in {"fact", "approved_metric"}:
                group = _json([candidate.kind, candidate.company_id, candidate.period, semantics])
                signature = _json(
                    [
                        candidate.content,
                        candidate.document_id,
                        candidate.snapshot_id,
                        [(e.value, e.unit, e.scale, e.operand_periods) for e in evidence],
                    ]
                )
                groups.setdefault(group, []).append((signature, item))
    conflicts = []
    for group, values in groups.items():
        if len({signature for signature, _ in values}) < 2:
            continue
        ids = [item.candidate_id for _, item in values]
        conflict = CandidateConflict(conflict_id=_id("conflict", [group, ids]), candidate_ids=ids)
        conflicts.append(conflict)
        for _, item in values:
            item.conflict_ids.append(conflict.conflict_id)
    return aggregated, conflicts


class FinancialMultiAgentOrchestrator:
    def __init__(self, *, planner, supervisor, router, specialists):
        self._planner = planner
        self._supervisor = supervisor
        self._router = router
        self._specialists = dict(specialists)

    @staticmethod
    def plan_fusion(question):
        from .fusion_contracts import decompose

        return decompose(question)

    def run_document(self, requirements, manifest, company_id, snapshot_id, tools):
        from .document_qa import document_candidates

        operations = self._planner.plan_document(requirements, manifest, snapshot_id)
        bundles = [self._supervisor.execute_document(op, tools) for op in operations]
        candidates = [
            candidate
            for bundle in bundles
            for candidate in document_candidates(bundle, company_id, manifest)
        ]
        return bundles, candidates

    def run(self, *, question: str, context: PlannerContext) -> OrchestrationResult:
        started = perf_counter()
        output = OrchestrationResult(question=question, context=context.model_copy(deep=True))

        def trace(stage, outcome, start, *, role=None, reasons=()):
            output.trace.append(
                StageExecution(
                    stage=stage,
                    outcome=outcome,
                    role=role,
                    reasons=list(reasons),
                    latency_ms=(perf_counter() - start) * 1000,
                )
            )

        def finish(status):
            start = perf_counter()
            output.status = status
            seen = {t.stage for t in output.trace}
            for stage in (
                "planning",
                "supervisor",
                "routing",
                "context_projection",
                "specialist_execution",
                "candidate_aggregation",
            ):
                if stage not in seen:
                    output.trace.append(
                        StageExecution(
                            stage=stage, outcome="skipped", reasons=output.stop_conditions
                        )
                    )
            metadata = output.usage.stages
            if output.planner_result:
                metadata["planning"] = output.planner_result.llm
            for execution in output.specialist_executions:
                metadata[execution.role] = execution.llm
            output.usage.calls = sum(m.calls for m in metadata.values())
            output.usage.calls_with_unknown_tokens = sum(
                sum(a.response.usage.total_tokens is None for a in m.attempts)
                if m.attempts
                else m.calls
                for m in metadata.values()
                if m.attempts or (m.calls and (not m.usage or m.usage.total_tokens is None))
            )
            output.usage.executions_with_unknown_usage = sum(
                e.usage_unknown for e in output.specialist_executions
            )
            for field in ("input_tokens", "output_tokens", "total_tokens"):
                values = [getattr(m.usage, field) for m in metadata.values() if m.calls and m.usage]
                known = [v for v in values if v is not None]
                setattr(output.usage, field, sum(known) if known else None)
            output.missing_evidence = sorted(set(output.missing_evidence))
            output.caveats = sorted(
                set(output.caveats + ["candidate_claims_pending_M6_verification"])
            )
            output.risks = _unique(output.risks)
            trace("finalization", status, start)
            for event in output.trace:
                output.stage_latency_ms[event.stage] = (
                    output.stage_latency_ms.get(event.stage, 0) + event.latency_ms
                )
            output.latency_ms = (perf_counter() - started) * 1000
            return output

        stage = "planning"
        start = perf_counter()
        try:
            planner = PlannerResult.model_validate(
                self._planner.plan(question, context.model_copy(deep=True))
            )
            output.planner_result = planner.model_copy(deep=True)
            output.risks.extend(planner.risks)
            output.caveats.extend(planner.caveats)
            output.missing_evidence.extend(planner.missing_information)
            trace(stage, planner.status, start, reasons=planner.reasons)
            if planner.status != "planned":
                output.stop_conditions.extend(planner.reasons or ["planner_" + planner.status])
                if planner.status == "failed":
                    output.errors.append(OrchestrationError(stage=stage, code="planner_failed"))
                return finish(planner.status)
            if not planner.plan:
                raise ValueError("planned_result_missing_plan")

            stage, start = "supervisor", perf_counter()
            supervisor = SupervisorResult.model_validate(
                self._supervisor.execute(planner.plan.model_copy(deep=True))
            )
            output.supervisor_result = supervisor.model_copy(deep=True)
            output.risks.extend(supervisor.risk_signals)
            output.caveats.extend(supervisor.evidence_bundle.limitations)
            output.missing_evidence.extend(supervisor.evidence_bundle.missing_requirement_ids)
            output.stop_conditions.extend(supervisor.triggered_stop_conditions)
            trace(stage, supervisor.status, start)
            if supervisor.status in {"blocked", "failed"}:
                output.stop_conditions.append("supervisor_" + supervisor.status)
                if supervisor.status == "failed":
                    output.errors.append(OrchestrationError(stage=stage, code="supervisor_failed"))
                return finish(supervisor.status)

            stage, start = "routing", perf_counter()
            routing = RoutingDecision.model_validate(
                self._router.route(
                    question=question,
                    planner_result=planner.model_copy(deep=True),
                    supervisor_result=supervisor.model_copy(deep=True),
                )
            )
            output.routing_decision = routing.model_copy(deep=True)
            output.risks.extend(routing.risk_signals)
            output.caveats.extend(routing.caveats)
            output.uncovered_requirements = [
                r for r in routing.requirements if r.status != "covered"
            ]
            output.missing_evidence.extend(routing.uncovered_requirement_ids)
            trace(stage, routing.status, start, reasons=routing.stop_reasons)
            if routing.status not in {"routed", "partial"}:
                output.stop_conditions.extend(routing.stop_reasons)
                return finish(routing.status if routing.status != "incomplete" else "failed")
            routes = [r for r in routing.routes if r.execution_eligible]
            if (
                len(routes) > 3
                or len({r.role for r in routes}) != len(routes)
                or {r.role for r in routes} != set(routing.selected_roles)
                or not routes
            ):
                raise ValueError("invalid_router_execution_selection")
        except Exception as error:
            output.errors.append(
                OrchestrationError(
                    stage=stage, code="stage_failed", error_type=type(error).__name__
                )
            )
            output.stop_conditions.append(stage + "_failed")
            trace(stage, "failed", start)
            return finish("failed")

        for route in routes:
            execution_start = perf_counter()
            execution = SpecialistExecution(
                execution_id="specialist:" + route.role,
                role=route.role,
                assigned_requirement_ids=list(route.covered_requirement_ids),
            )
            output.specialist_executions.append(execution)
            stage, start = "context_projection", perf_counter()
            try:
                execution.projection = build_specialist_context(supervisor, route)
                trace(stage, "completed", start, role=route.role)
                stage, start = "specialist_execution", perf_counter()
                if route.role not in self._specialists:
                    raise ValueError("selected_specialist_not_configured")
                result = SpecialistResult.model_validate(
                    self._specialists[route.role].analyze(
                        question=question,
                        supervisor_result=execution.projection.supervisor_result.model_copy(
                            deep=True
                        ),
                    )
                )
                if result.role != route.role or result.question != question:
                    raise ValueError("specialist_result_binding_mismatch")
                execution.result, execution.status, execution.llm = (
                    result,
                    result.status,
                    result.llm,
                )
                _check_assignment(result, execution.projection, route)
                covered = {
                    e.reference.model_dump_json()
                    for candidate in result.candidates
                    if candidate.status == "candidate"
                    and candidate.kind in {"fact", "approved_metric"}
                    for e in result.supporting_evidence
                    if e.evidence_id in candidate.supporting_evidence_ids
                }
                for requirement in routing.requirements:
                    if requirement.requirement_id in route.covered_requirement_ids:
                        complete = all(
                            ref.model_dump_json() in covered
                            for ref in requirement.supporting_references
                        )
                        target = (
                            execution.covered_requirement_ids
                            if complete
                            else execution.missing_requirement_ids
                        )
                        target.append(requirement.requirement_id)
                output.missing_evidence.extend(execution.missing_requirement_ids)
                if result.status in {"generated", "partial"}:
                    execution.status = (
                        "partial"
                        if execution.missing_requirement_ids
                        or any(t.outcome == "excluded" for t in result.trace)
                        else "generated"
                    )
                output.risks.extend(result.risks)
                output.caveats.extend(result.limitations)
                # LLM missing_information is an untrusted annotation. Coverage is
                # determined against Router targets; retain annotations verbatim
                # on SpecialistResult and as caveats, not invented missing targets.
                output.caveats.extend(
                    "specialist_annotation:" + route.role + ":" + text
                    for text in result.missing_evidence
                )
                if result.status == "failed":
                    execution.error = OrchestrationError(
                        stage=stage, code="specialist_failed", role=route.role
                    )
                    output.errors.append(execution.error)
                trace(stage, execution.status, start, role=route.role)
            except Exception as error:
                execution.status = "failed"
                execution.error = OrchestrationError(
                    stage=stage,
                    code="specialist_stage_failed",
                    error_type=type(error).__name__,
                    role=route.role,
                )
                execution.usage_unknown = (
                    stage == "specialist_execution" and execution.result is None
                )
                output.errors.append(execution.error)
                trace(stage, "failed", start, role=route.role)
                if stage == "context_projection":
                    trace(
                        "specialist_execution",
                        "skipped",
                        perf_counter(),
                        role=route.role,
                        reasons=["projection_failed"],
                    )
            if execution.status in {"failed", "abstained"}:
                execution.missing_requirement_ids = list(route.covered_requirement_ids)
                output.missing_evidence.extend(route.covered_requirement_ids)
                output.stop_conditions.append("specialist_" + execution.status + ":" + route.role)
            execution.latency_ms = (perf_counter() - execution_start) * 1000

        start = perf_counter()
        try:
            output.candidates, output.conflicts = aggregate_candidates(output.specialist_executions)
            trace("candidate_aggregation", "completed", start)
        except Exception as error:
            output.errors.append(
                OrchestrationError(
                    stage="candidate_aggregation",
                    code="aggregation_failed",
                    error_type=type(error).__name__,
                )
            )
            trace("candidate_aggregation", "failed", start)
            return finish("failed")
        if output.candidates:
            partial = (
                supervisor.status == "partial"
                or routing.status == "partial"
                or output.conflicts
                or output.errors
                or any(e.status != "generated" for e in output.specialist_executions)
            )
            return finish("partial" if partial else "completed")
        return finish("failed" if output.errors else "abstained")
