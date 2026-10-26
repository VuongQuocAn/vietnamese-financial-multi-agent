"""M1-03d: targeted inventory audit, optional pilot <=12; không scan dataset."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.document_processing.contracts.path_mapping import (
    PathRootMapping,
)
from vietnamese_financial_multi_agent.document_processing.crop_audit import (
    audit_page,
    reference_request,
    select_inventory_pages,
    summarize,
)
from vietnamese_financial_multi_agent.document_processing.crop_recovery import (
    recover_crop,
    select_pilot,
)
from vietnamese_financial_multi_agent.document_processing.ocr_loader import OCRLoadError
from vietnamese_financial_multi_agent.document_processing.path_resolver import resolve_path


def read_jsonl(path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def snapshot(path):
    before = path.stat()
    if before.st_size > 32 * 1024 * 1024:
        raise ValueError("oversized_inventory_source")
    with path.open("rb") as stream:
        content = stream.read(32 * 1024 * 1024 + 1)
    if len(content) > 32 * 1024 * 1024:
        raise ValueError("oversized_inventory_source")
    return [before.st_size, before.st_mtime_ns, before.st_ino, hashlib.sha256(content).hexdigest()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("artifacts/dataset-inventory"))
    parser.add_argument(
        "--bindings", type=Path, help="Caller-approved mappings + image_bindings JSON"
    )
    parser.add_argument("--execute", action="store_true", help="Ghi tối đa 12 eligible table crops")
    args = parser.parse_args()
    config = load_data_config()
    inventory = args.inventory
    selected = select_inventory_pages(
        read_jsonl(inventory / "page_manifest.jsonl"),
        read_jsonl(inventory / "inventory_warnings.jsonl"),
    )
    bindings = json.loads(args.bindings.read_text(encoding="utf-8")) if args.bindings else {}
    mappings = [PathRootMapping.model_validate(m) for m in bindings.get("mappings", [])]
    image_bindings = {k: tuple(v) for k, v in bindings.get("image_bindings", {}).items()}
    # Binding local manifest được dùng trong M1-03c; không suy ra Colab/Drive roots.
    local_mapping = PathRootMapping(
        mapping_id="development-manifest-local-binding",
        source_root="processed/Financial_Report_OCR",
        path_style="posix",
        destination_root_key="FINANCIAL_OCR_DIR",
        category="ocr_page_json",
        containment_policy="lexical_then_runtime",
    )
    records, failures, requests, snapshots = [], [], {}, {}
    pages_loaded = 0
    for page in selected:
        source = page["source"]
        request = reference_request(
            source, "ocr_page_json", "M1-01/page_manifest", ["source"], [local_mapping]
        )
        # Resolver trước direct snapshot, không tin suffix từ manifest.
        resolution = resolve_path(request, config)
        if resolution.status != "resolved":
            failures.append({"source": source, "code": resolution.status})
            continue
        target = resolution.confirmed_target
        path = config.get_root(target.root_key).joinpath(*target.relative_suffix.split("/"))
        snapshots[source] = (path, snapshot(path))
        requests[source] = request
        try:
            records.extend(
                audit_page(
                    request,
                    config,
                    mappings,
                    expected_identity=(page["symbol"], page["year"], page["page"]),
                    image_bindings=image_bindings,
                    run_identity=bindings.get("run_identity"),
                )
            )
            pages_loaded += 1
        except OCRLoadError as error:
            failures.append({"source": source, "code": error.code})
    output = config.project_root / "artifacts/crop-recovery"
    output.mkdir(parents=True, exist_ok=True)
    preferred = set()
    for name in ("representative_pages.json", "pilot_candidates.json"):
        for page in json.loads((inventory / name).read_text(encoding="utf-8")):
            preferred.add((page["symbol"], page["year"], page["page"]))
    pilot = select_pilot(records, preferred)
    recovery = [
        recover_crop(
            record,
            requests[record.ocr_source],
            config,
            mappings,
            image_bindings=image_bindings,
            dry_run=not args.execute,
        )
        | {"selection_reason": "eligible_table; preferred_manifest_then_symbol_round_robin"}
        for record in pilot
    ]
    after = {source: snapshot(path) == before for source, (path, before) in snapshots.items()}
    summary = summarize(records) | {
        "target_pages": len(selected),
        "pages_loaded": pages_loaded,
        "page_failures": len(failures),
        "baseline_missing_occurrences": 572,
        "baseline_missing_occurrences_on_selected_pages": sum(
            p["references"]["crop:colab_suffix_missing"] for p in selected
        ),
        "approved_mapping_count": len(mappings),
        "dry_run": not args.execute,
        "pilot_selected": len(pilot),
        "recovery_status": dict(Counter(r["status"] for r in recovery)),
        "recovered_files": sum(r["status"] == "recovered" for r in recovery),
        "source_json_unchanged": all(after.values()),
        "source_json_files_hashed": len(after),
        "blocker": "no_eligible_candidate; source bindings require caller approval"
        if not pilot
        else None,
        "coverage": "only inventory pages with previous missing-crop warning; current unmapped is not missing",
    }
    for name, values in (
        ("audit.jsonl", [r.export() for r in records]),
        ("recovery.jsonl", recovery),
        ("page-failures.jsonl", failures),
    ):
        (output / name).write_text(
            "".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values),
            encoding="utf-8",
        )
    for name, value in (("audit-summary.json", summary), ("source-verification.json", after)):
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not all(after.values()):
        raise SystemExit("source_changed")


if __name__ == "__main__":
    main()
