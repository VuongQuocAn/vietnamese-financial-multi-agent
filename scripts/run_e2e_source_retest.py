"""At most four saved Pilot inputs; reuses the bounded runner without opening Gold."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from run_vifinbench_pilot import run, sha
from vietnamese_financial_multi_agent.core.persistence import atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", required=True)
    parser.add_argument("--task", choices=("E2E-REMED-01", "E2E-REMED-02"), default="E2E-REMED-01")
    args = parser.parse_args()
    if not 1 <= len(set(args.ids)) <= 4 or len(args.ids) != len(set(args.ids)):
        parser.error("select at most four distinct affected inputs")
    root = Path(__file__).resolve().parents[1]
    storage, output, baseline = (
        args.storage_root.resolve(),
        args.output.resolve(),
        args.baseline.resolve(),
    )
    if not output.is_relative_to(storage / "artifacts/evidence" / args.task):
        parser.error("output outside task evidence")
    if not baseline.is_relative_to(storage / "artifacts/evidence/E2E-VAL-01"):
        parser.error("baseline must be saved Pilot evidence")
    if args.mode == "prepare":
        saved = json.loads((baseline / "questions-only.json").read_bytes())
        cases = [c for c in saved if c["id"] in args.ids]
        assert {c["id"] for c in cases} == set(args.ids), "id_missing_from_saved_inputs"
        output.mkdir(parents=True, exist_ok=False)
        (output / "provider").mkdir()
        (output / "results").mkdir()
        atomic_json(output / "questions-only.json", cases)
        aliases = {c["document_alias"] for c in cases}
        source_hashes = {
            p.relative_to(storage).as_posix(): sha(p)
            for alias in aliases
            for p in (storage / "ViFinBench/refined" / Path(*alias.split("_"))).glob("*.json")
        }
        imported_hashes = {
            p.relative_to(storage).as_posix(): sha(p)
            for alias in aliases
            for p in (storage / "artifacts/evidence/VFB-IMPORT-03/full-final" / alias).glob(
                "*.json"
            )
        }
        old = json.loads((baseline / "receipt.json").read_bytes())
        atomic_json(
            output / "receipt.json",
            dict(
                baseline_sha=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                prepared_at_utc=datetime.now(UTC).isoformat(),
                baseline_receipt_sha256=sha(baseline / "receipt.json"),
                runtime_hashes={
                    p.relative_to(root).as_posix(): sha(p) for p in (root / "src").rglob("*.py")
                },
                source_hashes=source_hashes,
                imported_hashes=imported_hashes,
                pilot_hashes=old["pilot_hashes"],
                runner_sha256=sha(root / "scripts/run_vifinbench_pilot.py"),
                retest_runner_sha256=sha(Path(__file__)),
                question_manifest_sha256=sha(output / "questions-only.json"),
                settings=dict(
                    total_call_cap=40, per_question_cap=10, timeout_seconds=300, retries=0
                ),
            ),
        )
        print(json.dumps(dict(prepared=len(cases), cap=40)), flush=True)
        return
    receipt = json.loads((output / "receipt.json").read_bytes())
    assert receipt["retest_runner_sha256"] == sha(Path(__file__))
    assert set(args.ids) == {
        c["id"] for c in json.loads((output / "questions-only.json").read_bytes())
    }
    try:
        for identifier in args.ids:
            run(root, storage, output, [identifier])
            saved = json.loads((output / "results" / f"{identifier}.json").read_bytes())
            errors = saved.get("response", {}).get("trace", {}).get("provider_errors", [])
            if set(errors) & {"authentication", "provider_unavailable", "rate_limit"}:
                print(json.dumps(dict(stopped="provider_unavailable", case=identifier)), flush=True)
                break
    finally:
        assert all(sha(storage / p) == h for p, h in receipt["imported_hashes"].items())
        print(
            json.dumps(dict(imported_files_unchanged=len(receipt["imported_hashes"]))), flush=True
        )


if __name__ == "__main__":
    main()
