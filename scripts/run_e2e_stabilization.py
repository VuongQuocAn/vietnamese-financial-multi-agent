"""Replay exactly the frozen nine QA against the pinned corpus; no Gold in runtime."""

import argparse
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import vietnamese_financial_multi_agent as package

ROOT = Path(__file__).resolve().parents[1]
package.__path__ = [str(ROOT / "src")]

from run_vifinbench_pilot import run, sha  # noqa: E402
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest  # noqa: E402
from vietnamese_financial_multi_agent.core.persistence import atomic_json  # noqa: E402


def prepare(storage, output):
    FinancialQARequest(
        question="Validate run budget", max_provider_calls=10, request_timeout_seconds=600
    )
    baseline_path = storage / "artifacts/evidence/QWEN-THINK-01/live-final/receipt.json"
    baseline = json.loads(baseline_path.read_bytes())
    manifest = storage / "artifacts/evidence/E2E-VAL-01/baseline-nine/questions-only.json"
    cases = json.loads(manifest.read_bytes())
    assert len(cases) == 9 and len({c["id"] for c in cases}) == 9
    priors = [
        storage / "artifacts/evidence/E2E-STABILIZE-01" / name
        for name in ("live-nine-final", "live-release")
    ]
    prior_used = sum(len(list((prior / "provider").glob("*.json"))) for prior in priors)
    assert prior_used < 90
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
            prior_evidence_hashes={
                p.relative_to(storage).as_posix(): sha(p)
                for prior in priors
                for p in prior.rglob("*")
                if p.is_file()
            },
            prior_attempts=prior_used,
            task_total_call_cap=90,
            settings=dict(
                total_call_cap=90 - prior_used, per_question_cap=10, timeout_seconds=600, retries=0
            ),
            client_profile=dict(
                QWEN_THINKING_BUDGET="true",
                stage_timeout_seconds=180,
                max_output_tokens_base=8192,
                prompt_token_estimate="ceil(chars/2), reserve1024, output clamped inside24576",
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
    wire = []

    def observe(response):
        response.read()
        event = dict(http_status=response.status_code)
        try:
            raw = response.json()
            if response.status_code == 200:
                choice = raw.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content") or ""
                event.update(
                    finish_reason=choice.get("finish_reason"), inline_thinking="</think>" in content
                )
            else:
                # Whitelisted diagnostics only; never serialize server messages,
                # which can echo inputs or credentials.
                message = str(raw.get("error", raw.get("detail", ""))).lower()
                event["context_length_error"] = bool(
                    re.search(
                        r"context length|max_model_len|maximum context|maximum model", message
                    )
                )
        except ValueError:
            event["non_json_response"] = True
        wire.append(event)
        atomic_json(output / "wire-summary.json", wire)

    try:
        run(ROOT, storage, output, None, corpus=storage / receipt["corpus"], response_hook=observe)
    finally:
        checks = {
            key: all(sha(storage / p) == h for p, h in receipt[key].items())
            for key in ("local_hashes", "parent_evidence_hashes", "prior_evidence_hashes")
        }
        atomic_json(output / "preservation.json", checks)
        assert all(checks.values()), checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--storage-root", type=Path, required=True)
    args = parser.parse_args()
    storage = args.storage_root.resolve()
    output = storage / "artifacts/evidence/E2E-STABILIZE-01/final-nine"
    (prepare if args.mode == "prepare" else validate)(storage, output)


if __name__ == "__main__":
    main()
