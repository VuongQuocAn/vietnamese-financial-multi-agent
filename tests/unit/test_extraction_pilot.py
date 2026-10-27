"""Synthetic bounded-pilot tests; no financial datasets or real provenance."""

import copy
import json
import subprocess
from pathlib import Path

import pytest
from vietnamese_financial_multi_agent.document_processing import extraction_pilot as pilot
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError, digest
from vietnamese_financial_multi_agent.document_processing.local_crop_mapping import page_request

from .test_crop_recovery import audit
from .test_crop_recovery import sample as sample
from .test_extraction_validation import ledger, recovered
from .test_path_resolver import config as config
from .test_raw_ocr_contracts import payload as payload


def row(source="source-a", symbol="BBS", year="2021", references=1, **kwargs):
    return dict(
        source=source,
        symbol=symbol,
        year=year,
        page=1,
        references={"crop:colab_suffix_missing": references},
        tables=[],
        element_types={"table": 1},
        warnings={},
        **kwargs,
    )


def test_selection_determinism_dedup_and_groups():
    rows = [row("b"), row("a"), row("risk"), row("c", year="2022")]
    a, meta = pilot.select_sample(rows + [rows[0]], {"risk"})
    b, _ = pilot.select_sample(list(reversed(rows)), {"risk"})
    assert a == b
    assert [x["row"]["source"] for x in a] == ["risk", "a", "c"]
    assert len({x["row"]["source"] for x in a}) == len(a)
    assert [x["group"] for x in a] == ["risk-focused", "coverage", "coverage"]
    assert len(meta["missing_coverage_strata"]) == 13
    assert meta["metadata_signals"]["invalid_bbox"] == 0


@pytest.mark.parametrize(
    "kwargs", [{"max_pages": 31}, {"max_references": 501}, {"max_pages": True}, {"max_pages": 0}]
)
def test_invalid_bounds(kwargs):
    with pytest.raises(CropError, match="bounds"):
        pilot.select_sample([row()], set(), **kwargs)


def test_budget_no_replacement_and_missing_binding():
    selected, meta = pilot.select_sample([row("a", references=501), row("b")], set())
    assert selected == [] and len(meta["omitted"]) == 1
    with pytest.raises(CropError, match="missing_approved_binding"):
        pilot.select_sample([row()], {"unapproved"})
    with pytest.raises(CropError, match="human_sample_budget"):
        pilot.select_sample([row("risk", references=501)], {"risk"})
    with pytest.raises(CropError, match="ambiguous_inventory"):
        pilot.select_sample([row(), row(references=2)], set())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def prepare(sample, *, recovery=False, mutation=None, pages=1):
    """Independent synthetic inventory/approved plan; never used as real evidence."""
    prior = sample.config.project_root / "artifacts/synthetic-approved"
    rows, audits, snapshots, images, entries = [], [], {}, {}, []
    for number in range(1, pages + 1):
        r = row(f"processed/Financial_Report_OCR/BBS/2021/ocr_json/page_{number}.json")
        r["page"] = number
        sample.payload["page"].update(symbol="BBS", year="2021", page=number)
        # Two separate image bindings prevent treating a page tuple as run identity.
        image_reference = f"/approved/raw/BBS/2021/page_{number}.png"
        sample.payload["page"]["image"] = image_reference
        image_path = sample.config.financial_report_dir / f"BBS/2021/page_{number}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(sample.image_path.read_bytes())
        sample.source = sample.config.financial_ocr_dir / f"BBS/2021/ocr_json/page_{number}.json"
        sample.source.parent.mkdir(parents=True, exist_ok=True)
        sample.request = page_request(r)
        sample.identity = ("BBS", "2021", number)
        sample.image_bindings = {image_reference: sample.identity}
        records = audit(sample)
        audits.extend(a.export() for a in records)
        if recovery:
            entries.append(recovered(sample))
        if mutation:
            mutation(sample, image_path)
        snap = pilot.snapshot(sample.source, sample.config)
        snapshots[r["source"]] = [
            snap["metadata"][0],
            snap["metadata"][1],
            snap["metadata"][3],
            snap["sha256"],
        ]
        images[image_reference] = list(sample.identity)
        rows.append(r)
    bindings = dict(
        mappings=[m.model_dump(mode="json") for m in sample.mappings],
        image_bindings=images,
        source_snapshots={
            image: {
                "sha256": pilot.snapshot(
                    sample.config.financial_report_dir / f"BBS/2021/page_{identity[2]}.png",
                    sample.config,
                )["sha256"]
            }
            for image, identity in images.items()
        },
    )
    context = dict(rows=rows, audit=audits, bindings=bindings, json_snapshots=snapshots)
    value = dict(version=1, context=context, candidates=[])
    plan = dict(plan_id=digest(value), **value)
    quality = ledger(entries[0]) if recovery else dict(issue_count=0, issues=[])
    quality["plan_id"] = plan["plan_id"]
    paths = [prior / x for x in ("plan.json", "inventory.jsonl", "index.jsonl", "ledger.json")]
    write_json(paths[0], plan)
    write_json(paths[3], quality)
    for path, values in ((paths[1], rows), (paths[2], entries)):
        path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf-8")
    return paths


