"""Synthetic local mapping controls; never represented as real corpus results."""

import json
from copy import deepcopy

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.document_processing.contracts.path_mapping import (
    PathRootMapping,
)
from vietnamese_financial_multi_agent.document_processing.crop_audit import (
    CropError,
    audit_page,
    summarize,
)
from vietnamese_financial_multi_agent.document_processing.local_crop_mapping import (
    candidate_mapping,
    page_request,
    save_private_bindings,
    verify_local_mappings,
)

from .test_path_resolver import config as config
from .test_raw_ocr_contracts import element
from .test_raw_ocr_contracts import payload as payload


@pytest.fixture
def local(config, payload):
    row = dict(
        symbol="SYNTHETIC",
        year="2025",
        page=1,
        source="processed/Financial_Report_OCR/SYNTHETIC/2025/ocr_json/page_1.json",
    )
    payload["page"]["image"] = "/fixture/Financial_Report/SYNTHETIC/2025/page_1.png"
    payload["elements"] = [element("table"), element("table")]
    for i, table in enumerate(payload["elements"]):
        table["id"] = f"table-{i}"
        table["crop"] = (
            f"/fixture/Financial_Report_OCR/SYNTHETIC/2025/ocr_crops/page_1/tables/{i}.png"
        )
    raw = config.financial_report_dir / "SYNTHETIC/2025/page_1.png"
    raw.parent.mkdir(parents=True)
    Image.new("RGB", (100, 100), (12, 23, 45)).save(raw)
    crop = config.financial_ocr_dir / "SYNTHETIC/2025/ocr_crops/page_1/tables/0.png"
    crop.parent.mkdir(parents=True)
    Image.new("RGB", (10, 10)).save(crop)
    source = config.financial_ocr_dir / "SYNTHETIC/2025/ocr_json/page_1.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(payload), encoding="utf-8")
    return config, row, payload, source, raw


def verify(local):
    config, row, payload, source, _ = local
    source.write_text(json.dumps(payload), encoding="utf-8")
    return verify_local_mappings([row], config)


@pytest.mark.parametrize("prefix", ["/content/fixture", "drive/fixture", "fixture"])
@pytest.mark.parametrize(
    "category,marker,key",
    [
        ("raw_page_image", "Financial_Report", "FINANCIAL_REPORT_DIR"),
        ("ocr_crop", "Financial_Report_OCR", "FINANCIAL_OCR_DIR"),
    ],
)
def test_full_exact_root(prefix, category, marker, key):
    root = prefix + "/" + marker
    result = candidate_mapping(root + "/SYNTHETIC/2025/page_1.png", category)
    assert result.source_root == root
    assert result.destination_root_key == key


@pytest.mark.parametrize(
    "original",
    [
        "/fixture/Foreign/S/2025/page.png",
        "/fixture/Financial_Report_OCR/S/2025/page.png",
        "/Financial_Report/x/Financial_Report/S/2025/page.png",
        "/Financial_Report/Financial_Report_OCR/S/2025/page.png",
        "/fixture/Financial_Report/../S/page.png",
        "//fixture/Financial_Report/S/page.png",
        "/fixture/Financial_Report/C:/page.png",
        "/fixture/Financial_Report/S\\page.png",
        "/fixture/Financial_Report/S/%2e/page.png",
    ],
)
def test_unknown_ambiguous_and_unsafe_roots(original):
    with pytest.raises(CropError):
        candidate_mapping(original, "raw_page_image")


