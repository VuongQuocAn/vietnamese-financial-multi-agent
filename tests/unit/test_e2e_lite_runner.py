"""Offline guards for the bounded evaluation runner; no financial gold fixtures."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/evaluate_e2e_lite.py"
SPEC = importlib.util.spec_from_file_location("e2e_lite_runner", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.mark.parametrize("events,size", [([{}] * 8, 10), ([], 12001), ([{"tokens": 24999}], 10)])
def test_live_limits_stop_before_transport(events, size, tmp_path):
    from vietnamese_financial_multi_agent.core.llm_contracts import (
        GenerationParameters,
        LLMRequest,
        Message,
        ModelIdentity,
    )

    def unexpected(_):
        pytest.fail("transport must not execute after budget is exhausted")

    gateway = runner.BoundedGateway(SimpleNamespace(generate=unexpected), tmp_path)
    gateway.events = events
    request = LLMRequest(
        contract_version="llm_gateway_v1",
        request_id="budget-control",
        model=ModelIdentity(provider="gemini", model="gemini-3.5-flash-lite"),
        messages=[Message(role="user", content="x" * size)],
        generation=GenerationParameters(max_output_tokens=100),
    )
    response = gateway.generate(request)
    assert response.error.category == "quota_exceeded"
    assert len(gateway.events) == len(events)


def test_question_matrix_preserves_two_turn_followup():
    assert len(runner.QUESTIONS) == 9
    assert [case for case, _ in runner.QUESTIONS[-2:]] == ["Q8.1", "Q8.2"]
    assert "tỷ lệ đó" in runner.QUESTIONS[-1][1]