def manifest(sample, **kwargs):
    return pilot.build_manifest(sample.config, *prepare(sample, **kwargs))


def test_frozen_repeatability_and_no_source_mutation(sample):
    value = manifest(sample, recovery=True)
    assert value.pages[0].group == "risk-focused"
    before = [s.model_dump() for s in value.snapshots]
    path = pilot.freeze_manifest(value, sample.config)
    assert pilot.freeze_manifest(value, sample.config) == path
    a = pilot.execute_manifest(sample.config, run="first")
    b = pilot.execute_manifest(sample.config, run="second")
    assert a == b and a["report_id"] == b["report_id"]
    assert pilot.execute_manifest(sample.config, run="second") == b
    assert before == [pilot.snapshot(Path(s.path), sample.config) for s in value.snapshots]
    group = a["groups"]["risk-focused"]
    assert group["human_requires_review"] == 1
    assert group["availability"] == {"reconstructed_available": 1}
    assert group["mapping_status"] == {"missing": 1}
    assert a["records"][0]["report"]["ledger_status"] == "consistent"
    public = json.dumps(pilot.public_statistics(a))
    for private in (
        str(sample.config.project_root),
        value.manifest_id,
        value.pages[0].image_reference,
        value.pages[0].request.reference.original_path,
        "synthetic-reviewer",
    ):
        assert private not in public
    assert "accuracy" not in public and "score" not in public
    assert a["understanding_status"] == "not_supplied"


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "structural",
        "missing_image",
        "unsafe_image",
        "missing_original",
        "invalid_recovery",
    ],
)
def test_page_results_and_failure_denominators(sample, mode):
    def mutate(s, image_path):
        if mode == "structural":
            s.source.write_text('{"page": {}}', encoding="utf-8")
        elif mode in {"missing_image", "unsafe_image"}:
            data = json.loads(s.source.read_text(encoding="utf-8"))
            data["page"]["image"] = (
                "/approved/raw/absent.png"
                if mode == "missing_image"
                else "/approved/raw/../escape.png"
            )
            write_json(s.source, data)
        elif mode == "valid":
            from PIL import Image

            Image.new("RGB", (4, 5)).save(s.config.financial_ocr_dir / "table.png")

    value = manifest(sample, mutation=mutate, recovery=mode == "invalid_recovery")
    if mode == "invalid_recovery":
        # Before freezing, alter only synthetic sidecar. The unchanged validator
        # must report the invalid evidence; no pilot remediation is allowed.
        sidecar = next(
            s for s in value.snapshots if "recovered_crops" in s.path and s.path.endswith(".json")
        )
        write_json(Path(sidecar.path), {})
        payload = value.model_dump(mode="json")
        payload["snapshots"] = [
            pilot.snapshot(Path(s.path), sample.config) for s in value.snapshots
        ]
        payload["manifest_id"] = digest({k: v for k, v in payload.items() if k != "manifest_id"})
        value = pilot.parse_manifest(payload, sample.config)
    pilot.freeze_manifest(value, sample.config)
    report = pilot.execute_manifest(sample.config, run="first")
    record = report["records"][0]
    g = report["groups"][record["group"]]
    assert g["selected_pages"] == 1 and g["expected_references"] == 1
    if mode == "structural":
        assert g["failed_pages"] == 1 and g["unverified_references"] == 1
        assert record["report"]["structural_status"] == "invalid"
        assert record["report"]["issues"]
    elif mode in {"missing_image", "unsafe_image"}:
        assert record["report"]["image_status"] == "invalid"
        assert record["report"]["source_binding_status"] == "not_verified"
    elif mode == "valid":
        assert g["availability"] == {"existing_original": 1}
    else:
        assert g["availability"] == {"missing_unrecovered": 1}
    if mode == "invalid_recovery":
        assert "invalid_recovery_sidecar" in g["issue_codes"]
        assert g["human_requires_review"] == 1


