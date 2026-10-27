"""Synthetic contract tests; không live provider hoặc đánh giá tài chính."""

import ast
import json
import socket
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    GatewayError,
    GenerationParameters,
    JSONOutput,
    LLMContractError,
    LLMRequest,
    Message,
    OutputSpec,
    ResponseProvenance,
    SchemaReference,
    Usage,
    llm_gateway_json_schema,
    parse_json_output,
    parse_llm_request,
    parse_llm_response,
)


def request() -> dict:
    return {
        "contract_version": "llm_gateway_v1",
        "request_id": "synthetic-1",
        "model": {"provider": "provider-a", "model": "family/model:version"},
        "messages": [{"role": "user", "content": "Đọc văn bản tiếng Việt: Ỹ, ệ, đ."}],
        "generation": {},
    }


def reference() -> SchemaReference:
    return SchemaReference(
        schema_id="urn:synthetic:example",
        name="example",
        version="v1",
        dialect="https://json-schema.org/draft/2020-12/schema",
    )


def response() -> dict:
    return {
        "contract_version": "llm_gateway_v1",
        "request_id": "synthetic-1",
        "status": "success",
        "finish_reason": "stop",
        "provenance": {"requested_model": request()["model"], "metadata_source": "unknown"},
        "usage": {"status": "unknown", "source": "unknown"},
        "cost": {"status": "unknown", "source": "unknown"},
        "output": {"format": "text", "text": "Tổng hợp tiếng Việt."},
    }


def error(category: str, retryability: str = "unknown") -> dict:
    return {
        "category": category,
        "code": category,
        "retryability": retryability,
        "origin": "provider",
    }


def test_request_roundtrip_order_and_unicode() -> None:
    payload = request()
    payload["messages"] = [
        {"role": role, "content": f" {role}: Tiếng Việt\n"}
        for role in ("system", "developer", "user", "assistant", "user")
    ]
    model = parse_llm_request(payload)
    assert model.export() == payload
    assert parse_llm_request(model.to_json()).export() == payload
    assert model.to_json() == parse_llm_request(dict(reversed(list(payload.items())))).to_json()
    assert "Tiếng Việt" in model.to_json()


@pytest.mark.parametrize("value", ["", " \n\t", None, 3, [], {}, b"text"])
def test_invalid_message_content(value) -> None:
    payload = request()
    payload["messages"][0]["content"] = value
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


@pytest.mark.parametrize(
    "value",
    [[], None, "text", [{"role": "tool", "content": "a"}], [{"role": "user", "content": ["a"]}]],
)
def test_invalid_conversation(value) -> None:
    payload = request()
    payload["messages"] = value
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


@pytest.mark.parametrize("value", ["", " ", "model with spaces", "../model?x", None, 42, True])
def test_invalid_model_identifier(value) -> None:
    payload = request()
    payload["model"]["model"] = value
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("temperature", -1),
        ("temperature", float("nan")),
        ("temperature", float("inf")),
        ("temperature", True),
        ("top_p", -0.1),
        ("top_p", 1.1),
        ("top_p", "0.5"),
        ("max_output_tokens", 0),
        ("max_output_tokens", 1.5),
        ("max_output_tokens", True),
        ("seed", "1"),
        ("seed", False),
        ("stop_sequences", [""]),
        ("stop_sequences", "stop"),
        ("provider_kwargs", {}),
    ],
)
def test_generation_invalid(field, value) -> None:
    payload = request()
    payload["generation"][field] = value
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


@pytest.mark.parametrize("value", [None, 0.0, 0.7])
def test_missing_null_value(value) -> None:
    payload = request()
    assert "temperature" not in parse_llm_request(payload).export()["generation"]
    payload["generation"]["temperature"] = value
    assert parse_llm_request(payload).export()["generation"]["temperature"] == value


def test_no_business_defaults_no_truncation() -> None:
    payload = request()
    payload["messages"][0]["content"] = "ệ" * 100_000
    model = parse_llm_request(payload)
    assert model.export()["generation"] == {}
    assert len(model.messages[0].content) == 100_000
    assert GenerationParameters(temperature=9.0).temperature == 9  # capability TBD


@pytest.mark.parametrize(
    "payload",
    [
        {"format": "xml"},
        {"format": "text", "schema_ref": reference().export()},
        {"format": "json", "strict": True},
        {"format": "json", "strict": False},
    ],
)
def test_invalid_output_specs(payload) -> None:
    with pytest.raises(ValidationError):
        OutputSpec.model_validate(payload)


