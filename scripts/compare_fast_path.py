"""Compare paired PERF-01 timings and released semantics, never tune source oracles."""

import json
from pathlib import Path
from statistics import median

from profile_fast_path import save


def semantic_payload(value, *, financial_execution=False):
    if isinstance(value, dict):
        ignored = {
            "request_id",
            "latency_ms",
            "total_latency_ms",
            "build_ms",
            "search_ms",
            "retrieval_ms",
            "stage_latency_ms",
        }
        if financial_execution:
            # These M5 invocation identities are generated anew for each run.
            # M6 outcomes and persisted verified-claim identities remain compared.
            ignored |= {
                "plan_id",
                "source_plan_id",
                "supervisor_plan_id",
                "planner_plan_id",
                "candidate_id",
            }
        return {
            k: semantic_payload(
                v, financial_execution=financial_execution or k == "financial_execution"
            )
            for k, v in value.items()
            if k not in ignored
        }
    if isinstance(value, list):
        return [semantic_payload(v, financial_execution=financial_execution) for v in value]
    return value


def main():
    base = Path("artifacts/evidence/PERF-01")
    before, after = [
        json.loads((base / f"{phase}.json").read_bytes()) for phase in ("baseline", "after")
    ]
    assert before["seed_sha256"] == after["seed_sha256"]
    rows = []
    semantic_fields = [
        "status",
        "answer_vi",
        "citations",
        "caveats",
        "limitations",
        "used_verified_claim_ids",
        "rejected_claims",
        "deferred_claims",
    ]
    trace_fields = [
        "native_decisions",
        "firewall_decision",
        "m7_status",
        "unanswered_requirements",
        "selected_agents",
        "executed_agents",
    ]
    for a, b in zip(before["cases"], after["cases"], strict=True):
        assert (a["case_id"], a["question"], a["force_refresh"]) == (
            b["case_id"],
            b["question"],
            b["force_refresh"],
        )
        suffix = "refresh" if a["force_refresh"] else "reuse"
        x, y = [
            json.loads((base / phase / f"{a['case_id']}-{suffix}.json").read_bytes())
            for phase in (before.get("trace_phase", "baseline"), "after")
        ]
        differences = [k for k in semantic_fields if x[k] != y[k]]
        differences += ["trace." + k for k in trace_fields if x["trace"][k] != y["trace"][k]]
        if semantic_payload(x) != semantic_payload(y):
            differences.append("normalized_full_payload")
        rows.append(
            dict(
                case_id=a["case_id"],
                force_refresh=a["force_refresh"],
                before_ms=a["elapsed_ms"],
                after_ms=b["elapsed_ms"],
                improvement_percent=100 * (1 - b["elapsed_ms"] / a["elapsed_ms"]),
                semantic_differences=differences,
                before_mode=a["mode"],
                after_mode=b["mode"],
            )
        )
    summary = {}
    for label, refresh in [("force_refresh", True), ("reuse_request", False)]:
        selected = [r for r in rows if r["force_refresh"] == refresh]
        a, b = [median(r[f"{phase}_ms"] for r in selected) for phase in ("before", "after")]
        summary[label] = dict(before_ms=a, after_ms=b, improvement_percent=100 * (1 - b / a))
    final_ledger_equal = (
        base / before.get("trace_phase", "baseline") / "BBS_2025/ledger/verified-claims.json"
    ).read_bytes() == (base / "after/BBS_2025/ledger/verified-claims.json").read_bytes()
    save(
        base / "comparison.json",
        dict(
            cases=rows,
            medians=summary,
            correctness_regressions=sum(bool(r["semantic_differences"]) for r in rows),
            provider_calls=0,
            final_ledger_bytes_equal=final_ledger_equal,
            sample_limit="six offline cases, no P95/system-wide claim",
        ),
    )
    print(json.dumps(summary, indent=2))
    assert not any(r["semantic_differences"] for r in rows), "semantic_regression_requires_review"
    assert final_ledger_equal, "persisted_record_drift_requires_review"


if __name__ == "__main__":
    main()
