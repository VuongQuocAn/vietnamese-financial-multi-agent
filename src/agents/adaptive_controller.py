"""Bounded Planner → execution → M6 → semantic Judge → affected replanning."""

import json
from time import perf_counter

from ..verification.adapter import to_verification_input
from ..verification.adaptive_judge import (
    AdaptiveJudge,
    bind_coverage,
    evidence_inventory,
    ground_feedback,
)
from ..verification.runtime import VerificationRuntime


class AdaptiveFinancialController:
    def __init__(self, orchestrator, catalog, gateway, model):
        reset = getattr(orchestrator, "reset_request", None)
        if reset:
            reset()
        self.orchestrator, self.catalog = orchestrator, catalog
        self.gateway, self.model = gateway, model
        self.rounds = []
        self.provider_metadata = []
        self.stage_latency_ms = {}
        self.batch = None

    def run(self, question, context):
        seen, accepted, seen_issues = set(), {}, set()
        histories, output, last_usable = [], None, None
        round_started = perf_counter()
        for revision in range(3):
            if self.rounds:
                self.rounds[-1]["latency_ms"] = (perf_counter() - round_started) * 1000
            round_started = perf_counter()
            output = self.orchestrator.run(question=question, context=context)
            proposal = output.planner_result.effective_proposal if output.planner_result else None
            signature = (
                json.dumps(
                    dict(
                        operations=sorted(
                            (
                                o.operation,
                                o.canonical_item_id or "",
                                o.formula_id or "",
                                o.period or "",
                            )
                            for o in proposal.operations
                        ),
                        assignments=sorted(
                            (
                                a.role,
                                a.task,
                                sorted(a.indicators),
                                sorted(a.formulas),
                                sorted(a.depends_on),
                            )
                            for a in proposal.assignments
                        ),
                        reasoning=proposal.reasoning_required,
                        reasoning_steps=[
                            s.model_dump(mode="json") for s in proposal.reasoning_steps
                        ],
                    ),
                    ensure_ascii=False,
                )
                if proposal
                else "none"
            )
            event = dict(
                revision=revision,
                planner=output.planner_result.model_dump(mode="json")
                if output.planner_result
                else None,
                status=output.status,
                judge=None,
                stop_reason=None,
            )
            self.rounds.append(event)
            event["tools"] = (
                [
                    dict(
                        event=t.execution_kind,
                        tool=t.operation,
                        request=t.bound_request,
                        latency_ms=t.latency_ms,
                    )
                    for t in output.supervisor_result.tool_trace
                ]
                if output.supervisor_result
                else []
            )
            event["specialists"] = [
                dict(
                    role=e.role,
                    event="PROVIDER_DEGRADED"
                    if e.llm.error
                    else "LLM_AGENT_EXECUTED"
                    if e.llm.calls
                    else "CACHE_HIT"
                    if e.llm.status == "cache_hit"
                    else "DETERMINISTIC_COMPONENT_EXECUTED",
                    calls=e.llm.calls,
                    latency_ms=e.latency_ms,
                    candidates=[
                        dict(candidate_id=c.candidate_id, content=c.content)
                        for c in e.result.candidates
                    ]
                    if e.result
                    else [],
                )
                for e in output.specialist_executions
            ]
            if output.status not in {"completed", "partial"} or not proposal:
                event["stop_reason"] = "execution_unavailable"
                output = last_usable or output
                break
            if signature in seen or proposal.stop_reason:
                event["stop_reason"] = proposal.stop_reason or "no_substantive_plan_progress"
                output = last_usable or output
                break
            seen.add(signature)
            last_usable = output
            start = perf_counter()
            batch = to_verification_input(output)
            self.stage_latency_ms["handoff"] = (
                self.stage_latency_ms.get("handoff", 0) + (perf_counter() - start) * 1000
            )
            self.batch = batch
            start = perf_counter()
            runtime = VerificationRuntime(self.catalog, self.gateway, model=self.model)
            self.stage_latency_ms["setup"] = (
                self.stage_latency_ms.get("setup", 0) + (perf_counter() - start) * 1000
            )
            histories = runtime.verify(batch, allow_revision=False)
            self.provider_metadata.extend(runtime.provider_metadata)
            for name, latency in runtime.stage_latency_ms.items():
                self.stage_latency_ms[name] = self.stage_latency_ms.get(name, 0) + latency
            judge = AdaptiveJudge(self.gateway, self.model)
            review_histories = dict(accepted)
            review_histories.update({h.outcome.parent_candidate_id: h for h in histories})
            review_histories = list(review_histories.values())
            inventory = evidence_inventory(output, review_histories)
            feedback = bind_coverage(
                judge.assess(question, output, review_histories), question, output, review_histories
            )
            feedback = ground_feedback(feedback, inventory)
            event["evidence_inventory"] = inventory
            event["judge"] = feedback.model_dump(mode="json")
            event["judge_latency_ms"] = judge.latency_ms
            event["m6_decisions"] = {
                h.outcome.parent_candidate_id: h.outcome.final.decision for h in histories
            }
            affected = {i.claim_id for i in feedback.issues if i.claim_id}
            for history in histories:
                record = history.outcome.final
                if record.decision == "ACCEPT" and record.candidate_id not in affected:
                    if feedback.assessment in {
                        "PASS",
                        "REVISION_NEEDED",
                        "INSUFFICIENT_EVIDENCE",
                        "JUDGE_ERROR",
                    } or record.original_claim.kind in {
                        "fact",
                        "approved_metric",
                    }:
                        accepted[record.candidate_id] = history
                else:
                    accepted.pop(record.candidate_id, None)
            if not feedback.revision_required:
                event["stop_reason"] = feedback.assessment
                break
            issue_keys = {
                (tuple(sorted(i.required_evidence)), i.evidence_state)
                for i in feedback.issues
                if i.required_evidence
            }
            if (
                revision
                and issue_keys
                and issue_keys <= seen_issues
                and all(state == "RETRIEVED_NOT_USED" for _, state in issue_keys)
            ):
                event["stop_reason"] = "retrieved_evidence_not_used_after_revision"
                break
            seen_issues.update(issue_keys)
            if revision == 2 or getattr(self.gateway, "exhausted", False):
                event["stop_reason"] = "revision_or_request_budget_exhausted"
                break
            reserve = getattr(self.gateway, "reserve_revision", None)
            if reserve and not reserve():
                event["stop_reason"] = "shared_revision_budget_exhausted"
                break
            context = context.model_copy(
                update=dict(
                    feedback=feedback.model_dump(mode="json"),
                    previous_proposal=proposal,
                    reusable_results=[
                        dict(evidence_inventory=inventory, verified_candidates=list(accepted))
                    ]
                    + [
                        dict(
                            role=e.role,
                            result=dict(
                                status=e.result.status,
                                analyses=[
                                    dict(
                                        candidate_id=c.candidate_id,
                                        kind=c.kind,
                                        content=c.content,
                                        evidence_ids=c.supporting_evidence_ids,
                                        reasoning=c.reasoning.model_dump(mode="json")
                                        if c.reasoning
                                        else None,
                                    )
                                    for c in e.result.candidates
                                    if c.kind == "supported_interpretation"
                                ],
                                evidence_indicators=[
                                    s.canonical_item_id for s in e.result.supporting_evidence
                                ],
                                missing_evidence=e.result.missing_evidence,
                                generation_issues=[
                                    t.reasons for t in e.result.trace if t.outcome == "excluded"
                                ],
                            ),
                        )
                        for e in output.specialist_executions
                        if e.result
                    ],
                )
            )
        # Native proof objects stay unmodified; semantic veto never creates ACCEPT.
        if self.rounds:
            self.rounds[-1]["latency_ms"] = (perf_counter() - round_started) * 1000
        final = {h.outcome.parent_candidate_id: h for h in histories}
        for key, history in list(final.items()):
            if history.outcome.final.decision == "ACCEPT" and key not in accepted:
                del final[key]
        final.update(accepted)
        return output, list(final.values())
