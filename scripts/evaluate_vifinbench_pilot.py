"""Offline post-hoc Pilot report from saved outputs and explicit reviewer verdicts."""

import argparse
import json
from collections import Counter
from pathlib import Path

from run_vifinbench_pilot import pilot_inputs, sha
from vietnamese_financial_multi_agent.core.persistence import atomic_json

VERDICTS = {"correct", "incorrect", "partial", "abstain"}


def resolve_pointer(document, pointer):
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError("invalid_json_pointer")
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        document = document[int(token)] if isinstance(document, list) else document[token]
    return document


def evaluate(storage, run, reviews):
    receipt = json.loads((run / "receipt.json").read_bytes())
    gold = {
        row["id"]: row
        for path in pilot_inputs(storage)
        for row in map(json.loads, path.read_text(encoding="utf-8-sig").splitlines())
    }
    cases = json.loads((run / "questions-only.json").read_bytes())
    assert set(reviews) == {c["id"] for c in cases}, "review_must_cover_exact_run"
    assert all(sha(storage / p) == h for p, h in receipt["pilot_hashes"].items())
    rows = []
    for case in cases:
        identifier = case["id"]
        saved = json.loads((run / "results" / f"{identifier}.json").read_bytes())
        response = saved.get("response", {})
        trace = response.get("trace", {})
        review = reviews[identifier]
        assert review["verdict"] in VERDICTS and review["reason"]
        assert case["question"] == gold[identifier]["question"]
        ledger_path = run / "ledgers" / identifier / "verified-claims.json"
        ledger = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
        # Membership control only; financial semantics remain an explicit reviewer judgement.
        used = set(response.get("used_verified_claim_ids", []))
        assert all(claim in ledger for claim in used)
        citations = []
        for citation in response.get("citations", []):
            source_refs = citation["source_citations"]
            resolved = []
            assert set(citation["bound_verified_claim_ids"]) <= used
            for source in source_refs:
                reference = source["source"]["reference"]
                page = reference["anchor"]["page"]
                relative = (
                    Path("ViFinBench/refined")
                    / page["symbol"]
                    / page["year"]
                    / f"page_{page['page']:04}.json"
                ).as_posix()
                assert relative in receipt["source_hashes"]
                assert sha(storage / relative) == receipt["source_hashes"][relative]
                assert page["source_ref"] == "json:sha256:" + receipt["source_hashes"][relative]
                value = resolve_pointer(
                    json.loads((storage / relative).read_bytes()), reference["source_pointer"]
                )
                resolved.append(
                    dict(
                        artifact=relative,
                        pointer=reference["source_pointer"],
                        value=value,
                        source_digest_verified=True,
                    )
                )
            citations.append(dict(citation=citation, resolved=resolved))
        events = [json.loads(p.read_bytes()) for p in (run / "provider").glob("*.json")]
        events = [e for e in events if e["case_id"] == identifier]
        assert len(events) == saved["transport_attempts"]
        rows.append(
            dict(
                id=identifier,
                group=case["group"],
                difficulty=case["difficulty"],
                question=case["question"],
                gold=gold[identifier]["answer"],
                gold_evidence=gold[identifier].get("evidence"),
                gold_supporting_evidence=gold[identifier].get("supporting_evidence", []),
                system_answer=response.get("answer_vi"),
                status=response.get("status", "runner_exception"),
                **review,
                citations=citations,
                citation_count=len(citations),
                wall_seconds=saved["wall_seconds"],
                pipeline_seconds=saved.get("pipeline_seconds"),
                calls=len(events),
                known_tokens=sum(
                    e.get("response", {}).get("usage", {}).get("total_tokens") or 0 for e in events
                ),
                unknown_usage=sum(
                    e.get("response", {}).get("usage", {}).get("total_tokens") is None
                    for e in events
                ),
                native_decisions=trace.get("native_decisions", {}),
                planner_coverage=trace.get("m7_lite", {}).get("coverage"),
                tools=dict(Counter(t["request"]["tool"] for t in trace.get("tool_calls", []))),
                trace_file=f"results/{identifier}.json",
                ledger_file=f"ledgers/{identifier}/verified-claims.json",
            )
        )
    metrics = {}
    for group in ("all", "single_hop", "multi_hop", "numerical"):
        subset = [r for r in rows if group == "all" or r["group"] == group]
        if not subset:
            continue
        counts = Counter(r["verdict"] for r in subset)
        answered = len(subset) - counts["abstain"]
        metrics[group] = dict(
            n=len(subset),
            verdicts=dict(counts),
            accuracy=counts["correct"] / len(subset),
            answer_coverage=answered / len(subset),
            selective_accuracy=counts["correct"] / answered if answered else None,
            calls=sum(r["calls"] for r in subset),
            wall_seconds=round(sum(r["wall_seconds"] for r in subset), 3),
            citations=sum(r["citation_count"] for r in subset),
        )
    return dict(
        metrics=metrics,
        rows=rows,
        judgement="manual post-hoc; no LLM judge; partial receives no accuracy credit",
        provenance="refined JSON only, not PDF-verified",
        evaluated_run_sha256=sha(run / "receipt.json"),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    args = parser.parse_args()
    output = args.run / "evaluation.json"
    if output.exists():
        parser.error("evaluation already exists; keep before/after runs separate")
    report = evaluate(args.storage_root, args.run, json.loads(args.reviews.read_bytes()))
    atomic_json(output, report)
    lines = [
        "# E2E-VAL-01 — Đối chiếu từng QA",
        "",
        "Gold chỉ được mở hậu kiểm. Verdict do agent đánh giá từ output/traces; "
        "chưa có reviewer thứ hai. Nguồn JSON-only, chưa PDF-verified.",
        "",
        "Accuracy = correct/N; coverage = (correct+partial+incorrect)/N; "
        "partial không nhận điểm accuracy. Coverage planner được lưu riêng trong JSON.",
        "",
        "| Nhóm | N | Verdicts | Accuracy | Coverage | Calls | Wall s |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for group, m in report["metrics"].items():
        lines.append(
            f"| {group} | {m['n']} | {m['verdicts']} | {m['accuracy']:.2%} | "
            f"{m['answer_coverage']:.2%} | {m['calls']} | {m['wall_seconds']} |"
        )
    for row in report["rows"]:
        lines.extend(
            [
                "",
                f"## {row['id']} — {row['verdict']}",
                "",
                row["question"],
                "",
                f"**Gold:** {row['gold']['display']}",
                "",
                f"**Hệ thống:** {row['system_answer']}",
                "",
                f"**Đánh giá:** {row['reason']}",
                "",
                f"Status {row['status']}; {row['calls']} calls; {row['wall_seconds']}s gồm load; "
                f"{row['pipeline_seconds']}s pipeline; {row['known_tokens']} known tokens; "
                f"{row['unknown_usage']} unknown usage; {row['citation_count']} citations. "
                f"M6 {row['native_decisions']}; tools {row['tools']}.",
                "",
                f"[Agent/tool trace]({row['trace_file']}), [Ledger]({row['ledger_file']}). "
                "Gold/source references và kiểm pointer/hash nằm trong evaluation.json.",
                "",
            ]
        )
        for citation in row["citations"]:
            for ref in citation["resolved"]:
                lines.append(
                    f"- {ref['artifact']} `{ref['pointer']}` → `{ref['value']}`; SHA256 khớp."
                )
    (args.run / "qa-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
