"""Bounded conversion of accepted M5 saved traces; no orchestration or live calls."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from vietnamese_financial_multi_agent.agents import OrchestrationResult
from vietnamese_financial_multi_agent.verification import VerificationInput, to_verification_input

CASE_IDS = (
    "E01",
    "E02",
    "E03",
    "E06",
    "E10",
    "E11",
    "E13",
    "E17",
    "E18",
    "E23",
    "E24",
    "E25",
    "E26",
    "E29",
    "E30",
    "E31",
    "E34",
    "E35",
    "E36",
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_new(path, payload):
    # Source traces are immutable and existing evaluation outputs are never overwritten.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def evaluate(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    source_map = json.loads(
        (root / "artifacts/evidence/M5-08-review/offline-source-map.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = {
        c["id"]: c
        for c in json.loads((root / "evaluation/m5-08-scenarios.json").read_text(encoding="utf-8"))
    }
    sources = []
    for case_id in CASE_IDS:
        entry = next(e for e in source_map if e["id"] == case_id)
        case = manifest[case_id]
        controlled = any(
            case.get(k)
            for k in ("injection", "specialist_failure", "projection_fault", "aggregation_control")
        ) or case_id in {"E29", "E30"}
        sources.append(
            (
                case_id,
                root / entry["path"],
                entry["sha256"],
                "synthetic_control_on_persisted_BBS"
                if controlled
                else "persisted_BBS_mock_generation",
            )
        )
    for case_id in ("E11", "E37"):
        path = root / f"artifacts/evidence/M5-08-live-saved-replay/result-{case_id}.json"
        group = "saved_Gemini_response_replay"
        if manifest[case_id].get("injection"):
            group += "_with_synthetic_control"
        sources.append((f"replay-{case_id}", path, digest(path), group))

    rows = []
    for case_id, path, expected_hash, group in sources:
        assert digest(path) == expected_hash, f"Accepted trace hash mismatch: {case_id}"
        source = OrchestrationResult.model_validate_json(path.read_text(encoding="utf-8"))
        before = source.model_dump_json()
        batch = to_verification_input(source)
        wire = batch.model_dump_json()
        assert batch == to_verification_input(source), case_id
        assert VerificationInput.model_validate_json(wire) == batch, case_id
        assert len(batch.claims) == len(source.candidates), case_id
        assert batch.conflicts == source.conflicts, case_id
        for name in (
            "caveats",
            "risks",
            "missing_evidence",
            "uncovered_requirements",
            "stop_conditions",
            "errors",
            "question",
            "context",
        ):
            assert getattr(batch, name) == getattr(source, name), (case_id, name)
        for original, claim in zip(source.candidates, batch.claims, strict=True):
            restored = claim.model_dump(
                exclude={"provenance", "verification_status", "decision", "findings"}
            )
            restored.update(claim.provenance.model_dump(exclude={"m5_candidate_id"}))
            assert restored == original.model_dump(), (case_id, original.candidate_id)
            assert claim.candidate_id == claim.provenance.m5_candidate_id, case_id
            assert claim.verification_status == "pending" and claim.decision is None, case_id
            assert not claim.financial_fact_verified and not claim.findings, case_id
        assert batch.verification_status == "pending" and not batch.financial_fact_verified
        assert source.model_dump_json() == before and digest(path) == expected_hash, case_id
        save_new(output / f"batch-{case_id}.json", json.loads(wire))
        row = dict(
            id=case_id,
            group=group,
            source=path.relative_to(root).as_posix(),
            source_sha256=expected_hash,
            passed=True,
            status=batch.orchestration_status,
            claims=len(batch.claims),
            conflicts=len(batch.conflicts),
            origins=sum(len(c.provenance.origins) for c in batch.claims),
            calculations=sum(c.calculation is not None for c in batch.claims),
            issues=[i.model_dump() for i in batch.issues],
        )
        rows.append(row)
        print(
            f"{case_id}: PASS ({group}, {len(batch.claims)} claims, {len(batch.issues)} issues)",
            flush=True,
        )
    summary = dict(
        passed=len(rows),
        total=len(sources),
        actual_llm_calls=0,
        groups=dict(Counter(r["group"] for r in rows)),
        statuses=dict(Counter(r["status"] for r in rows)),
        claims=sum(r["claims"] for r in rows),
        calculations=sum(r["calculations"] for r in rows),
        conflicts=sum(r["conflicts"] for r in rows),
        issues=sum(len(r["issues"]) for r in rows),
        scope="Conversion integrity only; no financial verification accuracy or new M5 benchmark.",
        rows=rows,
    )
    save_new(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evaluate(Path.cwd().resolve(), args.output.resolve())
