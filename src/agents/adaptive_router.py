"""Deterministic read-only specialist routing; no tool, Gateway or agent execution."""

from itertools import combinations

from ..tools.question_understanding import normalize
from .cash_flow_earnings_quality_specialist import ITEM_LABELS as CASH_ITEMS
from .contracts import SPECIALIST_BOUNDARIES
from .liquidity_leverage_specialist import ITEM_LABELS as DEBT_ITEMS
from .liquidity_leverage_specialist import METRIC_LABELS as DEBT_METRICS
from .liquidity_leverage_specialist import _debt_semantics_error
from .planner_contracts import PlannerResult
from .profitability_specialist import ITEM_LABELS as PROFIT_ITEMS
from .profitability_specialist import METRIC_LABELS as PROFIT_METRICS
from .query_planner import _explicit_constraints
from .routing_contracts import (
    RoutingDecision,
    RoutingRequirement,
    RoutingTrace,
    SpecialistRoute,
)
from .specialist_common import SpecialistResult, select_evidence
from .supervisor import SupervisorResult

# Capabilities come from the implemented domains, roles from the approved registry.
_DOMAINS = {
    "profitability": (PROFIT_ITEMS, PROFIT_METRICS),
    "liquidity_and_leverage": (DEBT_ITEMS, DEBT_METRICS),
    "cash_flow_and_earnings_quality": (CASH_ITEMS, {}),
}
_CAPABILITIES = {
    boundary.role: tuple(set(ids) for ids in _DOMAINS[boundary.role])
    for boundary in SPECIALIST_BOUNDARIES
}
_ROLES = tuple(_CAPABILITIES)
_METRIC_RISKS = {"formula_not_approved", "incomplete_lineage"}


def _unique(models):
    return [v for _, v in sorted({m.model_dump_json(): m for m in models}.items())]


def _ancestors(key, requirements):
    found = {key}
    for dependency in requirements[key].dependencies:
        found.update(_ancestors(dependency, requirements))
    return found


def _related(key, requirements):
    def supports(requirement):
        return any(
            dependency == key
            or (
                requirements[dependency].evidence_type in {"citations", "lineage"}
                and supports(requirements[dependency])
            )
            for dependency in requirement.dependencies
        )

    return _ancestors(key, requirements) | {
        r.requirement_id
        for r in requirements.values()
        if r.evidence_type in {"citations", "lineage"} and supports(r)
    }


def _targets(planner):
    plan = planner.plan
    facts = [r for r in plan.requirements if r.evidence_type == "fact"]
    metrics = [r for r in plan.requirements if r.evidence_type == "metric"]
    # Planner adds metric operands to query.required_indicators. They are inputs,
    # not independently requested factual workloads. Explicit fact operations win.
    if metrics and planner.query.intent in {"calculated_metric", "evidence_explanation"}:
        # Single-metric intent has no independent factual workload. Gemini may
        # explicitly retrieve/source operands before calculation; those operations
        # are still supporting evidence. Mixed fact+metric intent remains multi-step.
        facts = []
    elif planner.proposal:
        explicit = {
            o.canonical_item_id
            for o in planner.proposal.operations
            if o.operation == "find_financial_facts"
        }
        facts = [r for r in facts if r.canonical_item_id in explicit]
    else:
        requirements = {r.requirement_id: r for r in plan.requirements}
        operands = {k for m in metrics for k in _ancestors(m.requirement_id, requirements)}
        facts = [r for r in facts if r.requirement_id not in operands]
    targets = sorted([*facts, *metrics], key=lambda r: r.requirement_id)
    unsupported = set(planner.proposal.unsupported_capabilities if planner.proposal else [])
    unsupported.update(set(planner.query.requested_formula_ids) - {r.formula_id for r in metrics})
    return targets, sorted(unsupported)


