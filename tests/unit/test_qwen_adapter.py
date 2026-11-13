"""Synthetic contract checks; không đánh giá độ chính xác tài chính."""

import base64
import json
from unittest.mock import Mock

import httpx
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_contracts import SchemaReference
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry
from vietnamese_financial_multi_agent.core.qwen_adapter import QwenAdapter, QwenSettings

from .test_llm_gateway import request


def test_json_mapping_local_validation_and_partial():
    reference = SchemaReference(
        schema_id="urn:test:ratio",
        name="ratio",
        version="v1",
        dialect="https://json-schema.org/draft/2020-12/schema",
    )
    registry = LocalSchemaRegistry(
        [
            (
                reference,
                {
                    "type": "object",
                    "properties": {"ratio": {"type": "number", "const": 2.5}},
                    "required": ["ratio"],
                    "additionalProperties": False,
                },
            )
        ]
    )
    req = request(
        provider="qwen",
        model="test-model",
        spec={
            "format": "json",
            "schema_ref": reference.export(),
            "strict": True,
        },
    )
    req.generation.max_output_tokens = 128
    req.generation.stop_sequences = ["END"]
    seen = []
    raw = {
        "model": "test-model",
        "usage": {"prompt_tokens": 8, "completion_tokens": 6},
        "choices": [{"finish_reason": "stop", "message": {"content": '{"ratio":2.5}'}}],
    }

    def handler(http_request):
        seen.append(json.loads(http_request.content))
        return httpx.Response(200, json=raw)

    adapter = QwenAdapter(
        QwenSettings("https://test.invalid/v1", "test-secret", "test-model"),
        schema_registry=registry,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    gateway = SharedLLMGateway({"qwen": adapter}, schema_registry=registry)
    try:
        response = gateway.generate(req)
        assert response.status == "success" and response.output.validation_status == "schema_valid"
        assert response.usage.input_tokens == 8 and response.usage.total_tokens is None
        assert response.cost.status == "unknown" and response.correlation == req.correlation
        assert seen[0]["max_tokens"] == 128 and seen[0]["stop"] == ["END"]
        assert seen[0]["chat_template_kwargs"] == {"enable_thinking": False}
        raw["choices"][0]["message"]["content"] = '{"ratio":3}'
        assert gateway.generate(req).output.validation_status == "schema_invalid"
        raw["choices"][0] = {"finish_reason": "length", "message": {"content": '{"ratio":'}}
        assert gateway.generate(req).status == "partial"
        req.output_spec.strict = None
        assert gateway.generate(req).error.category == "invalid_request"
    finally:
        adapter.close()


def test_errors_and_images_never_reach_text_endpoint():
    client = Mock()
    adapter = QwenAdapter(
        QwenSettings("https://test.invalid/v1", "secret", "test-model"), client=client
    )
    req = request(provider="qwen", model="test-model")
    req.messages[0].images = [
        {
            "mime_type": "image/png",
            "data": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode(),
        }
    ]
    assert SharedLLMGateway({"qwen": adapter}).generate(req).error.category == "invalid_request"
    client.post.assert_not_called()
    req.messages[0].images = []
    for code, expected in [
        (401, "authentication"),
        (429, "rate_limit"),
        (503, "provider_unavailable"),
    ]:
        client.post.return_value = httpx.Response(code, text="secret provider diagnostics")
        response = adapter(req)
        assert response.error.category == expected
        assert response.error.retryability == "not_retryable"
        assert "diagnostics" not in response.to_json()
    client.post.side_effect = httpx.ReadTimeout("secret diagnostics")
    assert adapter(req).error.category == "timeout"


def test_external_config_and_provider_selection(tmp_path, monkeypatch):
    from vietnamese_financial_multi_agent.api import text_gateway

    path = tmp_path / "api_info.json"
    path.write_text(
        json.dumps(
            {"BASE_URL": "https://test.invalid/v1", "API_KEY": "secret", "MODEL_NAME": "test-model"}
        ),
        encoding="utf-8",
    )
    for name in ("QWEN_BASE_URL", "QWEN_API_KEY", "QWEN_MODEL_NAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TEXT_LLM_PROVIDER", "qwen")
    configured = create_text_gateway(tmp_path)
    try:
        assert configured.model.provider == "qwen" and configured.model.model == "test-model"
        assert "secret" not in repr(configured.adapter.settings)
    finally:
        configured.close()
    monkeypatch.setenv("QWEN_MODEL_NAME", "override-model")
    assert QwenSettings.from_environment(tmp_path).model == "override-model"
    gemini = Mock()
    monkeypatch.setattr(text_gateway, "create_qa_adapter", lambda root: (gemini, None))
    configured = create_text_gateway(tmp_path, provider="gemini")
    assert configured.model.provider == "gemini" and configured.adapter is gemini
    configured.close()
