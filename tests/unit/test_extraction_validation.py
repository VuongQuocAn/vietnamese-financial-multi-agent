"""Synthetic engineering checks only; no real OCR/financial quality labels."""

import copy
import hashlib
import json

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.document_processing import extraction_validation as ev
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError, digest
from vietnamese_financial_multi_agent.document_processing.extraction_artifacts import (
    read_local_evidence,
)

from .test_crop_recovery import audit, recover
from .test_crop_recovery import sample as sample
from .test_path_resolver import config as config
from .test_raw_ocr_contracts import payload as payload


def validate(sample, **kwargs):
    options = dict(expected_identity=sample.identity, image_bindings=sample.image_bindings)
    options.update(kwargs)
    return ev.validate_extraction(sample.request, sample.config, sample.mappings, **options)


def recovered(sample):
    record = audit(sample)[0]
    entry = recover(sample, record, dry_run=False)
    entry.update(
        element_id=record.element_id,
        element_type=record.element_type,
        crop_field=record.field,
        availability="reconstructed_available",
        validation_status="validated",
    )
    return json.loads(json.dumps(entry))


def ledger(entry):
    return dict(
        plan_id="a" * 64,
        issue_count=1,
        issues=[
            dict(
                recovery_id=entry["recovery_id"],
                png_sha256=entry["reconstructed_image_hash"],
                page_identity=entry["page_identity"],
                element_id=entry["element_id"],
                original_bbox=entry["bbox"],
                issue_code="source_bbox_incomplete_table",
                status="requires_review",
                follow_up_task="M1-04a",
                bbox_modified=False,
                complete_table=False,
                reported_by="synthetic-reviewer",
                evidence_basis="synthetic",
                review_sheet_number=1,
            )
        ],
    )


def codes(report):
    return {i.code for i in report.issues}


def snapshots(sample):
    return {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for root in [
            sample.config.financial_ocr_dir,
            sample.config.financial_report_dir,
            sample.root,
        ]
        if root.exists()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_recovered_deterministic_readonly_provenance(sample):
    entry = recovered(sample)
    inputs = copy.deepcopy(entry)
    before = snapshots(sample)
    a = validate(sample, recovery_entries=[entry])
    b = validate(sample, recovery_entries=[entry])
    assert a == b
    assert a.crops[0].availability == "reconstructed_available"
    assert a.crops[0].original_equivalence == "unverified"
    assert a.crops[0].mapping_status == "missing"
    assert a.structural_status == "valid" and a.image_status == "checked"
    assert a.source_binding_status == "caller_bound_run_unverified"
    assert a.ledger_status == "not_verified"
    assert "bbox_ledger_not_verified" in codes(a)
    assert before == snapshots(sample) and entry == inputs
    assert sample.payload["page"]["image"] not in json.dumps(a.export())
    assert str(sample.config.project_root) not in json.dumps(a.export())
    assert sample.payload["elements"][0]["crop"] not in json.dumps(a.export())


def test_original_available_no_recovery(sample):
    Image.new("RGB", (4, 5)).save(sample.config.financial_ocr_dir / "table.png")
    report = validate(sample, recovery_entries=[])
    assert report.crops[0].availability == "existing_original"
    assert report.crops[0].recovery_id is None
    assert not sample.root.exists()


def test_corrupt_original_no_fallback(sample):
    entry = recovered(sample)
    (sample.config.financial_ocr_dir / "table.png").write_bytes(b"broken")
    report = validate(sample, recovery_entries=[entry])
    assert report.crops[0].availability == "missing_unrecovered"
    assert "image_decode_failed" in codes(report)


@pytest.mark.parametrize("entries", [None, []])
def test_missing_alternative(sample, entries):
    report = validate(sample, recovery_entries=entries)
    assert report.crops[0].availability == "missing_unrecovered"
    assert codes(report) & {"recovery_entry_missing", "recovery_not_verified"}
    assert not sample.root.exists()


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "duplicate_context",
        "missing_field",
        "id",
        "source",
        "bbox",
        "image_hash",
        "element",
        "path",
        "status",
        "dimensions",
        "identity",
        "method",
        "extra",
        "issues",
    ],
)
def test_untrusted_index_fails_closed(sample, change):
    entry = recovered(sample)
    entries = [entry]
    if change == "duplicate":
        entries.append(copy.deepcopy(entry))
    elif change == "duplicate_context":
        entries.append(dict(entry, recovery_id="b" * 64))
    elif change == "missing_field":
        del entry["source_image_hash"]
    else:
        key, value = {
            "id": ("recovery_id", "b" * 64),
            "source": ("ocr_source", "other-source"),
            "bbox": ("bbox", [1, 1, 2, 2]),
            "image_hash": ("source_image_hash", "b" * 64),
            "element": ("element_id", "other-table"),
            "path": ("output_relative_path", "../outside.png"),
            "status": ("validation_status", "pending"),
            "dimensions": ("width", 88),
            "identity": ("page_identity", ["OTHER", "2025", 1]),
            "method": ("method_version", "2"),
            "extra": ("private_extra", "secret"),
            "issues": ("issues", []),
        }[change]
        entry[key] = value
    report = validate(sample, recovery_entries=entries)
    assert report.crops[0].availability == "missing_unrecovered"
    assert report.crops[0].recovery_id is None