@pytest.mark.parametrize("raw", ["null", "true", "42", '"Việt"', "[]", '{"value":1}'])
def test_json_syntax_is_not_schema_success(raw) -> None:
    output = parse_json_output(raw)
    assert output.validation_status == "json_valid"
    assert output.payload == json.loads(raw)
    unverified = parse_json_output(raw, schema_ref=reference())
    assert unverified.validation_status == "unverified"
    assert unverified.validation is None
    assert (
        JSONOutput.model_validate(json.loads(unverified.to_json())).export() == unverified.export()
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{",
        "text",
        "{} trailing",
        "NaN",
        "Infinity",
        '{"a":1,"a":2}',
        '{"nested":{"a":1,"a":2}}',
    ],
)
def test_malformed_json(raw) -> None:
    output = parse_json_output(raw, schema_ref=reference())
    assert output.validation_status == "invalid_json"
    assert output.payload is None


@pytest.mark.parametrize("status", ["schema_valid", "schema_invalid"])
def test_explicit_schema_attestation(status) -> None:
    payload = parse_json_output('{"synthetic":1}', schema_ref=reference()).export()
    payload["validation_status"] = status
    with pytest.raises(ValidationError):
        JSONOutput.model_validate(payload)
    payload["validation"] = {
        "schema_ref": reference().export(),
        "validator_id": "synthetic-validator/v1",
        "status": status,
    }
    assert JSONOutput.model_validate(payload).validation_status == status
    payload["validation"]["schema_ref"]["version"] = "v2"
    with pytest.raises(ValidationError):
        JSONOutput.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"payload": True},
        {"validation_status": "schema_valid"},
        {"validation_status": "invalid_json"},
        {"format": "text"},
        {"text": "ambiguous"},
        {"validation_status": "unverified"},
    ],
)
def test_output_cannot_silently_change_meaning(changes) -> None:
    payload = parse_json_output("1").export() | changes
    with pytest.raises(ValidationError):
        JSONOutput.model_validate(payload)


def test_text_json_ambiguity_explicit_format() -> None:
    payload = response()
    payload["output"] = {"format": "text", "text": '{"a":1}'}
    assert parse_llm_response(payload).output.format == "text"
    payload["output"]["payload"] = {"a": 1}
    with pytest.raises(LLMContractError):
        parse_llm_response(payload)


def test_unknown_zero_and_provider_token_accounting() -> None:
    assert Usage(status="unknown", source="unknown").total_tokens is None
    actual = Usage(status="available", source="provider_reported", input_tokens=0)
    assert actual.input_tokens == 0 and actual.total_tokens is None
    usage = Usage(
        status="available",
        source="provider_reported",
        input_tokens=10,
        output_tokens=20,
        total_tokens=99,
        cached_tokens=3,
        reasoning_tokens=4,
    )
    assert usage.total_tokens == 99


@pytest.mark.parametrize(
    "updates",
    [
        {"input_tokens": -1},
        {"total_tokens": True},
        {"output_tokens": "1"},
        {"cached_tokens": 0},
        {"source": "provider_reported"},
        {"status": "available"},
    ],
)
def test_inconsistent_usage(updates) -> None:
    with pytest.raises(ValidationError):
        Usage.model_validate({"status": "unknown", "source": "unknown"} | updates)


