"""Semantic synthesis of existing M6 assessments; deterministic Judge remains release gate."""

import json
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.llm_contracts import (
    GenerationParameters,
    JSONOutput,
    LLMRequest,
    Message,
    OutputSpec,
    RequestConstraints,
)


class JudgeIssue(FinancialModel):
    claim_id: str | None = None
    issue_type: Literal[
        "MISSING_EVIDENCE",
        "UNSUPPORTED_LOGIC",
        "CONTRADICTION",
        "INCOMPLETE_COVERAGE",
        "SOURCE_QUALITY",
    ]
    explanation: str = Field(min_length=1, max_length=1500)
    required_evidence: list[str] = Field(default_factory=list, max_length=16)
    suggested_action: Literal[
        "REQUEST_ADDITIONAL_EVIDENCE", "REVISE_ANALYSIS", "DROP_CLAIM", "STOP"
    ]


class JudgeFeedback(FinancialModel):
    assessment: Literal["PASS", "REVISION_NEEDED", "REJECT", "INSUFFICIENT_EVIDENCE", "JUDGE_ERROR"]
    issues: list[JudgeIssue] = Field(default_factory=list, max_length=16)
    revision_required: bool = False
    explanation: str = ""


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
        payload = dict(
            instruction=(
                "Bạn là Judge tổng hợp cho yêu cầu tài chính. Evidence Critic và Logic Critic đã "
                "đánh giá từng claim bên dưới: sử dụng kết quả đó, không thực hiện lại toàn bộ critics. "
                "Phản biện mức bao phủ mục tiêu, mâu thuẫn giữa claims và thiếu tiền đề. "
                "Không nâng ACCEPT hoặc phủ quyết deterministic blockers. PASS chỉ khi đáp ứng yêu cầu "
                "trong phạm vi nguồn; kết luận chất lượng lợi nhuận cần CFO và lợi nhuận, "
                "không suy tốt/xấu từ lợi nhuận tăng. Thiếu dữ liệu có thể truy xuất thì REVISION_NEEDED, "
                "chỉ rõ required_evidence canonical IDs và suggested_action. Không thể bổ sung thì "
                "INSUFFICIENT_EVIDENCE/REJECT. Không yêu cầu ratio chưa approved. "
                "claim_id phải thuộc candidates hoặc null cho thiếu coverage toàn câu hỏi. "
                "Không xem OCR quotation tự khớp là chứng minh PDF đúng. Xuất duy nhất JSON theo schema."
            ),
            schema=JudgeFeedback.model_json_schema(),
            question=question,
            planner=proposal.model_dump(mode="json") if proposal else None,
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
            feedback = JudgeFeedback.model_validate(response.output.payload)
            if any(
                i.claim_id and i.claim_id not in {r.candidate_id for r in records}
                for i in feedback.issues
            ):
                raise ValueError("judge_foreign_claim")
            if feedback.revision_required != (feedback.assessment == "REVISION_NEEDED"):
                raise ValueError("judge_revision_mismatch")
            if feedback.assessment == "REVISION_NEEDED" and not feedback.issues:
                raise ValueError("judge_feedback_required")
            return feedback
        except Exception:
            return JudgeFeedback(assessment="JUDGE_ERROR", explanation="semantic_judge_failed")
        finally:
            self.latency_ms = (perf_counter() - started) * 1000