@pytest.mark.parametrize(
    "fault",
    [
        "sidecar_missing",
        "sidecar_wrong",
        "sidecar_duplicate",
        "output_missing",
        "output_corrupt",
        "pixels",
    ],
)
def test_artifact_integrity(sample, fault):
    entry = recovered(sample)
    output = sample.root / entry["output_relative_path"]
    sidecar = sample.root / (entry["recovery_id"] + ".json")
    if fault == "sidecar_missing":
        sidecar.unlink()
    elif fault == "sidecar_wrong":
        sidecar.write_text("{}", encoding="utf-8")
    elif fault == "sidecar_duplicate":
        sidecar.write_text('{"recovery_id":1,"recovery_id":2}', encoding="utf-8")
    elif fault == "output_missing":
        output.unlink()
    elif fault == "output_corrupt":
        output.write_bytes(b"broken")
    else:
        Image.new("RGB", (entry["width"], entry["height"])).save(output)
        entry["reconstructed_image_hash"] = hashlib.sha256(output.read_bytes()).hexdigest()
        saved = json.loads(sidecar.read_text())
        saved["reconstructed_image_hash"] = entry["reconstructed_image_hash"]
        sidecar.write_text(json.dumps(saved))
    before = snapshots(sample)
    report = validate(sample, recovery_entries=[entry])
    assert report.crops[0].availability == "missing_unrecovered"
    assert snapshots(sample) == before


def test_recovered_header_rejected_before_pixel_decode(sample, monkeypatch):
    from vietnamese_financial_multi_agent.document_processing import extraction_artifacts as ea

    entry = recovered(sample)
    output = sample.root / entry["output_relative_path"]
    Image.new("RGB", (100, 100)).save(output)
    entry["reconstructed_image_hash"] = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = sample.root / (entry["recovery_id"] + ".json")
    saved = json.loads(sidecar.read_text())
    saved["reconstructed_image_hash"] = entry["reconstructed_image_hash"]
    sidecar.write_text(json.dumps(saved))

    def forbidden(*args):
        pytest.fail("Untrusted wrong dimensions reached pixel decoder")

    monkeypatch.setattr(ea, "_validate_png", forbidden)
    report = validate(sample, recovery_entries=[entry])
    assert report.crops[0].availability == "missing_unrecovered"
    assert "invalid_recovered_image" in codes(report)


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("dimension", "coordinate_dimensions_mismatch"),
        ("bbox", "invalid_bbox_geometry"),
        ("bounds", "bbox_outside_image"),
        ("missing", "source_image_missing"),
        ("corrupt", "image_decode_failed"),
        ("jpeg", "image_decode_failed"),
        ("unsafe", "source_image_unsafe"),
        ("hash", "source_image_changed"),
        ("binding", "image_binding_not_verified"),
        ("identity", "source_identity_mismatch"),
    ],
)
def test_json_image_checks(sample, scenario, code):
    options = {}
    if scenario == "dimension":
        sample.payload["page"]["width"] = 90
    elif scenario == "bbox":
        sample.payload["elements"][0]["bbox"] = [5, 2, 1, 40]
    elif scenario == "bounds":
        sample.payload["elements"][0]["bbox"] = [1, 2, 101, 40]
    elif scenario == "missing":
        sample.image_path.unlink()
    elif scenario == "corrupt":
        sample.image_path.write_bytes(b"broken")
    elif scenario == "jpeg":
        Image.new("RGB", (100, 100)).save(sample.image_path, format="JPEG")
    elif scenario == "unsafe":
        sample.payload["page"]["image"] = "/approved/raw/../outside.png"
    elif scenario == "hash":
        options["expected_image_hash"] = "a" * 64
    elif scenario == "binding":
        options["image_bindings"] = {}
    elif scenario == "identity":
        options["expected_identity"] = ("OTHER", "2025", 1)
    sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    report = validate(sample, **options)
    assert code in codes(report)
    assert report.structural_status == "valid"
    assert not sample.root.exists()


