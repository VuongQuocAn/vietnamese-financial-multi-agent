"""M1-03f: plan/dry-run/verify or execute exactly one authorized batch <=24."""

import argparse
import json
from collections import Counter
from pathlib import Path

from audit_missing_crops import read_jsonl, snapshot
from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.document_processing.contracts import PathRootMapping
from vietnamese_financial_multi_agent.document_processing.crop_audit import (
    CropError,
    audit_page,
    digest,
    select_inventory_pages,
    summarize,
)
from vietnamese_financial_multi_agent.document_processing.crop_evidence import (
    public_expansion_statistics,
)
from vietnamese_financial_multi_agent.document_processing.crop_expansion import (
    artifact_root,
    candidates,
    execute_batch,
    frozen_plan,
    inspect_outputs,
    recovery_id,
    validate_approval,
    write_index,
    write_once,
)
from vietnamese_financial_multi_agent.document_processing.crop_recovery import _check_components
from vietnamese_financial_multi_agent.document_processing.local_crop_mapping import (
    page_request,
    verify_local_mappings,
)
from vietnamese_financial_multi_agent.document_processing.path_resolver import resolve_path


def collect(config, inventory):
    rows = select_inventory_pages(
        read_jsonl(inventory / "page_manifest.jsonl"),
        read_jsonl(inventory / "inventory_warnings.jsonl"),
    )
    if len(rows) != 193:
        raise CropError("inventory_coverage_mismatch")
    requests = {r["source"]: page_request(r) for r in rows}
    snapshots = {}
    for source, request in requests.items():
        resolution = resolve_path(request, config)
        if resolution.status != "resolved":
            raise CropError("inventory_source_unavailable")
        target = resolution.confirmed_target
        path = config.get_root(target.root_key) / target.relative_suffix
        snapshots[source] = snapshot(path)
    bindings = verify_local_mappings(rows, config)
    old = config.project_root / "artifacts/crop-recovery/M1-03e/local-bindings.json"
    _check_components(old)
    if json.loads(old.read_text(encoding="utf-8")) != json.loads(json.dumps(bindings)):
        raise CropError("pilot_bindings_changed")
    if (
        bindings["statistics"]["mappings_verified"] != 2
        or bindings["statistics"]["mappings_rejected"]
        or bindings["statistics"]["discovery_failures"]
        or bindings["statistics"]["image_bindings_verified"] != 193
    ):
        raise CropError("mapping_verification_failed")
    mappings = [PathRootMapping.model_validate(m) for m in bindings["mappings"]]
    images = {k: tuple(v) for k, v in bindings["image_bindings"].items()}
    records = []
    for row in rows:
        records.extend(
            audit_page(
                requests[row["source"]],
                config,
                mappings,
                expected_identity=(row["symbol"], row["year"], row["page"]),
                image_bindings=images,
            )
        )
    # Include all audit states, not only eligible candidates, in the source binding.
    context = dict(
        rows=rows, bindings=bindings, json_snapshots=snapshots, audit=[r.export() for r in records]
    )
    return records, requests, mappings, images, frozen_plan(records, context)


def pilot_review(config, records, states):
    prior_path = config.project_root / "artifacts/crop-recovery/M1-03e/execute.jsonl"
    _check_components(prior_path)
    prior = read_jsonl(prior_path)
    by_id = {s["recovery_id"]: s for s in states}
    ids = {recovery_id(r) for r in candidates(records)}
    if len(prior) != 12 or len({r["recovery_id"] for r in prior}) != 12:
        raise CropError("pilot_count_mismatch")
    reviewed = []
    for old in prior:
        rid = old["recovery_id"]
        current = by_id.get(rid, {})
        if (
            rid not in ids
            or current.get("status") != "already_recovered"
            or any(
                current.get(k) != old.get(k)
                for k in (
                    "reconstructed_image_hash",
                    "source_image_hash",
                    "method",
                    "method_version",
                    "original_crop_reference",
                    "width",
                    "height",
                )
            )
        ):
            raise CropError("pilot_output_changed")
        reviewed.append(dict(recovery_id=rid, png_sha256=current["reconstructed_image_hash"]))
    return sorted(reviewed, key=lambda r: r["recovery_id"])