def _scope_error(evidence, requirement, planner, upstream):
    query = planner.query
    selector = requirement.selector
    _, explicit_scopes, _, explicit_periods = _explicit_constraints(planner.question)
    scope = (explicit_scopes or [query.reporting_scope])[0]
    if any(
        getattr(selector, field) not in (None, getattr(evidence, field))
        for field in ("document_id", "snapshot_id", "company_id", "period")
    ):
        return "requirement_context_mismatch"
    if query.selectors and not any(
        all(
            getattr(s, field) in (None, getattr(evidence, field))
            for field in ("document_id", "snapshot_id", "company_id", "period")
        )
        for s in query.selectors
    ):
        return "query_context_mismatch"
    if query.reporting_year and evidence.period[:4] != str(query.reporting_year):
        return "reporting_period_mismatch"
    if explicit_periods and evidence.period not in explicit_periods:
        return "reporting_period_mismatch"
    if query.reporting_periods and evidence.period not in query.reporting_periods:
        return "reporting_period_mismatch"
    matches = [
        f
        for f in upstream.evidence_bundle.facts
        if f.reference == evidence.reference
        or (
            evidence.calculation
            and f.reference.observation
            in {o.observation for o in evidence.calculation.trace.operands}
        )
    ]
    for match in matches:
        record, context = match.record, match.record.context
        statement = record.canonical_item_id[:3].upper()
        period_type = "as_of" if statement == "B01" else "fiscal_year"
        if (
            context.statement_type != statement
            or context.period_type != period_type
            or context.mapped_item_code != record.canonical_item_id
            or not context.currency
            or record.value.unit != context.currency
            or context.scale <= 0
        ):
            return "statement_period_or_unit_mismatch"
        if evidence.kind == "fact" and (
            selector.statement_type not in (None, context.statement_type)
            or selector.period_type not in (None, context.period_type)
            or (
                selector.source_page
                and not any(c.pdf_page == selector.source_page for c in match.citations)
            )
        ):
            return "requirement_context_mismatch"
        requested_scope = selector.reporting_scope or scope
        if requested_scope and (
            match.reporting_scope.status != "resolved"
            or match.reporting_scope.reporting_scope != requested_scope
            or context.reporting_scope not in (None, requested_scope)
        ):
            return "reporting_scope_unresolved_or_mismatched"
    if evidence.calculation:
        calc = evidence.calculation
        policy = (calc.evidence.closure.readiness or {}).get("formula_policy", {})
        if (
            policy.get("execution_approved") is not True
            or policy.get("definition_sha256") != calc.formula_digest
            or policy.get("approval_reference") != calc.trace.approval.decision_reference
        ):
            return "metric_formula_not_approved"
        if calc.formula_id == "debt_to_assets":
            return _debt_semantics_error(calc, upstream.evidence_bundle)
    return None


def _bindings(plan):
    return [
        r.model_dump(
            include={
                "requirement_id",
                "evidence_type",
                "canonical_item_id",
                "formula_id",
                "selector",
                "dependencies",
                "importance",
            }
        )
        for r in plan.requirements
    ]


