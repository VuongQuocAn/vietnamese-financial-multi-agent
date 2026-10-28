"""Small deterministic rotation/cap regression set; never use real credentials."""

import json
from types import SimpleNamespace

from google.genai import errors
from vietnamese_financial_multi_agent.api.document_store import DocumentStore
from vietnamese_financial_multi_agent.api.metadata_service import (
    POOL_CREDENTIAL,
    POOL_SCOPE,
    FreeTierKeyPool,
    MetadataGeminiAdapter,
    compose_metadata_service,
)
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError, parse_llm_request
from vietnamese_financial_multi_agent.core.llm_quota_budget import QuotaLimits, Reservation
from vietnamese_financial_multi_agent.document_processing.metadata_preflight import (
    DEFAULT_METADATA_MODEL,
    metadata_schema_registry,
)


def request():
    return parse_llm_request(
        dict(
            contract_version="llm_gateway_v1",
            request_id="pool-test",
            model=dict(provider="gemini", model=DEFAULT_METADATA_MODEL),
            messages=[dict(role="user", content="Synthetic request")],
            generation=dict(max_output_tokens=32),
        )
    )


def adapter(category=None, calls=None):
    def generate(req):
        if calls is not None:
            calls.append(category)
        response = FakeLLMTransport()(req)
        if category:
            response.status, response.output, response.finish_reason = "error", None, "error"
            response.error = GatewayError(
                category=category, code=category, origin="provider", retryability="unknown"
            )
        return response

    return generate


def generate(pool):
    return pool.generate(
        request(),
        project_ref=POOL_SCOPE,
        credential_ref=POOL_CREDENTIAL,
        reservation=Reservation(token_upper_bound=100, token_basis="caller_attested_upper_bound"),
    )


def test_rate_limit_rotates_and_successful_key_stays_selected(tmp_path):
    calls = []
    pool = FreeTierKeyPool(
        [adapter("rate_limit", calls), adapter(None, calls)], DocumentStore(tmp_path)
    )
    assert generate(pool).response.status == "success"
    assert [a["key_index"] for a in pool.attempts] == [0, 1]
    assert pool.status()[0]["cooldown_seconds"] > 0
    assert generate(pool).response.status == "success"
    assert calls == ["rate_limit", None, None]


def test_auth_disabled_and_all_unavailable_is_bounded(tmp_path):
    calls = []
    pool = FreeTierKeyPool(
        [adapter("authentication", calls), adapter("quota_exceeded", calls)],
        DocumentStore(tmp_path),
    )
    assert generate(pool).reason == "key_pool_unavailable"
    assert pool.keys[0].disabled
    assert generate(pool).reason == "key_pool_unavailable"
    assert len(calls) == 2


def test_one_cap_for_all_keys_and_survives_restart(tmp_path):
    store, calls = DocumentStore(tmp_path), []
    limits = QuotaLimits(rpm=10, tpm=1000, rpd=1)
    pool = FreeTierKeyPool(
        [adapter("rate_limit", calls), adapter(None, calls)], store, limits=limits
    )
    assert generate(pool).reason == "application_daily_limit"
    assert calls == ["rate_limit"]  # Rotation cannot multiply application budget.
    restarted = FreeTierKeyPool([adapter(None, calls)], store, limits=limits)
    assert generate(restarted).reason == "application_daily_limit"
    assert len(calls) == 1


def test_key_file_only_deduplicates_no_policy_or_scope(tmp_path, monkeypatch):
    key = "AIza" + "x" * 35
    key_file = tmp_path / "keys.txt"
    key_file.write_text(key + "\n" + key + "\ninvalid line\n")
    monkeypatch.setenv("GEMINI_API_KEY_FILE", str(key_file))
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    clients = []

    def client(**kwargs):
        clients.append(kwargs)
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.api.metadata_service.genai.Client", client
    )
    store = DocumentStore(tmp_path / "store")
    service, pool, options = compose_metadata_service(store)
    assert service is not None and len(pool.keys) == 1
    assert options == dict(credential_ref=POOL_CREDENTIAL)
    assert not (store.root / "accounting-scopes").exists()
    assert key not in json.dumps(pool.status())
    pool.close()
    assert compose_metadata_service(store)[0] is not None


def test_sdk_credential_error_and_retry_after_are_safe():
    def sdk_error(**kwargs):
        raise errors.ClientError(
            400, {"error": {"message": "must not leak", "details": [{"reason": "API_KEY_INVALID"}]}}
        )

    adapter = MetadataGeminiAdapter(
        SimpleNamespace(models=SimpleNamespace(generate_content=sdk_error)),
        schema_registry=metadata_schema_registry(),
    )
    result = adapter(request())
    assert result.error.category == "authentication" and "must not leak" not in result.to_json()

    def throttled(**kwargs):
        raise errors.ClientError(429, {"error": {"details": [{"retryDelay": "120s"}]}})

    adapter._sdk_client.models.generate_content = throttled
    assert adapter(request()).error.retry_after_seconds == 120
