"""Request-scoped coordination of existing M5/M6 lanes and one M7/Firewall release."""

from collections import Counter
from copy import copy

from ..agents.fusion_contracts import EvidenceFusionBundle
from ..agents.orchestrator import FinancialMultiAgentOrchestrator
from ..evidence.composition import payload_sha256
from ..evidence.composition_graph import CompositionGraphView, select_financial_catalog
from ..evidence.graph import graph_id
from ..outputs.information_firewall import InformationFirewall
from ..outputs.qa_composer import VietnameseQAComposer
from ..outputs.qa_contracts import VietnameseQARequest
from ..tools.graph_retrieval import GetGraphContextRequest, GraphRetrievalTools
from ..tools.question_understanding import understand
from ..verification.ledger import VerifiedClaimLedger


def run_fusion(pipeline, request, response, stage, stop, *, recovery_seen=None):
    recovery_seen = set() if recovery_seen is None else recovery_seen
    trace = response.trace
    parsed, issues = understand(request.question)
    forbidden = set(issues) & {
        "cross_document_comparison_blocked_D03_B10",
        "ambiguous_reporting_scope",
        "non_annual_period_unsupported",
        "invalid_period",
        "multiple_periods_unsupported",
    }
    if forbidden:
        return stop("unsupported", sorted(forbidden))
    if (
        request.period
        and parsed.reporting_year
        and request.period[:4] != str(parsed.reporting_year)
    ):
        return stop("clarification_required", ["period_conflict"])
    if (
        request.reporting_scope
        and parsed.reporting_scope
        and request.reporting_scope != parsed.reporting_scope
    ):
        return stop("clarification_required", ["reporting_scope_conflict"])
    year = parsed.reporting_year or (int(request.period[:4]) if request.period else None)
    identities = pipeline._document_identities(request, year, strict_year=True)
    if len(identities) != 1 or year is None:
        return stop("clarification_required", ["document_company_year_binding_unresolved"])
    document, company = next(iter(identities))
    manifests = [
        m
        for m in pipeline.compositions
        if m.logical_document_id == document
        and (request.composition_id is None or m.composition_id == request.composition_id)
    ]
    if len(manifests) != 1 or pipeline.document_repository is None:
        return stop("clarification_required", ["approved_document_composition_required"])
    manifest = manifests[0]
    scoped = copy(pipeline)
    financial_binding_error = None
    try:
        scoped.catalog = stage(
            "financial_binding", lambda: select_financial_catalog(pipeline.catalog, manifest)
        )
    except ValueError:
        # An incomplete financial graph cannot invalidate an independently pinned
        # document lane, nor authorize any financial calculation or graph proof.
        financial_binding_error = "financial_graph_binding_blocked"
    scoped.documents = [d for d in pipeline.documents if d.document_id == document]
    digest = payload_sha256(manifest.model_dump(mode="json"))
    snapshot = manifest.financial_snapshot.snapshot_id
    snapshots = sorted(
        {s.descriptor.snapshot_id for s in manifest.sources if s.status == "verified"}
    )
    if (
        request.snapshot_id is not None
        and request.snapshot_id != snapshot
        or request.composition_sha256 is not None
        and request.composition_sha256 != digest
        or request.document_snapshots
        and request.document_snapshots != snapshots
    ):
        return stop("clarification_required", ["fusion_source_binding_mismatch"])
    selection = pipeline.catalog.select(document, snapshot)
    if (
        selection.status != "selected"
        or selection.candidates[0].descriptor != manifest.financial_snapshot
    ):
        return stop("clarification_required", ["approved_financial_descriptor_required"])
    if any(
        f.company_id != company
        for f in pipeline.catalog.facts
        if (f.document_id, f.snapshot_id) == (document, snapshot)
    ):
        return stop("verification_blocked", ["financial_company_mismatch"])
    scope = request.reporting_scope or parsed.reporting_scope
    if scope:
        resolution = pipeline.catalog.get_reporting_scope(document, snapshot)
        if (
            resolution.status != "resolved"
            or resolution.evidence_status != "confirmed"
            or resolution.reporting_scope != scope
        ):
            return stop("clarification_required", ["requested_scope_unconfirmed"])
    bound = request.model_copy(
        update=dict(
            document_id=document,
            company_id=company,
            snapshot_id=snapshot,
            composition_id=manifest.composition_id,
            composition_sha256=digest,
            document_snapshots=snapshots,
        )
    )
    trace.document_id, trace.company_id, trace.snapshot_id = document, company, snapshot
    trace.composition_id, trace.planner_intent = manifest.composition_id, "mixed"
    from ..agents.qa_planning import plan_fusion

    try:
        plan = stage(
            "fusion_planning",
            lambda: (
                plan_fusion(pipeline.gateway, request)
                if request.execution_mode != "deterministic" and request.allow_gateway
                else FinancialMultiAgentOrchestrator.plan_fusion(request.question)
            ),
        )
    except ValueError:
        trace.limitations.append("adaptive_fusion_planner_failed_source_only_fallback")
        trace.execution_events.append(dict(event="PROVIDER_DEGRADED", component="FusionPlanner"))
        plan = FinancialMultiAgentOrchestrator.plan_fusion(request.question)
    if len(plan.requirements) > 12:
        return stop("clarification_required", ["narrower_question_required"])
    bundle = EvidenceFusionBundle(
        context=dict(
            bound.model_dump(mode="json"),
            reporting_year=year,
            financial_snapshot_descriptor=manifest.financial_snapshot.model_dump(mode="json"),
            reporting_scope_resolution=pipeline.catalog.get_reporting_scope(
                document, snapshot
            ).model_dump(mode="json"),
        ),
        plan=plan,
    )
    trace.planner_status = "planned"
    fusion_requirements = {}
    for part in plan.requirements:
        if part.lane not in {"financial", "document"}:
            bundle.missing_evidence.append(part.requirement_id)
            continue
        if part.lane == "financial" and financial_binding_error:
            part.support_status = "missing"
            part.reason = financial_binding_error
            part.missing_information = [financial_binding_error]
            bundle.missing_evidence.append(part.requirement_id)
            continue
        # Every lane inherits the already checked original request context. No subrequest
        # can select a second filing, company, scope or latest snapshot.
        updates = dict(
            question=part.original_span,
            document_snapshots=[],
            integration_lane=part.lane,
        )
        if part.lane == "financial":
            updates.update(
                question=(part.execution_question or part.original_span) + f" năm {year}",
                composition_id=None,
                composition_sha256=None,
            )
        else:
            updates.update(
                snapshot_id=None,
                period=None,
                reporting_scope=None,
                integration_v2=False,
            )
        child = stage(
            part.requirement_id,
            lambda updates=updates: scoped.run(
                bound.model_copy(update=updates), recovery_seen=recovery_seen
            ),
        )
        bundle.lane_results.append(
            dict(
                requirement_id=part.requirement_id,
                lane=part.lane,
                response=child.model_dump(mode="json"),
            )
        )
        fusion_requirements[part.requirement_id] = child.trace.answer_requirements
        trace.adaptive_rounds.extend(child.trace.adaptive_rounds)
        part.support_status = "accepted" if child.used_verified_claim_ids else "missing"
        if not child.used_verified_claim_ids:
            part.reason = next(iter(child.trace.errors), child.status)
            part.missing_information = child.trace.errors.copy()
            bundle.missing_evidence.append(part.requirement_id)
        trace.selected_agents.extend(child.trace.selected_agents)
        trace.executed_agents.extend(child.trace.executed_agents)
        trace.agent_stages.extend(child.trace.agent_stages)
        trace.tool_calls.extend(child.trace.tool_calls)
        trace.outcomes.extend(child.trace.outcomes)
        trace.candidate_count += child.trace.candidate_count
        trace.provider_calls += child.trace.provider_calls
        trace.known_total_tokens += child.trace.known_total_tokens
        trace.calls_with_unknown_tokens += child.trace.calls_with_unknown_tokens
        trace.provider_errors.extend(child.trace.provider_errors)
        trace.provider_stages.extend(child.trace.provider_stages)
        bundle.source_quality.extend(child.caveats)
        bundle.source_quality.extend(
            caveat
            for candidate in child.trace.document_candidates
            for caveat in candidate["caveats"]
        )
        for name in (
            "newly_accepted_claims",
            "reused_claims",
            "rejected_claims",
            "deferred_claims",
        ):
            setattr(response, name, getattr(response, name) + getattr(child, name))
    # Inspect original source paths for a selected document candidate. Structural
    # citations remain trace data and are never passed into M6 or the composer.
    candidates = [
        c for lane in bundle.lane_results for c in lane["response"]["trace"]["document_candidates"]
    ]
    graph_needed = any(
        p.kind in {"metric", "explanation", "source_context"} for p in plan.requirements
    )
    targets = {p.target for p in plan.requirements if p.lane == "financial"}
    # Metric identity is already the graph node identity, with exact operand edges.
    metric = next((m for m in scoped.catalog.metrics if m.definition.name in targets), None)
    if metric:
        start_node = metric.metric_id
    elif candidates:
        reference = candidates[0]["references"][0]
        start_node = graph_id(reference["kind"], reference["evidence"])
    else:
        fact = next(
            (
                f
                for f in scoped.catalog.facts
                if f.canonical_item_id in targets and f.context.period[:4] == str(year)
            ),
            None,
        )
        start_node = (
            graph_id("source_fact", fact.observation_identity().model_dump()) if fact else None
        )
    if start_node and graph_needed and not financial_binding_error:

        def graph_context():
            projection = CompositionGraphView(
                manifest,
                pipeline.document_repository,
                pipeline.catalog,
                document_id=document,
                composition_id=manifest.composition_id,
            )
            return GraphRetrievalTools(projection).get_graph_context(
                GetGraphContextRequest(
                    document_id=document,
                    composition_id=manifest.composition_id,
                    node_id=start_node,
                    depth=1,
                    limit=12,
                )
            )

        graph = stage("graph_context", graph_context)
        bundle.graph_paths.append(graph.model_dump(mode="json"))
        trace.tool_calls.append(
            dict(
                tool="get_graph_context",
                request=graph.request.model_dump(mode="json"),
                result=graph.model_dump(mode="json"),
            )
        )
        for node in ([graph.start] if graph.start else []) + graph.matches:
            bundle.original_citations.extend(
                c.model_dump(mode="json") for c in node.original_citations
            )
            bundle.source_quality.extend(node.caveats)
    trace.native_decisions = dict(Counter(o.final_decision for o in trace.outcomes))
    trace.selected_agents = list(dict.fromkeys(trace.selected_agents))
    trace.executed_agents = list(dict.fromkeys(trace.executed_agents))
    qa = VietnameseQARequest(**bound.model_dump(include=set(VietnameseQARequest.model_fields)))
    qa.allow_gateway = False
    if request.execution_mode != "deterministic" and request.allow_gateway:
        qa.adaptive_fusion_plan = plan
        qa.fusion_answer_requirements = fusion_requirements
    ledger = VerifiedClaimLedger(pipeline.repository)
    source = stage("composer", lambda: VietnameseQAComposer(ledger).compose(qa))
    for part in plan.requirements:
        coverage = [
            r
            for r in source.plan.requirements
            if r.requirement_id.startswith(part.requirement_id + ":")
        ]
        if part.support_status != "unsupported":
            part.support_status = (
                "accepted"
                if coverage and all(r.verified_claim_ids for r in coverage)
                else "missing"
            )
        if part.support_status == "accepted" and part.requirement_id in bundle.missing_evidence:
            bundle.missing_evidence.remove(part.requirement_id)
    rendered = stage("citations", lambda: pipeline.renderer.render_qa(source))
    firewall = stage(
        "firewall",
        lambda: InformationFirewall(ledger).evaluate_qa(
            request=qa, response=source, rendered=rendered
        ),
    )
    trace.document_release = dict(
        requirements=source.plan.model_dump(mode="json"), firewall=firewall.model_dump(mode="json")
    )
    bundle.source_quality = sorted(set(bundle.source_quality))
    trace.fusion_bundle = bundle.model_dump(mode="json")
    trace.unanswered_requirements = source.unanswered_requirements
    trace.m7_status, trace.firewall_decision = source.status, firewall.decision
    if firewall.release_status != "released":
        return stop("firewall_blocked", firewall.blockers)
    view = firewall.validated_output
    response.answer_vi, response.citations = view.rendered_text, view.references
    response.used_verified_claim_ids = view.verified_claim_ids
    response.caveats, response.limitations = view.caveats, view.limitations
    response.status = (
        "partial_verified_coverage"
        if source.status == "partial"
        else "completed_with_caveats"
        if source.status == "answered" and view.caveats
        else "completed"
        if source.status == "answered"
        else "verification_blocked"
    )
    response.mode = (
        "CACHE_HIT"
        if response.used_verified_claim_ids
        and all(lane["response"]["mode"] == "CACHE_HIT" for lane in bundle.lane_results)
        else "PARTIAL_REUSE_AND_REFRESH"
        if response.reused_claims
        else "FRESH_M5_M6_M7"
        if response.newly_accepted_claims
        else "BLOCKED"
    )
    if not response.used_verified_claim_ids and trace.provider_errors:
        response.status, response.mode = "provider_unavailable", "PROVIDER_FAILURE"
    return response