def test_input_failure_isolated_and_counts_retained(sample, monkeypatch):
    value = manifest(sample, pages=2)
    # Coverage picks one page per stratum. Freeze second page explicitly as risk
    # from approved evidence to exercise runtime isolation, without reselection.
    payload = value.model_dump(mode="json")
    plan = json.loads(Path(value.evidence_paths["plan"]).read_text(encoding="utf-8"))
    r = plan["context"]["rows"][1]
    second = copy.deepcopy(payload["pages"][0])
    second.update(
        group="risk-focused",
        request=page_request(r).model_dump(mode="json"),
        identity=["BBS", "2021", 2],
        image_reference="/approved/raw/BBS/2021/page_2.png",
    )
    payload["pages"].append(second)
    payload["image_bindings"][second["image_reference"]] = second["identity"]
    for relative in ("BBS/2021/ocr_json/page_2.json",):
        payload["snapshots"].append(
            pilot.snapshot(sample.config.financial_ocr_dir / relative, sample.config)
        )
    payload["snapshots"].append(
        pilot.snapshot(sample.config.financial_report_dir / "BBS/2021/page_2.png", sample.config)
    )
    payload["manifest_id"] = digest({k: v for k, v in payload.items() if k != "manifest_id"})
    value = pilot.parse_manifest(payload, sample.config)
    pilot.freeze_manifest(value, sample.config)
    real = pilot.validate_extraction

    def validate(request, *args, **kwargs):
        if request.reference.original_path.endswith("page_1.json"):
            raise OSError("secret path")
        return real(request, *args, **kwargs)

    monkeypatch.setattr(pilot, "validate_extraction", validate)
    report = pilot.execute_manifest(sample.config, run="first")
    assert len(report["records"]) == 2
    assert report["groups"]["coverage"]["failed_pages"] == 1
    assert report["groups"]["risk-focused"]["processed_pages"] == 1
    assert "secret path" not in json.dumps(report)


@pytest.mark.parametrize(
    "change", ["digest", "duplicate", "bounds", "binding", "snapshot", "path", "evidence", "roots"]
)
def test_invalid_or_mutated_manifest(sample, change):
    value = manifest(sample).model_dump(mode="json")
    if change == "duplicate":
        value["pages"].append(value["pages"][0])
    elif change == "bounds":
        value["pages"][0]["references"] = 501
    elif change == "binding":
        value["image_bindings"] = {}
    elif change == "snapshot":
        value["snapshots"] = []
    elif change == "path":
        value["snapshots"][0]["path"] = str(sample.config.project_root / "artifacts/../secret")
    elif change == "evidence":
        value["evidence_paths"]["extra"] = "secret"
    elif change == "roots":
        value["roots"] = {}
    if change != "digest":
        value["manifest_id"] = digest({k: v for k, v in value.items() if k != "manifest_id"})
    else:
        value["manifest_id"] = "a" * 64
    with pytest.raises(CropError):
        pilot.parse_manifest(value, sample.config)


