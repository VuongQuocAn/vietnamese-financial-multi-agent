"""Bounded table expansion with frozen local evidence and an explicit human gate."""

import json
import os
from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from .crop_audit import CropError, digest
from .crop_recovery import (
    METHOD,
    METHOD_VERSION,
    _check_components,
    _ExpansionPermit,
    _recover_crop,
    single_writer,
    validate_output_root,
)

TOTAL_CAP = 199
BATCH_CAP = 24


def recovery_id(record):
    # Same canonical payload as M1-03d/e. Never add expansion fields here.
    return digest([METHOD, METHOD_VERSION, record.export()])


def candidates(records):
    """Stable symbol/year round-robin; duplicate references cannot create new IDs."""
    refs, ids = {}, {}
    for record in records:
        if record.eligibility != "eligible_candidate":
            continue
        if record.element_type != "table" or record.field != "crop":
            raise CropError("non_table_candidate")
        rid = recovery_id(record)
        if record.path_key in refs and refs[record.path_key] != rid:
            raise CropError("ambiguous_duplicate_reference")
        refs[record.path_key] = rid
        ids[rid] = record
    if len(ids) > TOTAL_CAP:
        raise CropError("expansion_scope_exceeded")
    groups = defaultdict(list)
    for _rid, record in sorted(ids.items()):
        groups[record.page_identity[:2]].append(record)
    ordered = []
    while any(groups.values()):
        for key in sorted(groups):
            if groups[key]:
                ordered.append(groups[key].pop(0))
    return ordered


def frozen_plan(records, context):
    ordered = candidates(records)
    payload = dict(
        version=1,
        context=context,
        candidates=[dict(recovery_id=recovery_id(r), record=r.export()) for r in ordered],
    )
    # Normalize tuples for byte-for-byte comparison after JSON round-trip.
    payload = json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return dict(plan_id=digest(payload), **payload)


def artifact_root(config):
    root = config.project_root / "artifacts/crop-recovery/M1-03f"
    _check_components(root)
    for source in (config.financial_report_dir, config.financial_ocr_dir):
        if root.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(
            root.resolve()
        ):
            raise CropError("overlapping_artifact_root")
    return root


