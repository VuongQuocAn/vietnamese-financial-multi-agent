"""PERF-01: six persisted QA cases, offline paired timings; private outputs ignored."""

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from functools import wraps
from pathlib import Path
from time import perf_counter

from evaluate_generalization import pipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence.composition_graph import CompositionGraphView
from vietnamese_financial_multi_agent.evidence.document_repository import DocumentEvidenceRepository
from vietnamese_financial_multi_agent.evidence.search import EvidenceSearchIndex
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["baseline", "baseline-correction", "after"])
    args = parser.parse_args()
    root = Path.cwd()
    base = root / "artifacts/evidence/PERF-01"
    destination = base / f"{args.phase}.json"
    if destination.exists():
        raise ValueError("measurement_already_exists")
    measurements = defaultdict(lambda: dict(calls=0, inclusive_ms=0.0))

    def instrument(cls, name):
        original = getattr(cls, name)

        @wraps(original)
        def timed(*a, **kw):
            started = perf_counter()
            try:
                return original(*a, **kw)
            finally:
                row = measurements[f"{cls.__name__}.{name}"]
                row["calls"] += 1
                row["inclusive_ms"] += (perf_counter() - started) * 1000

        setattr(cls, name, timed)

    for cls, names in (
        (VerifiedClaimRepository, ["_read", "query", "admit_many"]),
        (DocumentEvidenceRepository, ["_read", "list_by_document"]),
        (EvidenceSearchIndex, ["__init__", "search"]),
        (CompositionGraphView, ["__init__"]),
    ):
        for name in names:
            instrument(cls, name)
    questions = json.loads((root / "artifacts/evidence/GEN-02/questions.json").read_bytes())
    questions = [
        next(q for q in questions if q["id"] == i)
        for i in ["D01", "D05", "D17", "D22", "D18", "D23"]
    ]
    inputs = list((root / "artifacts/evidence/EXT-01").glob("*/composition.json"))
    inputs += [root / "artifacts/evidence/EXT-01/repository/document-evidence.json"]
    inputs += list((root / "artifacts/source-quality").glob("*.json"))
    inputs += [
        root / "artifacts/evidence/GEN-02" / n
        for n in [
            "questions.json",
            "sources.json",
            "development-oracles.json",
            "holdout-oracles.json",
        ]
    ]
    initial = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if args.phase == "baseline":
        save(base / "input-hashes.json", initial)
    else:
        assert initial == json.loads((base / "input-hashes.json").read_bytes())
    seed = root / "artifacts/evidence/QA-01b/after-topic-fix/BBS_2025/ledger/verified-claims.json"
    target = base / args.phase / "BBS_2025/ledger/verified-claims.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, target)
    started = perf_counter()
    p, _ = pipeline(root, "BBS_2025", base / args.phase)
    initialization_ms = (perf_counter() - started) * 1000

    # A provider call is a hard error, including accidental optional paths.
    class NoGateway:
        def __getattr__(self, name):
            raise AssertionError("PERF-01 forbids provider calls")

    p.gateway = NoGateway()
    rows = []
    for q in questions:
        for refresh in (True, False):
            measurements.clear()
            request = FinancialQARequest(
                question=q["question"],
                force_refresh=refresh,
                allow_gateway=False,
                execution_mode="deterministic",
            )
            started = perf_counter()
            response = p.run(request)
            elapsed = (perf_counter() - started) * 1000
            actual = response.model_dump(mode="json")
            assert not response.trace.provider_calls and response.status != "internal_error"
            save(base / args.phase / f"{q['id']}-{'refresh' if refresh else 'reuse'}.json", actual)
            rows.append(
                dict(
                    case_id=q["id"],
                    question=q["question"],
                    force_refresh=refresh,
                    elapsed_ms=elapsed,
                    mode=response.mode,
                    status=response.status,
                    stages={k: s.model_dump(mode="json") for k, s in response.trace.stages.items()},
                    components=dict(measurements),
                )
            )
            print(q["id"], refresh, round(elapsed), response.mode, flush=True)
    assert initial == {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs
    }
    save(
        destination,
        dict(
            head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            initialization_ms=initialization_ms,
            cases=rows,
            seed_sha256=hashlib.sha256(seed.read_bytes()).hexdigest(),
            timings="inclusive parent/child; never sum nested components",
            provider_calls=0,
            input_hashes_unchanged=True,
        ),
    )


if __name__ == "__main__":
    main()
