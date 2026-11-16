"""Bounded corpus-runner controls; synthetic inputs do not measure financial accuracy."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import fallback_plan
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.evidence.refined_import import import_refined_document

from .test_refined_import import source

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "vfb_corpus_runner", SCRIPTS / "validate_vifinbench_json_pipeline.py"
)
runner = importlib.util.module_from_spec(SPEC)
# The CLI's sibling helper is imported exactly as when running python scripts/....
sys.path.insert(0, str(SCRIPTS))
try:
    SPEC.loader.exec_module(runner)
finally:
    sys.path.pop(0)


def test_discover_refined_documents_ignores_other_inputs(tmp_path):
    page = source(tmp_path)
    other = tmp_path / "TXT/2025"
    other.mkdir(parents=True)
    (other / "page_0001.json").write_text("{}", encoding="utf-8")
    (tmp_path / "gold.json").write_text("must not be read", encoding="utf-8")
    assert runner.discover_documents(tmp_path) == {"TST_2025": 1, "TXT_2025": 1}
    with pytest.raises(ValueError, match="no_refined_documents"):
        runner.discover_documents(other)
    # Source-backed cover after auditor front sheets; table/notes are not covers.
    folder = tmp_path / "TST/2025"
    (folder / "page_0001.json").write_text(
        json.dumps(
            dict(
                document_id="TST_2025",
                page=1,
                blocks=[dict(type="paragraph", text="Auditor signature")],
            )
        ),
        encoding="utf-8",
    )
    cover = dict(
        document_id="TST_2025",
        page=3,
        blocks=[
            dict(type="heading", text="CÔNG TY CỔ PHẦN TEST"),
            dict(type="heading", text="BÁO CÁO TÀI CHÍNH HỢP NHẤT"),
            dict(type="paragraph", text="Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2025"),
        ],
    )
    (folder / "page_0003.json").write_text(json.dumps(cover), encoding="utf-8")
    page["page"] = 4
    (folder / "page_0004.json").write_text(json.dumps(page), encoding="utf-8")
    _, facts, _, _ = import_refined_document(tmp_path, "TST_2025")
    assert facts[0].company_id
    assert any(s.reference.anchor.page.page == 3 for s in facts[0].sources)
    cover["blocks"][1]["text"] = "Other entity mentioned in notes"
    (folder / "page_0003.json").write_text(json.dumps(cover), encoding="utf-8")
    _, facts, _, _ = import_refined_document(tmp_path, "TST_2025")
    assert not facts[0].company_id


def test_corpus_runner_persists_two_documents_and_loads_index(tmp_path):
    root, output = tmp_path / "refined", tmp_path / "bundle"
    page = source(root)
    page["blocks"].insert(0, dict(type="heading", text="CÔNG TY CỔ PHẦN TEST"))
    (root / "TST/2025/page_0001.json").write_text(json.dumps(page), encoding="utf-8")
    text = root / "TXT/2025"
    text.mkdir(parents=True)
    (text / "page_0001.json").write_text(
        json.dumps(
            dict(
                document_id="TXT_2025",
                page=1,
                blocks=[dict(type="paragraph", text="Synthetic letter")],
            )
        ),
        encoding="utf-8",
    )
    summary = runner.validate(
        root, output, runner.discover_documents(root), projection_version="test-corpus"
    )
    assert [s["document_alias"] for s in summary] == ["TST_2025", "TXT_2025"]
    assert summary[0]["eligible_mapped_facts"] == summary[0]["financial_lookups"] == 1
    assert summary[0]["m5_candidates"] and summary[0]["restart_exact"]
    assert summary[1]["facts"] == 0 and summary[1]["m5_candidates"] == 0
    assert all(s["orphan_nodes"] == 0 for s in summary)
    assert (output / "coverage.csv").is_file()
    catalog = load_json_corpus_document(root, output, "TST_2025")
    focus = catalog.facts[0].model_copy(deep=True)
    focus.canonical_item_id = "b01.total_liabilities"
    focus.context.raw_item_label = "C. NỢ PHẢI TRẢ"
    assert runner.smoke_question(focus).startswith("Tổng nợ phải trả")
    focus.context.period = None
    assert runner.smoke_question(focus) == "Tổng nợ phải trả là bao nhiêu?"
    assert not fallback_plan(
        "Tổng nợ phải trả năm 2025 là bao nhiêu?",
        {
            "S1": dict(
                label="Tổng nợ phải trả",
                period=None,
                item="b01.total_liabilities",
                roles=["liquidity_and_leverage"],
            )
        },
    ).tasks
    assert catalog.descriptors[0].snapshot_id.endswith(":test-corpus")
    assert json.loads((output / "summary.json").read_bytes())["source_hashes_unchanged"]
    with pytest.raises(FileExistsError):
        runner.validate(root, output)
    # A later source edit cannot silently hydrate the old corpus projection.
    path = root / "TST/2025/page_0001.json"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="json_import_manifest_changed"):
        load_json_corpus_document(root, output, "TST_2025")


def test_corpus_runner_rejects_output_inside_source(tmp_path):
    source(tmp_path)
    with pytest.raises(ValueError, match="source_output_overlap"):
        runner.validate(tmp_path, tmp_path / "output")