def test_all_bbox_levels_actual_image_bounds(sample):
    sample.payload["page"]["width"] = 200
    sample.payload["elements"][0]["cells"][0]["lines"][0]["bbox"] = [1, 2, 150, 40]
    sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    report = validate(sample)
    assert any(i.code == "bbox_outside_image" and "lines" in i.path for i in report.issues)


def test_duplicate_source_identity_ambiguous(sample):
    entry = recovered(sample)
    sample.payload["elements"].append(copy.deepcopy(sample.payload["elements"][0]))
    sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    report = validate(sample, recovery_entries=[entry])
    assert "duplicate_id" in codes(report) and "ambiguous_source_binding" in codes(report)
    assert all(c.availability == "missing_unrecovered" for c in report.crops)


def test_structural_failure_isolated(sample):
    sample.payload["elements"][0]["bbox"] = [1, 2]
    sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    report = validate(sample)
    assert report.structural_status == "invalid"
    assert report.crops == () and "bbox_ledger_not_verified" in codes(report)
    assert any(i.category == "structural" and i.path[-1] == "bbox" for i in report.issues)


def test_payload_composition_no_mutation(sample):
    before = copy.deepcopy(sample.payload)
    first = ev.validate_extraction_payload(sample.payload, source_context="synthetic")
    assert first == ev.validate_extraction_payload(sample.payload, source_context="synthetic")
    assert before == sample.payload
    assert first.image_status == first.source_binding_status == "not_verified"


def understanding(sample):
    identity = {k: sample.payload["page"][k] for k in ("symbol", "year", "page", "image")}
    return dict(
        contract_version="document_understanding_v1",
        raw_page=identity,
        classification=dict(label=None, status="unresolved", anchors=[]),
        text_regions=[],
        tables=[],
        issues=[],
    )


def test_understanding_binding_explicit(sample):
    result = understanding(sample)
    result["raw_page"]["symbol"] = "OTHER"
    unverified = validate(sample, understanding=result)
    checked = validate(sample, understanding=result, raw_binding_verified=True)
    assert "raw_binding_not_verified" in codes(unverified)
    assert "raw_page_mismatch" not in codes(unverified)
    assert "raw_page_mismatch" in codes(checked)
    assert all(i.category != "structural" for i in checked.issues)


def test_understanding_invalid_and_sensitive_fields(sample):
    result = understanding(sample)
    result["/private/secret.txt"] = "private OCR"
    report = validate(sample, understanding=result)
    assert report.structural_status == "invalid"
    assert "private" not in json.dumps(report.export())
    assert any("[field]" in i.path for i in report.issues)
    assert report.crops  # DU failure does not stop independent artifact validation.


def test_human_issue_preserved(sample):
    entry = recovered(sample)
    review = ledger(entry)
    before = copy.deepcopy(review)
    report = validate(sample, recovery_entries=[entry], bbox_ledger=review, ledger_plan_id="a" * 64)
    assert report.ledger_status == "consistent"
    human = [i for i in report.issues if i.origin == "human_review"]
    assert len(human) == 1 and human[0].code == "source_bbox_incomplete_table"
    assert human[0].status == "requires_review"
    assert review == before and report.crops[0].availability == "reconstructed_available"
    # Even if pixels become unavailable, the recorded human issue is not closed.
    (sample.root / entry["output_relative_path"]).unlink()
    assert "source_bbox_incomplete_table" in codes(
        validate(sample, recovery_entries=[entry], bbox_ledger=review, ledger_plan_id="a" * 64)
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("png_sha256", "b" * 64),
        ("complete_table", True),
        ("original_bbox", [1, 2, 3, 4]),
        ("recovery_id", "b" * 64),
    ],
)
def test_inconsistent_human_ledger(sample, key, value):
    entry = recovered(sample)
    review = ledger(entry)
    review["issues"][0][key] = value
    report = validate(sample, recovery_entries=[entry], bbox_ledger=review, ledger_plan_id="a" * 64)
    assert report.ledger_status == "not_verified"
    assert "bbox_ledger_inconsistent" in codes(report)
    assert any(
        i.code == "source_bbox_incomplete_table" and i.status == "not_verified"
        for i in report.issues
    )