def test_decimal_money_roundtrip() -> None:
    cost = Cost(
        status="available",
        source="calculated",
        amount=Decimal("0.0000012300"),
        currency="USD",
        price_source="synthetic-price",
        pricing_version="v1",
        pricing_timestamp="2026-10-27T00:00:00Z",
    )
    assert cost.export()["amount"] == "0.0000012300"
    assert Cost.model_validate(json.loads(cost.to_json())).amount == cost.amount
    assert Cost(status="unknown", source="unknown").amount is None
    assert (
        Cost(
            status="available",
            source="provider_reported",
            amount="0",
            currency="VND",
            price_source="provider-receipt",
        ).amount
        == 0
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount", -1.0),
        ("amount", 0.1),
        ("amount", 0),
        ("amount", "-1"),
        ("amount", "NaN"),
        ("amount", "Infinity"),
        ("amount", True),
        ("currency", "usd"),
        ("currency", "US"),
        ("currency", "123"),
        ("currency", "US$"),
        ("currency", "USD\n"),
        ("pricing_timestamp", "2026-02-30T00:00:00Z"),
    ],
)
def test_invalid_cost(field, value) -> None:
    payload = {
        "status": "available",
        "source": "estimated",
        "amount": "1",
        "currency": "USD",
        "price_source": "synthetic",
        "pricing_version": "v1",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        Cost.model_validate(payload)


@pytest.mark.parametrize(
    "category",
    [
        "invalid_request",
        "invalid_configuration",
        "authentication",
        "authorization",
        "rate_limit",
        "quota_exceeded",
        "provider_unavailable",
        "timeout",
        "network",
        "structured_output_invalid",
        "schema_mismatch",
        "safety",
        "internal",
        "unknown_provider",
    ],
)
def test_error_taxonomy_safe_roundtrip(category) -> None:
    model = GatewayError.model_validate(error(category))
    assert model.safe_message == "LLM operation failed"
    assert GatewayError.model_validate(json.loads(model.to_json())).category == category


def test_rate_limit_not_quota_and_no_429_inference() -> None:
    transient = GatewayError.model_validate(error("rate_limit", "retryable"))
    assert transient.retryability == "retryable"
    quota = GatewayError.model_validate(
        error("quota_exceeded") | {"provider_error_code": "http_429"}
    )
    assert quota.retryability == "unknown"
    with pytest.raises(ValidationError):
        GatewayError.model_validate(error("quota_exceeded", "retryable"))


@pytest.mark.parametrize(
    "field", ["safe_message", "exception", "body", "api_key", "provider_error_code"]
)
def test_no_exception_or_secret_leakage(field) -> None:
    secret = "synthetic-sensitive-value"
    payload = response()
    payload.update(
        status="error",
        finish_reason="error",
        output=None,
        error=error("unknown_provider") | {field: secret},
    )
    with pytest.raises(LLMContractError) as caught:
        parse_llm_response(payload)
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value.issues)
    assert not hasattr(caught.value, "payload")


def test_secret_extra_key_safe_paths_nested_field() -> None:
    payload = request()
    payload["messages"][0]["content"] = 3
    payload["synthetic-sensitive-key"] = "sensitive-input"
    with pytest.raises(LLMContractError) as caught:
        parse_llm_request(payload)
    paths = [issue.path for issue in caught.value.issues]
    assert ("messages", 0, "content") in paths
    assert "synthetic-sensitive-key" not in repr(paths)
    assert "sensitive-input" not in repr(vars(caught.value))


@pytest.mark.parametrize("value", [float("nan"), object(), {1: "bad-key"}, "\ud800"])
def test_non_json_values_invalid_unicode(value) -> None:
    payload = request()
    payload["messages"][0]["content"] = value
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


@pytest.mark.parametrize(
    "payload", ['{"request_id":"a","request_id":"b"}', '{"messages":"\\ud800"}', "{", "NaN"]
)
def test_strict_json_entrypoint(payload) -> None:
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


def test_response_states_and_provenance() -> None:
    payload = response()
    assert parse_llm_response(payload).to_json() == parse_llm_response(payload).to_json()
    payload["status"] = "error"
    with pytest.raises(LLMContractError):
        parse_llm_response(payload)
    payload.update(output=None, error=error("timeout"), finish_reason="error")
    assert parse_llm_response(payload).output is None
    payload.update(status="refused", error=error("safety"), finish_reason="safety")
    assert parse_llm_response(payload).status == "refused"
    payload.update(
        status="partial",
        error=None,
        finish_reason="length",
        output={"format": "text", "text": "Incomplete"},
    )
    assert parse_llm_response(payload).status == "partial"
    payload.update(
        status="malformed",
        error=error("structured_output_invalid"),
        output=parse_json_output("{").export(),
    )
    assert parse_llm_response(payload).status == "malformed"
    payload.update(status="success", error=None, finish_reason="stop")
    with pytest.raises(LLMContractError):
        parse_llm_response(payload)
    provenance = {
        "requested_model": request()["model"],
        "metadata_source": "adapter_confirmed",
        "effective_model": {"provider": "provider-b", "model": "other"},
        "provider_reported_model": "alias-123",
    }
    model = ResponseProvenance.model_validate(provenance)
    assert model.requested_model != model.effective_model
    provenance["metadata_source"] = "unknown"
    with pytest.raises(ValidationError):
        ResponseProvenance.model_validate(provenance)


def test_schema_drift_and_public_fields() -> None:
    schema = llm_gateway_json_schema()
    artifact = Path(__file__).resolve().parents[2] / "schemas/llm_gateway_v1.schema.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == schema
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["$defs"]["Cost"]["properties"]["amount"]["anyOf"][0]["type"] == "string"
    assert schema["$defs"]["LLMRequest"]["additionalProperties"] is False
    assert set(LLMRequest.model_fields) == {
        "contract_version",
        "request_id",
        "model",
        "messages",
        "generation",
        "output_spec",
        "constraints",
        "correlation",
    }
    for definition in schema["$defs"].values():
        fields = definition.get("properties", {})
        assert not (
            {"api_key", "credentials", "account_id", "provider_kwargs", "exception", "body"}
            & fields.keys()
        )