@pytest.mark.parametrize("change", ["source", "evidence", "absent_crop", "output", "manifest"])
def test_source_or_output_changes_stop(sample, change):
    value = manifest(sample)
    pilot.freeze_manifest(value, sample.config)
    if change == "source":
        sample.source.write_bytes(sample.source.read_bytes() + b" ")
    elif change == "evidence":
        Path(value.evidence_paths["ledger"]).write_text("{}", encoding="utf-8")
    elif change == "absent_crop":
        (sample.config.financial_ocr_dir / "table.png").write_bytes(b"new")
    elif change == "manifest":
        path = pilot.output_root(sample.config) / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["pages"][0]["group"] = "risk-focused"
        write_json(path, data)
    else:
        write_json(pilot.output_root(sample.config) / "canonical-report.json", {})
    with pytest.raises(CropError):
        pilot.execute_manifest(sample.config, run="first")


def test_freeze_conflict_and_incomplete_snapshot(sample):
    value = manifest(sample)
    path = pilot.freeze_manifest(value, sample.config)
    write_json(path, {})
    with pytest.raises(CropError, match="conflict"):
        pilot.freeze_manifest(value, sample.config)
    payload = value.model_dump(mode="json")
    payload["snapshots"] = [s for s in payload["snapshots"] if s["path"] != str(sample.source)]
    payload["manifest_id"] = digest({k: v for k, v in payload.items() if k != "manifest_id"})
    with pytest.raises(CropError, match="missing_pilot_snapshot"):
        pilot.freeze_manifest(pilot.parse_manifest(payload, sample.config), sample.config)


def test_recomputed_manifest_cannot_replace_approved_mappings(sample):
    value = manifest(sample).model_dump(mode="json")
    value["mappings"][0]["mapping_id"] = "unapproved"
    value["manifest_id"] = digest({k: v for k, v in value.items() if k != "manifest_id"})
    with pytest.raises(CropError, match="binding_mismatch"):
        pilot.freeze_manifest(pilot.parse_manifest(value, sample.config), sample.config)


def test_nondeterminism_rejected_without_overwrite(sample, monkeypatch):
    from dataclasses import replace

    value = manifest(sample)
    pilot.freeze_manifest(value, sample.config)
    pilot.execute_manifest(sample.config, run="first")
    path = pilot.output_root(sample.config) / "canonical-report.json"
    before = path.read_bytes()
    real = pilot.validate_extraction

    def changed(*args, **kwargs):
        return replace(real(*args, **kwargs), image_status="not_verified")

    monkeypatch.setattr(pilot, "validate_extraction", changed)
    with pytest.raises(CropError, match="conflict"):
        pilot.execute_manifest(sample.config, run="second")
    assert path.read_bytes() == before
    assert not (path.parent / "second.json").exists()


def test_mutation_during_execution_stops_before_report(sample, monkeypatch):
    value = manifest(sample)
    pilot.freeze_manifest(value, sample.config)
    real = pilot.validate_extraction

    def changed(*args, **kwargs):
        result = real(*args, **kwargs)
        sample.source.write_bytes(sample.source.read_bytes() + b" ")
        return result

    monkeypatch.setattr(pilot, "validate_extraction", changed)
    with pytest.raises(CropError, match="source_changed"):
        pilot.execute_manifest(sample.config, run="first")
    assert not (pilot.output_root(sample.config) / "canonical-report.json").exists()


