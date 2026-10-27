"""Mocked SDK và trusted validation integration; không credentials/network thật."""

from unittest.mock import Mock

import httpx
import pytest
from google import genai
from google.genai import errors, types
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.gemini_adapter import (
    DEFAULT_GEMINI_MODEL,
    GeminiAdapter,
)
from vietnamese_financial_multi_agent.core.llm_contracts import (
    SchemaValidation,
    parse_llm_request,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry

REF = {
    "schema_id": "urn:synthetic:classification",
    "name": "classification",
    "version": "v1",
    "dialect": "https://json-schema.org/draft/2020-12/schema",
}
SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["income", "expense", "other"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["category", "confidence"],
    "additionalProperties": False,
}


def request(*, structured=False, **changes):
    payload = {
        "contract_version": "llm_gateway_v1",
        "request_id": "synthetic-gemini-1",
        "model": {"provider": "gemini", "model": DEFAULT_GEMINI_MODEL},
        "messages": [{"role": "user", "content": "Synthetic example"}],
        "generation": {},
        "correlation": {"trace_id": "synthetic-trace"},
    }
    if structured:
        payload["output_spec"] = {"format": "json", "schema_ref": REF, "strict": True}
    payload.update(changes)
    return parse_llm_request(payload)


def registry():
    return LocalSchemaRegistry([(request(structured=True).output_spec.schema_ref, SCHEMA)])


def sdk_response(text="Synthetic example", finish="STOP", **changes):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(parts=[types.Part(text=text)]), finish_reason=finish
            )
        ],
        **changes,
    )


def setup(raw, *, schemas=None):
    client = Mock()
    client.models.generate_content.return_value = raw
    adapter = GeminiAdapter(client, schema_registry=schemas)
    gateway = SharedLLMGateway({"gemini": adapter}, schema_registry=schemas)
    return client, gateway


def test_text_model_messages_generation_timeout_and_usage():
    client, gateway = setup(
        sdk_response(
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=9,
                candidates_token_count=0,
                total_token_count=10,
                thoughts_token_count=1,
                cached_content_token_count=2,
            ),
            model_version="synthetic-version",
        )
    )
    req = request(
        model={"provider": "gemini", "model": "explicit-model"},
        messages=[
            {"role": "system", "content": "instruction"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "next"},
        ],
        generation={
            "temperature": 0.7,
            "top_p": 0.9,
            "max_output_tokens": 64,
            "stop_sequences": ["END"],
            "seed": 7,
        },
        constraints={"timeout_seconds": 1.25},
    )
    result = gateway.generate(req)
    assert result.status == "success"
    assert result.request_id == req.request_id and result.correlation == req.correlation
    assert result.provenance.requested_model == req.model
    assert result.provenance.provider_reported_model == "synthetic-version"
    assert result.usage.export() == {
        "status": "available",
        "source": "provider_reported",
        "input_tokens": 9,
        "output_tokens": 0,
        "total_tokens": 10,
        "cached_tokens": 2,
        "reasoning_tokens": 1,
    }
    assert result.cost.amount is None and result.cost.status == "unknown"
    kwargs = client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "explicit-model"
    assert [c.role for c in kwargs["contents"]] == ["user", "model", "user"]
    cfg = kwargs["config"]
    assert cfg.system_instruction.parts[0].text == "instruction"
    for name, value in req.generation.export().items():
        assert getattr(cfg, name) == value
    assert cfg.http_options.timeout == 1250 and cfg.http_options.retry_options.attempts == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"model": {"provider": "other", "model": "opaque"}},
        {"generation": {"seed": None}},
        {"generation": {"temperature": 3.0}},
        {"messages": [{"role": "developer", "content": "unsupported"}]},
        {"messages": [{"role": "user", "content": "first"}, {"role": "system", "content": "late"}]},
        {"constraints": {"timeout_seconds": None}},
    ],
)
def test_invalid_capabilities_rejected_before_sdk(changes):
    client = Mock()
    result = GeminiAdapter(client)(request(**changes))
    assert result.error.category == "invalid_request"
    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize(
    "text,expected,status",
    [
        ('{"category":"other","confidence":0.5}', "schema_valid", "success"),
        ('{"category":"wrong","confidence":0.5}', "schema_invalid", "malformed"),
        ('{"category":"other","confidence":2}', "schema_invalid", "malformed"),
        ('{"category":', "invalid_json", "malformed"),
    ],
)
def test_gateway_executes_real_schema_validation(text, expected, status):
    schemas = registry()
    client, gateway = setup(sdk_response(text), schemas=schemas)
    spy = Mock(wraps=schemas.is_valid)
    schemas.is_valid = spy
    result = gateway.generate(request(structured=True))
    assert result.output.validation_status == expected and result.status == status
    assert result.output.raw_text == text
    assert result.output.schema_ref.export() == REF
    assert client.models.generate_content.call_args.kwargs["config"].response_json_schema == SCHEMA
    assert spy.call_count == (0 if expected == "invalid_json" else 1)
    if expected != "invalid_json":
        assert spy.call_args.args == (result.output.schema_ref, result.output.payload)
        assert result.output.validation.status == expected


def test_unverified_without_gateway_validator_and_json_without_schema():
    client = Mock()
    client.models.generate_content.return_value = sdk_response('{"synthetic":true}')
    adapter = GeminiAdapter(client, schema_registry=registry())
    gateway = SharedLLMGateway({"gemini": adapter})
    assert gateway.generate(request(structured=True)).output.validation_status == "unverified"
    result = gateway.generate(request(output_spec={"format": "json"}))
    assert result.output.validation_status == "json_valid"
    assert result.usage.status == "unknown" and result.usage.total_tokens is None


