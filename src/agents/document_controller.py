"""Bounded document replanning; literal quotations retain independent M6 replay."""

from ..verification.adaptive_judge import JudgeFeedback
from ..verification.evidence_context import EvidenceContextBuilder
from ..verification.runtime import VerificationRuntime
from .document_qa import document_candidates, document_operations
from .qa_planning import plan_document, structured_call
from .supervisor import RiskAwareSupervisor


def run_document_adaptive(gateway, request, requirements, manifest, tools):
    cache, seen, rounds = {}, set(), []
    feedback, histories, bundles, candidates = None, [], [], []
    for revision in range(3):
        plan = plan_document(
            gateway,
            request,
            requirements,
            feedback=feedback,
            reusable=[
                dict(candidate_id=h.final.original_claim.candidate_id, decision=h.final.decision)
                for h in histories
            ],
        )
        originals = {(r.target, r.label, r.kind) for r in requirements}
        if not originals <= {(r.target, r.label, r.kind) for r in plan.requirements}:
            raise ValueError("document_planner_omits_original_requirement")
        signature = plan.model_dump_json(exclude={"selection_reason"})
        event = dict(revision=revision, planner=plan.model_dump(mode="json"), cache_hits=0)
        rounds.append(event)
        if signature in seen:
            event["stop_reason"] = "no_substantive_plan_progress"
            break
        seen.add(signature)
        bundles = []
        for operation in document_operations(plan.requirements, manifest, request.snapshot_id):
            # Search wording may change; the claim obligation remains the exact
            # user-bound requirement that M6 and M7 replay independently.
            original = next(
                (
                    r
                    for r in requirements
                    if (r.target, r.label, r.kind)
                    == (
                        operation.requirement.target,
                        operation.requirement.label,
                        operation.requirement.kind,
                    )
                ),
                None,
            )
            if original:
                operation = operation.model_copy(update={"requirement": original})
            key = operation.request.model_dump_json()
            if key in cache:
                bundle = cache[key].model_copy(deep=True, update={"operation": operation})
                event["cache_hits"] += 1
            else:
                bundle = RiskAwareSupervisor.execute_document(operation, tools)
                cache[key] = bundle.model_copy(deep=True)
            bundles.append(bundle)
        candidates = [
            c for b in bundles for c in document_candidates(b, request.company_id, manifest)
        ]
        histories = VerificationRuntime.verify_document(
            candidates,
            EvidenceContextBuilder(tools=tools),
            manifest,
            request.company_id,
            request.snapshot_id,
        )
        if not plan.reasoning_required:
            event["stop_reason"] = "tool_only_exact_quotation_M6_gate"
            break
        try:
            feedback = structured_call(
                gateway,
                request.model,
                JudgeFeedback,
                dict(
                    instruction=(
                        "Bạn là Judge Document QA. Tổng hợp M6 evidence/source fidelity checks, "
                        "đánh giá độ bao phủ và thiếu điều kiện/ngoại lệ. Không coi OCR khớp là "
                        "chứng minh PDF đúng. Không override deterministic blockers. Nếu cần "
                        "bổ sung query thì REVISION_NEEDED với issues cụ thể; nếu nguồn không tin cậy "
                        "thì INSUFFICIENT_EVIDENCE. Không tự sửa quotation. Xuất đúng schema."
                    ),
                    question=request.question,
                    findings=[
                        dict(
                            candidate_id=h.final.original_claim.candidate_id,
                            content=h.final.original_claim.content,
                            quotations=h.final.original_claim.quotations,
                            decision=h.final.decision,
                            checks=h.final.checks,
                            reasons=h.final.reasons,
                            pages=sorted(
                                {
                                    c.pdf_page
                                    for c in h.final.original_claim.citations
                                    if c.pdf_page is not None
                                }
                            ),
                        )
                        for h in histories
                    ],
                ),
                "document-judge",
            )
        except Exception:
            feedback = JudgeFeedback(assessment="JUDGE_ERROR", explanation="document_judge_failed")
        event["judge"] = feedback.model_dump(mode="json")
        if feedback.assessment != "PASS":
            # A semantic veto cannot mutate native proof or admit a quotation.
            histories = []
        if not feedback.revision_required or revision == 2:
            event["stop_reason"] = feedback.assessment
            break
        reserve = getattr(gateway, "reserve_revision", None)
        if reserve and not reserve():
            event["stop_reason"] = "shared_revision_budget_exhausted"
            break
        feedback = feedback.model_dump(mode="json")
    return bundles, candidates, histories, rounds
