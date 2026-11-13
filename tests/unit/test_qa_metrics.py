"""Scoring mechanics only; these fixtures are not financial quality evidence."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def script(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[2] / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_numeric_equivalence_and_final_answer_scoring():
    metrics = script("qa_metrics")
    money = dict(value="1234567890", unit="VND")
    assert metrics.equivalent(dict(value="1.23", scale="1000000000", unit="VND"), money)
    ratio = dict(value="0.590584087509", unit="ratio")
    assert metrics.equivalent(dict(value="59.06", unit="percent"), ratio)
    assert metrics.equivalent(dict(value="0.59", unit="ratio"), ratio)
    assert not metrics.equivalent(dict(value="59.0", unit="percent"), ratio)
    assert not metrics.equivalent(dict(value="-0.59", unit="ratio"), ratio)
    assert not metrics.equivalent(dict(value="0.59", unit="VND"), ratio)
    review = dict(
        status="COMPLETED",
        answer="Tỷ trọng nợ khoảng 59,06% [1].",
        constraints_met=True,
        gold=[dict(id="debt", **ratio), dict(id="synthesis")],
        claims=[
            dict(
                id="debt",
                quote="Tỷ trọng nợ khoảng 59,06%",
                gold_ids=["debt"],
                numeric=dict(value="59.06", unit="percent"),
                correct=True,
                cited=True,
                citation_correct=True,
                assessment="Correct period, item and source page.",
            )
        ],
    )
    result = metrics.score(review)
    assert result["metrics"]["numeric_accuracy"] == 1
    assert result["metrics"]["numeric_em"] == 1
    assert result["metrics"]["claim_recall"] == 0.5
    assert result["metrics"]["claim_f1"] == pytest.approx(2 / 3)
    assert result["metrics"]["citation_accuracy"] == 1
    assert result["metrics"]["answer_accuracy"] == 0
    review["claims"][0]["citation_correct"] = False
    assert metrics.score(review)["metrics"]["claim_precision"] == 1
    assert metrics.score(review)["metrics"]["citation_accuracy"] == 0
    # A prohibition affects whole-answer compliance, not positive-claim recall.
    constrained = dict(review, gold=review["gold"][:1])
    constrained["claims"][0]["citation_correct"] = True
    assert metrics.score(constrained)["metrics"]["claim_recall"] == 1
    assert metrics.score(constrained)["metrics"]["answer_accuracy"] == 1
    constrained["constraints_met"] = False
    assert metrics.score(constrained)["metrics"]["claim_recall"] == 1
    assert metrics.score(constrained)["metrics"]["answer_accuracy"] == 0
    assert metrics.score(dict(status="INTERRUPTED"))["metrics"] is None
    review["claims"][0]["quote"] = "An ACCEPT claim missing from final answer"
    with pytest.raises(AssertionError, match="final_answer"):
        metrics.score(review)


def test_live_runner_persists_provider_failure_without_retry(tmp_path):
    runner = script("validate_v2_live")
    loader = Mock(return_value="BBS catalog")
    assert runner.case_catalog(tmp_path, "C10", loader) is None
    loader.assert_not_called()
    assert runner.case_catalog(tmp_path, "C01", loader) == "BBS catalog"
    loader.assert_called_once_with(tmp_path)
    request = runner.live_request(
        {"question": "A financial question"}, {"provider": "qwen", "model": "model"}
    )
    assert request.integration_v2 and request.force_refresh
    assert request.request_timeout_seconds <= 300
    response = SimpleNamespace(
        status="error",
        error=SimpleNamespace(category="timeout"),
        export=lambda: {"status": "error", "usage": {"total_tokens": None}},
    )
    gateway = Mock(generate=Mock(return_value=response))
    events = []
    wrapped = runner.BudgetedGateway(gateway, tmp_path, events, "case")
    with pytest.raises(runner.ValidationStopped, match="provider_non_success"):
        wrapped.generate(SimpleNamespace(export=lambda: {"request_id": "case"}))
    assert gateway.generate.call_count == 1
    assert runner.read(tmp_path / "provider-events.json")[0]["status"] == "error"
    assert events[0]["elapsed_seconds"] >= 0


def test_mixed_no_inference_constraint_is_scope_not_retrieval():
    from vietnamese_financial_multi_agent.agents.fusion_contracts import FusionPlan
    from vietnamese_financial_multi_agent.agents.qa_planning import (
        response_constraints,
        retain_response_constraints,
    )

    question = "Nêu doanh thu và chính sách. Không suy ra nguyên nhân từ chính sách."
    plan = FusionPlan(
        question=question,
        requirements=[
            dict(requirement_id="R1", original_span="Nêu doanh thu", lane="financial", kind="fact"),
            dict(requirement_id="R2", original_span="Chính sách", lane="document", kind="document"),
            dict(
                requirement_id="R3",
                original_span=response_constraints(question)[0],
                lane="financial",
                kind="interpretation",
                dependencies=["R2"],
            ),
        ],
    )
    assert len(retain_response_constraints(plan, question).requirements) == 2
    assert response_constraints("Không có số liệu. Nêu doanh thu.") == []
    plan.requirements[0].original_span = "Không suy ra nguyên nhân và tính tăng trưởng"
    assert len(retain_response_constraints(plan, question).requirements) == 2