def prepare(config, inventory):
    records, requests, mappings, images, plan = collect(config, inventory)
    root = artifact_root(config)
    write_once(root / "plan.json", plan)
    states = inspect_outputs(records, requests, config, mappings, images)
    reviewed = pilot_review(config, records, states)
    write_index(root, states)
    pending = [s["recovery_id"] for s in states if s["status"] == "dry_run"]
    write_once(
        root / ("execution-plan-" + digest(pending) + ".json"),
        dict(
            plan_id=plan["plan_id"],
            batch_cap=24,
            total_cap=199,
            batches=[pending[i : i + 24] for i in range(0, len(pending), 24)],
        ),
    )
    if any(s["status"] not in {"dry_run", "already_recovered"} for s in states):
        raise CropError("preflight_conflict")
    # Recollect ensures all JSON/raw source snapshots and mappings remain unchanged.
    if collect(config, inventory)[-1] != plan:
        raise CropError("source_changed")
    return records, requests, mappings, images, plan, states, reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    for flag in ("plan", "dry-run", "verify", "execute"):
        mode.add_argument("--" + flag, action="store_true")
    parser.add_argument("--batch-size", type=int, choices=range(1, 25), default=24)
    parser.add_argument(
        "--resume", action="store_true", help="Revalidate a clean interrupted batch"
    )
    parser.add_argument("--inventory", type=Path, default=Path("artifacts/dataset-inventory"))
    args = parser.parse_args()
    config = load_data_config()
    records, requests, mappings, images, plan, states, reviewed = prepare(config, args.inventory)
    root = artifact_root(config)
    approval_path = root / "visual-review-approval.json"
    _check_components(approval_path)
    approval = (
        json.loads(approval_path.read_text(encoding="utf-8")) if approval_path.exists() else None
    )
    approved = False
    try:
        validate_approval(approval, plan, reviewed)
        approved = True
    except CropError:
        if args.execute:
            raise
    batch = None
    if args.execute:
        batch = execute_batch(
            records,
            requests,
            config,
            mappings,
            images,
            plan=plan,
            refresh=lambda: collect(config, args.inventory)[-1],
            reviewed=reviewed,
            approval=approval,
            batch_size=args.batch_size,
            resume=args.resume,
        )
        states = inspect_outputs(records, requests, config, mappings, images)
    stats = summarize(records)
    reconstructed = sum(s["status"] == "already_recovered" for s in states)
    summary = dict(
        pages_audited=193,
        references_audited=stats["references_audited"],
        original_missing=stats["missing_references"],
        existing_original=stats["mapping_status"].get("existing", 0),
        existing_original_tables=sum(
            r.element_type == "table" and r.field == "crop" and r.mapping_status == "existing"
            for r in records
        ),
        original_table_missing=sum(
            r.element_type == "table" and r.field == "crop" and r.mapping_status == "missing"
            for r in records
        ),
        eligible=len(states),
        prior_reconstructed=len(reviewed),
        reconstructed_available=reconstructed,
        missing_unrecovered=len(states) - reconstructed,
        conflicts=sum(s["status"] not in {"already_recovered", "dry_run"} for s in states),
        unsupported_views=stats["eligibility"].get("unsupported_view", 0),
        non_table_requires_review=stats["requires_review"],
        new_outputs=0 if batch is None else batch["new_outputs"],
        human_approved=approved,
        source_unchanged=True,
        dry_run_status=dict(Counter(s["status"] for s in states)),
    )
    write_once(root / ("summary-" + digest(summary) + ".json"), summary)
    print(json.dumps(public_expansion_statistics(summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except CropError as error:
        raise SystemExit(error.code) from None
