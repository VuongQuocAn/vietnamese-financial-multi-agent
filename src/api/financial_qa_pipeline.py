"""Application coordination of M5 → actual M6 → admitted ledger → M7 release."""

import re
from collections import Counter
from time import perf_counter

from ..agents import (
    PlannerContext,
)
from ..tools.evidence_retrieval import EvidenceRetrievalTools
from ..tools.question_understanding import normalize
from ..verification.adapter import to_verification_input
from ..verification.evidence_context import EvidenceContextBuilder
from ..verification.ledger import VerifiedClaimLedger, build_verified_claim
from ..verification.ledger_contracts import VerifiedClaimQuery
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
        self.compositions = tuple(compositions)
        self.document_repository = document_repository
        if (
            not self.compositions
            and self.document_repository is None
            and len(catalog.descriptors) == 1
            and catalog.descriptors[0].source_kind == "json"
        ):
            from ..evidence.json_catalog import json_document_composition

            self.compositions = (json_document_composition(catalog),)
            self.document_repository = catalog
        from ..evidence.release_activation import select_active_releases

        self.compositions, self.document_repository = select_active_releases(
            self.compositions, self.document_repository
        )

    def _m5(self, request, *, catalog=None):
        from ..agents.lite_orchestrator import FinancialLiteOrchestrator

        catalog = self.catalog if catalog is None else catalog
        matches = [
            m
            for m in self.compositions
            if m.financial_snapshot is not None
            and (m.financial_snapshot.document_id, m.financial_snapshot.snapshot_id)
            == (request.document_id, request.snapshot_id)
            and (request.composition_id is None or m.composition_id == request.composition_id)
        ]
        return self.orchestrator or FinancialLiteOrchestrator(
            catalog,
            self.gateway
            if request.allow_gateway and request.execution_mode != "deterministic"
            else None,
            graph_enabled=request.m5_graph,
            composition=matches[0] if len(matches) == 1 else None,
            document_repository=self.document_repository,
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
        """Bind explicit selections and declared filing metadata; the model owns question semantics."""
        identities = self._document_identities(request, None)
        if len(identities) != 1:
            return None, "clarification_required", ["document_company_binding_unresolved"]
        document, company = next(iter(identities))
        selection = self.catalog.select(document, request.snapshot_id)
        if selection.status != "selected":
            return None, "clarification_required", ["snapshot_" + selection.status]
        snapshot = selection.candidates[0].descriptor.snapshot_id
        scope = request.reporting_scope
        if scope:
            resolution = self.catalog.get_reporting_scope(document, snapshot)
            if (
                resolution.status != "resolved"
                or resolution.evidence_status not in {"confirmed", "json_bound"}
                or resolution.reporting_scope != scope
            ):
                return None, "clarification_required", ["requested_scope_unconfirmed"]
        return (
            request.model_copy(
                update=dict(
                    document_id=document,
                    company_id=company,
                    snapshot_id=snapshot,
                    reporting_scope=scope,
                )
            ),
            None,
            [],
        )

    def _admit_documents(self, histories, response):
        trace = response.trace
        results = self.repository.admit_many(histories)
        for history, result in zip(histories, results, strict=True):
            decision = history.final
            trace.outcomes.append(
                CandidateOutcome(
                    candidate_id=decision.original_claim.candidate_id,
                    initial_decision=decision.decision,
                    final_decision=decision.decision,
                    reasons=decision.reasons,
                    validation={
                        k: "pass" if passed else "fail" for k, passed in decision.checks.items()
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
        return results

    def run(self, request: FinancialQARequest, *, recovery_seen=None) -> FinancialQAResponse:
        from copy import copy

        from ..core.request_gateway import RequestGateway

        request = FinancialQARequest.model_validate(request)
        scoped = copy(self)
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
        trace = PipelineTrace(
            request_id=request.request_id,
            answer_mode="lite",
            verification_mode="lite",
        )
        response = FinancialQAResponse(trace=trace)
        current = "context"
        bound, ledger, query = None, None, None
        lite_releasing = False
        lite_technical_failure = False
        document_bindings = {}

        def release_lite():
            nonlocal lite_releasing
            from ..outputs.qa_lite import compose_lite
            from .claim_selection import select_claims

            lite_releasing = True
            entries = ledger.find_claims(query).claims
            current_ids = [o.verified_claim_id for o in trace.outcomes if o.verified_claim_id]
            selected, excluded = select_claims(
                bound,
                entries,
                current_ids,
                scope_resolution=self.catalog.get_reporting_scope(
                    bound.document_id, bound.snapshot_id
                ),
            )
            selected.extend(
                entry
                for key in document_bindings
                if (entry := self.repository.get(key)) is not None
            )
            from ..verification.evidence_obligations import current_goal_support
            from ..verification.lite_contracts import LiteVerificationHistoryV2

            trace.integration_context["verified_requirements"] = {
                entry.identity.verified_claim_id: current_goal_support(
                    entry, bound.question, trace.integration_context.get("requirements", [])
                )
                if isinstance(entry.history, LiteVerificationHistoryV2)
                and entry.history.proof.batch.question == bound.question
                else document_bindings[entry.identity.verified_claim_id]
                if entry.identity.verified_claim_id in document_bindings
                else []
                for entry in selected
            }
            fields, metadata = stage(
                "composer",
                lambda: compose_lite(
                    bound,
                    selected,
                    gateway=self.gateway,
                    technical_errors=(
                        trace.integration_context.get("technical_errors", [])
                        or (trace.errors if lite_technical_failure else ())
                    ),
                    coverage_context=trace.integration_context,
                    source_available=any(
                        (f.document_id, f.snapshot_id, f.company_id)
                        == (bound.document_id, bound.snapshot_id, bound.company_id)
                        for f in self.catalog.facts
                    ),
                ),
            )
            metadata.update(
                input_claims=[e.identity.verified_claim_id for e in entries],
                excluded_claims=excluded,
            )
            trace.m7_lite = metadata
            if (
                not fields["used_verified_claim_ids"]
                and trace.integration_context.get("technical_errors")
                and (not trace.provider_errors)
            ):
                fields["status"] = "internal_error"
                metadata["final_status"] = "internal_error"
            trace.m7_status = fields["status"]
            trace.firewall_decision = "LITE_INTEGRITY_RELEASE" if selected else "LITE_NO_FINDINGS"
            trace.stages["citations"] = PipelineStage(status="COMPLETED")
            trace.stages["firewall"] = PipelineStage(
                status="NOT_EXECUTED", reasons=["lite_integrity_path"]
            )
            for key, value in fields.items():
                setattr(response, key, value)
            response.reused_claims = len(set(fields["used_verified_claim_ids"]) - set(current_ids))
            if fields["used_verified_claim_ids"] and response.mode in {
                "BLOCKED",
                "CLARIFICATION_REQUIRED",
                "PROVIDER_FAILURE",
            }:
                response.mode = "FRESH_M5_M6_M7" if current_ids else "PARTIAL_REUSE_ONLY"
            trace.provider_calls += metadata["calls"]
            trace.known_total_tokens += metadata["known_total_tokens"]
            trace.calls_with_unknown_tokens += metadata["unknown_usage"]
            return response

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
            nonlocal lite_technical_failure
            response.status = status
            trace.errors.extend(reasons)
            if ledger is not None and (not lite_releasing):
                lite_technical_failure = status in {"internal_error", "provider_unavailable"}
                # A stopped Planner/refresh must not erase independently admitted findings.
                ledger.cache.clear()
                return release_lite()
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
            bound, blocked, reasons = stage("context", lambda: self._context(request))
            if blocked:
                trace.stages["context"].status = blocked
                return stop(blocked, reasons)
            trace.document_id, trace.snapshot_id, trace.company_id = (
                bound.document_id,
                bound.snapshot_id,
                bound.company_id,
            )
            ledger = _RequestLedger(self.repository)
            query = VerifiedClaimQuery(
                company_id=bound.company_id,
                document_id=bound.document_id,
                snapshot_id=bound.snapshot_id,
                period=None,
            )
            entries = stage("ledger_lookup", lambda: ledger.find_claims(query).claims)
            from .claim_selection import select_claims

            selected, _ = select_claims(
                bound,
                entries,
                scope_resolution=self.catalog.get_reporting_scope(
                    bound.document_id, bound.snapshot_id
                ),
            )
            existing_ids = {e.identity.verified_claim_id for e in selected}
            response.reused_claims = len(existing_ids)
            if not bound.allow_gateway and bound.execution_mode != "deterministic":
                if not existing_ids:
                    return stop("verification_blocked", ["refresh_requires_allow_gateway"])
                response.mode = "PARTIAL_REUSE_ONLY"
                trace.limitations.append("refresh_disabled_missing_verified_coverage")
            else:

                def refresh():

                    if existing_ids:
                        trace.limitations.append("full_request_refresh_fallback")
                    snapshot = stage("request_snapshot", self.catalog.request_snapshot)
                    m5 = stage("m5_setup", lambda: self._m5(bound, catalog=snapshot))

                    def execute():

                        context = PlannerContext(
                            company_id=bound.company_id,
                            document_id=bound.document_id,
                            snapshot_id=bound.snapshot_id,
                            period=bound.period,
                            reporting_year=int(bound.period[:4]) if bound.period else None,
                            reporting_scope=bound.reporting_scope,
                            mode=bound.execution_mode,
                            model=bound.model,
                            provider_attempt_limit=1,
                            conversation_context=bound.conversation_context,
                        )
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
                    trace.selected_agents = (
                        output.routing_decision.selected_roles if output.routing_decision else []
                    )
                    trace.agent_stages = [e.model_dump(mode="json") for e in output.trace]
                    trace.executed_agents = list(
                        dict.fromkeys(
                            e.role
                            for e in output.trace
                            if e.stage == "specialist_execution"
                            and e.outcome != "blocked"
                            and any(x.role == e.role for x in output.specialist_executions)
                        )
                    )
                    trace.financial_execution = output.model_dump(mode="json")
                    trace.integration_context = output.integration_context
                    trace.integration_context["technical_errors"] = [e.code for e in output.errors]
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
                    batch = to_verification_input(output)
                    trace.candidate_count = len(batch.claims) + len(output.document_candidates)
                    # Reject foreign identities/citations before semantic calls or writes.
                    if batch.claims:
                        from ..verification.lite_runtime import LiteVerificationRuntime

                        runtime = LiteVerificationRuntime(
                            snapshot,
                            self.gateway
                            if bound.allow_gateway and bound.execution_mode != "deterministic"
                            else None,
                            model=bound.model,
                        )
                        histories = stage(
                            "m6",
                            lambda: runtime.verify(
                                batch, integration_context=trace.integration_context
                            ),
                        )
                        trace.verification_mode = "lite"
                        trace.m6_lite = runtime.summary
                        trace.integration_context["supported_requirements"] = runtime.summary.get(
                            "supported_requirements", {}
                        )
                        trace.integration_context["technical_errors"].extend(
                            reason
                            for finding in runtime.summary.get("findings", [])
                            for reason in finding["reasons"]
                            if reason
                            in {
                                "semantic_provider_failure",
                                "semantic_gateway_exception",
                                "semantic_verdict_missing_or_invalid",
                                "semantic_payload_limit",
                            }
                        )
                        for name, metadata in runtime.provider_metadata:
                            usage("m6_" + name, metadata)
                        for name, latency in runtime.stage_latency_ms.items():
                            trace.stages["m6_" + name] = PipelineStage(
                                status="COMPLETED", latency_ms=latency
                            )
                        admitted = []
                        signatures = {
                            e.identity.verified_claim_id: e.identity.verified_claim_id
                            for e in entries
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
                                signature = entry.identity.verified_claim_id
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
                        trace.m6_lite["ledger_admitted_claim_ids"] = [
                            o.verified_claim_id for o in trace.outcomes if o.verified_claim_id
                        ]
                        # Native policy has ABSTAIN/INVESTIGATE, no fabricated REJECT threshold.
                        response.rejected_claims = trace.native_decisions.get("ABSTAIN", 0)
                        response.deferred_claims = trace.native_decisions.get("INVESTIGATE", 0)
                        ledger.cache.clear()
                        stage("ledger_reload", lambda: ledger.find_claims(query))
                    if output.document_candidates:
                        trace.document_candidates = [
                            c.model_dump(mode="json") for c in output.document_candidates
                        ]
                        manifest = m5.composition
                        tools = EvidenceRetrievalTools.from_composition(
                            manifest,
                            m5.document_repository,
                            document_id=manifest.logical_document_id,
                            composition_id=manifest.composition_id,
                        )
                        from ..verification.document_verification import verify_document_claim

                        document_histories = stage(
                            "m6_document",
                            lambda: [
                                verify_document_claim(
                                    candidate,
                                    EvidenceContextBuilder(tools=tools),
                                    manifest,
                                    bound.company_id,
                                    bound.snapshot_id
                                    if manifest.financial_snapshot.source_kind == "json"
                                    else None,
                                    gateway=self.gateway
                                    if bound.allow_gateway
                                    and bound.execution_mode != "deterministic"
                                    else None,
                                    model=bound.model,
                                    goal_context=dict(
                                        question=bound.question,
                                        local_requirements=[
                                            r
                                            for r in trace.integration_context["requirements"]
                                            if any(
                                                candidate.candidate_id
                                                in state.get("document_candidate_ids", [])
                                                and r["requirement_id"]
                                                == state.get("document_goal")
                                                for state in trace.integration_context[
                                                    "tasks"
                                                ].values()
                                            )
                                        ],
                                    ),
                                )
                                for candidate in output.document_candidates
                            ],
                        )
                        for history in document_histories:
                            usage("m6_document", history.metadata)
                        old_count = len(trace.outcomes)
                        stage(
                            "admission_document",
                            lambda: self._admit_documents(document_histories, response),
                        )
                        by_candidate = {
                            h.final.original_claim.candidate_id: h for h in document_histories
                        }
                        for outcome in trace.outcomes[old_count:]:
                            history = by_candidate[outcome.candidate_id]
                            if (
                                outcome.verified_claim_id
                                and history.semantic
                                and history.semantic.verdict == "SUPPORTED"
                            ):
                                document_bindings[outcome.verified_claim_id] = (
                                    history.semantic.supported_requirement_ids
                                )
                        trace.native_decisions = dict(
                            Counter(o.final_decision for o in trace.outcomes)
                        )
                        response.rejected_claims = trace.native_decisions.get("ABSTAIN", 0)
                        response.deferred_claims = trace.native_decisions.get("INVESTIGATE", 0)
                        ledger.cache.clear()
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

            return release_lite()
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
