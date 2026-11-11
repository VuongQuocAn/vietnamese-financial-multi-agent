"""Build a compact review pack and deterministic audits; never auto-grade semantics.

Independent Codex assessments are stored separately in assessments.json, with
explicit satisfied content requirements and semantic findings for every run.
"""

import argparse
import json
import statistics
from collections import Counter
from decimal import Decimal
from pathlib import Path

from evaluate_e2e_lite import digest, save


def read(path):
    return json.loads(path.read_bytes())


def describe(values):
    if not values:
        return None
    return dict(
        n=len(values),
        mean=statistics.mean(values),
        median=statistics.median(values),
        stdev=statistics.stdev(values) if len(values) > 1 else None,
        minimum=min(values),
        maximum=max(values),
    )


def inspect(row, oracle):
    response = row.get("response", {})
    trace = response.get("trace", {})
    graphs, supplied, candidates, reported, tool_calls = [], [], [], set(), []
    fact_checks, metric_checks = [], []
    source_facts = {
        (f["document_id"], f["snapshot_id"], f["local_observation_id"]): f
        for f in oracle["facts"].values()
    }
    for m5 in row.get("m5", []):
        bundle = m5["supervisor_result"]["evidence_bundle"]
        candidates.extend(m5["candidates"])
        tool_calls.extend(m5["supervisor_result"]["tool_trace"])
        for fact in bundle["facts"]:
            record = fact["record"]
            key = (record["document_id"], record["snapshot_id"], record["local_observation_id"])
            expected = source_facts.get(key)
            if expected is not None:
                fact_checks.append(
                    record["value"] == expected["value"]
                    and record["context"] == expected["context"]
                    and record["sources"] == expected["sources"]
                )
        for execution in m5["specialist_executions"]:
            result = execution.get("result") or {}
            for t in result.get("trace", []):
                if t["outcome"] == "graph_use_reported_pending_M6":
                    reported.add(t["evidence_id"])
                elif t["outcome"] == "graph_context_supplied":
                    supplied.extend(json.loads(t["reasons"][0]))
            for evidence in result.get("supporting_evidence", []):
                if evidence["kind"] != "metric":
                    continue
                calculation = evidence.get("calculation") or {}
                operands = (calculation.get("trace") or {}).get("operands", [])
                values = {}
                for operand in operands:
                    ref = operand["observation"]
                    fact = source_facts.get(
                        (ref["document_id"], ref["snapshot_id"], ref["local_id"])
                    )
                    if fact is not None:
                        values[operand["role"]] = Decimal(fact["value"]["normalized_value"])
                expected = None
                if {"current_revenue", "prior_revenue"} <= values.keys():
                    expected = (values["current_revenue"] / values["prior_revenue"] - 1) * 100
                elif {"gross_profit", "revenue"} <= values.keys():
                    expected = values["gross_profit"] / values["revenue"] * 100
                elif {"liabilities", "assets"} <= values.keys():
                    expected = values["liabilities"] / values["assets"] * 100
                if expected is not None:
                    metric_checks.append(
                        abs(Decimal(evidence["value"]) - expected) < Decimal("0.005")
                    )
    # The bundle is merged only after a Specialist succeeds. Tool responses
    # still prove retrieval even when a later Specialist exception loses it.
    graphs = [
        t["response"]
        for t in tool_calls
        if t["operation"] == "get_graph_context" and t.get("response")
    ]
    outcomes = {o["candidate_id"]: o for o in trace.get("outcomes", [])}
    claims = []
    for c in candidates:
        outcome = outcomes.get(c["candidate_id"], {})
        used = any(o["candidate_id"] in reported for o in c.get("origins", []))
        claims.append(
            dict(
                kind=c["kind"],
                content=c["content"],
                reasoning=c.get("reasoning"),
                graph_use=used,
                verdict=outcome.get("final_decision"),
                verdict_reasons=outcome.get("reasons"),
                selected=outcome.get("verified_claim_id")
                in response.get("used_verified_claim_ids", []),
            )
        )
    citations = response.get("citations", [])
    # Check actual source binding (not just rendered page labels). Full entailment
    # remains a separate semantic judgment, including graph-only descriptions.
    source_locations = {
        (s["document_id"], s["snapshot_id"], s["reference"]["anchor"]["page"]["page"])
        for f in oracle["facts"].values()
        for s in f["sources"]
    }
    citation_checks = [
        (c["document_id"], c["snapshot_id"], c.get("pdf_page")) in source_locations
        for c in citations
    ]
    edges = {e["edge"]["edge_id"]: e["edge"]["relation"] for g in graphs for e in g["edges"]}
    return dict(
        run_id=row["run_id"],
        case=row["case"],
        graph=row["graph"],
        repetition=row["repetition"],
        question=row["question"],
        requirements=row["requirements"],
        answer=response.get("answer_vi"),
        status=response.get("status"),
        plan_sha256=row.get("plan_sha256"),
        technical_affected=bool(
            row["usage"]["failed_calls"]
            or row.get("technical_failure")
            or any(m.get("errors") for m in row.get("m5", []))
            or response.get("status") in {"internal_error", "provider_unavailable"}
        ),
        pipeline_errors=[e for m in row.get("m5", []) for e in m.get("errors", [])],
        financial_inputs=sorted(
            {
                (
                    match["record"]["document_id"],
                    match["record"]["snapshot_id"],
                    match["record"]["local_observation_id"],
                )
                for tool in tool_calls
                if tool["operation"] == "get_financial_fact"
                for match in (tool.get("response") or {}).get("matches", [])
            }
        ),
        model_parameters=sorted(
            {
                json.dumps(
                    {
                        "stage": e["request"]["request_id"].rsplit("-", 1)[0],
                        "model": e["request"]["model"],
                        "generation": e["request"]["generation"],
                    },
                    sort_keys=True,
                )
                for e in row["events"]
            }
        ),
        claims=claims,
        relations=dict(Counter(edges.values())),
        supplied_relations=dict(Counter(s["relation"] for s in supplied)),
        graph_calls=len(graphs),
        graph_used=sum(c["graph_use"] for c in claims),
        graph_accepted=sum(c["graph_use"] and c["verdict"] == "ACCEPT" for c in claims),
        graph_selected=sum(c["graph_use"] and c["selected"] for c in claims),
        tools=dict(Counter(t["operation"] for t in tool_calls)),
        pages=sorted({c["pdf_page"] for c in citations if c.get("pdf_page")}),
        source_facts_checked=len(fact_checks),
        source_fact_mismatches=fact_checks.count(False),
        metrics_checked=len(metric_checks),
        metric_mismatches=metric_checks.count(False),
        citation_bindings_checked=len(citation_checks),
        citation_binding_mismatches=citation_checks.count(False),
        usage=row["usage"],
        provider_attempts=len(row["provider_attempts"]),
        timings=row["timings"],
        latency_ms=row["comparison_latency_ms"],
        stage_latency_ms={
            "m5": max(
                0,
                trace.get("stages", {}).get("m5", {}).get("latency_ms", 0)
                - (
                    row.get("wall_latency_ms", row["comparison_latency_ms"])
                    - row["comparison_latency_ms"]
                ),
            ),
            "m6": trace.get("stages", {}).get("m6", {}).get("latency_ms", 0),
            "m7": trace.get("stages", {}).get("composer", {}).get("latency_ms", 0),
        },
        stages=trace.get("stages", {}),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/EF-CORE-02"))
    args = parser.parse_args()
    base = args.output
    oracle = read(base / "oracle.json")
    rows = [inspect(read(p), oracle) for p in sorted((base / "runs").glob("*.json"))]
    save(base / "review-pack.json", rows)
    assessments = read(base / "assessments.json") if (base / "assessments.json").exists() else {}
    summary = {}
    for graph in [False, True]:
        selected = [r for r in rows if r["graph"] == graph]
        valid = [r for r in selected if not r["technical_affected"]]
        graded = [r for r in valid if r["run_id"] in assessments]
        grades = [assessments[r["run_id"]] for r in graded]
        for r, a in zip(graded, grades, strict=True):
            assert set(a["satisfied"]) <= set(r["requirements"])
            assert a["label"] in {
                "CORRECT",
                "CORRECT_WITH_CAVEAT",
                "PARTIAL",
                "INCORRECT",
                "UNJUSTIFIED_REFUSAL",
            }
        summary["on" if graph else "off"] = dict(
            attempted=len(selected),
            technical_affected=len(selected) - len(valid),
            quality_denominator=len(graded),
            labels=dict(Counter(a["label"] for a in grades)),
            correctness=sum(a["label"] in {"CORRECT", "CORRECT_WITH_CAVEAT"} for a in grades)
            / len(grades)
            if grades
            else None,
            completeness=sum(len(a["satisfied"]) for a in grades)
            / sum(len(r["requirements"]) for r in graded)
            if graded
            else None,
            content_satisfied=sum(len(a["satisfied"]) for a in grades),
            content_total=sum(len(r["requirements"]) for r in graded),
            unsupported_answers=sum(bool(a["unsupported"]) for a in grades),
            citation_bindings_checked=sum(r["citation_bindings_checked"] for r in selected),
            citation_binding_mismatches=sum(r["citation_binding_mismatches"] for r in selected),
            source_facts_checked=sum(r["source_facts_checked"] for r in selected),
            source_fact_mismatches=sum(r["source_fact_mismatches"] for r in selected),
            metrics_checked=sum(r["metrics_checked"] for r in selected),
            metric_mismatches=sum(r["metric_mismatches"] for r in selected),
            graph_retrieved=sum(bool(r["relations"]) for r in selected),
            graph_used=sum(r["graph_used"] > 0 for r in selected),
            graph_supported_accept=sum(r["graph_accepted"] > 0 for r in selected),
            manual_additional_graph_used=sum(
                not r["graph_used"]
                and assessments.get(r["run_id"], {})
                .get("manual_graph_use", {})
                .get("confirmed", False)
                for r in selected
            ),
            manual_additional_graph_supported_accept=sum(
                not r["graph_accepted"]
                and assessments.get(r["run_id"], {})
                .get("manual_graph_use", {})
                .get("m6_accept", False)
                for r in selected
            ),
            manual_additional_graph_selected=sum(
                not r["graph_selected"]
                and assessments.get(r["run_id"], {})
                .get("manual_graph_use", {})
                .get("m7_selected", False)
                for r in selected
            ),
            # Resource statistics use technically clean executions; all-attempt
            # actual totals are retained alongside, including failed usage unknowns.
            tokens=describe(
                [r["usage"]["total_tokens"] for r in valid if not r["usage"]["unknown_usage_calls"]]
            ),
            input_tokens=describe(
                [r["usage"]["input_tokens"] for r in valid if not r["usage"]["unknown_usage_calls"]]
            ),
            output_tokens=describe(
                [
                    r["usage"]["output_tokens"]
                    for r in valid
                    if not r["usage"]["unknown_usage_calls"]
                ]
            ),
            latency_ms=describe([r["latency_ms"] for r in valid]),
            stage_latency_ms={
                name: describe([r["stage_latency_ms"][name] for r in valid])
                for name in ["m5", "m6", "m7"]
            },
            graph_setup_ms=describe([r["timings"]["graph_setup_ms"] for r in valid]),
            graph_traversal_ms=describe([r["timings"]["graph_traversal_ms"] for r in valid]),
            logical_calls=describe([r["usage"]["logical_calls"] for r in valid]),
            all_attempt_tokens=sum(r["usage"]["total_tokens"] for r in selected),
            all_logical_calls=sum(r["usage"]["logical_calls"] for r in selected),
            all_provider_attempts=sum(r["provider_attempts"] for r in selected),
            unknown_usage_calls=sum(r["usage"]["unknown_usage_calls"] for r in selected),
        )
    # A bounded replacement may repair a technical slot, never add a third
    # analytical repetition or replace an unfavorable but clean answer.
    slots = {}
    for row in rows:
        key = (row["case"], row["repetition"], row["graph"])
        if key not in slots or (slots[key]["technical_affected"] and not row["technical_affected"]):
            slots[key] = row
    effective = list(slots.values())
    pairs = []
    for off in effective:
        if off["graph"]:
            continue
        on = next(
            (
                r
                for r in effective
                if r["case"] == off["case"] and r["repetition"] == off["repetition"] and r["graph"]
            ),
            None,
        )
        if on is None:
            continue
        pair = dict(
            case=off["case"],
            repetition=off["repetition"],
            clean=not (off["technical_affected"] or on["technical_affected"]),
            financial_inputs_equal=off["financial_inputs"] == on["financial_inputs"],
            plan_equal=bool(off["plan_sha256"] and off["plan_sha256"] == on["plan_sha256"]),
        )
        if pair["clean"]:
            assert pair["plan_equal"], "uncontrolled_plan"
        off_parameters = {json.loads(s)["stage"]: json.loads(s) for s in off["model_parameters"]}
        on_parameters = {json.loads(s)["stage"]: json.loads(s) for s in on["model_parameters"]}
        pair["shared_stage_parameters_equal"] = all(
            off_parameters[s] == on_parameters[s]
            for s in off_parameters.keys() & on_parameters.keys()
        )
        if pair["clean"] and off["run_id"] in assessments and on["run_id"] in assessments:
            a, b = assessments[off["run_id"]], assessments[on["run_id"]]
            pair.update(
                completeness_delta=(len(b["satisfied"]) - len(a["satisfied"]))
                / len(off["requirements"]),
                token_delta=on["usage"]["total_tokens"] - off["usage"]["total_tokens"],
                latency_delta_ms=on["latency_ms"] - off["latency_ms"],
            )
        pairs.append(pair)
    save(
        base / "summary.json",
        dict(
            configurations=summary,
            pairs=pairs,
            paired_configurations=paired_summary(effective, pairs, assessments),
            planning=[
                dict(case=p.stem, usage=read(p)["metadata"]["usage"])
                for p in sorted((base / "plans").glob("*.json"))
            ],
            assessment_sha256=digest(base / "assessments.json") if assessments else None,
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def paired_summary(rows, pairs, assessments):
    """Use identical question/repetition denominators for the main comparison."""
    keys = {(p["case"], p["repetition"]) for p in pairs if p["clean"]}
    output = {}
    for graph in [False, True]:
        selected = [r for r in rows if r["graph"] == graph and (r["case"], r["repetition"]) in keys]
        graded = [r for r in selected if r["run_id"] in assessments]
        grades = [assessments[r["run_id"]] for r in graded]
        output["on" if graph else "off"] = dict(
            n=len(graded),
            labels=dict(Counter(a["label"] for a in grades)),
            correct=sum(a["label"] in {"CORRECT", "CORRECT_WITH_CAVEAT"} for a in grades),
            content_satisfied=sum(len(a["satisfied"]) for a in grades),
            content_total=sum(len(r["requirements"]) for r in graded),
            grounded=sum(
                not a["unsupported"] and a["label"] not in {"INCORRECT", "UNJUSTIFIED_REFUSAL"}
                for a in grades
            ),
            unsupported=sum(bool(a["unsupported"]) for a in grades),
            numeric_errors=sum(len(a["numeric_errors"]) for a in grades),
            citation_errors=sum(len(a["citation_errors"]) for a in grades),
            citation_bindings=sum(r["citation_bindings_checked"] for r in graded),
            tokens=describe(
                [
                    r["usage"]["total_tokens"]
                    for r in selected
                    if not r["usage"]["unknown_usage_calls"]
                ]
            ),
            input_tokens=describe(
                [
                    r["usage"]["input_tokens"]
                    for r in selected
                    if not r["usage"]["unknown_usage_calls"]
                ]
            ),
            output_tokens=describe(
                [
                    r["usage"]["output_tokens"]
                    for r in selected
                    if not r["usage"]["unknown_usage_calls"]
                ]
            ),
            logical_calls=describe([r["usage"]["logical_calls"] for r in selected]),
            provider_attempts=describe([r["provider_attempts"] for r in selected]),
            latency_ms=describe([r["latency_ms"] for r in selected]),
            stage_latency_ms={
                name: describe([r["stage_latency_ms"][name] for r in selected])
                for name in ["m5", "m6", "m7"]
            },
            graph_setup_ms=describe([r["timings"]["graph_setup_ms"] for r in selected]),
            graph_traversal_ms=describe([r["timings"]["graph_traversal_ms"] for r in selected]),
        )
    return output


if __name__ == "__main__":
    main()
