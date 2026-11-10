"""Application coordination of M5 → actual M6 → admitted ledger → M7 release."""

import re
from collections import Counter
from time import perf_counter

from ..agents import (
    AdaptiveSpecialistRouter,
    CashFlowEarningsQualitySpecialist,
    EvidenceAwareQueryPlanner,
    FinancialMultiAgentOrchestrator,
    LiquidityLeverageSpecialist,
    PlannerContext,
    ProfitabilitySpecialist,
    RiskAwareSupervisor,
)
from ..agents.document_qa_contracts import document_intent
from ..evidence.composition import payload_sha256
from ..evidence.snapshots import SnapshotCatalog
from ..outputs.citation_renderer import CitationRenderer
from ..outputs.firewall_qa_binding import request_inventory
from ..outputs.information_firewall import InformationFirewall
from ..outputs.qa_composer import VietnameseQAComposer, _assertion_signature, qa_claim_query
from ..outputs.qa_contracts import VietnameseQARequest
from ..tools.evidence_retrieval import EvidenceRetrievalTools
from ..tools.question_understanding import normalize, understand
from ..verification.adapter import to_verification_input
from ..verification.evidence_context import EvidenceContextBuilder
from ..verification.ledger import VerifiedClaimLedger, build_verified_claim
from ..verification.ledger_contracts import VerifiedClaimQuery
from ..verification.runtime import VerificationRuntime
from .qa_pipeline_contracts import (
    CandidateOutcome,
    FinancialQARequest,
    FinancialQAResponse,
    PipelineStage,
    PipelineTrace,
)


def _provider_failure_status(errors):
    if set(errors) & {"structured_output_invalid", "schema_mismatch"}:
        return "internal_error"
    return (
        "provider_unavailable"
        if set(errors)
        & {"provider_unavailable", "timeout", "rate_limit", "quota_exceeded", "authentication"}
        else "verification_blocked"
    )


class _RequestLedger:
    """Cache exact query results only for this synchronous request; invalidate on write."""

    def __init__(self, repository):
        self.ledger = VerifiedClaimLedger(repository)
        self.cache = {}

    def find_claims(self, query):
        key = query.model_dump_json()
        if key not in self.cache:
            self.cache[key] = self.ledger.find_claims(query)
        return self.cache[key].model_copy(deep=True)


