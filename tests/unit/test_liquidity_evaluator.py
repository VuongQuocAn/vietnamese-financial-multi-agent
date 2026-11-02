"""Focused regressions for scorer grammar and append-only evidence writing."""

import importlib
import json
from pathlib import Path


def evaluator(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("evaluate_m5_05_liquidity")


def test_independent_interpretation_scorer_compiles_and_rejects_invented_semantics(monkeypatch):
    api = evaluator(monkeypatch)
    text = "Cứ 100 đồng tổng tài sản tại thời điểm báo cáo tương ứng khoảng 59,06 đồng nợ phải trả."
    assert api.interpretation_valid(text, "59,06")
    assert not api.interpretation_valid(text, "59,07")
    assert not api.interpretation_valid(text.replace("nợ phải trả", "nợ vay"), "59,06")
    assert not api.interpretation_valid(text + " Doanh nghiệp an toàn.", "59,06")


def test_compatibility_summary_does_not_overwrite_bounded_regression_evidence(
    monkeypatch, tmp_path
):
    api = evaluator(monkeypatch)
    output = tmp_path / "output"
    output.mkdir()
    expected = {"accepted_execution_exact": 18}

    def completed_regressions(*_args):
        api.save(output / "regression-summary.json", expected)
        return expected.copy()

    monkeypatch.setattr(api, "profitability_regressions", completed_regressions)
    for suffix in ("before", "after"):
        folder = tmp_path / f"artifacts/evidence/M5-04-M5-05-{suffix}"
        folder.mkdir(parents=True)
        for index in range(13):
            api.save(
                folder / f"result-{index}.json", {"status": "generated", "candidate_id": suffix}
            )
    result = api.regressions(tmp_path, None, None, None, None, output, None, None)
    assert result["m5_04_before_after_exact"] == 13
    assert json.loads((output / "regression-summary.json").read_text()) == expected
    assert json.loads((output / "compatibility-summary.json").read_text()) == result
