"""PNG synthetic, không phải đánh giá OCR/tài chính; không cần dataset trong CI."""

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.document_processing import crop_audit, crop_recovery
from vietnamese_financial_multi_agent.document_processing.contracts import PathRootMapping
from vietnamese_financial_multi_agent.document_processing.crop_audit import (
    CropError,
    audit_page,
    reference_request,
    select_inventory_pages,
    summarize,
)
from vietnamese_financial_multi_agent.document_processing.crop_recovery import (
    recover_crop,
    select_pilot,
)

from .test_path_resolver import config as config
from .test_raw_ocr_contracts import element
from .test_raw_ocr_contracts import payload as payload


@pytest.fixture
def sample(config, payload):
    identity = ("SYNTHETIC", "2025", 1)
    image_ref = "/approved/raw/SYNTHETIC/2025/ảnh.png"
    payload["page"]["image"] = image_ref
    payload["elements"] = [element("table")]
    mappings = [
        PathRootMapping(
            mapping_id=category,
            source_root=root,
            path_style="posix",
            destination_root_key=key,
            category=category,
            containment_policy="lexical_then_runtime",
        )
        for category, root, key in (
            ("raw_page_image", "/approved/raw", "FINANCIAL_REPORT_DIR"),
            ("ocr_crop", "/synthetic-colab/crops", "FINANCIAL_OCR_DIR"),
            ("ocr_page_json", "/approved/json", "FINANCIAL_OCR_DIR"),
        )
    ]
    source = config.financial_ocr_dir / "page.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    image_path = config.financial_report_dir / "SYNTHETIC/2025/ảnh.png"
    image_path.parent.mkdir(parents=True)
    image = Image.new("RGB", (100, 100), (12, 34, 56))
    image.putpixel((2, 3), (200, 1, 2))
    image.save(image_path)
    request = reference_request(
        "/approved/json/page.json", "ocr_page_json", "synthetic-run", ["page"], mappings
    )
    return SimpleNamespace(
        config=config,
        payload=payload,
        request=request,
        mappings=mappings,
        source=source,
        image_path=image_path,
        identity=identity,
        image_bindings={image_ref: identity},
        root=config.project_root / "data/recovered_crops",
    )


def audit(sample, **kwargs):
    sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    options = dict(expected_identity=sample.identity, image_bindings=sample.image_bindings)
    options.update(kwargs)
    return audit_page(sample.request, sample.config, sample.mappings, **options)


def recover(sample, record, **kwargs):
    return recover_crop(
        record,
        sample.request,
        sample.config,
        sample.mappings,
        image_bindings=sample.image_bindings,
        **kwargs,
    )


def test_default_dry_run_no_writes(sample):
    records = audit(sample)
    before = {p: p.read_bytes() for p in (sample.source, sample.image_path)}
    result = recover(sample, records[0])
    assert result["status"] == "dry_run"
    assert not sample.root.exists()
    assert all(path.read_bytes() == value for path, value in before.items())


@pytest.mark.parametrize("mode", ["RGB", "L", "RGBA", "P"])
def test_crop_pixels_dimensions_hash_and_rerun(sample, mode):
    with Image.open(sample.image_path) as image:
        image.convert(mode).save(sample.image_path)
    record = audit(sample)[0]
    before = sample.image_path.read_bytes(), sample.source.read_bytes()
    result = recover(sample, record, dry_run=False)
    assert result["status"] == "recovered"
    output = sample.root / result["output_relative_path"]
    output_before = output.read_bytes(), output.stat().st_mtime_ns
    with Image.open(output) as actual, Image.open(sample.image_path) as source:
        assert actual.format == "PNG"
        assert actual.size == (29, 38)
        assert actual.mode == mode
        assert actual.tobytes() == source.crop(record.bbox).tobytes()
    assert hashlib.sha256(output.read_bytes()).hexdigest() == result["reconstructed_image_hash"]
    assert result["equivalent_to_original_crop"] == "unverified"
    assert recover(sample, record, dry_run=False)["status"] == "already_recovered"
    assert (output.read_bytes(), output.stat().st_mtime_ns) == output_before
    assert (sample.image_path.read_bytes(), sample.source.read_bytes()) == before
    assert len(list(sample.root.glob("*.png"))) == 1


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("existing", "existing"),
        ("missing", "missing"),
        ("unmapped", "unmapped"),
        ("ambiguous", "ambiguous"),
        ("unsafe", "unsafe"),
    ],
)
def test_mapping_status(sample, scenario, expected):
    if scenario == "existing":
        Image.new("RGB", (5, 5)).save(sample.config.financial_ocr_dir / "table.png")
    elif scenario == "unmapped":
        sample.mappings = [m for m in sample.mappings if m.category != "ocr_crop"]
    elif scenario == "ambiguous":
        sample.mappings.append(sample.mappings[1].model_copy(update={"mapping_id": "duplicate"}))
    elif scenario == "unsafe":
        sample.payload["elements"][0]["crop"] = "/synthetic-colab/crops/../escape.png"
    record = audit(sample)[0]
    assert record.mapping_status == expected
    assert recover(sample, record, dry_run=False)["status"] == (
        "recovered" if scenario == "missing" else "ineligible"
    )


