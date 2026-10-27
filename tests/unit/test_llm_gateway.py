"""Focused synthetic gateway tests; không inference hoặc đánh giá tài chính."""

import socket
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Correlation,
    Cost,
    GatewayError,
    JSONOutput,
    LLMContractError,
    LLMRequest,
    ModelIdentity,
    OutputSpec,
    SchemaReference,
    SchemaValidation,
    Usage,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway


def request(request_id="synthetic-1", provider="provider-a", model="model-one", spec=None):
    return LLMRequest(
        contract_version="llm_gateway_v1",
        request_id=request_id,
        model=ModelIdentity(provider=provider, model=model),
        messages=[{"role": "user", "content": "Ví dụ synthetic"}],
        generation={},
        output_spec=spec,
        correlation=Correlation(trace_id=request_id, caller="unit-test"),
    )


def reference():
    return SchemaReference(
        schema_id="urn:synthetic:example",
        name="example",
        version="v1",
        dialect="https://json-schema.org/draft/2020-12/schema",
    )


def test_routing_and_explicit_model_configuration_without_network(monkeypatch):
    def no_network(*args, **kwargs):
        pytest.fail("Unexpected network call")

    monkeypatch.setattr(socket, "socket", no_network)
    seen = []

    def transport(req):
        seen.append(req.export())
        return FakeLLMTransport()(req)

    gateway = SharedLLMGateway({"provider-a": transport, "provider-b": transport})
    for provider, model in [("provider-a", "opaque:other-provider"), ("provider-b", "v2")]:
        req = request(provider=provider, model=model)
        result = gateway.generate(req)
        assert result.status == "success"
        assert seen[-1] == req.export()
        assert result.provenance.requested_model == req.model
        assert result.correlation == req.correlation
    assert (
        gateway.generate(request(provider="unregistered")).error.category == "invalid_configuration"
    )
    assert len(seen) == 2


def test_invalid_request_rejected_before_transport():
    req = request()
    req.messages = []
    with pytest.raises(LLMContractError, match="LLM contract validation failed"):
        SharedLLMGateway({}).generate(req)


@pytest.mark.parametrize("field", ["request_id", "model", "correlation", "missing_correlation"])
def test_binding_rejects_contract_valid_mismatches(field):
    def transport(req):
        result = FakeLLMTransport()(req)
        if field == "request_id":
            result.request_id = "another-request"
        elif field == "model":
            result.provenance.requested_model.model = "another-model"
        elif field == "correlation":
            result.correlation.trace_id = "another-trace"
        else:
            result.correlation = None
        return result

    req = request()
    result = SharedLLMGateway({"provider-a": transport}).generate(req)
    assert result.error.category == "internal"
    assert result.request_id == req.request_id
    assert result.provenance.requested_model == req.model
    assert result.output is None


def test_transport_cannot_mutate_binding_snapshot_or_caller():
    def transport(req):
        req.request_id = "rewritten"
        req.model.model = "rewritten"
        req.messages[0].content = "rewritten"
        return FakeLLMTransport()(req)

    req = request()
    before = req.export()
    result = SharedLLMGateway({"provider-a": transport}).generate(req)
    assert result.error.category == "internal"
    assert result.request_id == before["request_id"]
    assert req.export() == before


@pytest.mark.parametrize("schema", [False, True])
@pytest.mark.parametrize("raw", ['{"synthetic":true}', "null", '{"partial":'])
def test_json_syntax_schema_and_malformed_preserved(schema, raw):
    ref = reference() if schema else None
    req = request(spec=OutputSpec(format="json", schema_ref=ref, strict=True if schema else None))
    result = SharedLLMGateway({"provider-a": FakeLLMTransport(json_text=raw)}).generate(req)
    assert result.output.raw_text == raw
    assert result.output.schema_ref == ref
    if raw.endswith(":"):
        assert result.status == "malformed"
        assert result.output.validation_status == "invalid_json"
        assert result.output.payload is None
        assert result.error.category == "structured_output_invalid"
    else:
        assert result.status == "success"
        assert result.output.validation_status == ("unverified" if schema else "json_valid")


