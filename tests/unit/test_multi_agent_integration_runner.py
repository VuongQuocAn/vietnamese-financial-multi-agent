"""Offline evaluation controls; these tests do not measure financial accuracy."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "multi_agent_integration", SCRIPTS / "evaluate_multi_agent_integration.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_transport_error_is_saved_before_fail_stop(tmp_path):
    from vietnamese_financial_multi_agent.core.llm_contracts import LLMRequest
    from vietnamese_financial_multi_agent.core.llm_gateway import _failure

    calls = []

    def unavailable(request):
        calls.append(request)
        return _failure(request, "provider_unavailable")

    request = LLMRequest(
        contract_version="llm_gateway_v1",
        request_id="offline-stop",
        model=dict(provider="qwen", model="offline"),
        messages=[dict(role="user", content="offline")],
        generation=dict(max_output_tokens=8),
    )
    gateway = runner.TracedGateway(SimpleNamespace(generate=unavailable), tmp_path)
    with pytest.raises(runner.ProviderStopped):
        gateway.generate(request)
    events = json.loads((tmp_path / "provider-events.json").read_text())
    assert len(calls) == len(events) == 1
    assert events[0]["response"]["error"]["category"] == "provider_unavailable"
    assert not issubclass(runner.ProviderStopped, Exception)


def test_http_configuration_error_stops_but_schema_error_is_a_result():
    for category, code in [("invalid_request", "http_400"), ("timeout", None)]:
        assert runner.must_stop(
            SimpleNamespace(error=SimpleNamespace(category=category, provider_error_code=code))
        )
    assert not runner.must_stop(
        SimpleNamespace(
            error=SimpleNamespace(category="schema_validation_failed", provider_error_code=None)
        )
    )


def test_mixed_source_request_preserves_document_namespace():
    service = SimpleNamespace(
        documents=[SimpleNamespace(document_id="document", company_id="company")]
    )
    reference = dict(document_id="document", question="Mixed source?", request_snapshot_id=None)
    request = runner.request_for(reference, service, dict(provider="qwen", model="offline"), {})
    assert request.snapshot_id is None
    assert request.document_id == "document"
    reference["request_snapshot_id"] = "financial-snapshot"
    assert (
        runner.request_for(reference, service, request.model, {}).snapshot_id
        == "financial-snapshot"
    )