@pytest.mark.parametrize("bbox", [[-1, 2, 30, 40], [1, 2, 101, 40], [1, 2, 1, 40], [30, 40, 1, 2]])
def test_invalid_geometry_no_clip(sample, bbox):
    sample.payload["elements"][0]["bbox"] = bbox
    record = audit(sample)[0]
    assert record.eligibility == "invalid_bbox"
    assert record.bbox == tuple(bbox)
    assert recover(sample, record, dry_run=False)["status"] == "ineligible"
    assert not sample.root.exists()


@pytest.mark.parametrize(
    "scenario,issue",
    [
        ("image_missing", "source_image_missing"),
        ("identity", "source_identity_mismatch"),
        ("binding", "source_identity_unverified"),
        ("dimensions", "coordinate_dimensions_mismatch"),
        ("oversize", "oversized_image"),
        ("corrupt", "image_decode_failed"),
    ],
)
def test_source_eligibility(sample, monkeypatch, scenario, issue):
    kwargs = {}
    if scenario == "image_missing":
        sample.image_path.unlink()
    elif scenario == "identity":
        kwargs["expected_identity"] = ("OTHER", "2025", 1)
    elif scenario == "binding":
        sample.image_bindings = {}
    elif scenario == "dimensions":
        sample.payload["page"]["width"] = 99
    elif scenario == "oversize":
        monkeypatch.setattr(crop_audit, "MAX_IMAGE_PIXELS", 100)
    else:
        sample.image_path.write_bytes(b"invalid synthetic PNG")
    record = audit(sample, **kwargs)[0]
    assert issue in record.issues
    assert record.eligibility != "eligible_candidate"


@pytest.mark.parametrize(
    "kind", ["signature", "seal", "seal_signature_region", "checkbox", "red_mark"]
)
def test_non_table_and_color_views_not_recovered(sample, kind):
    sample.payload["elements"] = [element(kind)]
    for field in crop_audit.CROP_FIELDS:
        if field in sample.payload["elements"][0]:
            sample.payload["elements"][0][field] = "/synthetic-colab/crops/" + field + ".png"
    records = audit(sample)
    for record in records:
        assert record.eligibility == (
            "requires_review" if record.field == "crop" else "unsupported_view"
        )
        assert recover(sample, record, dry_run=False)["status"] == "ineligible"
    assert not sample.root.exists()


def test_dedup_context_and_basename(sample):
    record = audit(sample)[0]
    other = replace(
        record, original_path="/different/table.png", deduplication_key="other", path_key="other"
    )
    summary = summarize([record, record, other])
    assert summary["references_audited"] == 3
    assert summary["missing_references"] == 3
    assert summary["unique_missing_paths"] == 2
    assert summary["eligible_candidates"] == 2
    assert len(select_pilot([record, record, other])) == 2
    first = audit(sample, run_identity="run-1")[0]
    second = audit(sample, run_identity="run-2")[0]
    assert first.deduplication_key != second.deduplication_key
    assert first.path_key != second.path_key


@pytest.mark.parametrize("change", ["image", "bbox", "missing_image", "mapping"])
def test_source_changes_between_audit_and_recovery(sample, change):
    record = audit(sample)[0]
    if change == "image":
        Image.new("RGB", (100, 100), (9, 8, 7)).save(sample.image_path)
    elif change == "bbox":
        sample.payload["elements"][0]["bbox"] = [2, 2, 30, 40]
        sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    elif change == "missing_image":
        sample.image_path.unlink()
    else:
        sample.mappings = []
    assert recover(sample, record, dry_run=False)["status"] == "source_changed"
    assert not sample.root.exists()