def test_missing_schema_identity_version_and_registry_snapshot():
    schemas = registry()
    ref = request(structured=True).output_spec.schema_ref
    copy = schemas.schema_for(ref)
    copy["required"] = []
    assert schemas.schema_for(ref) == SCHEMA
    ref.version = "v2"
    client, gateway = setup(sdk_response("{}"), schemas=schemas)
    req = request(structured=True)
    req.output_spec.schema_ref = ref
    assert gateway.generate(req).error.category == "invalid_configuration"
    client.models.generate_content.assert_not_called()
    result = GeminiAdapter(client)(request(structured=True))
    assert result.error.category == "invalid_configuration"


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "bad"},
        {"$ref": "https://invalid.example/schema"},
        {"$id": "https://invalid.example/base"},
    ],
)
def test_invalid_or_remote_schema_rejected(schema):
    with pytest.raises(ValueError, match="Invalid or nonlocal schema"):
        LocalSchemaRegistry([(request(structured=True).output_spec.schema_ref, schema)])


@pytest.mark.parametrize("tamper", ["request_id", "model", "attestation"])
def test_trusted_registry_does_not_bypass_binding_or_trust_transport(tamper):
    schemas = registry()
    spy = Mock(wraps=schemas.is_valid)
    schemas.is_valid = spy

    def transport(req):
        result = FakeLLMTransport(json_text='{"category":"other","confidence":0.5}')(req)
        if tamper == "attestation":
            result.output.validation_status = "schema_valid"
            result.output.validation = SchemaValidation(
                schema_ref=req.output_spec.schema_ref,
                status="schema_valid",
                validator_id="untrusted",
            )
        elif tamper == "model":
            result.provenance.requested_model.model = "mismatch"
        else:
            result.request_id = "mismatch"
        return result

    result = SharedLLMGateway({"gemini": transport}, schema_registry=schemas).generate(
        request(structured=True)
    )
    assert result.status == "error" and result.output is None
    spy.assert_not_called()


@pytest.mark.parametrize(
    "code,reason,category",
    [
        (400, None, "invalid_request"),
        (401, None, "authentication"),
        (403, None, "authorization"),
        (429, None, "rate_limit"),
        (429, "QUOTA_EXCEEDED", "quota_exceeded"),
        (503, None, "provider_unavailable"),
        (504, None, "timeout"),
    ],
)
def test_sdk_errors_are_sanitized(code, reason, category, caplog, capsys):
    client, gateway = setup(None)
    sentinel = "synthetic-private-exception"
    client.models.generate_content.side_effect = errors.APIError(
        code,
        {
            "error": {
                "message": sentinel,
                "details": [{"reason": reason}],
            }
        },
    )
    result = gateway.generate(request())
    assert result.error.category == category
    assert sentinel not in result.to_json() + caplog.text + str(capsys.readouterr())
    assert result.output is None
    assert client.models.generate_content.call_count == 1


@pytest.mark.parametrize(
    "failure,category",
    [
        (httpx.ReadTimeout("synthetic"), "timeout"),
        (RuntimeError("synthetic"), "provider_unavailable"),
    ],
)
def test_timeouts_and_transport_failure(failure, category):
    client, gateway = setup(None)
    client.models.generate_content.side_effect = failure
    assert gateway.generate(request()).error.category == category


@pytest.mark.parametrize(
    "raw",
    [
        None,
        types.GenerateContentResponse(),
        types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="STOP")]),
    ],
)
def test_invalid_sdk_response(raw):
    _, gateway = setup(raw)
    assert gateway.generate(request()).error.category == "internal"


@pytest.mark.parametrize("finish,status", [("SAFETY", "refused"), ("MAX_TOKENS", "partial")])
def test_safety_and_partial(finish, status):
    _, gateway = setup(sdk_response('{"incomplete":', finish=finish))
    result = gateway.generate(request(output_spec={"format": "json"}))
    assert result.status == status
    if finish == "SAFETY":
        assert result.error.category == "safety" and result.output is None
    else:
        assert result.output.validation_status == "invalid_json"


def test_sdk_retry_disabled_at_http_boundary():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(429, json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with genai.Client(
            api_key="synthetic-unit-credential",
            vertexai=False,
            http_options=types.HttpOptions(httpx_client=http_client),
        ) as client:
            gateway = SharedLLMGateway({"gemini": GeminiAdapter(client)})
            assert gateway.generate(request()).error.category == "rate_limit"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "text,validation",
    [
        ('{"category":"other","confidence":1}', "schema_valid"),
        ('{"category":"wrong","confidence":1}', "schema_invalid"),
    ],
)
def test_partial_status_preserved_after_local_validation(text, validation):
    _, gateway = setup(sdk_response(text, finish="MAX_TOKENS"), schemas=registry())
    result = gateway.generate(request(structured=True))
    assert result.status == "partial" and result.finish_reason == "length"
    assert result.output.validation_status == validation


def test_prompt_safety_refusal_without_candidate():
    _, gateway = setup(
        types.GenerateContentResponse(
            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY")
        )
    )
    result = gateway.generate(request())
    assert result.status == "refused" and result.error.category == "safety"


def test_environment_credentials_required_and_selected_explicitly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY is required"):
        GeminiAdapter.from_environment()
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-selected-credential")
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-unselected-credential")
    constructor = Mock()
    monkeypatch.setattr(genai, "Client", constructor)
    adapter = GeminiAdapter.from_environment()
    assert constructor.call_args.kwargs["api_key"] == "synthetic-selected-credential"
    assert constructor.call_args.kwargs["vertexai"] is False
    assert constructor.call_args.kwargs["http_options"].retry_options.attempts == 1
    adapter.close()
    constructor.return_value.close.assert_called_once()
