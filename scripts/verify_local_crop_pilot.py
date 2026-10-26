"""M1-03e: verify exact local mappings, re-audit <=193 pages, optional <=12 pilot."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from audit_missing_crops import read_jsonl, snapshot
from PIL import Image
from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.document_processing.contracts.path_mapping import (
    PathRootMapping,
)
from vietnamese_financial_multi_agent.document_processing.crop_audit import (
    CropError,
    audit_page,
    read_image,
    reference_request,
    select_inventory_pages,
    summarize,
)
from vietnamese_financial_multi_agent.document_processing.crop_recovery import (
    recover_crop,
    select_pilot,
)
from vietnamese_financial_multi_agent.document_processing.local_crop_mapping import (
    page_request,
    save_private_bindings,
    verify_local_mappings,
)
from vietnamese_financial_multi_agent.document_processing.path_resolver import resolve_path


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def run(config, inventory, output, *, execute=False):
    rows = select_inventory_pages(
        read_jsonl(inventory / "page_manifest.jsonl"),
        read_jsonl(inventory / "inventory_warnings.jsonl"),
    )
    before = {}
    for row in rows:
        result = resolve_path(page_request(row), config)
        if result.status != "resolved":
            raise CropError("inventory_source_unavailable")
        target = result.confirmed_target
        path = config.get_root(target.root_key) / target.relative_suffix
        before[row["source"]] = (path, snapshot(path))
    bindings = verify_local_mappings(rows, config)
    # Same evidence must serialize identically across runs; no fabricated run ID.
    output.mkdir(parents=True, exist_ok=True)
    save_private_bindings(output / "local-bindings.json", bindings)
    mappings = [PathRootMapping.model_validate(m) for m in bindings["mappings"]]
    image_bindings = {k: tuple(v) for k, v in bindings["image_bindings"].items()}
    records = []
    requests = {row["source"]: page_request(row) for row in rows}
    for row in rows:
        records.extend(
            audit_page(
                requests[row["source"]],
                config,
                mappings,
                expected_identity=(row["symbol"], row["year"], row["page"]),
                image_bindings=image_bindings,
            )
        )
    preferred = set()
    for name in ("representative_pages.json", "pilot_candidates.json"):
        for page in json.loads((inventory / name).read_text(encoding="utf-8")):
            preferred.add((page["symbol"], page["year"], page["page"]))
    pilot = select_pilot(records, preferred)
    options = dict(image_bindings=image_bindings)
    dry = [recover_crop(r, requests[r.ocr_source], config, mappings, **options) for r in pilot]
    ready = all(r["status"] in {"dry_run", "already_recovered"} for r in dry)
    if execute and (not ready or not pilot):
        raise CropError("pilot_dry_run_blocked")
    recovery, rerun, validation = [], [], []
    if execute:
        recovery = [
            recover_crop(r, requests[r.ocr_source], config, mappings, dry_run=False, **options)
            for r in pilot
        ]
        if not all(r["status"] in {"recovered", "already_recovered"} for r in recovery):
            write_json(output / "failed-execution.json", recovery)
            raise CropError("pilot_execution_failed")
        for record, result in zip(pilot, recovery, strict=True):
            path = config.project_root / "data/recovered_crops" / result["output_relative_path"]
            req = reference_request(
                record.source_image,
                "raw_page_image",
                record.ocr_source,
                ["page", "image"],
                mappings,
            )
            source, hashed = read_image(req, config)
            with source, Image.open(path) as image, source.crop(record.bbox) as expected:
                image.load()
                valid = (
                    image.format == "PNG"
                    and image.size == expected.size
                    and image.size == (result["width"], result["height"])
                    and image.mode == expected.mode
                    and image.tobytes() == expected.tobytes()
                    and hashlib.sha256(path.read_bytes()).hexdigest()
                    == result["reconstructed_image_hash"]
                    and hashed == result["source_image_hash"]
                    and result["bbox"] == record.bbox
                    and result["equivalent_to_original_crop"] == "unverified"
                )
            sidecar = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            valid = valid and all(sidecar[key] == result[key] for key in sidecar)
            validation.append(valid)
        output_before = {
            p.name: snapshot(p) for p in (config.project_root / "data/recovered_crops").iterdir()
        }
        rerun = [
            recover_crop(r, requests[r.ocr_source], config, mappings, dry_run=False, **options)
            for r in pilot
        ]
        output_after = {
            p.name: snapshot(p) for p in (config.project_root / "data/recovered_crops").iterdir()
        }
        if output_before != output_after or not all(
            r["status"] == "already_recovered" for r in rerun
        ):
            raise CropError("pilot_rerun_failed")
        if sum(name.endswith(".png") for name in output_after) > 12 or not all(validation):
            raise CropError("pilot_validation_failed")
    unchanged = {s: snapshot(p) == old for s, (p, old) in before.items()}
    image_unchanged = {}
    for original, saved in bindings["source_snapshots"].items():
        req = reference_request(
            original, "raw_page_image", "integrity", ["page", "image"], mappings
        )
        image, hashed = read_image(req, config)
        image.close()
        path = config.get_root(saved["root_key"]) / saved["relative_suffix"]
        meta = path.stat()
        image_unchanged[original] = (
            hashed == saved["sha256"]
            and meta.st_size == saved["size"]
            and meta.st_mtime_ns == saved["mtime_ns"]
            and meta.st_ino == saved["inode"]
        )
    summary = summarize(records) | dict(
        target_pages=len(rows),
        pages_audited=len(rows),
        baseline_missing_occurrences=572,
        baseline_selected=sum(r["references"]["crop:colab_suffix_missing"] for r in rows),
        issue_counts=dict(Counter(issue for r in records for issue in set(r.issues))),
        mapping=bindings["statistics"],
        pilot_selected=len(pilot),
        dry_run_status=dict(Counter(r["status"] for r in dry)),
        recovery_status=dict(Counter(r["status"] for r in recovery)),
        rerun_status=dict(Counter(r["status"] for r in rerun)),
        output_validations=len(validation),
        output_validation_passed=all(validation),
        source_json_files_hashed=len(unchanged),
        source_json_unchanged=all(unchanged.values()),
        source_image_files_hashed=len(image_unchanged),
        source_image_unchanged=all(image_unchanged.values()),
        execute=execute,
    )
    if not all(unchanged.values()) or not all(image_unchanged.values()):
        raise CropError("source_changed")
    phase = "execute" if execute else "dry-run"
    write_json(output / (phase + "-summary.json"), summary)
    write_json(
        output / (phase + "-source-verification.json"), dict(json=unchanged, images=image_unchanged)
    )
    for name, items in (
        ("audit", [r.export() for r in records]),
        (phase, recovery or dry),
        ("rerun", rerun),
    ):
        (output / (name + ".jsonl")).write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in items),
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("artifacts/dataset-inventory"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = load_data_config()
    run(
        config,
        args.inventory,
        config.project_root / "artifacts/crop-recovery/M1-03e",
        execute=args.execute,
    )


if __name__ == "__main__":
    main()
