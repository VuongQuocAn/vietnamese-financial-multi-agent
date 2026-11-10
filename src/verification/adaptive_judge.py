"""Semantic synthesis of existing M6 assessments; deterministic Judge remains release gate."""

import hashlib
import json
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_serializer

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)
from ..core.llm_gateway import unwrap_singleton_object
from ..core.schema_cache import model_schema


class JudgeIssue(FinancialModel):
    claim_id: str | None = None
    issue_type: Literal[
        "MISSING_EVIDENCE",
        "UNSUPPORTED_LOGIC",
        "CONTRADICTION",
        "INCOMPLETE_COVERAGE",
        "SOURCE_QUALITY",
        "EVIDENCE_NOT_USED",
    ]
    explanation: str = Field(min_length=1, max_length=1500)
    required_evidence: list[str] = Field(default_factory=list, max_length=16)
    suggested_action: Literal[
        "REQUEST_ADDITIONAL_EVIDENCE", "REVISE_ANALYSIS", "DROP_CLAIM", "STOP"
    ]
    evidence_state: (
        Literal["NOT_RETRIEVED", "RETRIEVED_NOT_USED", "VALIDATION_BLOCKED", "MIXED"] | None
    ) = None


class JudgeRecommendation(FinancialModel):
    assessment: Literal["PASS", "REVISION_NEEDED", "REJECT", "INSUFFICIENT_EVIDENCE", "JUDGE_ERROR"]
    issues: list[JudgeIssue] = Field(default_factory=list, max_length=16)
    revision_required: bool = False
    explanation: str = ""


class JudgeFeedback(JudgeRecommendation):
    # Coverage is backend-only and cannot be supplied as an LLM attestation.
    coverage: "AnswerCoverage | None" = None

    @model_serializer(mode="wrap")
    def serialize_feedback(self, handler):
        wire = handler(self)
        if wire.get("coverage") is None:
            wire.pop("coverage", None)
        return wire


class GoalCoverage(FinancialModel):
    requirement_id: str
    target_id: str | None
    interpretation: bool
    verified_candidate_ids: list[str] = Field(default_factory=list)
    blocked_candidate_ids: list[str] = Field(default_factory=list)
    missing_reason: str | None = None
    recoverable: bool = False


class AnswerCoverage(FinancialModel):
    goals: list[GoalCoverage] = Field(default_factory=list)
    complete: bool


def answer_coverage(question, output, histories):
    from types import SimpleNamespace

    from ..outputs.firewall_qa_binding import request_inventory
    from ..outputs.qa_composer import matches_financial_target, planned_requirements
    from ..outputs.qa_contracts import VietnameseQARequest

    proposal = output.planner_result.effective_proposal
    context = getattr(output, "context", None)
    records = [h.outcome.final for h in histories]
    inventory = evidence_inventory(output, histories)
    # Read-only coverage projections of *native ACCEPTs*, not admitted Ledger
    # entries. Never persisted or passed to output composition/admission. Reuse
    # M7's exact target/scope/ambiguity/explanation rules rather than a second
    # interpretation of completeness. Native proof/admission still runs later.
    entries = []
    for record in records:
        if record.decision != "ACCEPT":
            continue
        claim = record.original_claim
        if context and any(
            getattr(claim, k) != getattr(context, k)
            for k in ("company_id", "document_id", "snapshot_id")
        ):
            continue
        entries.append(
            SimpleNamespace(
                identity=SimpleNamespace(
                    verified_claim_id=record.candidate_id,
                    kind=claim.kind,
                    company_id=claim.company_id,
                    document_id=claim.document_id,
                    snapshot_id=claim.snapshot_id,
                    period=claim.period,
                ),
                accepted_claim=claim,
                decision=record,
                verification_status="verified",
                content=claim.content,
                citations=record.supporting_citations,
                caveats=record.caveats,
            )
        )
    request = VietnameseQARequest(
        question=question,
        **{
            k: getattr(context, k, None)
            for k in ("company_id", "document_id", "snapshot_id", "period", "reporting_scope")
        },
        answer_requirements=planned_requirements(question, proposal),
    )
    plan, status = request_inventory(request, entries)
    goals = []
    for target in plan.requirements:
        if not target.required:
            continue
        related = []
        for record in records:
            claim = record.original_claim
            if context and any(
                getattr(claim, k) != getattr(context, k)
                for k in ("company_id", "document_id", "snapshot_id")
            ):
                continue
            matches = matches_financial_target(claim, target, getattr(record, "logic", None))
            diagnostic_relation = (
                target.interpretation
                and claim.kind == "supported_interpretation"
                and set(target.required_indicators)
                <= {s.canonical_item_id for s in claim.supporting_evidence if s.kind == "fact"}
            )
            if not matches and not diagnostic_relation:
                continue
            related.append(record)
        verified = target.verified_claim_ids
        present = any(r["indicator"] == target.target_id for r in inventory)
        hard_blocked = any(
            r.validation and any(c.status == "fail" for c in r.validation.checks) for r in related
        )
        goals.append(
            GoalCoverage(
                requirement_id=target.requirement_id,
                target_id=target.target_id,
                interpretation=target.interpretation,
                verified_candidate_ids=verified,
                blocked_candidate_ids=[r.candidate_id for r in related if r.decision != "ACCEPT"],
                missing_reason=None if verified else target.reason or "unsupported_answer_goal",
                recoverable=not verified
                and present
                and not hard_blocked
                and target.reason != "ambiguous_verified_claims",
            )
        )
    return AnswerCoverage(goals=goals, complete=status == "answered")