def test_positive_negative_controls_and_audit(local, tmp_path):
    result = verify(local)
    assert result["statistics"]["mappings_verified"] == 2
    assert result["statistics"]["positive_controls"] == 2
    assert result["statistics"]["negative_controls"] == 4
    assert result["statistics"]["image_bindings_verified"] == 1
    assert not result["original_drive_identity_verified"]
    assert result["run_identity"] is None
    config, row, _, source, raw = local
    before = source.read_bytes(), raw.read_bytes()
    records = audit_page(
        page_request(row),
        config,
        [PathRootMapping.model_validate(m) for m in result["mappings"]],
        expected_identity=("SYNTHETIC", "2025", 1),
        image_bindings=result["image_bindings"],
    )
    assert [r.mapping_status for r in records] == ["existing", "missing"]
    assert records[1].eligibility == "eligible_candidate"
    assert records[1].verified_local_mapping_id
    summary = summarize(records + [records[1]])
    assert summary["missing_references"] == 2
    assert summary["unique_missing_paths"] == 1
    assert summary["contextual_missing_paths"] == 1
    assert before == (source.read_bytes(), raw.read_bytes())
    path = tmp_path / "ignored/bindings.json"
    assert save_private_bindings(path, result) == "created"
    metadata = path.stat().st_mtime_ns
    assert save_private_bindings(path, verify(local)) == "unchanged"
    assert path.stat().st_mtime_ns == metadata
    changed = deepcopy(result)
    changed["run_identity"] = "different"
    with pytest.raises(CropError, match="local_bindings_conflict"):
        save_private_bindings(path, changed)


@pytest.mark.parametrize("field,value", [("symbol", "OTHER"), ("year", "2024"), ("page", 2)])
def test_wrong_ocr_identity(local, field, value):
    local[2]["page"][field] = value
    result = verify(local)
    assert result["image_bindings"] == {}
    assert result["statistics"]["discovery_failures"] == 1


@pytest.mark.parametrize(
    "replacement",
    ["OTHER/2025/page_1.png", "SYNTHETIC/2024/page_1.png", "SYNTHETIC/2025/page_2.png"],
)
def test_same_basename_wrong_context_no_fallback(local, replacement):
    config = local[0]
    other = config.financial_report_dir / replacement
    other.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (100, 100)).save(other)
    local[2]["page"]["image"] = "/fixture/Financial_Report/" + replacement
    result = verify(local)
    assert result["image_bindings"] == {}
    assert result["statistics"]["mappings_rejected"] == 1


def test_wrong_dimensions(local):
    local[2]["page"]["width"] = 99
    result = verify(local)
    assert result["image_bindings"] == {}
    assert result["statistics"]["image_failure_counts"] == {"coordinate_dimensions_mismatch": 1}


def test_wrong_crop_context_keeps_missing_unmapped(local):
    local[2]["elements"][1]["crop"] = (
        "/fixture/Financial_Report_OCR/OTHER/2024/ocr_crops/page_2/tables/1.png"
    )
    result = verify(local)
    assert result["statistics"]["mappings_rejected"] == 1
    records = audit_page(
        page_request(local[1]),
        local[0],
        [PathRootMapping.model_validate(m) for m in result["mappings"]],
        expected_identity=("SYNTHETIC", "2025", 1),
        image_bindings=result["image_bindings"],
    )
    assert all(r.mapping_status == "unmapped" for r in records)
    assert all(r.eligibility == "requires_review" for r in records)


def test_missing_source_image(local):
    local[4].unlink()
    result = verify(local)
    assert result["image_bindings"] == {}
    assert result["statistics"]["mappings_rejected"] == 1


def test_multiple_prefixes_same_target_rejected(local):
    row = dict(
        local[1],
        page=2,
        source="processed/Financial_Report_OCR/SYNTHETIC/2025/ocr_json/page_2.json",
    )
    second = deepcopy(local[2])
    second["page"]["page"] = 2
    second["page"]["image"] = "/other/Financial_Report/SYNTHETIC/2025/page_1.png"
    source = local[3].with_name("page_2.json")
    source.write_text(json.dumps(second), encoding="utf-8")
    result = verify_local_mappings([local[1], row], local[0])
    assert result["statistics"]["ambiguous_prefixes"] == 2
    assert not result["image_bindings"]
