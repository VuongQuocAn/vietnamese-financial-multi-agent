"""Synthetic safety checks; these do not evaluate real financial crop quality."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from vietnamese_financial_multi_agent.document_processing import crop_expansion as expansion
from vietnamese_financial_multi_agent.document_processing.crop_audit import (
    CropError,
    audit_page,
    digest,
)
from vietnamese_financial_multi_agent.document_processing.crop_recovery import (
    METHOD,
    METHOD_VERSION,
    _ExpansionPermit,
    _recover_crop,
    recover_crop,
    single_writer,
    validate_output_root,
)
from vietnamese_financial_multi_agent.document_processing.crop_review import create_review_sheets

from .test_crop_recovery import audit, recover
from .test_crop_recovery import config as config
from .test_crop_recovery import payload as payload
from .test_crop_recovery import sample as sample


@pytest.fixture
def bundle(sample, request):
    original = sample.payload["elements"][0]
    sample.payload["elements"] = []
    for i in range(getattr(request, "param", 30)):
        table = deepcopy(original)
        table.update(id=f"table-{i}", crop=f"/synthetic-colab/crops/table-{i}.png")
        sample.payload["elements"].append(table)
    records = audit(sample)
    for record in expansion.candidates(records)[:12]:
        assert recover(sample, record, dry_run=False)["status"] == "recovered"
    requests = {r.ocr_source: sample.request for r in records}
    context = dict(bindings=sample.image_bindings)
    plan = expansion.frozen_plan(records, context)
    states = expansion.inspect_outputs(
        records,
        requests,
        sample.config,
        sample.mappings,
        sample.image_bindings,
    )
    reviewed = sorted(
        [
            dict(recovery_id=s["recovery_id"], png_sha256=s["reconstructed_image_hash"])
            for s in states
            if s["status"] == "already_recovered"
        ],
        key=lambda r: r["recovery_id"],
    )
    approval = expansion.approval_template(plan, reviewed)
    approval.update(
        approved=True,
        verdict="approved",
        reviewer="Synthetic test reviewer",
        reviewed_at=datetime.now(UTC).isoformat(),
    )
    for item in approval["items"]:
        item["verdict"] = "approved"

    def refresh():
        fresh = audit_page(
            sample.request,
            sample.config,
            sample.mappings,
            expected_identity=sample.identity,
            image_bindings=sample.image_bindings,
        )
        return expansion.frozen_plan(fresh, context)

    return sample, records, requests, plan, states, reviewed, approval, refresh


def execute(bundle, **kwargs):
    sample, records, requests, plan, _, reviewed, approval, refresh = bundle
    options = dict(plan=plan, refresh=refresh, reviewed=reviewed, approval=approval)
    options.update(kwargs)
    return expansion.execute_batch(
        records, requests, sample.config, sample.mappings, sample.image_bindings, **options
    )


def output_snapshot(sample):
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in sample.root.iterdir()}


def test_caps_and_identity_stability(bundle):
    sample, records, _, _, states, *_ = bundle
    for record, state in zip(expansion.candidates(records), states, strict=True):
        assert state["recovery_id"] == digest([METHOD, METHOD_VERSION, record.export()])
    pending = next(
        r
        for r in records
        if expansion.recovery_id(r)
        not in {s["recovery_id"] for s in states if s["status"] == "already_recovered"}
    )
    assert recover(sample, pending)["status"] == "pilot_cap_reached"
    assert recover(sample, pending, cap=199)["status"] == "invalid_pilot_cap"
    assert recover(sample, pending, cap=999999)["status"] == "invalid_pilot_cap"
    assert len(list(sample.root.glob("*.png"))) == 12


def test_deterministic_balanced_selection_and_duplicates(sample):
    record = audit(sample)[0]
    records = [
        replace(
            record,
            page_identity=(symbol, year, 1),
            path_key=f"{symbol}{year}{n}",
            element_id=str(n),
            original_path=f"/ref/{symbol}/{year}/{n}",
        )
        for n in range(3)
        for symbol in ("BBS", "BCC", "BED")
        for year in ("2021", "2025")
    ]
    first = expansion.candidates(records)
    assert first == expansion.candidates(list(reversed(records)) + records)
    assert len({r.page_identity[:2] for r in first[:6]}) == 6
    assert len(first) == 18
    with pytest.raises(CropError, match="ambiguous_duplicate_reference"):
        expansion.candidates([record, replace(record, bbox=(0, 0, 1, 1))])


def test_total_scope_and_non_table_rejected(sample):
    record = audit(sample)[0]
    records = [replace(record, path_key=str(n), element_id=str(n)) for n in range(200)]
    assert len(expansion.candidates(records[:199])) == 199
    with pytest.raises(CropError, match="expansion_scope_exceeded"):
        expansion.candidates(records)
    with pytest.raises(CropError, match="non_table_candidate"):
        expansion.candidates([replace(record, element_type="seal")])


@pytest.mark.parametrize("size", [0, 25, 199, True, 1.5])
def test_invalid_batch_size(bundle, size):
    with pytest.raises(CropError, match="invalid_batch_size"):
        execute(bundle, batch_size=size)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "false",
        "rejected",
        "hash",
        "id",
        "plan",
        "reviewer",
        "time",
        "item",
    ],
)
def test_approval_fail_closed(bundle, mutation):
    approval = deepcopy(bundle[6])
    if mutation == "missing":
        approval = None
    elif mutation == "false":
        approval["approved"] = False
    elif mutation == "rejected":
        approval["verdict"] = "rejected"
    elif mutation in {"hash", "id"}:
        approval["reviewed"][0]["png_sha256" if mutation == "hash" else "recovery_id"] = "bad"
    elif mutation == "plan":
        approval["plan_id"] = "bad"
    elif mutation == "reviewer":
        approval["reviewer"] = ""
    elif mutation == "time":
        approval["reviewed_at"] = "2026-01-01"
    else:
        approval["items"][0]["verdict"] = "rejected"
    before = output_snapshot(bundle[0])
    with pytest.raises(CropError, match="visual_approval_required"):
        execute(bundle, approval=approval)
    assert output_snapshot(bundle[0]) == before


def test_batches_idempotency_and_provenance(bundle):
    sample, records, _, _, _, _, _, _ = bundle
    before = output_snapshot(sample)
    sources = sample.source.read_bytes(), sample.image_path.read_bytes()
    one = execute(bundle, batch_size=10)
    assert (one["new_outputs"], one["total"]) == (10, 22)
    assert all(output_snapshot(sample)[k] == v for k, v in before.items())
    two = execute(bundle, batch_size=24)
    assert (two["new_outputs"], two["total"]) == (8, 30)
    after = output_snapshot(sample)
    assert execute(bundle)["new_outputs"] == 0
    assert output_snapshot(sample) == after
    assert sources == (sample.source.read_bytes(), sample.image_path.read_bytes())
    root = expansion.artifact_root(sample.config)
    index = [json.loads(s) for s in (root / "recovery-index.jsonl").read_text().splitlines()]
    assert len(index) == len(records)
    for item in index:
        assert item["availability"] == "reconstructed_available"
        assert item["validation_status"] == "validated"
        assert item["equivalent_to_original_crop"] == "unverified"
        assert item["element_type"] == "table" and item["crop_field"] == "crop"
        assert item["source_image_hash"] and item["original_crop_reference"]
        assert item["bbox"] and item["page_identity"] and item["reconstructed_image_hash"]


@pytest.mark.parametrize("bundle", [45], indirect=True)
def test_full_batch_writes_exactly_24_new_outputs(bundle):
    prior = output_snapshot(bundle[0])
    first = execute(bundle, batch_size=24)
    assert first["new_outputs"] == 24 and first["total"] == 36
    assert all(output_snapshot(bundle[0])[k] == v for k, v in prior.items())
    second = execute(bundle, batch_size=24)
    assert second["new_outputs"] == 9 and second["total"] == 45


@pytest.mark.parametrize("changed", ["bbox", "source", "bindings"])
def test_changed_inputs_block_before_write(bundle, changed):
    sample = bundle[0]
    if changed == "bbox":
        sample.payload["elements"][0]["bbox"] = [0, 0, 5, 5]
        sample.source.write_text(json.dumps(sample.payload), encoding="utf-8")
    elif changed == "source":
        from PIL import Image

        Image.new("RGB", (100, 100), "red").save(sample.image_path)
    else:
        sample.image_bindings.clear()
    before = output_snapshot(sample)
    with pytest.raises(CropError, match="approved_plan_changed"):
        execute(bundle)
    assert output_snapshot(sample) == before


def test_conflict_and_incomplete_sidecar_preserved(bundle):
    sample = bundle[0]
    sidecar = next(sample.root.glob("*.json"))
    sidecar.unlink()  # Synthetic interruption after PNG, before sidecar.
    before = output_snapshot(sample)
    with pytest.raises(CropError, match="preflight_conflict"):
        execute(bundle)
    assert output_snapshot(sample) == before


def test_interruption_fail_closed_and_safe_retry_requires_review(bundle):
    root = expansion.artifact_root(bundle[0].config)
    expansion.write_once(root / "batch-interrupted.started.json", {"status": "running"})
    before = output_snapshot(bundle[0])
    with pytest.raises(CropError, match="interrupted_batch_requires_review"):
        execute(bundle)
    assert output_snapshot(bundle[0]) == before


def test_partial_batch_failure_stops_next_batch(bundle, monkeypatch):
    real = expansion._recover_crop
    calls = 0

    def failing(*args, **kwargs):
        nonlocal calls
        if kwargs.get("dry_run") is False:
            calls += 1
        if calls == 2 and kwargs.get("dry_run") is False:
            return {"status": "io_error", "recovery_id": expansion.recovery_id(args[0])}
        return real(*args, **kwargs)

    monkeypatch.setattr(expansion, "_recover_crop", failing)
    with pytest.raises(CropError, match="batch_execution_failed"):
        execute(bundle)
    assert len(list(bundle[0].root.glob("*.png"))) == 13
    monkeypatch.setattr(expansion, "_recover_crop", real)
    before = output_snapshot(bundle[0])
    with pytest.raises(CropError, match="failed_batch_requires_review"):
        execute(bundle)
    assert output_snapshot(bundle[0]) == before


def test_post_write_integrity_failure_stops_execution(bundle):
    calls = 0

    def fail():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise CropError("source_changed")

    with pytest.raises(CropError, match="source_changed"):
        execute(bundle, batch_size=1, integrity=fail)
    with pytest.raises(CropError, match="failed_batch_requires_review"):
        execute(bundle)


def test_shared_writer_lock_blocks_pilot_and_expansion(bundle):
    sample = bundle[0]
    with single_writer(sample.config):
        with pytest.raises(CropError, match="recovery_writer_locked"):
            execute(bundle)
        result = recover(sample, bundle[1][0], dry_run=False)
        assert result["status"] == "recovery_writer_locked"
    with single_writer(sample.config):
        pass  # Persistent lock inode can be safely reacquired after release.


def test_total_engine_capacity_not_arbitrary(sample):
    record = audit(sample)[0]
    sample.root.mkdir(parents=True)
    for i in range(199):
        (sample.root / f"{i}.png").write_bytes(b"synthetic reserved slot")
    permit = _ExpansionPermit(frozenset({expansion.recovery_id(record)}))
    result = _recover_crop(
        record,
        sample.request,
        sample.config,
        sample.mappings,
        image_bindings=sample.image_bindings,
        cap=199,
        _permit=permit,
    )
    assert result["status"] == "pilot_cap_reached"
    result = _recover_crop(
        record,
        sample.request,
        sample.config,
        sample.mappings,
        image_bindings=sample.image_bindings,
        cap=200,
        _permit=permit,
    )
    assert result["status"] == "invalid_pilot_cap"


def test_unknown_outputs_and_root_traversal(bundle):
    sample = bundle[0]
    (sample.root / "unknown.png").write_bytes(b"synthetic")
    with pytest.raises(CropError, match="unknown_recovery_output"):
        execute(bundle)
    with pytest.raises(CropError, match="unapproved_output_root"):
        validate_output_root(sample.root / ".." / "escape", sample.config)
    changed = sample.config.model_copy(update={"financial_report_dir": sample.root})
    with pytest.raises(CropError, match="overlapping_output_root"):
        validate_output_root(sample.root, changed)


def test_contact_sheets_preserve_sources_and_never_approve(bundle):
    sample, records, requests, plan, states, reviewed, *_ = bundle
    before = sample.source.read_bytes(), sample.image_path.read_bytes(), output_snapshot(sample)
    manifest = create_review_sheets(
        sample.config,
        records,
        states,
        requests,
        sample.mappings,
        sample.image_bindings,
        plan,
        reviewed,
    )
    assert len(manifest) == 12
    assert before == (
        sample.source.read_bytes(),
        sample.image_path.read_bytes(),
        output_snapshot(sample),
    )
    root = expansion.artifact_root(sample.config)
    template = json.loads((root / "visual-review-approval.template.json").read_text())
    assert template["approved"] is False and template["reviewer"] is None
    assert not (root / "visual-review-approval.json").exists()
    assert len(list((root / "review").glob("*.png"))) == 12


def test_checkpoint_change_or_partial_file_not_overwritten(tmp_path):
    target = tmp_path / "checkpoint.json"
    expansion.write_once(target, {"status": "pending"})
    before = target.read_bytes()
    with pytest.raises(CropError, match="checkpoint_conflict"):
        expansion.write_once(target, {"status": "done"})
    assert target.read_bytes() == before


def test_no_default_png_writes(sample):
    record = audit(sample)[0]
    assert (
        recover_crop(
            record,
            sample.request,
            sample.config,
            sample.mappings,
            image_bindings=sample.image_bindings,
        )["status"]
        == "dry_run"
    )
    assert not sample.root.exists()


def test_clean_partial_batch_resume(bundle):
    sample, records, _, plan, states, *_ = bundle
    pending = [s["recovery_id"] for s in states if s["status"] == "dry_run"][:4]
    root = expansion.artifact_root(sample.config)
    expansion.write_once(
        root / "batch-interrupted.started.json",
        dict(
            status="running",
            plan_id=plan["plan_id"],
            pending=pending,
        ),
    )
    record = next(r for r in records if expansion.recovery_id(r) == pending[0])
    result = _recover_crop(
        record,
        sample.request,
        sample.config,
        sample.mappings,
        image_bindings=sample.image_bindings,
        cap=199,
        _permit=_ExpansionPermit(frozenset(expansion.recovery_id(r) for r in records)),
        dry_run=False,
    )
    assert result["status"] == "recovered"
    before = output_snapshot(sample)
    report = execute(bundle, resume=True, batch_size=3)
    assert report["new_outputs"] == 3
    assert all(output_snapshot(sample)[k] == v for k, v in before.items())
    checkpoint = json.loads((root / "batch-interrupted.finished.json").read_text())
    assert checkpoint["status"] == "interrupted_validated"
    assert len(checkpoint["completed"]) == 1 and len(checkpoint["pending"]) == 3


def test_process_lock_released_after_interruption(sample):
    import subprocess
    import sys

    code = """
