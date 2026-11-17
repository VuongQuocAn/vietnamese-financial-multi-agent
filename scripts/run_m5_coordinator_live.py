"""Bounded new questions on pinned real JSON filings; no benchmark/Gold input."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from run_vfb_qwen_e2e import digest, run
from vietnamese_financial_multi_agent.core.persistence import atomic_json

CASES = [
    dict(
        id="M5C-SH-01",
        group="single_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="Doanh thu thuần năm 2025 của BBS là bao nhiêu?",
    ),
    dict(
        id="M5C-MH-01",
        group="multi_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="BBS năm 2025: nêu lợi nhuận sau thuế và lưu chuyển tiền thuần từ hoạt động kinh doanh, sau đó dùng hai kết quả này tính dòng tiền kinh doanh trừ lợi nhuận sau thuế. Chỉ so sánh số học, không suy nguyên nhân.",
    ),
    dict(
        id="M5C-MH-02",
        group="multi_hop",
        difficulty="probe",
        document_alias="ADC_2021",
        question="ADC năm 2021: nêu doanh thu thuần và lưu chuyển tiền thuần từ hoạt động kinh doanh, sau đó lấy dòng tiền kinh doanh chia doanh thu thuần để tính tỷ lệ phần trăm. Sử dụng kết quả tra cứu của hai phần trước.",
    ),
]


def prepare(root, output, ids, call_cap):
    cases = [c for c in CASES if not ids or c["id"] in ids]
    output.mkdir(parents=True, exist_ok=False)
    (output / "provider").mkdir()
    (output / "results").mkdir()
    atomic_json(output / "questions-only.json", cases)
    source_hashes = {}
    for alias in {c["document_alias"] for c in cases}:
        company, year = alias.split("_")
        for path in sorted((root / "ViFinBench/refined" / company / year).rglob("*.json")):
            source_hashes[path.relative_to(root).as_posix()] = digest(path)
    atomic_json(
        output / "implementation.json",
        dict(
            baseline_sha=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            committed=False,
            prepared_at_utc=datetime.now(UTC).isoformat(),
            benchmark_hashes={},
            runtime_hashes={
                p.relative_to(root).as_posix(): digest(p)
                for p in sorted((root / "src").rglob("*.py"))
            },
            source_hashes=source_hashes,
            runner_sha256=digest(root / "scripts/run_vfb_qwen_e2e.py"),
            targeted_runner_sha256=digest(Path(__file__)),
            corpus="artifacts/evidence/VFB-IMPORT-03/full-final",
            question_manifest_sha256=digest(output / "questions-only.json"),
            settings=dict(
                provider="qwen",
                adaptive_coordinator=True,
                max_calls_per_question=8,
                total_call_cap=call_cap,
                timeout_seconds=300,
                graph_enabled=True,
                retries=0,
            ),
        ),
    )
    print(json.dumps(dict(prepared=len(cases), call_cap=call_cap)), flush=True)


def check_sources(root, output):
    receipt = json.loads((output / "implementation.json").read_bytes())
    assert all(
        digest(root / name) == expected for name, expected in receipt["source_hashes"].items()
    )
    print(json.dumps(dict(source_hashes_unchanged=len(receipt["source_hashes"]))), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/M5-COORD-01/live-v1")
    )
    parser.add_argument("--ids", nargs="+", choices=[c["id"] for c in CASES])
    parser.add_argument("--call-cap", type=int, choices=range(1, 25), default=18)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    destination = (project / args.output).resolve()
    if not destination.is_relative_to(project / "artifacts/evidence/M5-COORD-01"):
        parser.error("output outside M5-COORD-01")
    if args.mode == "prepare":
        prepare(project, destination, args.ids, args.call_cap)
    else:
        try:
            run(project, destination, args.ids)
        finally:
            check_sources(project, destination)