def test_reported_understanding_issues_keep_locations_and_sources(sample):
    result = understanding(sample)
    item = dict(code="missing_provenance", path=["tables", 0], message="private OCR text")
    result["issues"] = [item, dict(item, message="another private note")]
    result["tables"] = [
        dict(
            id="t",
            origin="inferred_from_text",
            anchors=[],
            cells=[],
            status="unresolved",
            issues=[item],
        )
    ]
    before = copy.deepcopy(result)
    report = validate(sample, understanding=result)
    assert len([i for i in report.issues if i.origin == "understanding_reported"]) == 3
    assert (
        len(
            [
                i
                for i in report.issues
                if i.origin == "document_understanding_v1" and i.code == "missing_provenance"
            ]
        )
        == 1
    )
    assert result == before
    assert "private" not in json.dumps(report.export())


@pytest.mark.parametrize("scenario", ["ambiguous_image", "ambiguous_crop", "unsafe_crop", "run"])
def test_binding_boundaries_no_alternatives(sample, scenario):
    entry = recovered(sample)
    kwargs = {}
    if scenario.startswith("ambiguous"):
        category = "raw_page_image" if scenario.endswith("image") else "ocr_crop"
        rule = next(m for m in sample.mappings if m.category == category)
        sample.mappings.append(rule.model_copy(update={"mapping_id": "duplicate"}))
    elif scenario == "unsafe_crop":
        sample.payload["elements"][0]["crop"] = "/synthetic-colab/crops/../table.png"
        sample.source.write_text(json.dumps(sample.payload))
    else:
        kwargs["run_identity"] = "different-synthetic-run"
    report = validate(sample, recovery_entries=[entry], **kwargs)
    assert report.crops[0].availability == "missing_unrecovered"


def test_missing_source_is_not_structural_failure(sample):
    sample.source.unlink()
    report = validate(sample)
    assert report.structural_status == "not_verified"
    assert report.crops == ()
    assert "path_failure" in codes(report)


def test_source_changes_during_validation(sample, monkeypatch):
    entry = recovered(sample)
    original = ev.read_image
    count = 0

    def changing(request, config):
        nonlocal count
        count += 1
        if count == 2:
            Image.new("RGB", (100, 100), (22, 33, 44)).save(sample.image_path)
        return original(request, config)

    monkeypatch.setattr(ev, "read_image", changing)
    report = validate(sample, recovery_entries=[entry])
    assert "source_changed" in codes(report)
    assert report.crops[0].availability == "missing_unrecovered"


def test_audit_source_change_isolated(sample, monkeypatch):
    original = ev.audit_page

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        sample.payload["page"]["dpi"] = 201
        sample.source.write_text(json.dumps(sample.payload))
        return result

    monkeypatch.setattr(ev, "audit_page", changed)
    report = validate(sample)
    assert "source_changed" in codes(report)
    assert report.crops[0].availability == "missing_unrecovered"


@pytest.mark.parametrize("target", ["image", "recovered", "sidecar"])
def test_symlink_targets_fail_closed(sample, target):
    entry = recovered(sample)
    path = {
        "image": sample.image_path,
        "recovered": sample.root / entry["output_relative_path"],
        "sidecar": sample.root / (entry["recovery_id"] + ".json"),
    }[target]
    actual = path.with_name("actual-" + path.name)
    actual.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(actual)
    except OSError:
        pytest.skip("Symlink creation privilege unavailable")
    report = validate(sample, recovery_entries=[entry])
    assert report.crops[0].availability == "missing_unrecovered"


def test_evidence_reader_only_approved_ignored_artifacts(sample):
    path = sample.config.project_root / "artifacts/test-index.jsonl"
    path.parent.mkdir()
    path.write_bytes(b'{"a":1}\n{"a":2}\n')
    assert read_local_evidence(path, sample.config, jsonl=True) == [{"a": 1}, {"a": 2}]
    with pytest.raises(CropError, match="unapproved_evidence_path"):
        read_local_evidence(sample.source, sample.config)
    path.write_bytes(b'{"a":1,"a":2}')
    with pytest.raises(CropError, match="invalid_evidence_json"):
        read_local_evidence(path, sample.config)


def test_issue_dedup_preserves_distinct_origins():
    report = ev.ExtractionReport(
        "token", "valid", "not_verified", "not_verified", "not_verified", ()
    )
    a = ev.ExtractionIssue("same_code", "quality", "validator", "token", ("bbox",))
    b = ev.ExtractionIssue("same_code", "quality", "human_review", "token", ("bbox",))
    c = ev.ExtractionIssue("same_code", "quality", "validator", "token", ("page", "bbox"))
    assert len(ev._finish(report, [a, a, b, c]).issues) == 3
    assert digest(report.export())
