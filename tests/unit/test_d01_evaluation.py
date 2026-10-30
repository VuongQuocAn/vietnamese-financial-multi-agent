"""Engineering controls for D-01; synthetic equality is not financial accuracy."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from .test_evidence_contracts import fact


def test_cross_filing_equal_values_require_scope_and_entity(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("evaluate_d01_coverage")
    left, right = fact(document="filing-a"), fact(document="filing-b")
    original = [f.model_dump_json() for f in (left, right)]
    assert module.compare_observations([left, right])[0]["status"] == "consistent"
    right.context.reporting_scope = None
    result = module.compare_observations([left, right])[0]
    assert result["status"] == "undetermined" and result["numeric_equal"] is True
    assert "reporting_scope" in result["reasons"]
    right.context.reporting_scope = "separate"
    right.company_id = "another-entity"
    assert module.compare_observations([left, right])[0]["status"] == "undetermined"
    assert left.model_dump_json() == original[0]
    assert len(module.fixed_queries()) == 29


def test_reference_year_translation_keeps_current_and_comparative_distinct(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("evaluate_d01_coverage")
    metrics, _ = module.metrics_for(
        2024, dict(document_id="synthetic", attempt_id="synthetic"), [], []
    )
    yoy = next(m for m in metrics if m.definition.name == "revenue_yoy")
    assert yoy.request.operand_periods == {"current_revenue": "2024", "prior_revenue": "2023"}
    assert yoy.definition.compatibility.period_pairs[0].left == "2024"
    assert yoy.definition.compatibility.period_pairs[0].right == "2023"


def test_windows_persistence_retry_is_bounded_and_keeps_other_errors(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("evaluate_d01_coverage")
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    calls = []
    error = PermissionError("synthetic replace lock")
    error.winerror = 5

    def write(record):
        calls.append(record)
        raise error

    with pytest.raises(PermissionError):
        module.persist(SimpleNamespace(put=write), "record")
    assert calls == ["record", "record"]
    calls.clear()
    error.winerror = 13
    with pytest.raises(PermissionError):
        module.persist(SimpleNamespace(put=write), "record")
    assert calls == ["record"]