@pytest.mark.parametrize("kind", ["format", "schema", "schema_valid", "schema_invalid"])
def test_structured_binding_and_untrusted_attestation(kind):
    req = request(spec=OutputSpec(format="json", schema_ref=reference()))

    def transport(bound):
        if kind == "format":
            bound.output_spec = OutputSpec(format="text")
        elif kind == "schema":
            bound.output_spec.schema_ref.version = "v2"
        result = FakeLLMTransport()(bound)
        if kind in ("schema_valid", "schema_invalid"):
            result.output.validation_status = kind
            result.output.validation = SchemaValidation(
                schema_ref=reference(), validator_id="synthetic-untrusted", status=kind
            )
            if kind == "schema_invalid":
                result.status = "malformed"
                result.error = GatewayError(
                    category="schema_mismatch",
                    code="schema_mismatch",
                    origin="adapter",
                    retryability="not_retryable",
                )
        return result

    result = SharedLLMGateway({"provider-a": transport}).generate(req)
    assert result.status == "error"
    assert result.output is None
    assert result.error.category == (
        "structured_output_invalid" if kind == "format" else "schema_mismatch"
    )


@pytest.mark.parametrize("invalid", [None, {"status": "success"}, "mutable_status"])
def test_invalid_response_revalidated(invalid):
    def transport(req):
        if invalid == "mutable_status":
            result = FakeLLMTransport(json_text="{")(request(spec=OutputSpec(format="json")))
            result.status = "success"  # mutable model phải được revalidate.
            return result
        return invalid

    result = SharedLLMGateway({"provider-a": transport}).generate(request())
    assert result.error.category == "internal"


@pytest.mark.parametrize(
    "exc,category", [(RuntimeError, "provider_unavailable"), (TimeoutError, "timeout")]
)
def test_exception_sanitization_and_next_request(exc, category, caplog, capsys):
    sentinel = "synthetic-private-exception-body"

    def transport(req):
        if req.request_id == "fail":
            raise exc(sentinel)
        return FakeLLMTransport()(req)

    gateway = SharedLLMGateway({"provider-a": FakeLLMTransport(transport)})
    result = gateway.generate(request("fail"))
    assert result.error.category == category
    assert result.error.safe_message == "LLM operation failed"
    assert sentinel not in result.to_json() + caplog.text + str(capsys.readouterr())
    assert gateway.generate(request("next")).status == "success"


@pytest.mark.parametrize("category", ["rate_limit", "quota_exceeded", "timeout"])
def test_provider_errors_preserved_without_retry(category):
    calls = []

    def transport(req):
        calls.append(req.request_id)
        result = FakeLLMTransport()(req)
        result.status, result.output, result.finish_reason = "error", None, "error"
        result.error = GatewayError(
            category=category,
            code=category,
            origin="provider",
            retryability="unknown",
            provider_error_code="http_429" if category != "timeout" else "http_408",
        )
        return result

    result = SharedLLMGateway({"provider-a": transport}).generate(request())
    assert result.error.category == category
    assert result.error.origin == "provider"
    assert len(calls) == 1


@pytest.mark.parametrize("available", [False, True])
def test_usage_cost_and_provenance_preserved(available):
    responses = []

    def transport(req):
        result = FakeLLMTransport()(req)
        if available:
            result.usage = Usage(
                status="available", source="provider_reported", input_tokens=7, output_tokens=0
            )
            result.cost = Cost(
                status="available",
                source="provider_reported",
                amount=Decimal("0.001200"),
                currency="USD",
                price_source="synthetic",
            )
            result.provenance.metadata_source = "provider_reported"
            result.provenance.provider_reported_model = "synthetic-alias"
        responses.append(result)
        return result

    result = SharedLLMGateway({"provider-a": transport}).generate(request())
    assert result.export() == responses[0].export()
    assert result.usage.total_tokens is None
    if available:
        assert result.cost.export()["amount"] == "0.001200"
    else:
        assert result.usage.input_tokens is None
        assert result.cost.amount is None
    result.usage.status = "not_available"
    assert responses[0].usage.status == ("available" if available else "unknown")


def test_concurrent_requests_and_partial_json_are_isolated():
    def transport(req):
        result = FakeLLMTransport(json_text="{")(req)
        result.status, result.finish_reason = "partial", "length"
        return result

    gateway = SharedLLMGateway({"provider-a": transport})
    requests = [request(f"synthetic-{i}", spec=OutputSpec(format="json")) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(gateway.generate, requests))
    for req, result in zip(requests, results, strict=True):
        assert result.request_id == req.request_id
        assert result.correlation == req.correlation
        assert result.status == "partial"
        assert isinstance(result.output, JSONOutput)
        assert result.output.validation_status == "invalid_json"