def bind_coverage(feedback, question, output, histories):
    """A semantic PASS cannot hide missing native goals or promote an M6 decision."""
    coverage = answer_coverage(question, output, histories)
    feedback.coverage = coverage
    if feedback.assessment != "PASS" or coverage.complete:
        return feedback
    missing = [g for g in coverage.goals if not g.verified_candidate_ids]
    inventory = evidence_inventory(output, histories)
    records = [h.outcome.final for h in histories]

    def guidance(goal):
        available = [
            {k: r[k] for k in ("indicator", "period", "value", "unit", "native_status")}
            for r in inventory
            if r["native_status"] != "VALIDATION_BLOCKED"
        ]
        prior = [
            r.original_claim.content
            for r in records
            if r.candidate_id in goal.blocked_candidate_ids
        ]
        operations = [
            step.operation.model_dump(mode="json")
            for r in records
            if getattr(r.original_claim, "reasoning", None)
            and r.original_claim.reasoning.calculation
            for step in r.original_claim.reasoning.calculation.steps
        ]
        return (
            f"Goal {goal.requirement_id}: {goal.missing_reason}. "
            "Compare/calculate compatible premises, explain the relationship and its actual limits. "
            "Repeating facts/signs or generic insufficiency does not answer this analytical goal. "
            "Reuse retrieved sources; request only genuinely missing inputs. "
            f"Available premises: {json.dumps(available, ensure_ascii=False)}. "
            f"Prior candidate conclusions: {json.dumps(prior, ensure_ascii=False)}. "
            f"Existing computations: {json.dumps(operations, ensure_ascii=False)}. "
        )[:1500]

    feedback.issues = [
        JudgeIssue(
            issue_type="INCOMPLETE_COVERAGE",
            explanation=guidance(g),
            required_evidence=[g.target_id] if g.target_id else [],
            suggested_action="REVISE_ANALYSIS" if g.recoverable else "STOP",
        )
        for g in missing
    ]
    feedback.revision_required = any(g.recoverable for g in missing)
    feedback.assessment = (
        "REVISION_NEEDED" if feedback.revision_required else "INSUFFICIENT_EVIDENCE"
    )
    feedback.explanation = "native_answer_coverage_incomplete"
    return feedback


