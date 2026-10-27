"""M1-04b: default read-only preflight, explicit freeze or frozen-manifest execution."""

import argparse
import json
from pathlib import Path

from vietnamese_financial_multi_agent.core import load_data_config
from vietnamese_financial_multi_agent.document_processing.crop_audit import CropError
from vietnamese_financial_multi_agent.document_processing.extraction_pilot import (
    build_manifest,
    execute_manifest,
    freeze_manifest,
    public_statistics,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--run", default="first")
    parser.add_argument(
        "--plan", type=Path, default=Path("artifacts/crop-recovery/M1-03f/plan.json")
    )
    parser.add_argument(
        "--inventory", type=Path, default=Path("artifacts/dataset-inventory/page_manifest.jsonl")
    )
    parser.add_argument(
        "--index", type=Path, default=Path("artifacts/crop-recovery/M1-03f/recovery-index.jsonl")
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("artifacts/crop-recovery/M1-03f/visual-review-quality-issues.json"),
    )
    args = parser.parse_args()
    try:
        config = load_data_config()
        if args.execute:
            report = execute_manifest(config, run=args.run)
            print(json.dumps(public_statistics(report), sort_keys=True))
        else:

            def absolute(path):
                return path if path.is_absolute() else config.project_root / path

            manifest = build_manifest(
                config, *(absolute(p) for p in (args.plan, args.inventory, args.index, args.ledger))
            )
            if args.freeze:
                freeze_manifest(manifest, config)
            print(
                json.dumps(
                    dict(
                        mode="frozen" if args.freeze else "preflight",
                        pages=len(manifest.pages),
                        references=sum(p.references for p in manifest.pages),
                        missing_strata=len(manifest.selection["missing_coverage_strata"]),
                    )
                )
            )
    except (CropError, OSError, ValueError, KeyError, TypeError):
        # No raw exception details/paths in CLI; inspect private inputs locally.
        raise SystemExit("Pilot stopped: input, integrity, policy or output conflict.") from None


if __name__ == "__main__":
    main()