def write_once(path, value):
    """Exclusive/idempotent local checkpoint; partial files fail closed."""
    _check_components(path)
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode()
    if path.exists():
        if path.read_bytes() != content:
            raise CropError("checkpoint_conflict")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _check_components(path)
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def validate_approval(approval, plan, reviewed):
    """Human supplied only. Timestamp/reviewer are attribution, not authentication."""
    try:
        checked = datetime.fromisoformat(approval["reviewed_at"])
        valid = (
            approval["approved"] is True
            and approval["verdict"] == "approved"
            and type(approval["reviewer"]) is str
            and bool(approval["reviewer"].strip())
            and checked.utcoffset() is not None
            and checked <= datetime.now(checked.tzinfo)
            and approval["plan_id"] == plan["plan_id"]
            and approval["reviewed"] == reviewed
            and len(reviewed) == 12
            and len({r["recovery_id"] for r in reviewed}) == 12
            and all(r["verdict"] == "approved" for r in approval["items"])
            and approval["items"] == [dict(**r, verdict="approved") for r in reviewed]
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise CropError("visual_approval_required")


def approval_template(plan, reviewed):
    return dict(
        approved=False,
        verdict="pending",
        reviewer=None,
        reviewed_at=None,
        plan_id=plan["plan_id"],
        reviewed=reviewed,
        items=[dict(**r, verdict="pending") for r in reviewed],
    )


def inspect_outputs(records, requests, config, mappings, image_bindings):
    """Reopen/re-encode/pixel/hash/sidecar checks through the unchanged engine."""
    selected = candidates(records)
    root = validate_output_root(config.project_root / "data/recovered_crops", config)
    permitted = frozenset(recovery_id(r) for r in selected)
    if root.exists():
        for path in root.iterdir():
            _check_components(path)
            if path.suffix not in {".png", ".json"} or path.stem not in permitted:
                raise CropError("unknown_recovery_output")
    permit = _ExpansionPermit(permitted)
    results = []
    for record in selected:
        result = _recover_crop(
            record,
            requests[record.ocr_source],
            config,
            mappings,
            image_bindings=image_bindings,
            cap=TOTAL_CAP,
            _permit=permit,
        )
        result.update(
            element_id=record.element_id,
            element_type=record.element_type,
            crop_field=record.field,
            validation_status=(
                "validated" if result["status"] == "already_recovered" else "pending"
            ),
        )
        result["availability"] = (
            "reconstructed_available"
            if result["status"] == "already_recovered"
            else "missing_unrecovered"
        )
        results.append(result)
    return results


def write_index(root, results):
    """Immutable index checkpoint plus atomically refreshed downstream projection."""
    write_once(root / ("index-" + digest(results) + ".json"), results)
    target = root / "recovery-index.jsonl"
    _check_components(target)
    temporary = root / ("index-" + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        for result in results:
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)


def execute_batch(
    records,
    requests,
    config,
    mappings,
    image_bindings,
    *,
    plan,
    refresh,
    reviewed,
    approval=None,
    batch_size=BATCH_CAP,
    integrity=lambda: None,
    resume=False,
):
    """One invocation = at most one batch. Refresh source scope before each run.

    refresh() returns a freshly audited frozen plan; integrity() verifies source
    snapshots after write. The production CLI supplies both; synthetic tests use
    small independent fixtures. Any failed checkpoint blocks subsequent batches.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= BATCH_CAP:
        raise CropError("invalid_batch_size")
    validate_approval(approval, plan, reviewed)
    with single_writer(config):
        root = artifact_root(config)
        if refresh() != plan or frozen_plan(records, plan["context"]) != plan:
            raise CropError("approved_plan_changed")
        write_once(root / "plan.json", plan)
        interrupted = []
        for started in root.glob("batch-*.started.json"):
            finished = started.with_name(started.name.replace(".started.", ".finished."))
            _check_components(started)
            _check_components(finished)
            if not finished.exists():
                if not resume:
                    raise CropError("interrupted_batch_requires_review")
                interrupted.append((started, finished))
                continue
            if json.loads(finished.read_text(encoding="utf-8"))["status"] not in {
                "completed",
                "interrupted_validated",
            }:
                raise CropError("failed_batch_requires_review")
        states = inspect_outputs(records, requests, config, mappings, image_bindings)
        if any(s["status"] not in {"dry_run", "already_recovered"} for s in states):
            write_once(root / ("conflict-" + digest(states) + ".json"), states)
            raise CropError("preflight_conflict")
        by_id = {s["recovery_id"]: s for s in states}
        if any(
            by_id.get(r["recovery_id"], {}).get("status") != "already_recovered"
            or by_id[r["recovery_id"]]["reconstructed_image_hash"] != r["png_sha256"]
            for r in reviewed
        ):
            raise CropError("review_outputs_changed")
        integrity()
        for started, finished in interrupted:
            saved = json.loads(started.read_text(encoding="utf-8"))
            if (
                saved.get("plan_id") != plan["plan_id"]
                or type(saved.get("pending")) is not list
                or not 1 <= len(saved["pending"]) <= BATCH_CAP
                or len(set(saved["pending"])) != len(saved["pending"])
                or any(r not in by_id for r in saved["pending"])
            ):
                raise CropError("interrupted_checkpoint_conflict")
            write_once(
                finished,
                dict(
                    status="interrupted_validated",
                    completed=[
                        r for r in saved["pending"] if by_id[r]["status"] == "already_recovered"
                    ],
                    pending=[r for r in saved["pending"] if by_id[r]["status"] == "dry_run"],
                ),
            )
        lookup = {recovery_id(r): r for r in candidates(records)}
        pending = [s for s in states if s["status"] == "dry_run"][:batch_size]
        if not pending:
            write_index(root, states)
            return dict(status="completed", new_outputs=0, total=len(states))
        if sum(s["status"] == "already_recovered" for s in states) + len(pending) > len(lookup):
            raise CropError("expansion_scope_exceeded")
        batch_id = uuid4().hex
        write_once(
            root / f"batch-{batch_id}.started.json",
            dict(
                plan_id=plan["plan_id"],
                pending=[s["recovery_id"] for s in pending],
                status="running",
            ),
        )
        created, failures = [], []
        try:
            permit = _ExpansionPermit(frozenset(lookup))
            for state in pending:
                record = lookup[state["recovery_id"]]
                result = _recover_crop(
                    record,
                    requests[record.ocr_source],
                    config,
                    mappings,
                    image_bindings=image_bindings,
                    dry_run=False,
                    cap=TOTAL_CAP,
                    _permit=permit,
                )
                if result["status"] != "recovered":
                    failures.append(result)
                    raise CropError("batch_execution_failed")
                created.append(result["recovery_id"])
            integrity()
            if refresh() != plan:
                raise CropError("approved_plan_changed")
            after = inspect_outputs(records, requests, config, mappings, image_bindings)
            by_id = {s["recovery_id"]: s for s in after}
            if any(by_id[r]["status"] != "already_recovered" for r in created):
                raise CropError("batch_validation_failed")
            count = sum(s["status"] == "already_recovered" for s in after)
            before = sum(s["status"] == "already_recovered" for s in states)
            if count != before + len(created) or len(created) > BATCH_CAP or count > TOTAL_CAP:
                raise CropError("batch_count_mismatch")
            write_index(root, after)
        except Exception as error:
            write_once(
                root / f"batch-{batch_id}.finished.json",
                dict(
                    status="failed",
                    completed=created,
                    failed=failures,
                    reason=error.code if isinstance(error, CropError) else "unexpected_failure",
                    needs_review=True,
                ),
            )
            raise
        report = dict(status="completed", completed=created, new_outputs=len(created), total=count)
        write_once(root / f"batch-{batch_id}.finished.json", report)
        return report
