"""Replay exactly the frozen nine QA against the pinned corpus; no Gold in runtime."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import vietnamese_financial_multi_agent as package

ROOT = Path(__file__).resolve().parents[1]
package.__path__ = [str(ROOT / "src")]

from run_vifinbench_pilot import run, sha  # noqa: E402
from vietnamese_financial_multi_agent.core.persistence import atomic_json  # noqa: E402


def prepare(storage, output):
    baseline_path = storage / "artifacts/evidence/QWEN-THINK-01/live-final/receipt.json"
    baseline = json.loads(baseline_path.read_bytes())
    manifest = storage / "artifacts/evidence/E2E-VAL-01/baseline-nine/questions-only.json"
    cases = json.loads(manifest.read_bytes())
    assert len(cases) == 9 and len({c["id"] for c in cases}) == 9
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("provider", "results"):
        (output / folder).mkdir()
    atomic_json(output / "questions-only.json", cases)
    names = subprocess.check_output(
        ["git", "ls-files", "-m", "-o", "--exclude-standard"], cwd=storage, text=True
    ).splitlines()
    parents = ["E2E-VAL-01", "QWEN-THINK-01", *(f"E2E-REMED-0{i}" for i in range(1, 5))]
    atomic_json(
        output / "receipt.json",
        dict(
            implementation_sha=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            prepared_at_utc=datetime.now(UTC).isoformat(),
            baseline_receipt_sha256=sha(baseline_path),
            frozen_manifest_sha256=sha(manifest),
            question_manifest_sha256=sha(output / "questions-only.json"),
            runtime_hashes={
                p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "src").rglob("*.py")
            },
            runner_sha256=sha(ROOT / "scripts/run_vifinbench_pilot.py"),
            stabilization_runner_sha256=sha(Path(__file__)),
            **{
                key: baseline[key]
                for key in ("source_hashes", "imported_hashes", "pilot_hashes", "corpus")
            },
            local_hashes={
                name: sha(storage / name) for name in names if (storage / name).is_file()
            },
            parent_evidence_hashes={
                p.relative_to(storage).as_posix(): sha(p)
                for name in parents
                for p in (storage / "artifacts/evidence" / name).rglob("*")
                if p.is_file()
            },
            settings=dict(total_call_cap=90, per_question_cap=10, timeout_seconds=600, retries=0),
            client_profile=dict(
                QWEN_THINKING_BUDGET="true",
                stage_timeout_seconds=180,
                max_output_tokens_floor=8192,
                context_changed=False,
                template_override=False,
            ),
        ),
    )
    print(json.dumps(dict(prepared=len(cases), total_call_cap=90)), flush=True)


def validate(storage, output):
    receipt = json.loads((output / "receipt.json").read_bytes())
    assert sha(Path(__file__)) == receipt["stabilization_runner_sha256"]
    os.environ["QWEN_THINKING_BUDGET"] = "true"
    try:
        run(ROOT, storage, output, None, corpus=storage / receipt["corpus"])
    finally:
        checks = {
            key: all(sha(storage / p) == h for p, h in receipt[key].items())
            for key in ("local_hashes", "parent_evidence_hashes")
        }
        atomic_json(output / "preservation.json", checks)
        assert all(checks.values()), checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--storage-root", type=Path, required=True)
    args = parser.parse_args()
    storage = args.storage_root.resolve()
    output = storage / "artifacts/evidence/E2E-STABILIZE-01/live-nine"
    (prepare if args.mode == "prepare" else validate)(storage, output)


if __name__ == "__main__":
    main()
