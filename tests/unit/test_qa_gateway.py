"""Credential composition offline; không đọc local keys thật hoặc gọi Gemini."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.api import qa_gateway


def test_local_format_dedup_precedence_and_safe_errors(tmp_path):
    key_one, key_two = "AIza" + "a" * 35, "AIza" + "b" * 35
    folder = tmp_path / "src/api/api_key"
    folder.mkdir(parents=True)
    path = folder / "api_gemini.txt"
    path.write_text(
        "\ufeff# local keys\n" + key_one + "\n" + key_one + "\nheader\n" + key_two, encoding="utf-8"
    )
    selected = qa_gateway.resolve_qa_credential(tmp_path, environment={}, key_index=1)
    assert selected.key == key_two and selected.key_count == 2
    assert selected.source == "local_default_file" and key_two not in repr(selected)
    env = {"GEMINI_API_KEY": key_one, "GEMINI_API_KEY_FILE": "missing"}
    assert qa_gateway.resolve_qa_credential(tmp_path, environment=env).source == "environment"
    assert (
        qa_gateway.resolve_qa_credential(tmp_path, environment=env, key_file=path).source
        == "configured_file"
    )
    with pytest.raises(qa_gateway.QACredentialError, match="^key_index_out_of_range$"):
        qa_gateway.resolve_qa_credential(tmp_path, environment={}, key_index=2)
    with pytest.raises(qa_gateway.QACredentialError, match="^key_format_invalid$"):
        qa_gateway.resolve_qa_credential(tmp_path, environment={"GEMINI_API_KEY": "bad"})
    with pytest.raises(qa_gateway.QACredentialError, match="^key_file_unreadable$"):
        qa_gateway.resolve_qa_credential(tmp_path, environment={}, key_file="missing")


def test_composition_uses_selected_key_and_disables_sdk_retries(monkeypatch, tmp_path):
    seen = []
    key = "AIza" + "c" * 35
    monkeypatch.setenv("GEMINI_API_KEY", key)

    class Client:
        def __init__(self, **options):
            seen.append(options)

        def close(self):
            seen.append("closed")

    monkeypatch.setattr(qa_gateway.genai, "Client", Client)
    adapter, credential = qa_gateway.create_qa_adapter(tmp_path)
    assert credential.source == "environment"
    assert seen[0]["api_key"] == key
    assert seen[0]["http_options"].retry_options.attempts == 1
    assert seen[0]["vertexai"] is False
    adapter.close()
    assert seen[-1] == "closed"


@pytest.mark.parametrize("second_success", [True, False])
def test_rotation_cooldown_shared_pipeline_and_exhaustion(tmp_path, second_success):
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
    from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway

    from .test_llm_gateway import request

    calls = []

    def transport(index):
        def call(req):
            calls.append(index)
            response = _failure(req, "rate_limit")
            response.error.provider_error_code = "http_429"
            if index == 1 and second_success:
                from vietnamese_financial_multi_agent.core.fake_llm_transport import (
                    FakeLLMTransport,
                )

                response = FakeLLMTransport()(req)
            return response

        return Mock(side_effect=call)

    pool = qa_gateway.FreeTierKeyPool(
        [transport(0), transport(1)], SimpleNamespace(root=tmp_path), max_attempts=2
    )
    adapter = qa_gateway.QARotatingAdapter(pool)
    scoped = RequestGateway(SharedLLMGateway({"gemini": adapter}), max_calls=8, timeout_seconds=30)
    req = request(provider="gemini", model="gemini-3.5-flash-lite")
    response = scoped.generate(req)
    assert calls == [0, 1]
    assert pool.status()[0]["cooldown_seconds"] > 0
    assert [e["key_index"] for e in adapter.events] == [0, 1]
    if second_success:
        assert response.status == "success"
        scoped.generate(req.model_copy(update={"request_id": "next-agent"}))
        assert calls == [0, 1, 1]
    else:
        assert response.error.retryability == "not_retryable"
        assert len(scoped.events) == 1
        scoped.generate(req)
        assert calls == [0, 1]