def test_human_issues_survive_structural_failure(sample):
    value = manifest(
        sample,
        recovery=True,
        mutation=lambda s, _: s.source.write_text('{"page":{}}', encoding="utf-8"),
    )
    pilot.freeze_manifest(value, sample.config)
    result = pilot.execute_manifest(sample.config, run="first")
    assert result["groups"]["risk-focused"]["human_requires_review"] == 1
    assert result["groups"]["risk-focused"]["failed_pages"] == 1


def test_aggregation_units_and_empty_group():
    issue = dict(
        code="empty_cell_text", category="quality", origin="raw_ocr_v1", status="requires_review"
    )
    report = dict(
        issues=[issue, issue],
        crops=[],
        structural_status="not_verified",
        image_status="not_verified",
        ledger_status="not_verified",
        source_binding_status="not_verified",
    )
    records = [dict(group="coverage", expected_references=3, failure="failed", report=report)]
    g = pilot.aggregate(records)
    assert g["coverage"]["issue_codes"]["empty_cell_text"] == 2
    assert g["coverage"]["pages_with_issue_code"]["empty_cell_text"] == 1
    assert g["coverage"]["unverified_references"] == 3
    assert g["coverage"]["statuses"]["structural_status"] == {"not_verified": 1}
    assert g["risk-focused"]["selected_pages"] == 0
    # Arbitrary issue codes remain private, never become public object keys.
    g["coverage"]["issue_codes"]["private-secret"] = 1
    assert "private-secret" not in json.dumps(
        pilot.public_statistics(dict(groups=g, records=records))
    )
    g["coverage"]["selected_pages"] = "private-secret"
    with pytest.raises(CropError, match="public_statistics"):
        pilot.public_statistics(dict(groups=g, records=records))


def test_public_other_page_count_is_union():
    issues = [
        dict(code=c, category="artifact", origin="source_binding", status="not_verified")
        for c in ("run_identity_not_verified", "missing_target")
    ]
    record = dict(
        group="coverage",
        expected_references=0,
        failure=None,
        report=dict(
            issues=issues,
            crops=[],
            structural_status="valid",
            image_status="checked",
            ledger_status="consistent",
            source_binding_status="not_verified",
        ),
    )
    public = pilot.public_statistics(dict(groups=pilot.aggregate([record]), records=[record]))
    assert public["coverage"]["issue_codes"]["other"] == 2
    assert public["coverage"]["pages_with_issue_code"]["other"] == 1


def test_symlink_or_junction_rejected(sample, tmp_path):
    root = sample.config.project_root / "artifacts"
    root.mkdir(exist_ok=True)
    target = tmp_path / "outside"
    target.mkdir()
    link = root / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        import os

        if os.name != "nt":
            pytest.skip("symlinks unavailable on this filesystem")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
        )
        if result.returncode:
            pytest.skip("Windows symlink permission/junction support unavailable")
    with pytest.raises(CropError):
        pilot.snapshot(link / "file.json", sample.config)


@pytest.mark.parametrize("run", ["../escape", "FIRST", "a/b", ""])
def test_unsafe_run_labels(sample, run):
    with pytest.raises(CropError, match="invalid_pilot_run"):
        pilot.execute_manifest(sample.config, run=run)


def test_local_artifacts_are_ignored_not_tracked():
    root = Path(__file__).resolve().parents[2]
    paths = [
        "artifacts/extraction-validation/M1-04b/manifest.json",
        "artifacts/extraction-validation/M1-04b/first.json",
        "data/raw/private.json",
    ]
    result = subprocess.run(
        ["git", "check-ignore", *paths], cwd=root, capture_output=True, text=True
    )
    assert result.returncode == 0 and len(result.stdout.splitlines()) == len(paths)
    tracked = subprocess.run(
        ["git", "ls-files", "--", "artifacts", "data/raw", "data/processed"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert not tracked.stdout.strip()