class AdaptiveSpecialistRouter:
    def route(
        self,
        *,
        question: str,
        planner_result: PlannerResult | None = None,
        supervisor_result: SupervisorResult | None = None,
    ) -> RoutingDecision:
        planner, upstream = planner_result, supervisor_result
        decision = RoutingDecision(
            question=question,
            planner_plan_id=planner.plan.plan_id if planner and planner.plan else None,
            supervisor_plan_id=upstream.plan_id if upstream else None,
            planner_status=planner.status if planner else None,
            supervisor_status=upstream.status if upstream else None,
            routes=[SpecialistRoute(role=role) for role in _ROLES],
            skipped_roles=list(_ROLES),
        )

        def stop(status, *reasons):
            decision.status = status
            decision.stop_reasons = sorted(set(reasons))
            if planner and planner.plan:
                targets, unsupported = _targets(planner)
                decision.requirements = [
                    RoutingRequirement(
                        requirement_id=r.requirement_id,
                        kind=r.evidence_type,
                        target_id=r.canonical_item_id
                        if r.evidence_type == "fact"
                        else r.formula_id,
                        importance=r.importance,
                        status="blocked",
                        reasons=decision.stop_reasons,
                    )
                    for r in targets
                ] + [
                    RoutingRequirement(
                        requirement_id="unsupported:" + name,
                        kind="capability",
                        target_id=name,
                        status="unsupported",
                        reasons=["unsupported_capability"],
                    )
                    for name in unsupported
                ]
                decision.uncovered_requirement_ids = sorted(
                    r.requirement_id for r in decision.requirements
                )
            for route in decision.routes:
                route.eligibility = "blocked" if status != "unsupported" else "unsupported"
                route.selection_reason = ";".join(decision.stop_reasons)
            decision.trace.append(
                RoutingTrace(stage="risk", outcome=status, reasons=decision.stop_reasons)
            )
            decision.trace.append(
                RoutingTrace(stage="decision", outcome=status, reasons=decision.stop_reasons)
            )
            return decision

        if planner is None:
            return stop("incomplete", "planner_result_required")
        decision.caveats = list(planner.caveats)
        decision.risk_signals = _unique(
            [
                *planner.risks,
                *(planner.plan.risks if planner.plan else []),
                *(planner.validation.risks if planner.validation else []),
                *(upstream.risk_signals if upstream else []),
                *(upstream.initial_validation.risks if upstream else []),
                *(
                    upstream.final_plan_state.risks
                    if upstream and upstream.final_plan_state
                    else []
                ),
                *([r for s in upstream.step_results for r in s.risk_signals] if upstream else []),
            ]
        )
        if question != planner.question or question != planner.query.original_question:
            return stop("incomplete", "question_planner_mismatch")
        decision.trace.append(
            RoutingTrace(
                stage="intent",
                outcome=planner.query.intent,
                reasons=["planner_query_and_explicit_operations"],
            )
        )
        if planner.status != "planned":
            status = (
                planner.status
                if planner.status in {"clarification_required", "unsupported", "blocked"}
                else "incomplete"
            )
            return stop(
                status,
                *(planner.reasons or ["planner_" + planner.status]),
                *planner.missing_information,
            )
        if not planner.plan or not planner.validation or not planner.validation.execution_eligible:
            return stop("incomplete", "valid_planner_plan_required")
        if upstream is None:
            return stop("incomplete", "supervisor_result_required")
        decision.caveats = sorted(set(decision.caveats + upstream.evidence_bundle.limitations))
        if (
            upstream.plan_id != planner.plan.plan_id
            or not upstream.final_plan_state
            or upstream.final_plan_state.query != planner.query
            or planner.plan.query != planner.query
            or _bindings(upstream.final_plan_state) != _bindings(planner.plan)
        ):
            return stop("incomplete", "planner_supervisor_binding_mismatch")
        if (
            upstream.status in {"blocked", "failed"}
            or not upstream.initial_validation.execution_eligible
        ):
            return stop(
                "blocked", "supervisor_" + upstream.status, *upstream.initial_validation.errors
            )
        _, scopes, _, _ = _explicit_constraints(question)
        if len(scopes) > 1:
            return stop("clarification_required", "ambiguous_reporting_scope")
        if planner.query.cross_document_comparison:
            return stop("blocked", "D03-B10_cross_document_compatibility_unresolved")
        if any(
            r.blocking
            and (
                r.code == "cross_document_compatibility_unresolved"
                or (r.code == "ambiguous_snapshot" and not r.requirement_ids and not r.step_ids)
                or (
                    r.code == "reporting_scope_unresolved"
                    and (scopes or planner.query.reporting_scope)
                    and not r.requirement_ids
                    and not r.step_ids
                )
            )
            for r in decision.risk_signals
        ):
            return stop("blocked", "global_risk_blocker")

        targets, unsupported = _targets(planner)
        requirements = {r.requirement_id: r for r in upstream.final_plan_state.requirements}
        resolved = {r.requirement_id for r in upstream.resolved_requirements}
        # Periods are checked against typed target selectors below, including B01
        # dates and comparative metric operands. Avoid the prose year filter.
        selected = SpecialistResult(question="", upstream_status=upstream.status)
        select_evidence(
            upstream,
            selected,
            item_labels={**PROFIT_ITEMS, **DEBT_ITEMS, **CASH_ITEMS},
            metric_labels={**PROFIT_METRICS, **DEBT_METRICS},
            period_roles={
                "gross_margin": "revenue",
                "revenue_yoy": "current_revenue",
                "debt_to_assets": "assets",
            },
        )
        evidence = sorted(selected.supporting_evidence, key=lambda e: e.reference.model_dump_json())
        # No implicit selection between original/recovery, or companies/documents.
        contexts = {
            (e.company_id, e.document_id, e.snapshot_id)
            for e in evidence
            if any(
                (
                    e.canonical_item_id == t.canonical_item_id
                    if t.evidence_type == "fact"
                    else e.calculation and e.calculation.formula_id == t.formula_id
                )
                for t in targets
            )
        }
        if len(contexts) > 1:
            return stop("blocked", "ambiguous_evidence_context_or_snapshot")
        relevant_risks = {}
        coverage = {role: set() for role in _ROLES}
        for target in targets:
            key = target.requirement_id
            kind = target.evidence_type
            target_id = target.canonical_item_id if kind == "fact" else target.formula_id
            item = RoutingRequirement(
                requirement_id=key, kind=kind, target_id=target_id, importance=target.importance
            )
            decision.requirements.append(item)
            roles = [
                role
                for role, (items, metrics) in _CAPABILITIES.items()
                if target_id in (items if kind == "fact" else metrics)
            ]
            if target_id in PROFIT_ITEMS and any(
                phrase in normalize(question)
                for phrase in ("kha nang sinh loi", "phan tich sinh loi")
            ):
                roles = [role for role in roles if role == "profitability"]
                decision.trace.append(
                    RoutingTrace(
                        stage="intent",
                        outcome="explicit_profitability_analysis",
                        requirement_id=key,
                        reasons=["separate_profitability_workload_requested"],
                    )
                )
            decision.trace.append(
                RoutingTrace(
                    stage="capability",
                    outcome="matched" if roles else "unsupported",
                    requirement_id=key,
                    reasons=roles or ["unsupported_capability"],
                )
            )
            related = _related(key, requirements)
            risks = []
            for risk in decision.risk_signals:
                affected = set(risk.requirement_ids) | {
                    k
                    for s in planner.plan.steps
                    if s.step_id in risk.step_ids
                    for k in s.output_evidence_ids
                }
                if (not affected or affected & related) and not (
                    kind == "fact" and risk.code in _METRIC_RISKS
                ):
                    risks.append(risk)
            relevant_risks[key] = risks
            blockers = [r.code for r in risks if r.blocking]
            missing = [
                k
                for k in sorted(related)
                if requirements[k].importance == "required"
                and (requirements[k].resolution != "resolved" or k not in resolved)
            ]
            if not roles:
                item.status, item.reasons = "unsupported", ["unsupported_capability"]
            elif blockers:
                item.status, item.reasons = "blocked", sorted(set(blockers))
            elif missing:
                item.reasons = ["required_evidence_unresolved:" + k for k in missing]
            else:
                matches, errors = [], []
                for candidate in evidence:
                    if (kind == "fact" and candidate.canonical_item_id != target_id) or (
                        kind == "metric"
                        and (
                            not candidate.calculation
                            or candidate.calculation.formula_id != target_id
                        )
                    ):
                        continue
                    error = _scope_error(candidate, target, planner, upstream)
                    if error:
                        errors.append(error)
                    elif candidate.reference not in requirements[key].references:
                        errors.append("requirement_reference_mismatch")
                    else:
                        matches.append(candidate)
                if matches:
                    item.status, item.reasons = "covered", ["evidence_eligible"]
                    item.supporting_references = _unique([m.reference for m in matches])
                    item.citations = _unique([c for m in matches for c in m.citations])
                    item.caveats = sorted(
                        set(
                            [c for m in matches for c in m.caveats]
                            + [c for k in related for c in requirements[k].caveats]
                            + [
                                "source_review_status:" + view.status
                                for f in upstream.evidence_bundle.facts
                                if f.reference in item.supporting_references
                                for view in f.source_review.matches
                            ]
                        )
                    )
                    for role in roles:
                        coverage[role].add(key)
                else:
                    item.reasons = sorted(
                        set(errors or selected.missing_evidence or ["eligible_evidence_missing"])
                    )
            decision.trace.append(
                RoutingTrace(
                    stage="evidence", outcome=item.status, requirement_id=key, reasons=item.reasons
                )
            )
            decision.trace.append(
                RoutingTrace(
                    stage="risk",
                    outcome="blocked" if blockers else "passed",
                    requirement_id=key,
                    reasons=sorted(set(blockers)) or ["no_blocking_risk"],
                )
            )
        for name in unsupported:
            decision.requirements.append(
                RoutingRequirement(
                    requirement_id="unsupported:" + name,
                    kind="capability",
                    target_id=name,
                    status="unsupported",
                    reasons=["unsupported_capability"],
                )
            )
        available = {r.requirement_id for r in decision.requirements if r.status == "covered"}
        # Exhaustive set cover is bounded to the three approved roles. Tie break:
        # cash+profit overlap prefers cash; profit alone prefers profitability.
        prefer_cash = any(t.target_id.startswith("b03.") for t in decision.requirements)
        ranked = (_ROLES[2], _ROLES[0], _ROLES[1]) if prefer_cash else _ROLES
        chosen = ()
        for size in range(1, len(ranked) + 1):
            choices = [
                c
                for c in combinations(ranked, size)
                if set().union(*(coverage[r] for r in c)) == available
            ]
            if available and choices:
                chosen = choices[0]
                break
        assigned = set()
        for role in chosen:
            assigned.update(coverage[role])
        for route in decision.routes:
            items, metrics = _CAPABILITIES[route.role]
            relevant = [
                r
                for r in decision.requirements
                if r.target_id in (items if r.kind == "fact" else metrics)
            ]
            route.required_requirement_ids = [
                r.requirement_id for r in relevant if r.importance == "required"
            ]
            route.missing_requirement_ids = [
                r.requirement_id for r in relevant if r.status != "covered"
            ]
            route.risk_signals = _unique(
                [risk for r in relevant for risk in relevant_risks.get(r.requirement_id, [])]
            )
            route.eligibility = (
                "partially_eligible"
                if coverage[route.role] and route.missing_requirement_ids
                else "eligible"
                if coverage[route.role]
                else "blocked"
                if relevant
                else "not_relevant"
            )
            route.execution_eligible = route.role in chosen
            if route.execution_eligible:
                # Assign overlaps exactly once in deterministic preferred-role order.
                prior = set().union(*(coverage[r] for r in chosen[: chosen.index(route.role)]))
                owned = [r for r in relevant if r.requirement_id in coverage[route.role] - prior]
                route.covered_requirement_ids = [r.requirement_id for r in owned]
                route.assigned_items = sorted({r.target_id for r in owned if r.kind == "fact"})
                route.assigned_formulas = sorted({r.target_id for r in owned if r.kind == "metric"})
                route.supporting_references = _unique(
                    [e for r in owned for e in r.supporting_references]
                )
                route.citations = _unique([c for r in owned for c in r.citations])
                route.caveats = sorted(
                    set(decision.caveats + [c for r in owned for c in r.caveats])
                )
                route.selection_reason = (
                    "minimum_specialist_cover_cash_profit_priority"
                    if prefer_cash and route.role == _ROLES[2]
                    else "minimum_specialist_cover"
                )
            else:
                route.selection_reason = (
                    "covered_by_selected_specialist"
                    if coverage[route.role]
                    else "no_eligible_evidence"
                    if relevant
                    else "no_requested_capability"
                )
            decision.trace.append(
                RoutingTrace(
                    stage="decision",
                    outcome="selected" if route.execution_eligible else "skipped",
                    role=route.role,
                    reasons=[route.selection_reason],
                )
            )
        decision.selected_roles = [r for r in _ROLES if r in chosen]
        decision.skipped_roles = [r for r in _ROLES if r not in chosen]
        decision.covered_requirement_ids = sorted(assigned)
        decision.uncovered_requirement_ids = sorted(
            r.requirement_id for r in decision.requirements if r.status != "covered"
        )
        required_missing = any(
            r.status != "covered" and r.importance == "required" for r in decision.requirements
        )
        decision.status = (
            "partial"
            if chosen and (required_missing or upstream.status == "partial")
            else "routed"
            if chosen
            else "unsupported"
            if decision.requirements
            and all(r.status == "unsupported" for r in decision.requirements)
            else "blocked"
        )
        if not chosen:
            decision.stop_reasons = sorted(
                {reason for r in decision.requirements for reason in r.reasons}
                or {"no_routable_requirements"}
            )
        decision.caveats = sorted(
            set(decision.caveats + [c for r in decision.requirements for c in r.caveats])
        )
        return decision