def evidence_inventory(output, histories):
    """Tool retrieval is independent of whether a Specialist emitted valid claims."""
    supervisor = getattr(output, "supervisor_result", None)
    if supervisor is None:
        return []
    records = [h.outcome.final for h in histories]
    routing = getattr(output, "routing_decision", None)
    rows = {}
    for match in supervisor.evidence_bundle.facts:
        fact = match.record
        key = hashlib.sha256(match.reference.model_dump_json().encode()).hexdigest()[:16]
        supported = [
            r
            for r in records
            if any(e.reference == match.reference for e in r.original_claim.supporting_evidence)
        ]
        native = (
            "M6_ACCEPT"
            if any(r.decision == "ACCEPT" and r.original_claim.kind == "fact" for r in supported)
            else "RETRIEVED_PENDING_M6"
        )
        if native != "M6_ACCEPT" and any(
            r.validation and any(c.status == "fail" for c in r.validation.checks) for r in supported
        ):
            native = "VALIDATION_BLOCKED"
        rows[key] = dict(
            evidence_key=key,
            indicator=fact.canonical_item_id,
            period=fact.context.period,
            value=str(fact.value.normalized_value),
            unit=fact.value.unit,
            scale=str(fact.context.scale),
            native_status=native,
            assigned_roles=[
                r.role
                for r in routing.routes
                if r.execution_eligible and fact.canonical_item_id in r.assigned_items
            ]
            if routing
            else [],
            used_by_claim_ids=[r.candidate_id for r in supported],
        )
    return list(rows.values())


def ground_feedback(feedback, inventory):
    """Never turn retrieved evidence into fictitious missing-source requests."""
    for issue in feedback.issues:
        if not issue.required_evidence:
            continue
        rows = [r for r in inventory if r["indicator"] in issue.required_evidence]
        present = {r["indicator"] for r in rows}
        if not present:
            issue.evidence_state = "NOT_RETRIEVED"
        elif present != set(issue.required_evidence):
            issue.evidence_state = "MIXED"
        elif any(r["native_status"] == "VALIDATION_BLOCKED" for r in rows):
            issue.evidence_state = "VALIDATION_BLOCKED"
        else:
            issue.evidence_state = "RETRIEVED_NOT_USED"
            if issue.issue_type == "MISSING_EVIDENCE":
                issue.issue_type = "EVIDENCE_NOT_USED"
                issue.explanation = (
                    "Tool inventory xác nhận evidence đã được truy xuất; cần sửa assignment/analysis, không phải tìm lại cùng nguồn. Judge: "
                    + issue.explanation[:1000]
                )
            if issue.suggested_action == "REQUEST_ADDITIONAL_EVIDENCE":
                issue.suggested_action = "REVISE_ANALYSIS"
    return feedback