def test_source_change_during_second_read(sample, monkeypatch):
    record = audit(sample)[0]
    actual = crop_recovery.read_image

    def changed(*args):
        image, _ = actual(*args)
        return image, "changed"

    monkeypatch.setattr(crop_recovery, "read_image", changed)
    assert recover(sample, record, dry_run=False)["status"] == "source_changed"
    assert not sample.root.exists()


@pytest.mark.parametrize(
    "suffix",
    [
        "../escape",
        "data/raw",
        "data/processed",
        "Financial_Report",
        "data/recovered_crops/../escape",
    ],
)
def test_output_traversal_and_unapproved_root(sample, suffix):
    result = recover(
        sample, audit(sample)[0], output_root=sample.config.project_root / suffix, dry_run=False
    )
    assert result["status"] == "unapproved_output_root"
    assert not sample.root.exists()


def test_output_root_overlap(sample):
    sample.config = sample.config.model_copy(
        update={"financial_report_dir": sample.config.project_root / "data"}
    )
    with pytest.raises(CropError, match="overlapping_output_root"):
        crop_recovery.validate_output_root(sample.root, sample.config)


@pytest.mark.parametrize("junction", [False, True])
def test_output_link_escape(sample, junction):
    record = audit(sample)[0]
    sample.root.parent.mkdir()
    target = sample.config.project_root / "outside"
    target.mkdir()
    if junction:
        if os.name != "nt":
            pytest.skip("Native junction chỉ có trên Windows; symlink được test riêng")
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(sample.root), str(target)], capture_output=True
        )
        if completed.returncode:
            pytest.skip("Runner không hỗ trợ tạo native Windows junction")
    else:
        try:
            sample.root.symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("Runner không cấp quyền/hỗ trợ symlink")
    assert recover(sample, record, dry_run=False)["status"] == "unsafe_output_link"
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("change", ["png", "sidecar", "missing_sidecar"])
def test_conflict_never_overwrites(sample, change):
    record = audit(sample)[0]
    result = recover(sample, record, dry_run=False)
    output = sample.root / result["output_relative_path"]
    sidecar = output.with_suffix(".json")
    if change == "png":
        output.write_bytes(b"preexisting user content")
    elif change == "sidecar":
        sidecar.write_text("{}")
    else:
        sidecar.unlink()
    before = {p: p.read_bytes() for p in sample.root.iterdir()}
    assert recover(sample, record, dry_run=False)["status"] == "output_conflict"
    assert {p: p.read_bytes() for p in sample.root.iterdir()} == before


def test_exclusive_write_race(sample, monkeypatch):
    record = audit(sample)[0]
    original = Path.open

    def racing(path, mode="r", *args, **kwargs):
        if mode == "xb" and path.suffix == ".png":
            with original(path, "wb") as stream:
                stream.write(b"another writer")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing)
    result = recover(sample, record, dry_run=False)
    assert result["status"] == "output_conflict"
    assert (sample.root / result["output_relative_path"]).read_bytes() == b"another writer"


def test_output_validation_failure_no_false_success(sample, monkeypatch):
    def invalid(*args):
        raise CropError("output_validation_failed")

    monkeypatch.setattr(crop_recovery, "_validate_png", invalid)
    result = recover(sample, audit(sample)[0], dry_run=False)
    assert result["status"] == "output_validation_failed"
    assert not sample.root.exists()


def test_cap_across_reruns_and_deterministic_selection(sample):
    record = audit(sample)[0]
    records = [
        replace(record, deduplication_key=str(i), page_identity=(symbol, "2025", i))
        for i in range(20)
        for symbol in ("BBS", "BCC", "BED")
    ]
    # Keys cần identity context như audit thật.
    records = [replace(r, deduplication_key=f"{r.page_identity}") for r in records]
    selected = select_pilot(records)
    assert selected == select_pilot(list(reversed(records)))
    assert len(selected) == 12
    assert {r.page_identity[0] for r in selected} == {"BBS", "BCC", "BED"}
    sample.root.mkdir(parents=True)
    for index in range(12):
        (sample.root / f"{index}.png").write_bytes(b"preexisting")
    assert recover(sample, record, dry_run=False)["status"] == "pilot_cap_reached"
    assert len(list(sample.root.iterdir())) == 12


