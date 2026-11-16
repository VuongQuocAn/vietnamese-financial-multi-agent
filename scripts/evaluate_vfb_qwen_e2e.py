"""Offline evaluation artifact assembly; never imported by the answering runner."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median

from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import resolve_pointer

VERDICTS = {"CORRECT", "PARTIAL", "INCORRECT", "NO_ANSWER"}


def load(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(root, output, *, expected_count=15, task_id="VFB-E2E-03"):
    cases = load(output / "questions-only.json")
    # Enforce phase separation: all selected answers must exist before reading Gold.
    assert expected_count in {5, 15} and len(cases) == expected_count
    results = {c["id"]: load(output / "results" / f"{c['id']}.json") for c in cases}
    judgments = load(output / "judgments.json")
    assert set(judgments) == set(results)
    receipt = load(output / "implementation.json")
    assert digest(output / "questions-only.json") == receipt["question_manifest_sha256"]
    assert all(
        digest(root / name) == expected for name, expected in receipt["runtime_hashes"].items()
    )
    assert all(
        digest(root / name) == expected for name, expected in receipt["benchmark_hashes"].items()
    )
    corpus = root / receipt["corpus"]
    inventory = load(corpus / "source-inventory.json")
    sources = {}
    for manifest in inventory.values():
        for page in manifest["pages"]:
            path = root / "ViFinBench/refined" / page["path"]
            assert digest(path) == page["sha256"]
            sources["json:sha256:" + page["sha256"]] = load(path)
    gold = {}
    for group in {c["group"] for c in cases}:
        path = root / "ViFinBench/benchmark" / group / "full.jsonl"
        gold.update(
            {r["id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
        )
    events = [load(p) for p in sorted((output / "provider").glob("[0-9][0-9][0-9].json"))]
    all_records, full_text = (
        [],
        [
            f"# {task_id} — Câu hỏi, Gold và đáp án nguyên văn",
            "",
            f"Gold chỉ được đọc trong hậu kiểm sau khi đủ{len(cases)}result files; không gọi LLM chấm điểm.",
            "",
        ],
    )
    for case in cases:
        identifier = case["id"]
        result, judgment, expected = results[identifier], judgments[identifier], gold[identifier]
        assert judgment["verdict"] in VERDICTS
        assert result["request"]["question"] == expected["question"] == case["question"]
        response = result["response"]
        trace = response["trace"]
        provider = [e for e in events if e["case_id"] == identifier]
        assert result["transport_attempts"] == trace["provider_calls"] == len(provider)
        assert trace["known_total_tokens"] == sum(
            e["response"]["usage"]["total_tokens"] or 0 for e in provider
        )
        checks = []
        for citation in response["citations"]:
            for source in citation["source_citations"]:
                reference = source["source"]["reference"]
                page = reference["anchor"]["page"]
                raw = resolve_pointer(sources[page["source_ref"]], reference["source_pointer"])
                assert source["pdf_page"] is None and not source["financial_fact_verified"]
                checks.append(
                    dict(
                        citation_id=citation["citation_id"],
                        page=page["page"],
                        pointer=reference["source_pointer"],
                        resolved_value=raw,
                        bound_to_released_claims=bool(
                            set(citation["bound_verified_claim_ids"])
                            & set(response["used_verified_claim_ids"])
                        ),
                    )
                )
        assert all(c["bound_to_released_claims"] for c in checks)
        tools = Counter(t.get("request", {}).get("tool", "unknown") for t in trace["tool_calls"])
        gold_evidence = expected["evidence"]
        gold_evidence = gold_evidence if isinstance(gold_evidence, list) else [gold_evidence]
        gold_pages = sorted(
            {e["page"] for e in [*gold_evidence, *expected.get("supporting_evidence", [])]}
        )
        usage = Counter(dict(input_tokens=0, output_tokens=0, total_tokens=0))
        for event in provider:
            for name in ("input_tokens", "output_tokens", "total_tokens"):
                usage[name] += event["response"]["usage"].get(name) or 0
        record = dict(
            **case,
            **judgment,
            gold_answer=expected["answer"],
            gold_evidence=expected["evidence"],
            gold_reasoning=expected.get("reasoning"),
            gold_record=expected,
            system_answer=response["answer_vi"],
            system_status=response["status"],
            gold_pages=gold_pages,
            cited_pages=sorted({c["page"] for c in checks}),
            citations=response["citations"],
            source_checks=checks,
            latency_seconds=result["wall_seconds"],
            load_seconds=result["load_seconds"],
            calls=len(provider),
            usage=dict(usage),
            unknown_usage_calls=sum(
                e["response"]["usage"]["total_tokens"] is None for e in provider
            ),
            agents=trace["executed_agents"],
            tools=dict(tools),
            m6=trace["native_decisions"],
            m5_status=trace["planner_status"],
            m7_status=trace["m7_status"],
            stages=trace["stages"],
            errors=trace["errors"],
        )
        all_records.append(record)
        full_text.extend(
            [
                f"## {identifier} — {judgment['verdict']}",
                "",
                "### Câu hỏi nguyên văn",
                "",
                case["question"],
                "",
                "### Gold Answer nguyên văn (object)",
                "",
                "```json",
                json.dumps(expected["answer"], ensure_ascii=False, indent=2),
                "```",
                "",
                "### Câu trả lời hệ thống nguyên văn",
                "",
                response["answer_vi"],
                "",
                "### Đánh giá hậu kiểm",
                "",
                judgment["assessment"],
                "",
                f"Nguyên nhân: {judgment['root_cause']}",
                "",
                f"Citations: {judgment['citation_assessment']}",
                "",
                f"Trace: `results/{identifier}.json`; {len(provider)}calls; {usage['total_tokens']}known tokens; E2E{result['wall_seconds']}s; load{result['load_seconds']}s.",
                "",
            ]
        )
    summary = {}
    for group in ["single_hop", "multi_hop", "numerical", "all"]:
        subset = [r for r in all_records if group == "all" or r["group"] == group]
        summary[group] = dict(
            count=len(subset),
            verdicts=dict(Counter(r["verdict"] for r in subset)),
            calls=sum(r["calls"] for r in subset),
            tokens=sum(r["usage"]["total_tokens"] for r in subset),
            latency_sum_seconds=round(sum(r["latency_seconds"] for r in subset), 3),
            latency_mean_seconds=round(mean(r["latency_seconds"] for r in subset), 3),
            latency_median_seconds=round(median(r["latency_seconds"] for r in subset), 3),
            load_sum_seconds=round(sum(r["load_seconds"] for r in subset), 3),
        )
    atomic_json(
        output / "evaluation.json",
        dict(evaluated_at_utc=datetime.now(UTC).isoformat(), records=all_records, summary=summary),
    )
    (output / "answers-and-gold.md").write_text("\n".join(full_text), encoding="utf-8")
    fields = [
        "id",
        "group",
        "difficulty",
        "document_alias",
        "verdict",
        "system_status",
        "latency_seconds",
        "load_seconds",
        "calls",
        "usage",
        "agents",
        "tools",
        "m6",
        "root_cause",
    ]
    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in all_records)
    labels_valid = all(
        set(map(int, re.findall(r"\[(\d+)\]", r["system_answer"])))
        <= {c["display_number"] for c in r["citations"]}
        for r in all_records
    )
    assert labels_valid
    atomic_json(
        output / "integrity.json",
        dict(
            runtime_hashes_unchanged=True,
            benchmark_hashes_unchanged=True,
            question_manifest_unchanged=True,
            source_hashes_verified=len(sources),
            question_count=len(results),
            transport_trace_counts_match=True,
            citation_labels_valid=labels_valid,
            citation_source_references_resolved=sum(len(r["source_checks"]) for r in all_records),
            json_only_no_pdf_verification=True,
            gold_evaluation_phase_only=True,
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/VFB-E2E-03/run-v2"))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    evaluate(project, project / args.output)
