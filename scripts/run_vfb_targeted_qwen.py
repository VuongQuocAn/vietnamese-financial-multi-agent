"""VFB-E2E-04: reuse the E2E03 runner on five frozen questions, no Gold input."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from run_vfb_qwen_e2e import digest, run
from vietnamese_financial_multi_agent.core.persistence import atomic_json

IDS = {"VFB-SH-0016", "VFB-SH-0080", "VFB-MH-0018", "VFB-NR-0077", "VFB-NR-0103"}


def prepare(root, output):
    before = root / "artifacts/evidence/VFB-E2E-03/run-v2"
    cases = [c for c in json.loads((before / "questions-only.json").read_bytes()) if c["id"] in IDS]
    assert len(cases) == 5
    output.mkdir(parents=True, exist_ok=False)
    (output / "provider").mkdir()
    (output / "results").mkdir()
    atomic_json(output / "questions-only.json", cases)
    prior = json.loads((before / "implementation.json").read_bytes())
    atomic_json(
        output / "implementation.json",
        dict(
            baseline_sha=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            committed=False,
            prepared_at_utc=datetime.now(UTC).isoformat(),
            benchmark_hashes=prior["benchmark_hashes"],
            runtime_hashes={
                str(p.relative_to(root)): digest(p) for p in sorted((root / "src").rglob("*.py"))
            },
            runner_sha256=digest(root / "scripts/run_vfb_qwen_e2e.py"),
            targeted_runner_sha256=digest(Path(__file__)),
            corpus=prior["corpus"],
            document_bundles={
                alias: "artifacts/evidence/VFB-E2E-04/projection-v1/" + alias
                for alias in ("ADC_2021", "AMC_2025")
            },
            question_manifest_sha256=digest(output / "questions-only.json"),
            settings=dict(
                provider="qwen",
                max_calls_per_question=6,
                total_call_cap=30,
                timeout_seconds=300,
                graph_enabled=True,
                retries=0,
            ),
        ),
    )
    print(json.dumps(dict(prepared=len(cases), ids=[c["id"] for c in cases])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/VFB-E2E-04/live-v1")
    )
    parser.add_argument("--ids", nargs="+", choices=sorted(IDS))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    destination = (project / args.output).resolve()
    if not destination.is_relative_to(project / "artifacts/evidence/VFB-E2E-04"):
        parser.error("output outside E2E04")
    if args.mode == "prepare":
        prepare(project, destination)
    else:
        run(project, destination, args.ids)
