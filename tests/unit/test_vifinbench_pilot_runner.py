"""Input isolation and fixed sampling controls; no live API or financial fixture."""

import importlib.util
import json
import sys
from pathlib import Path


def runner_module(filename="run_vifinbench_pilot.py"):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("pilot_runner", scripts / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_sampling_ignores_gold_and_never_opens_full(tmp_path):
    runner = runner_module()
    benchmark = tmp_path / "ViFinBench/benchmark"
    benchmark.mkdir(parents=True)
    (benchmark / "document_metadata.json").write_text(
        json.dumps(
            {
                "TEST_2025": {"aliases": ["Issuer"], "fiscal_year": 2025},
            }
        )
    )
    for group in runner.GROUPS:
        directory = benchmark / group
        directory.mkdir()
        # Invalid content would fail immediately if full input were read.
        (directory / "full.jsonl").write_text("FORBIDDEN")
        rows = [
            dict(
                id=f"{group}-{i}",
                difficulty=runner.DIFFICULTIES[i // 5],
                question="Issuer năm 2025?",
                answer={"Gold": "must never enter runtime"},
                evidence={"document_id": "WRONG_2000"},
            )
            for i in range(15)
        ]
        (directory / "pilot.jsonl").write_text("\n".join(map(json.dumps, rows)))
    cases = runner.select_cases(tmp_path)
    assert [c["id"] for c in cases] == [f"{g}-{i}" for g in runner.GROUPS for i in (0, 5, 10)]
    assert all(c["document_alias"] == "TEST_2025" for c in cases)
    assert all(set(c) == {"id", "group", "difficulty", "question", "document_alias"} for c in cases)


def test_run_rejects_manifest_change_before_gateway(tmp_path, monkeypatch):
    runner = runner_module()
    output = tmp_path / "output"
    output.mkdir()
    (output / "questions-only.json").write_text("[]")
    (output / "receipt.json").write_text(json.dumps({"question_manifest_sha256": "wrong"}))

    def unexpected(*args, **kwargs):
        raise RuntimeError("gateway must not be constructed")

    monkeypatch.setattr(runner, "create_text_gateway", unexpected)
    import pytest

    with pytest.raises(AssertionError):
        runner.run(tmp_path, tmp_path, output, None)


def test_citation_pointer_resolves_escaped_keys_without_numeric_conversion():
    evaluator = runner_module("evaluate_vifinbench_pilot.py")
    document = {"a/b": {"x~y": ["001.000", "(2.000)"]}}
    assert evaluator.resolve_pointer(document, "/a~1b/x~0y/0") == "001.000"
    assert evaluator.resolve_pointer(document, "/a~1b/x~0y/1") == "(2.000)"