class AdaptiveJudge:
    def __init__(self, gateway, model):
        self.gateway, self.model = gateway, model
        self.latency_ms = 0

    def assess(self, question, output, histories):
        started = perf_counter()
        proposal = output.planner_result.effective_proposal if output.planner_result else None
        if proposal and not proposal.reasoning_required:
            # A checked direct fact/calculation needs no second semantic review.
            return JudgeFeedback(assessment="PASS", explanation="tool_only_deterministic_M6_gate")
        records = [h.outcome.final for h in histories]
        inventory = evidence_inventory(output, histories)
        payload = dict(
            instruction=(
                "Bạn là Judge tổng hợp cho yêu cầu tài chính. Evidence Critic và Logic Critic đã "
                "đánh giá từng claim bên dưới: sử dụng kết quả đó, không thực hiện lại toàn bộ critics. "
                "Phản biện mức bao phủ mục tiêu, mâu thuẫn giữa claims và thiếu tiền đề. "
                "answer_coverage được backend tính TRƯỚC lượt gọi này từ native M6 ACCEPT và rules M7, "
                "không phải lời tự nhận của Specialist. Đọc từng goal: verified_candidate_ids, "
                "blocked_candidate_ids, missing_reason và recoverable. Nếu answer_coverage.complete=false "
                "thì không PASS chỉ vì có đủ numeric facts hoặc inventory. Goal chưa đáp ứng nhưng "
                "recoverable=true: REVISION_NEEDED với claim_id=null và INCOMPLETE_COVERAGE; sửa assignment "
                "khi evidence đã có, không yêu cầu retrieval trùng. Không thể sửa hợp lệ: "
                "INSUFFICIENT_EVIDENCE. complete=true chỉ đủ coverage, vẫn phải phản biện semantic correctness. "
                "Không nâng ACCEPT hoặc phủ quyết deterministic blockers. PASS chỉ khi đáp ứng yêu cầu "
                "trong phạm vi nguồn; kết luận chất lượng lợi nhuận cần CFO và lợi nhuận, "
                "không suy tốt/xấu từ lợi nhuận tăng. Thiếu dữ liệu có thể truy xuất thì REVISION_NEEDED, "
                "chỉ rõ required_evidence canonical IDs và suggested_action. Không thể bổ sung thì "
                "INSUFFICIENT_EVIDENCE/REJECT. Không yêu cầu ratio chưa approved. "
                "claim_id phải thuộc candidates hoặc null cho thiếu coverage toàn câu hỏi. "
                "Không xem OCR quotation tự khớp là chứng minh PDF đúng. Xuất duy nhất JSON theo schema."
                " Tool evidence_inventory là toàn bộ evidence đã truy xuất, kể cả khi Specialist lỗi schema "
                "hoặc không tạo claim. Không kết luận thiếu CFO/PAT chỉ vì candidate không có nó. "
                "Nếu evidence đã có, phân biệt chưa giao/chưa dùng/validation blocked; yêu cầu sửa assignment "
                "hoặc bỏ claim sai phạm vi thay vì truy xuất lại cùng nguồn. Không yêu cầu Specialist ngoài "
                "capability phải nhận evidence đó. Có thể PASS câu trả lời có giới hạn nếu đã mô tả đúng "
                "quan hệ PAT/CFO và thừa nhận chưa đủ kết luận toàn diện chất lượng lợi nhuận."
            ),
            schema=model_schema(JudgeRecommendation),
            question=question,
            planner=proposal.model_dump(mode="json") if proposal else None,
            evidence_inventory=inventory,
            answer_coverage=answer_coverage(question, output, histories).model_dump(mode="json"),
            candidates=[
                dict(
                    claim_id=r.candidate_id,
                    content=r.original_claim.content,
                    evidence=[
                        dict(
                            indicator=e.canonical_item_id,
                            value=e.value,
                            unit=e.unit,
                            scale=e.scale,
                            period=e.period,
                            reference=e.reference.model_dump(mode="json"),
                            pages=sorted(
                                {c.pdf_page for c in e.citations if c.pdf_page is not None}
                            ),
                        )
                        for e in r.original_claim.supporting_evidence
                    ],
                    deterministic_decision=r.decision,
                    blockers=r.unresolved_blockers,
                    evidence_assessment=dict(
                        status=r.evidence.status,
                        assertions=[
                            dict(
                                content=a.content,
                                status=a.status,
                                missing=a.missing,
                                reasons=a.reasons,
                            )
                            for a in r.evidence.assertions
                        ],
                    )
                    if r.evidence
                    else None,
                    logic_assessment=[
                        dict(
                            content=a.content,
                            status=a.status,
                            missing=a.missing_evidence,
                            reasons=a.reason_codes,
                        )
                        for a in r.logic.assertions
                    ]
                    if r.logic
                    else None,
                )
                for r in records
            ],
        )
        try:
            request = LLMRequest(
                contract_version="llm_gateway_v1",
                request_id="adaptive-judge-" + uuid4().hex,
                model=self.model,
                messages=[Message(role="user", content=json.dumps(payload, ensure_ascii=False))],
                generation=GenerationParameters(temperature=0, max_output_tokens=2500),
                output_spec=OutputSpec(format="json"),
                constraints=RequestConstraints(timeout_seconds=45),
            )
            response = self.gateway.generate(request)
            if response.status != "success" or not isinstance(response.output, JSONOutput):
                raise ValueError("judge_provider_failed")
            recommendation = JudgeRecommendation.model_validate(
                unwrap_singleton_object(response.output.payload)
            )
            feedback = JudgeFeedback(**recommendation.model_dump())
            if any(
                i.claim_id and i.claim_id not in {r.candidate_id for r in records}
                for i in feedback.issues
            ):
                raise ValueError("judge_foreign_claim")
            if feedback.revision_required != (feedback.assessment == "REVISION_NEEDED"):
                raise ValueError("judge_revision_mismatch")
            if feedback.assessment == "REVISION_NEEDED" and not feedback.issues:
                raise ValueError("judge_feedback_required")
            return ground_feedback(feedback, inventory)
        except Exception:
            return JudgeFeedback(assessment="JUDGE_ERROR", explanation="semantic_judge_failed")
        finally:
            self.latency_ms = (perf_counter() - started) * 1000