class FinancialQAPipeline:
    def __init__(
        self,
        *,
        catalog,
        documents,
        repository,
        gateway=None,
        orchestrator=None,
        compositions=(),
        document_repository=None,
    ):
        self.catalog, self.documents, self.repository = catalog, list(documents), repository
        self.gateway, self.orchestrator = gateway, orchestrator
        self.renderer = CitationRenderer()
        self.compositions = tuple(compositions)
        self.document_repository = document_repository
        from ..evidence.release_activation import select_active_releases

        self.compositions, self.document_repository = select_active_releases(
            self.compositions, self.document_repository
        )

    def _m5(self, request, *, document=False, catalog=None):
        catalog = self.catalog if catalog is None else catalog
        gateway = (
            self.gateway
            if request.allow_gateway and request.execution_mode != "deterministic"
            else None
        )
        deterministic = request.execution_mode == "deterministic"
        return self.orchestrator or FinancialMultiAgentOrchestrator(
            planner=EvidenceAwareQueryPlanner(
                SnapshotCatalog([]) if document else catalog,
                () if document else self.documents,
                gateway,
            ),
            supervisor=RiskAwareSupervisor(catalog),
            router=AdaptiveSpecialistRouter(),
            specialists={
                "profitability": ProfitabilitySpecialist(
                    gateway, model=request.model, deterministic=deterministic
                ),
                "liquidity_and_leverage": LiquidityLeverageSpecialist(
                    gateway, model=request.model, deterministic=deterministic
                ),
                "cash_flow_and_earnings_quality": CashFlowEarningsQualitySpecialist(
                    gateway, model=request.model, deterministic=deterministic
                ),
            },
        )

    def _document_identities(self, request, year, *, strict_year=False):
        documents = [
            d
            for d in self.documents
            if (
                (request.document_id is None or d.document_id == request.document_id)
                and (request.company_id is None or d.company_id == request.company_id)
                and (
                    year is None
                    or (request.document_id is not None and not strict_year)
                    or d.reporting_year == year
                )
            )
        ]
        # Use declared aliases as constraints, never filenames or text similarity.
        text = normalize(request.question)
        mentioned = {
            d.company_id
            for d in self.documents
            if any(
                re.search(r"(?<!\w)" + re.escape(normalize(a)) + r"(?!\w)", text)
                for a in d.company_aliases
            )
        }
        if mentioned:
            documents = [d for d in documents if mentioned == {d.company_id}]
        return {(d.document_id, d.company_id) for d in documents}

    def _context(self, request):
        parsed, issues = understand(request.question)
        blocked = {
            "cross_document_comparison_blocked_D03_B10",
            "unsupported_question_or_formula",
            "unsupported_formula",
            "non_annual_period_unsupported",
            "invalid_period",
            "multiple_periods_unsupported",
        } & set(issues)
        if blocked and not (
            request.execution_mode == "auto"
            and blocked == {"cross_document_comparison_blocked_D03_B10"}
        ):
            return None, "unsupported", sorted(blocked)
        year = parsed.reporting_year or (int(request.period[:4]) if request.period else None)
        if year is None and request.execution_mode == "auto":
            filing = re.findall(
                r"bao cao(?: nam)? ((?:19|20|21)\d{2})", normalize(request.question)
            )
            if len(set(filing)) == 1:
                year = int(filing[0])
            if year is None:
                # A unique declared company-alias/year pair identifies a filing;
                # another unanchored year can be its comparative column. Two
                # explicit filings remain ambiguous and are never merged here.
                text = normalize(request.question)
                anchored = {
                    int(match[1])
                    for document in self.documents
                    for alias in document.company_aliases
                    for match in re.finditer(
                        r"(?<!\w)"
                        + re.escape(normalize(alias))
                        + r"\s+(?:nam\s+)?((?:19|20|21)\d{2})\b",
                        text,
                    )
                }
                if len(anchored) == 1:
                    year = next(iter(anchored))
        identities = self._document_identities(request, year)
        if len(identities) != 1:
            return None, "clarification_required", ["document_company_binding_unresolved"]
        document, company = next(iter(identities))
        selection = self.catalog.select(document, request.snapshot_id)
        if selection.status != "selected":
            return None, "clarification_required", ["snapshot_" + selection.status]
        snapshot = selection.candidates[0].descriptor.snapshot_id
        bound = request.model_copy(
            update=dict(
                document_id=document,
                company_id=company,
                snapshot_id=snapshot,
            )
        )
        if year is None:
            return None, "clarification_required", ["period_required"]
        from ..evidence.metric_preparation import prepare_missing_metric

        # Request-bound metadata preparation uses existing formula authority only.
        # Computation, compatibility, M6 and ledger admission still run normally.
        self.catalog = prepare_missing_metric(
            self.catalog, document, snapshot, year, parsed.formula_id
        )
        if parsed.formula_id and not any(
            m.definition.name == parsed.formula_id
            and (m.request.document_id, m.request.snapshot_id) == (document, snapshot)
            for m in self.catalog.metrics
        ):
            policies = [p for p in self.catalog.policies if p.formula_id == parsed.formula_id]
            reason = "approved_metric_preparation_unavailable"
            if len(policies) == 1:
                comparative = policies[0].period_relation == "consecutive_fiscal_years_descending"
                counts = [
                    sum(
                        (f.document_id, f.snapshot_id, f.canonical_item_id, f.context.period)
                        == (
                            document,
                            snapshot,
                            operand.canonical_item_id,
                            str(year - int(comparative and i == 1))
                            + ("-12-31" if operand.statement_type == "B01" else ""),
                        )
                        for f in self.catalog.facts
                    )
                    for i, operand in enumerate(policies[0].operands)
                ]
                if any(count != 1 for count in counts):
                    reason = "metric_operands_missing_or_ambiguous"
            return None, "unsupported", [reason]
        plan, status = request_inventory(bound, [])
        if status in {"unsupported", "clarification_required"} and request.execution_mode != "auto":
            return None, status, plan.reasons + plan.missing_information
        scope = request.reporting_scope or parsed.reporting_scope
        if scope:
            resolution = self.catalog.get_reporting_scope(document, snapshot)
            if (
                resolution.status != "resolved"
                or resolution.evidence_status != "confirmed"
                or resolution.reporting_scope != scope
            ):
                return None, "clarification_required", ["requested_scope_unconfirmed"]
        if not any(
            (f.document_id, f.snapshot_id, f.company_id) == (document, snapshot, company)
            and f.context.period[:4] == str(year)
            for f in self.catalog.facts
        ):
            return None, "verification_blocked", ["no_usable_context_evidence"]
        return bound, None, []

    def _document_context(self, request):
        parsed, issues = understand(request.question)
        if set(issues) & {
            "cross_document_comparison_blocked_D03_B10",
            "non_annual_period_unsupported",
            "invalid_period",
            "multiple_periods_unsupported",
            "semantic_intent_requires_gateway",
        }:
            return None, None, issues
        if parsed.period or request.period or request.reporting_scope or parsed.reporting_scope:
            return None, None, ["document_reporting_context_unconfirmed"]
        identities = self._document_identities(request, parsed.reporting_year, strict_year=True)
        if len(identities) != 1:
            return None, None, ["document_company_binding_unresolved"]
        document, company = next(iter(identities))
        manifests = [
            m
            for m in self.compositions
            if m.logical_document_id == document
            and (request.composition_id is None or m.composition_id == request.composition_id)
        ]
        if len(manifests) != 1 or self.document_repository is None:
            return None, None, ["approved_document_composition_required"]
        manifest = manifests[0]
        snapshots = {
            source.descriptor.snapshot_id
            for source in manifest.sources
            if source.status == "verified"
        }
        if request.snapshot_id and request.snapshot_id not in snapshots:
            return None, None, ["document_snapshot_not_in_composition"]
        digest = payload_sha256(manifest.model_dump(mode="json"))
        if request.composition_sha256 and request.composition_sha256 != digest:
            return None, None, ["document_composition_fingerprint_mismatch"]
        bound = request.model_copy(
            update=dict(
                document_id=document,
                company_id=company,
                composition_id=manifest.composition_id,
                composition_sha256=digest,
            )
        )
        return bound, manifest, []

    def _run_document(self, request, requirements, response, stage, stop, recovery_seen):
        trace = response.trace
        bound, manifest, reasons = stage("context", lambda: self._document_context(request))
        if reasons:
            return stop("clarification_required", reasons)
        trace.document_id = bound.document_id
        trace.company_id = bound.company_id
        trace.snapshot_id = bound.snapshot_id
        trace.composition_id = bound.composition_id
        trace.planner_intent = "document"
        adaptive_document = bound.execution_mode != "deterministic" and bound.allow_gateway
        if not adaptive_document:
            trace.limitations.append("document_deterministic_no_gateway")
        qa_request = VietnameseQARequest(
            **bound.model_dump(include=set(VietnameseQARequest.model_fields))
        )
        qa_request.allow_gateway = False
        ledger = _RequestLedger(self.repository)
        query = qa_claim_query(qa_request, None)
        # Validate current composition pins before a cache hit or fresh retrieval.
        tools = stage(
            "composition",
            lambda: EvidenceRetrievalTools.from_composition(
                manifest,
                self.document_repository,
                document_id=bound.document_id,
                composition_id=bound.composition_id,
            ),
        )
        try:
            entries = stage("ledger_lookup", lambda: ledger.find_claims(query).claims)
            plan, coverage = request_inventory(qa_request, entries)
            existing_ids = set(plan.selected_verified_claim_ids)
            if coverage == "answered" and not bound.force_refresh:
                response.mode = "CACHE_HIT"
            else:
                document_histories = None

                def execute_document():
                    nonlocal document_histories
                    if adaptive_document:
                        from ..agents.document_controller import run_document_adaptive

                        try:
                            bundles, candidates, document_histories, rounds = run_document_adaptive(
                                self.gateway,
                                bound,
                                requirements,
                                manifest,
                                tools,
                            )
                            trace.adaptive_rounds.extend(rounds)
                            return bundles, candidates
                        except ValueError:
                            trace.limitations.append(
                                "document_planner_failed_exact_source_fallback"
                            )
                            trace.execution_events.append(
                                dict(event="PROVIDER_DEGRADED", component="DocumentPlanner")
                            )
                    return self._m5(bound, document=True).run_document(
                        requirements, manifest, bound.company_id, bound.snapshot_id, tools
                    )

                bundles, candidates = stage(
                    "m5",
                    execute_document,
                )
                trace.planner_status = "planned"
                trace.agent_stages = [
                    {"component": "EvidenceAwareQueryPlanner", "stage": "document_planning"},
                    {"component": "RiskAwareSupervisor", "stage": "document_search"},
                    {
                        "component": "FinancialMultiAgentOrchestrator",
                        "stage": "document_candidate_generation",
                    },
                ]
                trace.selected_agents = [
                    "EvidenceAwareQueryPlanner",
                    "RiskAwareSupervisor",
                    "FinancialMultiAgentOrchestrator",
                ]
                trace.executed_agents = (
                    ["Planner"]
                    if adaptive_document
                    and any(
                        e["event"] == "LLM_AGENT_EXECUTED"
                        and e["request_id"].startswith("document-planner-")
                        for e in getattr(self.gateway, "events", [])
                    )
                    else []
                )
                trace.execution_events.extend(
                    [
                        dict(event="TOOL_EXECUTED", component="BM25"),
                        dict(
                            event="DETERMINISTIC_COMPONENT_EXECUTED",
                            component="DocumentCandidateBuilder",
                        ),
                    ]
                )
                trace.tool_calls = [
                    dict(
                        component="RiskAwareSupervisor",
                        tool=b.operation.operation,
                        operation_id=b.operation.operation_id,
                        request=b.operation.request.model_dump(mode="json"),
                        requirement=b.operation.requirement.target,
                        status=b.result.status,
                        reasons=b.result.reasons,
                        matches=[
                            dict(
                                evidence_ids=[e.model_dump(mode="json") for e in m.evidence_ids],
                                snapshot_id=m.snapshot_id,
                                pdf_page=m.pdf_page,
                                reasons=m.ranking_reasons,
                                limitations=m.limitations,
                            )
                            for m in b.result.matches
                        ],
                    )
                    for b in bundles
                ]
                trace.document_candidates = [c.model_dump(mode="json") for c in candidates]
                trace.candidate_count = len(candidates)
                if any(b.result.status == "unavailable" for b in bundles) and not existing_ids:
                    return stop("verification_blocked", ["document_search_unavailable"])
                if candidates:
                    histories = stage(
                        "m6",
                        lambda: (
                            document_histories
                            if document_histories is not None
                            else VerificationRuntime.verify_document(
                                candidates,
                                EvidenceContextBuilder(tools=tools),
                                manifest,
                                bound.company_id,
                                bound.snapshot_id,
                            )
                        ),
                    )
                    trace.tool_calls.extend(
                        dict(
                            component="EvidenceContextBuilder",
                            tool="get_evidence_sources",
                            request={"reference": e.reference.model_dump(mode="json")},
                            status="resolved" if e.available else "unavailable",
                            reasons=e.caveats,
                            snapshot_id=e.snapshot_id,
                            pages=sorted(
                                {c.pdf_page for c in e.citations if c.pdf_page is not None}
                            ),
                        )
                        for history in histories
                        for e in history.final.evidence
                    )
                    from ..evidence.conditional_recovery import recover_histories

                    recovery = stage(
                        "ocr_recovery_detection",
                        lambda: recover_histories(
                            histories,
                            manifest,
                            self.document_repository,
                            seen=recovery_seen,
                            gateway=self.gateway,
                            allow_gateway=bool(
                                self.gateway
                                and bound.allow_gateway
                                and bound.execution_mode != "deterministic"
                            ),
                        ),
                    )
                    if recovery:
                        trace.document_release["ocr_recovery"] = recovery
                        trace.provider_calls += sum(r.get("calls", 0) for r in recovery)
                        trace.known_total_tokens += sum(
                            (r.get("usage", {}).get("total_tokens") or 0) for r in recovery
                        )
                        trace.provider_errors.extend(
                            r["error_code"] for r in recovery if "error_code" in r
                        )
                    results = stage("admission", lambda: self.repository.admit_many(histories))
                    for history, result in zip(histories, results, strict=True):
                        decision = history.final
                        trace.outcomes.append(
                            CandidateOutcome(
                                candidate_id=decision.original_claim.candidate_id,
                                initial_decision=decision.decision,
                                final_decision=decision.decision,
                                reasons=decision.reasons,
                                validation={
                                    k: "pass" if passed else "fail"
                                    for k, passed in decision.checks.items()
                                },
                                evidence_status="supported"
                                if decision.checks["content_fidelity"]
                                else "insufficient_evidence",
                                logic_statuses=[
                                    "consistent"
                                    if decision.checks["relationship_support"]
                                    else "insufficient_context"
                                ],
                                admission_status=result.status,
                                verified_claim_id=result.verified_claim_id,
                            )
                        )
                        if result.status == "stored":
                            response.newly_accepted_claims += 1
                    trace.native_decisions = dict(Counter(o.final_decision for o in trace.outcomes))
                    response.rejected_claims = sum(r.status == "rejected" for r in results)
                    response.deferred_claims = trace.native_decisions.get("INVESTIGATE", 0)
                    ledger.cache.clear()
            source = stage("composer", lambda: VietnameseQAComposer(ledger).compose(qa_request))
            trace.answer_requirements = source.plan.requirements
            trace.m7_status = source.status
            trace.unanswered_requirements = source.unanswered_requirements
            rendered = stage("citations", lambda: self.renderer.render_qa(source))
            firewall = stage(
                "firewall",
                lambda: InformationFirewall(ledger).evaluate_qa(
                    request=qa_request,
                    response=source,
                    rendered=rendered,
                ),
            )
            trace.firewall_decision = firewall.decision
            trace.document_release = dict(
                **trace.document_release,
                requirements=source.plan.model_dump(mode="json"),
                firewall=firewall.model_dump(mode="json"),
            )
            view = firewall.validated_output
            if firewall.release_status != "released":
                response.answer_vi = view.message_vi
                return stop("firewall_blocked", firewall.blockers)
            response.answer_vi, response.citations = view.rendered_text, view.references
            response.used_verified_claim_ids = view.verified_claim_ids
            response.caveats, response.limitations = view.caveats, view.limitations
            response.reused_claims = len(set(view.verified_claim_ids) & existing_ids)
            response.status = {
                "answered": "completed_with_caveats" if view.caveats else "completed",
                "partial": "partial_verified_coverage",
            }.get(source.status, "verification_blocked")
            if response.used_verified_claim_ids and response.mode != "CACHE_HIT":
                response.mode = "PARTIAL_REUSE_AND_REFRESH" if existing_ids else "FRESH_M5_M6_M7"
            return response
        finally:
            tools.close_search()

    def run(self, request: FinancialQARequest, *, recovery_seen=None) -> FinancialQAResponse:
        from copy import copy

        from ..core.request_gateway import RequestGateway

        request = FinancialQARequest.model_validate(request)
        scoped = copy(self)
        if request.execution_mode == "auto" and self.gateway is None and request.allow_gateway:
            result = scoped._run(
                request.model_copy(update={"execution_mode": "deterministic"}),
                recovery_seen=recovery_seen,
            )
            result.trace.execution_events.append(
                dict(event="PROVIDER_DEGRADED", reason="gateway_unavailable_deterministic_baseline")
            )
            return result
        if request.execution_mode != "deterministic" and request.allow_gateway and self.gateway:
            if not isinstance(self.gateway, RequestGateway):
                scoped.gateway = RequestGateway(
                    self.gateway,
                    max_calls=request.max_provider_calls,
                    timeout_seconds=request.request_timeout_seconds,
                )
            start = len(scoped.gateway.events)
            result = scoped._run(request, recovery_seen=recovery_seen)
            events = scoped.gateway.events[start:]
            result.trace.execution_events.extend(events)
            result.trace.provider_calls = len(events)
            result.trace.known_total_tokens = sum(e["tokens"] or 0 for e in events)
            result.trace.calls_with_unknown_tokens = sum(e["tokens"] is None for e in events)
            result.trace.provider_errors = [e["error"] for e in events if e["error"]]
            result.trace.provider_stages = [
                dict(
                    stage=e["request_id"].rsplit("-", 1)[0],
                    calls=1,
                    known_total_tokens=e["tokens"],
                    errors=[e["error"]] if e["error"] else [],
                    model=e["model"],
                    usage=e["usage"],
                    cost=e["cost"],
                    latency_ms=e["latency_ms"],
                )
                for e in events
            ]
            if scoped.gateway.exhausted:
                result.trace.limitations.append("request_provider_budget_exhausted")
            return result
        return scoped._run(request, recovery_seen=recovery_seen)

    def _run(self, request: FinancialQARequest, *, recovery_seen=None) -> FinancialQAResponse:
        recovery_seen = set() if recovery_seen is None else recovery_seen
        request = FinancialQARequest.model_validate_json(request.model_dump_json())
        started = perf_counter()
        trace = PipelineTrace(request_id=request.request_id)
        response = FinancialQAResponse(trace=trace)
        current = "context"

        def stage(name, call):
            nonlocal current
            current = name
            start = perf_counter()
            try:
                value = call()
            except Exception:
                trace.stages[name] = PipelineStage(
                    status="FAILED", latency_ms=(perf_counter() - start) * 1000
                )
                raise
            trace.stages[name] = PipelineStage(
                status="COMPLETED", latency_ms=(perf_counter() - start) * 1000
            )
            return value

        def stop(status, reasons=()):
            response.status = status
            trace.errors.extend(reasons)
            if status == "clarification_required":
                response.mode = "CLARIFICATION_REQUIRED"
                response.answer_vi = (
                    "Cần làm rõ tài liệu, snapshot, kỳ, chỉ tiêu hoặc phạm vi báo cáo."
                )
            elif status == "unsupported":
                response.answer_vi = "Yêu cầu vượt quá khả năng QA đã được hỗ trợ."
                if "metric_operands_missing_or_ambiguous" in reasons:
                    response.answer_vi = "Chưa có đủ toán hạng duy nhất trong tài liệu và snapshot đã chọn để tính chỉ số."
                elif (
                    "approved_metric_preparation_unavailable" in reasons
                    or "metric_missing_or_ambiguous_in_selected_filing" in reasons
                ):
                    response.answer_vi = "Chưa có metric được chuẩn bị hợp lệ và duy nhất cho kỳ, tài liệu và snapshot đã chọn."
            elif status == "provider_unavailable":
                response.mode = "PROVIDER_FAILURE"
                response.answer_vi = "Nhà cung cấp chưa khả dụng; chưa có đủ claim đã xác minh."
            elif status == "internal_error":
                response.answer_vi = "Chưa xử lý được yêu cầu do lỗi kỹ thuật. Ngữ cảnh hội thoại được giữ để bạn có thể tiếp tục."
            return response

        def usage(name, metadata):
            if not metadata.calls:
                return
            trace.provider_calls += metadata.calls
            tokens = metadata.usage.total_tokens if metadata.usage else None
            trace.known_total_tokens += tokens or 0
            trace.calls_with_unknown_tokens += (
                sum(a.response.usage.total_tokens is None for a in metadata.attempts)
                if metadata.attempts
                else (metadata.calls if tokens is None else 0)
            )
            errors = [a.response.error.code for a in metadata.attempts if a.response.error]
            if metadata.error and not errors:
                errors = [metadata.error.code]
            trace.provider_errors.extend(errors)
            trace.provider_stages.append(
                dict(
                    stage=name,
                    calls=metadata.calls,
                    known_total_tokens=tokens,
                    errors=errors,
                    model=metadata.model.model_dump(mode="json") if metadata.model else None,
                    usage=metadata.usage.model_dump(mode="json") if metadata.usage else None,
                    cost=metadata.cost.model_dump(mode="json") if metadata.cost else None,
                    provider_error_codes=[
                        a.response.error.provider_error_code
                        for a in metadata.attempts
                        if a.response.error
                    ],
                )
            )

        try:
            intent, requirements = document_intent(request.question)
            from ..agents.fusion_contracts import is_mixed
            from .fusion_pipeline import run_fusion

            if is_mixed(request.question):
                return run_fusion(self, request, response, stage, stop, recovery_seen=recovery_seen)
            if intent == "mixed":
                _, issues = understand(request.question)
                if "cross_document_comparison_blocked_D03_B10" in issues:
                    return stop("unsupported", ["cross_document_comparison_blocked_D03_B10"])
                return stop("unsupported", ["mixed_decomposition_unresolved"])
            if intent == "document":
                return self._run_document(
                    request, requirements, response, stage, stop, recovery_seen
                )
            bound, blocked, reasons = stage("context", lambda: self._context(request))
            if blocked:
                trace.stages["context"].status = blocked
                return stop(blocked, reasons)
            trace.document_id, trace.snapshot_id, trace.company_id = (
                bound.document_id,
                bound.snapshot_id,
                bound.company_id,
            )
            parsed, _ = understand(bound.question)
            qa_request = VietnameseQARequest(
                **bound.model_dump(include=set(VietnameseQARequest.model_fields)),
            )
            # M7 protected deterministic composition is sufficient; no reorder call
            # on cache hits. All optional semantic calls belong to M5/M6 here.
            qa_request.allow_gateway = False
            ledger = _RequestLedger(self.repository)
            query = VerifiedClaimQuery(
                company_id=bound.company_id,
                document_id=bound.document_id,
                snapshot_id=bound.snapshot_id,
                period=bound.period or parsed.period,
            )
            entries = stage("ledger_lookup", lambda: ledger.find_claims(query).claims)
            plan, coverage = request_inventory(qa_request, entries)
            existing_ids = set(plan.selected_verified_claim_ids)
            response.reused_claims = len(existing_ids)
            if coverage == "clarification_required" and bound.execution_mode != "auto":
                return stop("clarification_required", plan.missing_information)
            if coverage == "answered" and not bound.force_refresh:
                response.mode = "CACHE_HIT"
            elif not bound.allow_gateway and bound.execution_mode != "deterministic":
                if not existing_ids:
                    return stop("verification_blocked", ["refresh_requires_allow_gateway"])
                response.mode = "PARTIAL_REUSE_ONLY"
                trace.limitations.append("refresh_disabled_missing_verified_coverage")
            else:

                def refresh():
                    from ..agents.adaptive_controller import AdaptiveFinancialController

                    if existing_ids:
                        trace.limitations.append("full_request_refresh_fallback")
                    adaptive_histories = None
                    snapshot = stage("request_snapshot", self.catalog.request_snapshot)
                    m5 = stage("m5_setup", lambda: self._m5(bound, catalog=snapshot))
                    controller = AdaptiveFinancialController(
                        m5, snapshot, self.gateway, bound.model
                    )

                    def execute():
                        nonlocal adaptive_histories
                        context = PlannerContext(
                            company_id=bound.company_id,
                            document_id=bound.document_id,
                            snapshot_id=bound.snapshot_id,
                            period=bound.period or parsed.period,
                            reporting_year=parsed.reporting_year
                            or (int(bound.period[:4]) if bound.period else None),
                            reporting_scope=bound.reporting_scope or parsed.reporting_scope,
                            mode=bound.execution_mode,
                            model=bound.model,
                            provider_attempt_limit=1,
                            conversation_context=bound.conversation_context,
                        )
                        if bound.execution_mode != "deterministic" and bound.allow_gateway:
                            output, adaptive_histories = controller.run(bound.question, context)
                            trace.adaptive_rounds = controller.rounds
                            return output
                        return m5.run(question=bound.question, context=context)

                    output = stage(
                        "m5",
                        execute,
                    )
                    trace.stages["m5"].status = output.status
                    if output.question != bound.question or any(
                        getattr(output.context, field) != getattr(bound, field)
                        for field in ("company_id", "document_id", "snapshot_id")
                    ):
                        return stop("verification_blocked", ["m5_request_context_mismatch"])
                    trace.planner_status = (
                        output.planner_result.status if output.planner_result else None
                    )
                    proposal = (
                        output.planner_result.effective_proposal if output.planner_result else None
                    )
                    trace.planner_intent = proposal.intent if proposal else None
                    if (
                        proposal
                        and bound.execution_mode == "auto"
                        and output.status in {"completed", "partial"}
                    ):
                        from ..outputs.qa_composer import planned_requirements

                        qa_request.answer_requirements = planned_requirements(
                            bound.question, proposal
                        )
                    trace.selected_agents = (
                        output.routing_decision.selected_roles if output.routing_decision else []
                    )
                    trace.agent_stages = [e.model_dump(mode="json") for e in output.trace]
                    trace.executed_agents = list(
                        dict.fromkeys(
                            e.role
                            for e in output.trace
                            if e.stage == "specialist_execution"
                            and any(
                                x.role == e.role and x.llm.calls and x.llm.status == "success"
                                for x in output.specialist_executions
                            )
                        )
                    )
                    trace.financial_execution = output.model_dump(mode="json")
                    if output.supervisor_result:
                        trace.tool_calls = [
                            dict(
                                request=e.bound_request,
                                result=e.response.model_dump(mode="json") if e.response else None,
                                tool=e.operation,
                                event=e.execution_kind,
                                status=e.final_state,
                                latency_ms=e.latency_ms,
                                reasons=e.reasons,
                            )
                            for e in output.supervisor_result.tool_trace
                        ]
                    for name, metadata in output.usage.stages.items():
                        usage(name, metadata)
                    if output.status not in {"completed", "partial"}:
                        status = {
                            "failed": _provider_failure_status(trace.provider_errors)
                            if trace.provider_errors
                            else "verification_blocked"
                            if output.planner_result
                            and any(
                                reason.startswith(("invalid_", "answer_target_"))
                                for reason in output.planner_result.reasons
                            )
                            else "internal_error",
                            "clarification_required": "clarification_required",
                            "unsupported": "unsupported",
                        }.get(output.status, "verification_blocked")
                        return stop(status, output.stop_conditions)
                    batch = (
                        controller.batch
                        if adaptive_histories is not None
                        else to_verification_input(output)
                    )
                    # Exact duplicates from one upstream result are one candidate.
                    unique = {}
                    for claim in batch.claims:
                        old = unique.get(claim.candidate_id)
                        if old is not None and old != claim:
                            return stop("verification_blocked", ["conflicting_duplicate_candidate"])
                        unique[claim.candidate_id] = claim
                    batch.claims = list(unique.values())
                    if len(unique) == len(set(c.candidate_id for c in output.candidates)):
                        batch.issues = [
                            i for i in batch.issues if i.code != "duplicate_candidate_id"
                        ]
                    trace.candidate_count = len(batch.claims)
                    # Reject foreign identities/citations before semantic calls or writes.
                    if any(
                        (c.company_id, c.document_id, c.snapshot_id)
                        != (bound.company_id, bound.document_id, bound.snapshot_id)
                        or any(
                            (
                                x.document_id,
                                x.snapshot_id,
                                x.source.document_id,
                                x.source.snapshot_id,
                            )
                            != (bound.document_id, bound.snapshot_id) * 2
                            for x in c.citations
                        )
                        for c in batch.claims
                    ):
                        return stop("verification_blocked", ["candidate_source_context_mismatch"])
                    if batch.claims:
                        runtime = (
                            controller
                            if adaptive_histories is not None
                            else VerificationRuntime(
                                self.catalog,
                                self.gateway
                                if bound.allow_gateway and bound.execution_mode != "deterministic"
                                else None,
                                model=bound.model,
                            )
                        )
                        histories = stage(
                            "m6",
                            lambda: (
                                adaptive_histories
                                if adaptive_histories is not None
                                else runtime.verify(batch)
                            ),
                        )
                        for name, metadata in runtime.provider_metadata:
                            usage("m6_" + name, metadata)
                        for name, latency in runtime.stage_latency_ms.items():
                            trace.stages["m6_" + name] = PipelineStage(
                                status="COMPLETED", latency_ms=latency
                            )
                        admitted = []
                        signatures = {
                            _assertion_signature(e): e.identity.verified_claim_id for e in entries
                        }
                        for history in histories:
                            final = history.outcome.final
                            outcome = CandidateOutcome(
                                candidate_id=history.outcome.parent_candidate_id,
                                initial_decision=history.outcome.attempts[0].decision,
                                final_decision=final.decision,
                                reasons=final.reason_codes,
                                validation={
                                    c.check_id: c.status
                                    for c in sorted(
                                        final.validation.checks,
                                        key=lambda c: {
                                            "not_applicable": 0,
                                            "pass": 1,
                                            "undetermined": 2,
                                            "fail": 3,
                                        }[c.status],
                                    )
                                }
                                if final.validation
                                else {},
                                evidence_status=final.evidence.status if final.evidence else None,
                                logic_statuses=[a.status for a in final.logic.assertions]
                                if final.logic
                                else [],
                            )
                            trace.outcomes.append(outcome)
                            if final.decision == "ACCEPT":
                                entry = build_verified_claim(history)
                                signature = _assertion_signature(entry)
                                if signature in signatures:
                                    outcome.admission_status = "idempotent"
                                    outcome.verified_claim_id = signatures[signature]
                                else:
                                    signatures[signature] = entry.identity.verified_claim_id
                                    admitted.append((history, outcome))
                        if admitted:
                            results = stage(
                                "admission",
                                lambda: self.repository.admit_many([h for h, _ in admitted]),
                            )
                            for (_, outcome), result in zip(admitted, results, strict=True):
                                outcome.admission_status, outcome.verified_claim_id = (
                                    result.status,
                                    result.verified_claim_id,
                                )
                                if result.status == "stored":
                                    response.newly_accepted_claims += 1
                                if result.reason:
                                    trace.errors.append(result.reason)
                        trace.native_decisions = dict(
                            Counter(o.final_decision for o in trace.outcomes)
                        )
                        # Native policy has ABSTAIN/INVESTIGATE, no fabricated REJECT threshold.
                        response.rejected_claims = trace.native_decisions.get("ABSTAIN", 0)
                        response.deferred_claims = trace.native_decisions.get("INVESTIGATE", 0)
                        ledger.cache.clear()
                        stage("ledger_reload", lambda: ledger.find_claims(query))
                    if output.conflicts:
                        return stop("verification_blocked", ["unresolved_candidate_conflicts"])
                    response.mode = "PARTIAL_REUSE_AND_REFRESH" if existing_ids else "BLOCKED"

                stopped = refresh()
                if stopped is not None:
                    if not existing_ids or stopped.status not in {
                        "clarification_required",
                        "provider_unavailable",
                        "unsupported",
                    }:
                        return stopped
                    response.mode = "PARTIAL_REUSE_AND_REFRESH"
                    trace.limitations.append("refresh_stopped_preserved_verified_partial")

            source = stage("composer", lambda: VietnameseQAComposer(ledger).compose(qa_request))
            trace.answer_requirements = source.plan.requirements
            trace.m7_status = source.status
            trace.unanswered_requirements = source.unanswered_requirements
            rendered = stage("citations", lambda: self.renderer.render_qa(source))
            decision = stage(
                "firewall",
                lambda: InformationFirewall(ledger).evaluate_qa(
                    request=qa_request,
                    response=source,
                    rendered=rendered,
                ),
            )
            trace.firewall_decision = decision.decision
            view = decision.validated_output
            if decision.release_status != "released":
                response.answer_vi = view.message_vi
                return stop(
                    "firewall_blocked"
                    if decision.decision == "BLOCK"
                    else "clarification_required",
                    decision.blockers,
                )
            response.answer_vi, response.citations = view.rendered_text, view.references
            response.used_verified_claim_ids = view.verified_claim_ids
            response.caveats, response.limitations = view.caveats, view.limitations
            response.status = {
                "answered": "completed_with_caveats" if view.caveats else "completed",
                "partial": "partial_verified_coverage",
                "unsupported": "unsupported",
            }.get(source.status, "verification_blocked")
            if not view.verified_claim_ids and trace.provider_errors:
                return stop(_provider_failure_status(trace.provider_errors), trace.provider_errors)
            if (
                response.mode == "BLOCKED"
                and response.newly_accepted_claims
                and view.verified_claim_ids
            ):
                response.mode = "FRESH_M5_M6_M7"
            response.reused_claims = len(set(view.verified_claim_ids) & existing_ids)
            return response
        except Exception as error:
            from pydantic import ValidationError

            if isinstance(error, ValidationError):
                trace.errors.extend(
                    "schema:" + ".".join(str(p) for p in e["loc"]) + ":" + e["type"]
                    for e in error.errors(include_input=False)
                )
            return stop("internal_error", [current + ":" + type(error).__name__])
        finally:
            trace.total_latency_ms = (perf_counter() - started) * 1000
