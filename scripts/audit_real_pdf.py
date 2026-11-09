"""Summarize E2E-02 observations with explicit human/Codex PDF judgments.

No classification is inferred from completed_with_caveats or M6 ACCEPT.
judgments.json is a separate, per-question review against frozen PDF references.
"""

import argparse
import csv
from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

from evaluate_real_pdf import digest, read, runtime, save


def distribution(values):
    values = sorted(values)
    if not values:
        return None
    # Explicit nearest-rank P90; one observation per question, not inference.
    return dict(
        n=len(values),
        median_ms=median(values),
        p90_ms=values[(9 * len(values) + 9) // 10 - 1],
        min_ms=values[0],
        max_ms=values[-1],
        above_10s=sum(v > 10000 for v in values),
        above_30s=sum(v > 30000 for v in values),
        above_60s=sum(v > 60000 for v in values),
    )


def audit(base):
    freeze = read(base / "freeze.json")
    assert all(digest(base / n) == h for n, h in freeze["files"].items())
    runtime(base, freeze["runtime_head"])
    from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

    questions = {q["id"]: q for q in read(base / "questions.json")}
    refs = {r["id"]: r for r in read(base / "reference.json")}
    judgments = {j["id"]: j for j in read(base / "judgments.json")}
    rows = read(base / "results.json")
    assert len(rows) == len(judgments) == len(questions) == 40
    entries = {
        e.identity.verified_claim_id: e for e in VerifiedClaimRepository(base / "ledger").list_all()
    }
    inputs = read(base / "catalog-inputs.json")
    facts = {
        (f["document_id"], f["snapshot_id"], f["local_observation_id"]): f for f in inputs["facts"]
    }
    counts = Counter(
        dict.fromkeys(
            (
                "CORRECT",
                "PARTIAL",
                "INCORRECT",
                "JUSTIFIED_ABSTAIN",
                "UNJUSTIFIED_ABSTAIN",
                "CLARIFICATION",
                "RUNTIME_FAILURE",
            ),
            0,
        )
    )
    levels, modes = defaultdict(Counter), Counter()
    selected, executed, tools = Counter(), Counter(), Counter()
    times, stages = defaultdict(list), defaultdict(list)
    provider_calls = tokens = unknown = 0
    citation_rows, claim_rows, audited = [], [], []
    latency = []
    for row in rows:
        q, ref, judgment = questions[row["id"]], refs[row["id"]], judgments[row["id"]]
        actual = row.get("actual", {})
        trace = actual.get("trace", {})
        claim_errors = []
        for identity in actual.get("used_verified_claim_ids", []):
            entry = entries.get(identity)
            errors = []
            if entry is None:
                errors.append("missing_ledger_entry")
            else:
                if entry.identity.document_id != ref["document_id"]:
                    errors.append("wrong_document")
                claim = entry.accepted_claim
                if entry.identity.kind != "document":
                    calc = claim.calculation
                    if calc:
                        values = []
                        for op in calc.trace.operands:
                            r = op.observation
                            f = facts.get((r.document_id, r.snapshot_id, r.local_id))
                            if not f:
                                errors.append("operand_not_in_original_catalog")
                            else:
                                values.append(Decimal(f["value"]["normalized_value"]))
                        if len(values) == 2:
                            expected = (
                                values[0] / values[1] - int(calc.formula_id == "revenue_yoy")
                            ) * 100
                            if abs(Decimal(calc.result) - expected) > Decimal("0.005"):
                                errors.append("independent_decimal_mismatch")
                        else:
                            errors.append("formula_NOT_VERIFIABLE")
                    for support in claim.supporting_evidence:
                        r = support.reference.observation
                        if r:
                            f = facts.get((r.document_id, r.snapshot_id, r.local_id))
                            if not f or Decimal(support.value) != Decimal(
                                f["value"]["normalized_value"]
                            ):
                                errors.append("canonical_value_mismatch")
                            elif (
                                support.canonical_item_id != f["canonical_item_id"]
                                or support.scale != f["context"]["scale"]
                                or support.period != f["context"]["period"]
                                or support.unit != f["value"]["unit"]
                                or support.company_id != f["company_id"]
                            ):
                                errors.append("financial_context_mismatch")
            claim_rows.append(dict(id=q["id"], claim_id=identity, errors=errors))
            claim_errors.extend(errors)
        for citation in actual.get("citations", []):
            errors = []
            if citation["document_id"] != ref["document_id"]:
                errors.append("wrong_document")
            if citation["pdf_page"] not in ref["expected_pages"]:
                errors.append("page_outside_reference_requires_review")
            for identity in citation["bound_verified_claim_ids"]:
                entry = entries.get(identity)
                if not entry or identity not in actual["used_verified_claim_ids"]:
                    errors.append("not_bound_to_released_ledger_claim")
                elif any(
                    source not in [c.model_dump(mode="json") for c in entry.citations]
                    for source in citation["source_citations"]
                ):
                    errors.append("source_binding_mismatch")
            for source in citation["source_citations"]:
                anchor = source["source"]["reference"]["anchor"]
                if anchor["page"]["page"] != citation["pdf_page"]:
                    errors.append("source_page_mismatch")
            citation_rows.append(
                dict(
                    id=q["id"],
                    citation_id=citation["citation_id"],
                    page=citation["pdf_page"],
                    errors=errors,
                    pdf_support=judgment.get("citation_overrides", {}).get(
                        citation["source_locator"]["source_pointer"],
                        judgment.get("citation_default", judgment["citation_correct"]),
                    ),
                )
            )
        classification = judgment["classification"]
        assert classification in {
            "CORRECT",
            "PARTIAL",
            "INCORRECT",
            "JUSTIFIED_ABSTAIN",
            "UNJUSTIFIED_ABSTAIN",
            "CLARIFICATION",
            "RUNTIME_FAILURE",
        }
        counts[classification] += 1
        levels[q["level"]][classification] += 1
        mode = actual.get("mode", "RUNTIME_FAILURE")
        modes[mode] += 1
        times["all"].append(row["elapsed_ms"])
        times[f"L{q['level']}"].append(row["elapsed_ms"])
        times[mode].append(row["elapsed_ms"])
        if actual.get("used_verified_claim_ids"):
            times["answered_only"].append(row["elapsed_ms"])
        if mode == "FRESH_M5_M6_M7" and any(
            name in trace.get("executed_agents", [])
            for name in (
                "profitability",
                "liquidity_and_leverage",
                "cash_flow_and_earnings_quality",
            )
        ):
            times["fresh_financial_only"].append(row["elapsed_ms"])
        selected.update(trace.get("selected_agents", []))
        executed.update(trace.get("executed_agents", []))
        tools.update(c["tool"] for c in trace.get("tool_calls", []))
        provider_calls += trace.get("provider_calls", 0)
        tokens += trace.get("known_total_tokens", 0)
        unknown += trace.get("calls_with_unknown_tokens", 0)
        stage_values = {
            name: stage["latency_ms"]
            for name, stage in trace.get("stages", {}).items()
            if stage["status"] != "NOT_EXECUTED"
        }
        for name, value in stage_values.items():
            stages[name].append(value)
        retrieval = [
            c["latency_ms"]
            for c in trace.get("tool_calls", [])
            if "latency_ms" in c
            and c["tool"]
            in {"find_financial_facts", "get_evidence_sources", "search_document_evidence"}
        ]
        context_ms = row.get("conversation", {}).get("resolution_latency_ms")
        if context_ms is not None:
            times["conversation_resolution"].append(context_ms)
        latency.append(
            dict(
                id=q["id"],
                level=q["level"],
                mode=mode,
                total_ms=row["elapsed_ms"],
                conversation_resolution_ms=context_ms,
                measured_retrieval_tool_ms=sum(retrieval) if retrieval else None,
                **stage_values,
            )
        )
        audited.append(dict(**judgment, claim_audit_errors=claim_errors))
    save(base / "audit.json", dict(questions=audited, claims=claim_rows, citations=citation_rows))
    with (base / "latency.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = list(dict.fromkeys(k for row in latency for k in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(latency)
    summary = dict(
        runtime_head=freeze["runtime_head"],
        counts=dict(counts),
        by_level=dict(levels),
        ratios={key: value / 40 for key, value in counts.items()},
        modes=dict(modes),
        latency={name: distribution(values) for name, values in times.items()},
        stage_latency_inclusive={name: distribution(values) for name, values in stages.items()},
        selected_agents=dict(selected),
        executed_agents=dict(executed),
        tools=dict(tools),
        provider_calls=provider_calls,
        known_tokens=tokens,
        calls_with_unknown_tokens=unknown,
        citation_occurrences=len(citation_rows),
        citation_accuracy=sum(c["pdf_support"] is True and not c["errors"] for c in citation_rows)
        / len(citation_rows)
        if citation_rows
        else None,
        citation_structural_errors=sum(bool(c["errors"]) for c in citation_rows),
        citation_pdf_supported=sum(c["pdf_support"] is True for c in citation_rows),
        citation_not_verifiable=sum(c["pdf_support"] == "NOT_VERIFIABLE" for c in citation_rows),
        independent_claim_errors=sum(bool(c["errors"]) for c in claim_rows),
        issue_severity=dict(Counter(i["severity"] for i in read(base / "issues.json"))),
        dimensions={
            name: dict(Counter(str(j[name]) for j in judgments.values()))
            for name in (
                "citation_correct",
                "financial_value_correct",
                "context_correct",
                "explanation_supported",
                "answer_complete",
            )
        },
        note="One sample/question; native stages and tool timings overlap, never add to total. "
        "Absent retrieval/provider timers are NOT_MEASURED, not zero. PDF support is "
        "reviewed at page/claim level; not independent cell-level provenance accuracy.",
    )
    save(base / "summary.json", summary)
    print(summary["counts"], summary["latency"]["all"])


if __name__ == "__main__":
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("artifacts/evidence/E2E-02"))
    audit(parser.parse_args().base)
