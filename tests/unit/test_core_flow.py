"""Boundary controls; synthetic fixtures are not financial-quality evidence."""

import json
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    inventory,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
from vietnamese_financial_multi_agent.api.claim_selection import select_claims
from vietnamese_financial_multi_agent.api.conversations import ConversationService
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_qa import gateway_for
from .test_financial_qa_pipeline import setup
from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_m5_lite import inputs
from .test_m6_lite import semantic_gateway


def test_semantic_plan_calculator_and_analysis_preserved():
    catalog, context = inputs()
    context.mode = "gemini"
    sources = inventory(catalog, context)
    handles = [k for k, s in sources.items() if "profitability" in s["roles"]]
    seen = []

    def transport(request):
        seen.append(request)
        if "supervisor" in request.request_id:
            body = dict(
                tasks=[
                    dict(
                        specialist="profitability",
                        objective="Đánh giá hiệu quả kinh doanh",
                        sources=handles,
                    )
                ]
            )
        else:
            prompt = json.loads(request.messages[0].content)
            evidence = prompt["evidence"]
            facts = [e["id"] for e in evidence if not e["operand_periods"]]
            body = dict(
                claims=[c["evidence_id"] for c in prompt["numeric_choices"]],
                missing_information=[],
                analyses=[
                    dict(
                        statement="Các chỉ tiêu phản ánh kết quả kinh doanh trong kỳ, chưa chứng minh nguyên nhân biến động.",
                        evidence_ids=[e["id"] for e in evidence],
                        operations=[
                            dict(operation_id="compare", operator="greater", inputs=facts[:2])
                        ],
                        claim_type="reasoned_conclusion",
                    )
                ],
            )
        return gateway_for(body, []).generate(request)

    result = FinancialLiteOrchestrator(catalog, Mock(generate=transport)).run(
        question="Đánh giá hiệu quả kinh doanh và sức sinh lời?", context=context
    )
    assert len(seen) == 2
    assert result.routing_decision.selected_roles == ["profitability"]
    assert any(
        t.operation == "calculate_financial_metric" for t in result.supervisor_result.tool_trace
    )
    from vietnamese_financial_multi_agent.verification.adapter import to_verification_input

    batch = to_verification_input(result)
    assert not batch.issues
    assert any(
        c.reasoning and c.reasoning.claim_type == "reasoned_conclusion" for c in batch.claims
    )
    assert all(c.status == "candidate" for c in batch.claims)
    assert not any(c.reasoning and c.reasoning.claim_type == "derived_fact" for c in batch.claims)
    wrapped = semantic_gateway()

    def semantic_array(request):
        response = wrapped.generate(request)
        response.output.payload = response.output.payload["verdicts"]
        response.output.raw_text = json.dumps(response.output.payload)
        return response

    runtime = LiteVerificationRuntime(catalog, Mock(generate=semantic_array))
    histories = runtime.verify(batch)
    assert runtime.summary["semantic_calls"] == 1
    assert any(
        h.outcome.final.decision == "ACCEPT"
        and h.outcome.final.original_claim.reasoning
        and h.outcome.final.original_claim.reasoning.claim_type == "reasoned_conclusion"
        for h in histories
    )


def test_display_label_is_not_canonical_identity():
    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.supporting_evidence[0].label = "Tên hiển thị khác"
    assert (
        LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0].outcome.final.decision
        == "ACCEPT"
    )
    claim.supporting_evidence[0].canonical_item_id = "b01.total_liabilities"
    assert (
        LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0].outcome.final.decision
        == "ABSTAIN"
    )


def test_selected_document_period_and_single_verified_followup(tmp_path):
    service, request, _, _, _ = setup(tmp_path)
    question = "Nhận xét tình hình tài chính?"
    bound, blocked, _ = service._lite_context(
        request.model_copy(update={"question": question, "m7_lite": True})
    )
    assert blocked is None and bound.period == "2030"
    conversation = ConversationService(service)
    state = conversation.create()
    conversation.send(state.conversation_id, request)
    state = conversation.history(state.conversation_id)
    followup = "Vậy tỷ lệ đó có chứng minh doanh nghiệp đang mất khả năng thanh toán không?"
    bound, _, inherited, _, _, clarification = conversation._resolve(
        state, FinancialQARequest(question=followup, m5_lite=True, m7_lite=True)
    )
    assert clarification is None and followup in bound.question
    assert "verified_claim_reference" in inherited
    assert bound.conversation_context[0]["verified_claim_ids"] == state.verified_claim_ids
    assert bound.document_id == state.selected_context.document_id


@pytest.mark.parametrize(
    "category,code", [("provider_unavailable", "http_503"), ("rate_limit", "http_429")]
)
def test_provider_retry_is_bounded_and_each_attempt_is_traced(monkeypatch, category, code):
    from vietnamese_financial_multi_agent.core.llm_gateway import _failure
    from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway

    from .test_llm_gateway import request

    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.core.request_gateway.sleep", lambda _: None
    )
    req = request()

    def unavailable(bound):
        response = _failure(bound, category)
        response.error.provider_error_code = code
        return response

    gateway = Mock(generate=Mock(side_effect=unavailable))
    scoped = RequestGateway(gateway, max_calls=4, timeout_seconds=30)
    assert scoped.generate(req).status == "error"
    assert gateway.generate.call_count == len(scoped.events) == 2
    assert [e["retry_attempt"] for e in scoped.events] == [0, 1]
    scoped = RequestGateway(gateway, max_calls=1, timeout_seconds=30)
    scoped.generate(req)
    assert len(scoped.events) == 1


def test_comparative_metric_survives_admission_reload_and_current_handoff(tmp_path):
    from vietnamese_financial_multi_agent.verification.adapter import to_verification_input

    catalog = SnapshotCatalog(**fixture("revenue_yoy"))
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        reporting_year=2030,
        mode="deterministic",
    )
    output = FinancialLiteOrchestrator(catalog).run(
        question="Tăng trưởng doanh thu năm 2030?", context=context
    )
    histories = LiteVerificationRuntime(catalog).verify(to_verification_input(output))
    repository = VerifiedClaimRepository(tmp_path)
    repository.admit_many(histories)
    entries = VerifiedClaimRepository(tmp_path).list_all()
    metric = next(e for e in entries if e.accepted_claim.calculation)
    assert set(
        metric.accepted_claim.calculation.trace.operands[i].context.period for i in range(2)
    ) == {"2029", "2030"}
    request = FinancialQARequest(
        question="Tăng trưởng doanh thu năm 2030?",
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
    )
    assert select_claims(request, [metric])[0] == [metric]
    assert select_claims(
        request.model_copy(update={"question": "Nhận xét tình hình tài chính năm 2030?"}),
        [metric],
        [metric.identity.verified_claim_id],
    )[0] == [metric]
