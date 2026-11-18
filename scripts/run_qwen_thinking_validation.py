"""Three frozen real QA inputs, existing Thinking endpoint, no Gold or retries."""

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

IDS = ("VFB-MH-0001", "VFB-NR-0001", "VFB-SH-0006")


def prepare(storage, output):
    saved = storage / "artifacts/evidence/E2E-REMED-04/retest-two/receipt.json"
    baseline = json.loads(saved.read_bytes())
    all_cases = json.loads(
        (storage / "artifacts/evidence/E2E-VAL-01/baseline-nine/questions-only.json").read_bytes()
    )
    cases = [next(c for c in all_cases if c["id"] == key) for key in IDS]
    output.mkdir(parents=True, exist_ok=False)
    for folder in ("provider", "results"):
        (output / folder).mkdir()
    atomic_json(output / "questions-only.json", cases)
    parents = ["E2E-VAL-01", *(f"E2E-REMED-0{i}" for i in range(1, 5))]
    old_evidence = {
        p.relative_to(storage).as_posix(): sha(p)
        for name in parents
        for p in (storage / "artifacts/evidence" / name).rglob("*")
        if p.is_file()
    }
    local_names = subprocess.check_output(
        ["git", "ls-files", "-m", "-o", "--exclude-standard"], cwd=storage, text=True
    ).splitlines()
    atomic_json(
        output / "receipt.json",
        dict(
            implementation_sha=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            prepared_at_utc=datetime.now(UTC).isoformat(),
            baseline_receipt_sha256=sha(saved),
            runtime_hashes={
                p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "src").rglob("*.py")
            },
            source_hashes=baseline["source_hashes"],
            imported_hashes=baseline["imported_hashes"],
            pilot_hashes=baseline["pilot_hashes"],
            parent_evidence_hashes=old_evidence,
            local_hashes={
                name: sha(storage / name) for name in local_names if (storage / name).is_file()
            },
            runner_sha256=sha(ROOT / "scripts/run_vifinbench_pilot.py"),
            thinking_runner_sha256=sha(Path(__file__)),
            question_manifest_sha256=sha(output / "questions-only.json"),
            corpus=baseline["corpus"],
            settings=dict(total_call_cap=30, per_question_cap=10, timeout_seconds=300, retries=0),
            client_profile=dict(
                QWEN_THINKING_BUDGET="true",
                max_output_tokens_floor=8192,
                stage_timeout_seconds=180,
                template_override=False,
                context_changed=False,
            ),
        ),
    )
    print(json.dumps(dict(prepared=3, ids=IDS, total_call_cap=30)), flush=True)


def validate(storage, output):
    receipt = json.loads((output / "receipt.json").read_bytes())
    assert sha(Path(__file__)) == receipt["thinking_runner_sha256"]
    assert receipt["client_profile"]["template_override"] is False
    assert [c["id"] for c in json.loads((output / "questions-only.json").read_bytes())] == list(IDS)
    os.environ["QWEN_THINKING_BUDGET"] = "true"
    wire_path = output / "wire-summary.json"
    wire_events = json.loads(wire_path.read_bytes()) if wire_path.exists() else []

    def observe(response):
        response.read()
        event = dict(http_status=response.status_code)
        if response.status_code == 200:
            raw = response.json()
            choice = raw.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content") or ""
            event.update(
                finish_reason=choice.get("finish_reason"),
                reasoning_chars=len(message.get("reasoning_content") or ""),
                inline_thinking="<think>" in content or "</think>" in content,
                content_chars=len(content),
                completion_tokens_details=raw.get("usage", {}).get("completion_tokens_details"),
            )
        wire_events.append(event)
        atomic_json(wire_path, wire_events)

    try:
        for identifier in IDS:
            run(
                ROOT,
                storage,
                output,
                [identifier],
                corpus=storage / receipt["corpus"],
                response_hook=observe,
            )
            result = json.loads((output / "results" / f"{identifier}.json").read_bytes())
            errors = result.get("response", {}).get("trace", {}).get("provider_errors", [])
            if set(errors) & {
                "authentication",
                "authorization",
                "provider_unavailable",
                "rate_limit",
            }:
                print(json.dumps(dict(stopped="provider_failure", case=identifier)), flush=True)
                break
    finally:
        checks = {
            key: all(sha(storage / p) == h for p, h in receipt[key].items())
            for key in ("parent_evidence_hashes", "local_hashes")
        }
        atomic_json(output / "preservation.json", checks)
        assert all(checks.values()), checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--storage-root", type=Path, required=True)
    args = parser.parse_args()
    storage = args.storage_root.resolve()
    output = storage / "artifacts/evidence/QWEN-THINK-01/live-final"
    (prepare if args.mode == "prepare" else validate)(storage, output)


if __name__ == "__main__":
    main()
