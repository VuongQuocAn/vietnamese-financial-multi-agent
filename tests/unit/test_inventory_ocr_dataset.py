"""Fixtures tổng hợp chỉ kiểm tra script, không phải dữ liệu nghiên cứu."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "inventory_ocr_dataset",
    Path(__file__).resolve().parents[2] / "scripts/inventory_ocr_dataset.py",
)
inventory_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory_module)


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "data"
    raw = root / "raw/Financial_Report/TEST/2021"
    processed = root / "processed/Financial_Report_OCR/TEST/2021/ocr_json"
    raw.mkdir(parents=True)
    processed.mkdir(parents=True)
    # Không giải mã ảnh trong inventory: fixture cố ý chỉ là bytes kiểm tra đường dẫn.
    (raw / "page_1.png").write_bytes(b"synthetic-path-fixture")
    document = {
        "page": {
            "symbol": "TEST",
            "year": "2021",
            "page": 1,
            "image": "/content/drive/Financial_Report/TEST/2021/page_1.png",
        },
        "elements": [{"id": "e1", "type": "text", "bbox": [0, 0, 10, 10], "text": "fixture"}],
        "provenance": {"architecture": "synthetic-fixture"},
    }
    return root, processed / "page_1.json", document, tmp_path / "out"


def run(corpus):
    root, path, document, output = corpus
    path.write_text(json.dumps(document), encoding="utf-8")
    return inventory_module.inventory(root, output)


def test_valid_deterministic_read_only(corpus):
    result = run(corpus)
    root, _, _, output = corpus
    before = inventory_module.snapshot(root)
    contents = {p.name: p.read_bytes() for p in output.iterdir()}
    assert result["parsed_page_json"] == 1
    assert result["references"]["page_image:colab_suffix_exists"] == 1
    assert inventory_module.inventory(root, output) == result
    assert inventory_module.snapshot(root) == before
    assert contents == {p.name: p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize("content", ["{broken", "[]", "null", "\ufffd"])
def test_broken_json(corpus, content):
    root, path, _, output = corpus
    path.write_text(content, encoding="utf-8")
    result = inventory_module.inventory(root, output)
    assert result["roles"]["page_json"] == 1
    assert result["parsed_page_json"] == 0
    assert result["warning_counts"]


def test_missing_elements(corpus):
    del corpus[2]["elements"]
    assert run(corpus)["warning_counts"]["missing_or_invalid_elements"] == 1


def test_unknown_type_and_nested_null(corpus):
    corpus[2]["elements"] = [
        {"type": "future_type", "bbox": [0, 0, 5, 5], "details": {"confidence": None}},
        {"type": "future_type", "bbox": [0, 0, 5, 5], "details": {}},
    ]
    result = run(corpus)
    assert result["taxonomy"]["future_type"] == {"count": 2, "pages": 1}
    schema = json.loads((corpus[3] / "element_schema_summary.json").read_text())
    field = schema["element:future_type"]["$.details.confidence"]
    assert field["types"] == {"null": 1}
    assert field["missing"] == 1


def test_empty_table(corpus):
    corpus[2]["elements"] = [{"type": "table", "cells": []}]
    result = run(corpus)
    assert result["table_count"] == 1
    assert result["warning_counts"]["table_without_cells"] == 1


def test_cells_missing_bbox_and_duplicate_positions(corpus):
    corpus[2]["elements"] = [
        {
            "type": "table",
            "cells": [
                {"row": 0, "col": 0, "text": "fixture", "lines": [{"text": "fixture"}]},
                {"row": 0, "col": 0, "text": "fixture", "bbox": [3, 3, 2, 2]},
            ],
        }
    ]
    result = run(corpus)
    assert result["cell_count"] == 2
    assert result["warning_counts"]["cell_bbox_missing_or_invalid"] == 2
    assert result["warning_counts"]["duplicate_row_col"] == 1


def test_auxiliary_and_unsupported_extension(corpus):
    _, path, _, _ = corpus
    (path.parent / "extra.xyz").write_bytes(b"fixture")
    (path.parent.parent / "state.json").write_text('{"ok":true}')
    (path.parent.parent / "log.jsonl").write_text("{}\n{bad\n")
    result = run(corpus)
    assert result["roles"]["other"] == 1
    assert result["roles"]["aux_json"] == 1
    assert result["roles"]["aux_jsonl"] == 1
    assert result["warning_counts"]["jsonl_invalid_line"] == 1


def test_missing_input(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        inventory_module.inventory(tmp_path / "absent", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_cli_missing_input(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        inventory_module.main(["--dataset-root", str(tmp_path / "missing"), "--summary"])
    assert error.value.code == 1
    assert "Dataset root does not exist" in capsys.readouterr().err


def test_hard_link_output_cannot_overwrite_source(corpus):
    root, path, document, output = corpus
    path.write_text(json.dumps(document))
    output.mkdir()
    os.link(path, output / "inventory_summary.json")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="Hard-linked"):
        inventory_module.inventory(root, output)
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "destination", ["raw", "processed", "processed/Financial_Report_OCR/TEST/2021"]
)
def test_cannot_write_source(corpus, destination):
    root, path, document, _ = corpus
    path.write_text(json.dumps(document))
    before = inventory_module.snapshot(root)
    with pytest.raises(ValueError, match="outside"):
        inventory_module.inventory(root, root / destination)
    assert inventory_module.snapshot(root) == before


@pytest.mark.parametrize(
    "value,expected",
    [
        ("page_1.png", "ambiguous"),
        ("Financial_Report/WRONG/2021/page_1.png", "ambiguous"),
        ("Financial_Report/TEST/2021/../page_1.png", "ambiguous"),
        ("Financial_Report/TEST/2021/absent.png", "unmapped"),
        (None, "missing"),
    ],
)
def test_reference_no_basename_matching(corpus, value, expected):
    assert inventory_module.reference_status(value, corpus[0], "TEST", "2021") == expected


def test_sampling_coverage_and_subset():
    pages = []
    for symbol in ("AAA", "BBB", "CCC"):
        for year in range(2021, 2026):
            for number in (1, 2):
                pages.append(
                    {
                        "symbol": symbol,
                        "year": str(year),
                        "page": number,
                        "source": f"{symbol}/{year}/{number}",
                        "element_types": {"text": 5},
                        "form_candidates": ["B01"] if number == 2 else [],
                        "implicit_table_candidate": False,
                        "text_count": 5,
                        "tables": [],
                        "warnings": {},
                    }
                )
    selected, pilot = inventory_module.select_samples(pages)
    assert len(selected) == 24 and len(pilot) == 6
    assert len({(p["symbol"], p["year"]) for p in selected}) == 15
    assert {p["source"] for p in pilot} <= {p["source"] for p in selected}
    assert all(p["page"] == 2 for p in selected[:15])
    assert inventory_module.select_samples(list(reversed(pages))) == (selected, pilot)


def test_implicit_table_is_candidate_only(corpus):
    corpus[2]["elements"] = [
        {
            "type": "text",
            "text": "2021 fixture",
            "bbox": [col * 100, row * 50, col * 100 + 50, row * 50 + 20],
        }
        for row in range(5)
        for col in range(3)
    ]
    assert run(corpus)["implicit_table_candidates"] == 1
    page = json.loads((corpus[3] / "page_manifest.jsonl").read_text())
    assert page["form_status"] == "unverified"