import sys
from vietnamese_financial_multi_agent.core import DataConfig
from vietnamese_financial_multi_agent.document_processing.crop_recovery import single_writer
config = DataConfig.model_validate_json(sys.argv[1])
with single_writer(config):
    print('ready', flush=True)
    sys.stdin.read()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, sample.config.model_dump_json()],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "ready"
        with pytest.raises(CropError, match="recovery_writer_locked"):
            with single_writer(sample.config):
                pass
    finally:
        process.terminate()
        process.wait(timeout=10)
    with single_writer(sample.config):
        pass


@pytest.mark.parametrize("junction", [False, True])
def test_expansion_rejects_linked_output_root(sample, junction):
    import os
    import subprocess

    records = audit(sample)
    sample.root.parent.mkdir(exist_ok=True)
    target = sample.config.project_root / "outside"
    target.mkdir()
    if junction:
        if os.name != "nt":
            pytest.skip("Native junction requires Windows")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(sample.root), str(target)], capture_output=True
        )
        if result.returncode:
            pytest.skip("Runner cannot create junction")
    else:
        try:
            sample.root.symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("Runner cannot create symlink")
    with pytest.raises(CropError, match="unsafe_output_link"):
        expansion.inspect_outputs(
            records,
            {r.ocr_source: sample.request for r in records},
            sample.config,
            sample.mappings,
            sample.image_bindings,
        )
    assert not list(target.iterdir())