@pytest.mark.parametrize("cap", [0, 13, True, -1])
def test_invalid_cap(sample, cap):
    assert recover(sample, audit(sample)[0], cap=cap)["status"] == "invalid_pilot_cap"
    with pytest.raises(CropError, match="invalid_pilot_cap"):
        select_pilot([], cap=cap)


def test_inventory_selection_only_known_missing_pages():
    pages = [
        dict(
            source="a.json",
            references={"crop:colab_suffix_missing": 2},
            symbol="S",
            year="2025",
            page=1,
        ),
        dict(source="b.json", references={}, symbol="S", year="2025", page=2),
    ]
    warnings = [dict(source="a.json", code="crop_reference_colab_suffix_missing", count=2)]
    assert select_inventory_pages(pages, warnings) == pages[:1]
    with pytest.raises(CropError, match="inventory_warning_mismatch"):
        select_inventory_pages(pages, [])
    with pytest.raises(CropError, match="duplicate_inventory_page"):
        select_inventory_pages(pages + pages[:1], warnings)
    with pytest.raises(CropError, match="inventory_coverage_mismatch"):
        select_inventory_pages([], [])


def test_actual_twelve_file_cap_and_rerun(sample):
    sample.payload["elements"] = []
    for index in range(13):
        table = element("table")
        table.update(id=f"table-{index}", crop=f"/synthetic-colab/crops/{index}.png")
        sample.payload["elements"].append(table)
    records = audit(sample)
    results = [recover(sample, record, dry_run=False) for record in records]
    assert [r["status"] for r in results] == ["recovered"] * 12 + ["pilot_cap_reached"]
    before = {p: p.read_bytes() for p in sample.root.iterdir()}
    assert recover(sample, records[0], dry_run=False)["status"] == "already_recovered"
    assert recover(sample, records[12], dry_run=False)["status"] == "pilot_cap_reached"
    assert {p: p.read_bytes() for p in sample.root.iterdir()} == before


def test_image_byte_limit(sample, monkeypatch):
    monkeypatch.setattr(crop_audit, "MAX_IMAGE_BYTES", 1)
    record = audit(sample)[0]
    assert "oversized_file" in record.issues
    assert record.eligibility == "requires_review"


@pytest.mark.parametrize("bbox", [[1, 2, 30], [1.5, 2, 30, 40], [True, 2, 30, 40]])
def test_bbox_requires_four_strict_integers(sample, bbox):
    from vietnamese_financial_multi_agent.document_processing.ocr_loader import OCRLoadError

    sample.payload["elements"][0]["bbox"] = bbox
    with pytest.raises(OCRLoadError, match="structural_failure"):
        audit(sample)
    assert not sample.root.exists()


def test_unsafe_source_link_metadata(sample, monkeypatch):
    import stat

    record = audit(sample)[0]
    original = Path.lstat

    def linked(path, *args, **kwargs):
        actual = original(path, *args, **kwargs)
        if path == sample.image_path:
            return SimpleNamespace(
                st_mode=actual.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
            )
        return actual

    monkeypatch.setattr(Path, "lstat", linked)
    assert recover(sample, record, dry_run=False)["status"] == "source_changed"
    assert not sample.root.exists()


def test_output_validation_after_write_leaves_no_success(sample, monkeypatch):
    original = crop_recovery._validate_png
    calls = 0

    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise CropError("output_validation_failed")
        return original(*args)

    monkeypatch.setattr(crop_recovery, "_validate_png", fail_second)
    record = audit(sample)[0]
    result = recover(sample, record, dry_run=False)
    assert result["status"] == "output_validation_failed"
    assert not list(sample.root.glob("*.json"))
    # Output lỗi giữ lại để review, không tự xóa hoặc ghi đè khi retry.
    assert recover(sample, record, dry_run=False)["status"] == "output_conflict"


def test_source_change_after_output_not_reported_as_success(sample, monkeypatch):
    actual = crop_recovery.read_image
    calls = 0

    def final_changed(*args):
        nonlocal calls
        calls += 1
        image, hashed = actual(*args)
        return image, hashed if calls == 1 else "changed"

    monkeypatch.setattr(crop_recovery, "read_image", final_changed)
    result = recover(sample, audit(sample)[0], dry_run=False)
    assert result["status"] == "source_changed"
