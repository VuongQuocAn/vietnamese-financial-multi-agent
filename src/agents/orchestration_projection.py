"""Copy the Router assignment and its dependency closure, without re-routing."""

from .orchestration_contracts import EvidenceProjection
from .routing_contracts import SpecialistRoute
from .specialist_common import _fact_error, _metric_error
from .supervisor import SupervisorResult


def build_specialist_context(
    supervisor_result: SupervisorResult, specialist_route: SpecialistRoute
) -> EvidenceProjection:
    route = specialist_route
    if not route.execution_eligible or not route.covered_requirement_ids:
        raise ValueError("route_not_execution_eligible")
    upstream = supervisor_result.model_copy(deep=True)
    plan, bundle = upstream.final_plan_state, upstream.evidence_bundle
    if not plan or upstream.status in {"blocked", "failed"}:
        raise ValueError("usable_upstream_plan_required")
    requirements = {r.requirement_id: r for r in plan.requirements}
    kept = set()

    def include(key):
        if key in kept:
            return
        if key not in requirements:
            raise ValueError("assignment_requirement_missing")
        kept.add(key)
        for dependency in requirements[key].dependencies:
            include(dependency)

    for key in [*route.covered_requirement_ids, *route.missing_requirement_ids]:
        if key in route.covered_requirement_ids or key in requirements:
            include(key)
    # Include source/lineage descendants of selected targets, never the shared
    # analysis bundle (which would reintroduce other agents' workloads).
    changed = True
    while changed:
        changed = False
        for requirement in requirements.values():
            if (
                requirement.evidence_type in {"citations", "lineage"}
                and requirement.requirement_id not in kept
                and requirement.dependencies
                and set(requirement.dependencies) <= kept
            ):
                include(requirement.requirement_id)
                changed = True

    references = route.supporting_references
    claim_facts = [
        f
        for f in bundle.facts
        if f.reference in references and f.record.canonical_item_id in route.assigned_items
    ]
    calculations = [
        c
        for c in bundle.calculations
        if c.formula_id in route.assigned_formulas
        and any(r.kind == "metric" and r.record_id == c.metric_id for r in references)
    ]
    observations = {o.observation for c in calculations if c.trace for o in c.trace.operands}
    claim_refs = [f.reference for f in claim_facts]
    bundle.facts = [
        f
        for f in bundle.facts
        if f.reference in claim_refs or f.reference.observation in observations
    ]
    bundle.claim_fact_references = claim_refs
    bundle.calculations = calculations
    metric_ids = {c.metric_id for c in calculations}
    fact_refs = [f.reference for f in bundle.facts]
    available = [*fact_refs, *[r for r in references if r.record_id in metric_ids]]
    if any(r not in available for r in references):
        raise ValueError("assignment_evidence_missing")
    citations = [c for f in bundle.facts for c in f.citations] + [
        cite for calc in calculations if calc.evidence for cite in calc.evidence.citations
    ]
    bundle.citations = [c for c in bundle.citations if c in citations]
    if any(c not in bundle.citations for c in route.citations):
        raise ValueError("assignment_citation_missing")
    for fact in bundle.facts:
        error = _fact_error(fact, bundle)
        if error:
            raise ValueError(error)
    for calc in calculations:
        error = _metric_error(calc, bundle)
        if error:
            raise ValueError(error)

    bundle.sources_and_lineage = [
        s
        for s in bundle.sources_and_lineage
        if getattr(s.request, "reference", None) in fact_refs
        or getattr(s.request, "metric_id", None) in metric_ids
    ]
    contexts = {(f.record.document_id, f.record.snapshot_id) for f in bundle.facts}
    for selection in bundle.snapshots:
        selection.candidates = [
            s
            for s in selection.candidates
            if (s.descriptor.document_id, s.descriptor.snapshot_id) in contexts
        ]
        for snapshot in selection.candidates:
            snapshot.metrics = [m for m in snapshot.metrics if m.metric_id in metric_ids]
            snapshot.source_review_bindings = [
                o
                for o in snapshot.source_review_bindings
                if any(f.reference.observation == o for f in bundle.facts)
            ]
    bundle.compatibility = [c for c in bundle.compatibility if c.metric_id in metric_ids]
    bundle.resolved_requirement_ids = [k for k in bundle.resolved_requirement_ids if k in kept]
    bundle.missing_requirement_ids = [k for k in bundle.missing_requirement_ids if k in kept]
    bundle.complete = not bundle.missing_requirement_ids
    bundle.limitations = sorted(set(bundle.limitations + route.caveats))

    steps = [s for s in plan.steps if set(s.output_evidence_ids) & kept]
    step_ids = {s.step_id for s in steps}

    def relevant(risk):
        return (
            not risk.requirement_ids
            and not risk.step_ids
            or bool(set(risk.requirement_ids) & kept or set(risk.step_ids) & step_ids)
        )

    plan.steps = steps
    plan.requirements = [r for r in plan.requirements if r.requirement_id in kept]
    plan.specialist_roles = [route.role]
    plan.risks = [r for r in plan.risks if relevant(r)]
    # Preserve original question, scope, periods and explicit constraints. Only
    # Router-approved targets change; operands stay in typed evidence above.
    plan.query.required_indicators = list(route.assigned_items)
    plan.query.requested_formula_ids = list(route.assigned_formulas)
    items = {f.record.canonical_item_id for f in bundle.facts}
    plan.query.selectors = [
        s
        for s in plan.query.selectors
        if s.canonical_item_id is None or s.canonical_item_id in items
    ]
    upstream.resolved_requirements = [
        r for r in upstream.resolved_requirements if r.requirement_id in kept
    ]
    upstream.missing_requirements = [
        r for r in upstream.missing_requirements if r.requirement_id in kept
    ]
    upstream.risk_signals = [r for r in upstream.risk_signals if relevant(r)]
    upstream.initial_validation.risks = [
        r for r in upstream.initial_validation.risks if relevant(r)
    ]
    # Full responses contain the global bundle; specialists use projected bundle.
    # Retain their source step IDs for lookup on OrchestrationResult instead.
    source_steps = [s.step_id for s in upstream.step_results if s.step_id in step_ids]
    upstream.step_results = []
    upstream.tool_trace = []
    upstream.execution_order = [s for s in upstream.execution_order if s in step_ids]
    upstream.executed_steps = len(source_steps)
    # Validate the projection, including the pruned plan DAG; never mutate source.
    upstream = SupervisorResult.model_validate_json(upstream.model_dump_json())
    return EvidenceProjection(
        role=route.role,
        source_plan_id=plan.plan_id,
        assigned_requirement_ids=list(route.covered_requirement_ids),
        dependency_requirement_ids=sorted(kept - set(route.covered_requirement_ids)),
        assigned_items=list(route.assigned_items),
        assigned_formulas=list(route.assigned_formulas),
        claim_fact_references=claim_refs,
        supporting_operand_references=[r for r in fact_refs if r not in claim_refs],
        metric_ids=sorted(metric_ids),
        citations=bundle.citations,
        source_step_ids=source_steps,
        supervisor_result=upstream,
    )
