"""Three targeted integration controls; no financial accuracy claims."""

import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
from vietnamese_financial_multi_agent.agents.qa_planning import fallback_fusion_plan
from vietnamese_financial_multi_agent.core.llm_contracts import (
    RequestConstraints,
    parse_llm_request,
)
from vietnamese_financial_multi_agent.core.qwen_adapter import QwenAdapter, QwenSettings
from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_evidence_obligations import gateway_with_goals, selection_case
from .test_llm_gateway import request


def test_thinking_final_channels_and_incomplete_reasoning_never_become_answers():
    req = request(provider="qwen", model="test-model", spec={"format": "json"})
    raw = dict(
        model="test-model",
        usage=dict(prompt_tokens=10, completion_tokens=30, total_tokens=40),
        choices=[dict(finish_reason="stop", message={})],
    )
    seen = []

    def handler(wire):
        seen.append(json.loads(wire.content))
        return httpx.Response(200, json=raw)

    adapter = QwenAdapter(
        QwenSettings("https://test.invalid/v1", "secret", "test-model"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        for message in (
            dict(reasoning_content='Private reasoning {"wrong":true}', content='{"final":true}'),
            dict(content='<think>{"wrong":true}</think>\n```json\n{"final":true}\n```'),
            dict(content='prefilled reasoning</think>\n{"final":true}'),
        ):
            raw["choices"][0]["message"] = message
            result = adapter(req)
            assert result.status == "success" and result.output.payload == {"final": True}
            assert result.usage.total_tokens == 40
            assert "chat_template_kwargs" not in seen[-1]
        raw["choices"][0] = dict(
            finish_reason="length", message=dict(content='<think>{"wrong":true}')
        )
        result = adapter(req)
        assert result.status == "partial" and result.finish_reason == "length"
        assert result.output.payload is None and "wrong" not in result.output.raw_text
        raw["choices"][0] = dict(
            finish_reason="stop", message=dict(content=None, reasoning_content='{"wrong":true}')
        )
        assert adapter(req).error.category == "structured_output_invalid"
    finally:
        adapter.close()


def test_thinking_budget_clamps_deadline_and_fallback_keeps_dependency(monkeypatch):
    req = parse_llm_request(request(provider="qwen", model="test-model"))
    calls = []

    # Use the existing synthetic response to keep real RequestGateway accounting.
    from .test_m6_lite import semantic_gateway

    underlying = semantic_gateway()
    req.messages[-1].content = "[]"
    baseline = underlying.generate(req)
    baseline.usage.total_tokens = 40

    def generate(bound):
        calls.append(bound)
        return baseline

    monkeypatch.delenv("QWEN_THINKING_BUDGET", raising=False)
    req.generation.max_output_tokens = 1800
    req.constraints = RequestConstraints(timeout_seconds=60)
    gateway = RequestGateway(SimpleNamespace(generate=generate), max_calls=1, timeout_seconds=90)
    gateway.generate(req)
    adapter = QwenAdapter(QwenSettings("https://test.invalid/v1", "secret", "test-model"))
    try:
        payload, timeout = adapter._payload(calls[0])
        assert 60 < timeout <= 90
        assert payload["max_tokens"] == req.generation.max_output_tokens == 1800
        assert req.constraints.timeout_seconds == 60
    finally:
        adapter.close()
    assert gateway.generate(req).status == "error" and len(calls) == 1

    question = (
        "Cuối năm 2030, phải thu ngắn hạn của khách hàng hay hàng tồn kho có số dư lớn hơn? "
        "Trong thuyết minh của khoản mục lớn hơn đó, đối tượng nêu tên riêng lớn nhất là ai?"
    )
    plan = fallback_fusion_plan(question)
    financial = [r for r in plan.requirements if r.lane == "financial"]
    document = [r for r in plan.requirements if r.lane == "document"]
    assert len(financial) == len(document) == 1
    assert financial[0].original_span in question
    assert financial[0].execution_question == financial[0].original_span
    assert document[0].dependencies == [financial[0].requirement_id]
    assert document[0].document_requirement is not None


def test_semantic_batch_split_preserves_full_closure_digest_and_ledger(monkeypatch, tmp_path):
    import vietnamese_financial_multi_agent.verification.lite_runtime as module
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    catalog, batch, context = selection_case()
    second = batch.claims[0].model_copy(deep=True)
    second.candidate_id = second.provenance.m5_candidate_id = "second"
    batch.claims.append(second)
    context["candidate_requirements"]["second"] = ["G1"]
    original = module.semantic_payload

    def payload(*args):
        # A full, individually valid row fits the unchanged 48K cap; two do not.
        return dict(original(*args), retained_source_context="x" * 25000)

    monkeypatch.setattr(module, "semantic_payload", payload)
    gateway = gateway_with_goals(["G1"])
    runtime = LiteVerificationRuntime(catalog, gateway, integration_v2=True)
    histories = runtime.verify(batch, integration_context=deepcopy(context))
    assert gateway.generate.call_count == 2
    assert len(runtime.provider_metadata) == 2
    sent = [
        json.loads(call.args[0].messages[-1].content) for call in gateway.generate.call_args_list
    ]
    assert all(
        len(rows) == 1 and rows[0]["retained_source_context"] == "x" * 25000 for rows in sent
    )
    for history in histories:
        proof = history.proof
        assert history.outcome.final.decision == "ACCEPT"
        assert proof.goal_context["task_results"] == context["task_results"]
        assert proof.semantic_input_sha256 == module.payload_digest(
            payload(proof.batch, proof.batch.claims[0], proof.goal_context)
        )
        assert VerifiedClaimRepository(tmp_path).admit(history).status == "stored"
    # A single oversized claim stays unverified without network or truncation.
    monkeypatch.setattr(
        module, "semantic_payload", lambda *args: dict(original(*args), retained="x" * 49000)
    )
    blocked_gateway = gateway_with_goals(["G1"])
    blocked = LiteVerificationRuntime(catalog, blocked_gateway, integration_v2=True)
    blocked_histories = blocked.verify(batch, integration_context=context)
    assert blocked_gateway.generate.call_count == 0
    assert all(h.proof.semantic_error == "semantic_payload_limit" for h in blocked_histories)
    assert not blocked.summary["supported_requirements"]