def test_no_network_environment_or_business_dependency(monkeypatch) -> None:
    def denied(*args, **kwargs):
        raise AssertionError("Network is outside contract scope")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    parse_llm_request(request())
    parse_llm_response(response())
    parse_json_output('{"synthetic":true}')
    import vietnamese_financial_multi_agent.core.llm_contracts as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert all(
        name and name.split(".")[0] in {"datetime", "decimal", "typing", "pydantic"}
        for name in imports
    )


def test_reject_future_version_metadata_and_mutation_at_export() -> None:
    payload = request()
    payload["contract_version"] = "llm_gateway_v2"
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)
    payload = request()
    payload["correlation"] = {"arbitrary": "metadata"}
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)
    model = parse_llm_request(request())
    model.messages.append(Message(role="user", content="valid"))
    model.messages[0].content = ""
    with pytest.raises(ValidationError):
        model.export()


@pytest.mark.parametrize("value", [0, -1, True, "10", float("inf")])
def test_invalid_timeout(value) -> None:
    payload = request() | {"constraints": {"timeout_seconds": value}}
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


@pytest.mark.parametrize("field", ["output_spec", "constraints", "correlation"])
def test_request_optional_missing_and_null(field) -> None:
    assert field not in parse_llm_request(request()).export()
    assert parse_llm_request(request() | {field: None}).export()[field] is None


def test_success_schema_invalid_and_incomplete_response_rules() -> None:
    output = parse_json_output("{}", schema_ref=reference()).export()
    output.update(
        validation_status="schema_invalid",
        validation={
            "schema_ref": reference().export(),
            "validator_id": "synthetic-validator",
            "status": "schema_invalid",
        },
    )
    payload = response() | {
        "status": "malformed",
        "output": output,
        "error": error("schema_mismatch"),
    }
    assert parse_llm_response(payload).output.validation.status == "schema_invalid"
    payload["error"] = error("structured_output_invalid")
    with pytest.raises(LLMContractError):
        parse_llm_response(payload)
    for updates in [
        {"output": None},
        {"finish_reason": "length"},
        {"error": error("timeout")},
        {"status": "refused"},
        {"status": "partial", "output": None},
        {"status": "pending"},
    ]:
        with pytest.raises(LLMContractError):
            parse_llm_response(response() | updates)


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "unknown", "source": "unknown", "amount": "0"},
        {"status": "not_available", "source": "unknown", "currency": "USD"},
        {"status": "available", "source": "provider_reported", "amount": "0", "currency": "USD"},
        {
            "status": "available",
            "source": "calculated",
            "amount": "0",
            "currency": "USD",
            "price_source": "synthetic",
        },
    ],
)
def test_cost_provenance_required_and_unknown_not_zero(payload) -> None:
    with pytest.raises(ValidationError):
        Cost.model_validate(payload)


@pytest.mark.parametrize(
    "updates",
    [
        {"retryability": "auto"},
        {"origin": "network"},
        {"retry_after_seconds": -1},
        {"retry_after_seconds": float("nan")},
        {"category": "other"},
        {"code": "timeout"},
    ],
)
def test_error_metadata_invalid(updates) -> None:
    with pytest.raises(ValidationError):
        GatewayError.model_validate(error("rate_limit") | updates)


def test_structured_payload_is_json_only_and_unverified_not_upgradeable() -> None:
    payload = parse_json_output("{}", schema_ref=reference()).export()
    for updates in [
        {"validation_status": "json_valid"},
        {"payload": object()},
        {"payload": {"not-json": object()}},
        {"payload": {"bad": float("nan")}},
    ]:
        with pytest.raises(ValidationError):
            JSONOutput.model_validate(payload | updates)


def test_model_instances_and_long_text_types() -> None:
    model = parse_llm_request(request())
    assert LLMRequest.model_validate(model).export() == model.export()
    assert model.model.provider == "provider-a"
    payload = request()
    del payload["model"]["provider"]
    with pytest.raises(LLMContractError):
        parse_llm_request(payload)


def test_export_revalidates_money_before_serialization() -> None:
    cost = Cost(
        status="available",
        source="provider_reported",
        amount="1.23",
        currency="USD",
        price_source="synthetic",
    )
    cost.amount = 0.1
    with pytest.raises(ValidationError):
        cost.export()
