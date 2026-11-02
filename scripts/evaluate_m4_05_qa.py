"""BBS QA deterministic benchmark; gold từ persisted facts/accepted M4-03, zero LLM."""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from evaluate_d01_coverage import compare_observations
from evaluate_d04_closure import save
from evaluate_m4_01_eligibility import d06_regression, regression_queries
from evaluate_m4_02_retrieval import hydrate, partial_scope_regression
from evaluate_m4_03_calculator import independent_check
from evaluate_m4_04_evidence import manifest, persisted_evidence
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    FinancialCalculationResponse,
    FinancialCalculator,
    FinancialQABaseline,
    FinancialRetrievalTools,
    QAContext,
    QADocument,
    QAResponse,
)
from vietnamese_financial_multi_agent.tools.question_understanding import ITEM_RULES


def setup(root):
    data, scopes, recovery = hydrate(root)
    data["evidence"] = persisted_evidence(root, scopes, recovery)
    documents = [
        QADocument(
            **{"document_id": scope["document_id"]},
            company_id=next(
                f.company_id for f in data["facts"] if f.document_id == scope["document_id"]
            ),
            company_aliases=["BBS"],
            reporting_year=year,
        )
        for year, scope in scopes.items()
    ]
    return data, scopes, recovery, documents


def context_for(case, scopes, recovery):
    fields = {}
    if case.get("snapshot"):
        fields["snapshot_id"] = (
            recovery.snapshot_id
            if case["snapshot"] == "recovery"
            else scopes[case["year"]]["snapshot_id"]
        )
    if case.get("followup"):
        fields.update(
            document_id=scopes[case["year"]]["document_id"],
            reporting_year=case["year"],
            formula_id=case["formula"],
        )
    return QAContext(**fields)


def reference_for(case, data, scopes, recovery, accepted):
    """Không gọi baseline, parser hoặc composer để tạo expected answer."""
    if case["group"] == "negative":
        return dict(
            status=case["expected_status"],
            intent=case["expected_intent"],
            tools=case["expected_tools"],
            result=None,
            sources=[],
        )
    scope = scopes[case["year"]]
    document = scope["document_id"]
    snapshot = recovery.snapshot_id if case.get("snapshot") == "recovery" else scope["snapshot_id"]
    if "formula" in case:
        rows = [
            a
            for a in accepted
            if a.document_id == document
            and a.snapshot_id == snapshot
            and a.formula_id == case["formula"]
        ]
        assert len(rows) == 1
        calc = rows[0]
        return dict(
            status="answered",
            intent="evidence_explanation" if case["group"] == "evidence" else "calculated_metric",
            tools=[
                "list_financial_metrics",
                "calculate_financial_metric",
                "get_metric_evidence_lineage",
            ],
            document_id=document,
            snapshot_id=snapshot,
            result=calc.result,
            unit="percent",
            sources=[c.source for c in calc.evidence.citations],
            facts=[f.record for o in calc.evidence.operands for f in o.facts.matches],
            trace=calc.trace,
        )
    rule = ITEM_RULES[case["item"]]
    period = f"{case['year']}-12-31" if rule.statement_type == "B01" else str(case["year"])
    facts = [
        f
        for f in data["facts"]
        if f.document_id == document
        and f.snapshot_id == snapshot
        and f.canonical_item_id == case["item"]
        and f.context.period == period
        and f.context.statement_type == rule.statement_type
    ]
    assert len(facts) == 1
    fact = facts[0]
    assert all(
        q.decision in {"usable", "usable_with_caveat"}
        for q in fact.quality_context
        if q.task_type == "direct_qa"
    )
    return dict(
        status="answered",
        intent="evidence_explanation" if case["group"] == "evidence" else "direct_fact",
        tools=["find_financial_facts", "get_evidence_sources"],
        document_id=document,
        snapshot_id=snapshot,
        period=period,
        result=str(fact.value.normalized_value),
        unit=fact.value.unit,
        sources=fact.sources,
        facts=[fact],
    )


def assess(response, gold):
    intent = response.parsed.intent == gold["intent"]
    tools = [s.tool for s in response.tool_trace] == gold["tools"]
    correct = response.status == gold["status"] and response.numerical_result == gold["result"]
    citations = False
    if gold["status"] == "answered":
        citations = [c.source for c in response.citations] == gold["sources"]
        correct &= (
            response.document_id == gold["document_id"]
            and response.snapshot_id == gold["snapshot_id"]
            and response.unit == gold["unit"]
            and [f.record for f in response.facts] == gold["facts"]
            and (not gold.get("period") or response.period == gold["period"])
        )
        if gold.get("trace"):
            correct &= (
                response.calculation is not None and response.calculation.trace == gold["trace"]
            )
    else:
        correct &= not response.citations and not response.calculation
    return dict(
        correct=bool(correct and intent and tools and (citations or gold["status"] != "answered")),
        intent_correct=intent,
        tools_correct=tools,
        grounded_citations=citations,
    )


def bounded_regressions(root, data, scopes, recovery, accepted, output):
    catalog = SnapshotCatalog(**data)
    calc = FinancialCalculator(catalog)
    rows = []
    for expected in accepted:
        actual = calc.calculate_financial_metric(expected.request)
        assert actual == expected
        metric = next(m for m in data["metrics"] if m.metric_id == actual.metric_id)
        assert actual.result == independent_check(metric, data["facts"])
        rows.append(dict(metric_id=actual.metric_id, result=actual.result, status=actual.status))
    assert len(rows) == 18
    partial_scope_regression(FinancialRetrievalTools(catalog), scopes)
    effective, queries = regression_queries(root, data, scopes, recovery)
    pairs = compare_observations(effective)
    assert pairs == load(root / "artifacts/evidence/D-02/cross-year-after-recovery.json")
    assert len(pairs) == 36 and all(p["status"] == "undetermined" for p in pairs)
    save(output / "d06-regression.json", d06_regression(root))
    for year, scope in scopes.items():
        expected = next(
            r["after"]
            for r in load(root / "artifacts/evidence/D-07/scope-results.json")
            if r["year"] == year
        )
        assert catalog.get_reporting_scope(**scope).model_dump(mode="json") == expected
    # Accepted M4-04 exact persisted evidence/anchor inventory; no redundant full retrieval replay.
    inventory = Counter(e.kind for e in data["evidence"])
    anchors = sum(n.kind == "anchor" for n in data["graph"].nodes)
    assert inventory == {"text": 139, "table": 24} and anchors == 2973
    assert all(
        metric == next(m for m in data["metrics"] if m.metric_id == metric.metric_id)
        for a in accepted
        for metric in [a.evidence.record]
    )
    save(output / "metric-regression.json", rows)
    return dict(
        computed_metrics=18,
        independent_arithmetic=18,
        accepted_execution_exact=18,
        original_eligible=15,
        recovery_eligible=3,
        accepted_queries=len(queries),
        undetermined_cross_document_pairs=len(pairs),
        d07_scope_views=5,
        d06_qa09_qa15_exact=True,
        partial_scope_exact=True,
        evidence_inventory=dict(inventory),
        anchors=anchors,
        lineages=18,
    )


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = manifest(root)
    hashes.update(
        {
            p.relative_to(root).as_posix(): digest(p)
            for p in (root / "artifacts/evidence/M4-04").rglob("*.json")
        }
    )
    save(output / "hashes-before.json", hashes)
    data, scopes, recovery, documents = setup(root)
    before = [r.model_dump_json() for r in [*data["facts"], *data["metrics"], *data["evidence"]]]
    accepted = [
        FinancialCalculationResponse.model_validate_json(json.dumps(r))
        for r in load(root / "artifacts/evidence/M4-03-final/executions.json")
    ]
    cases = load(root / "evaluation/m4-05-questions.json")
    groups = Counter(c["group"] for c in cases)
    assert (
        groups["direct"] >= 12
        and groups["analytical"] >= 9
        and groups["evidence"] >= 5
        and groups["negative"] >= 4
    )
    api = FinancialQABaseline(SnapshotCatalog(**data), documents)
    rows, gold_rows, responses = [], [], []
    for case in cases:
        gold = reference_for(case, data, scopes, recovery, accepted)
        context = context_for(case, scopes, recovery)
        start = perf_counter()
        response = api.answer(case["question"], context)
        latency = (perf_counter() - start) * 1000
        assert response.llm.calls == 0 and not response.financial_fact_verified
        assert QAResponse.model_validate_json(response.model_dump_json()) == response
        checks = assess(response, gold)
        rows.append(
            dict(
                id=case["id"],
                group=case["group"],
                question=case["question"],
                status=response.status,
                latency_ms=latency,
                **checks,
            )
        )
        responses.append(
            dict(
                id=case["id"],
                context=context.model_dump(mode="json"),
                response=response.model_dump(mode="json"),
            )
        )
        gold_rows.append(
            dict(
                id=case["id"],
                **{
                    k: [v.model_dump(mode="json") for v in value]
                    if isinstance(value, list) and value and hasattr(value[0], "model_dump")
                    else value.model_dump(mode="json")
                    if hasattr(value, "model_dump")
                    else value
                    for k, value in gold.items()
                },
            )
        )
        print(f"{case['id']}: {response.status}; correct={checks['correct']}", flush=True)
    save(output / "references.json", gold_rows)
    save(output / "responses.json", responses)
    save(output / "scores.json", rows)
    # Same hydrated records after fresh initialization, independent response deserialization.
    restarted = FinancialQABaseline(SnapshotCatalog(**data), documents)
    for case, saved in zip(cases, responses, strict=True):
        expected = QAResponse.model_validate_json(json.dumps(saved["response"]))
        assert restarted.answer(case["question"], context_for(case, scopes, recovery)) == expected
    regressions = bounded_regressions(root, data, scopes, recovery, accepted, output)
    assert before == [
        r.model_dump_json() for r in [*data["facts"], *data["metrics"], *data["evidence"]]
    ]
    after = {p: digest(root / p) for p in hashes}
    assert hashes == after
    save(output / "hashes-after.json", after)
    statuses = Counter(r["status"] for r in rows)
    answered = [r for r in rows if r["status"] == "answered"]
    summary = dict(
        mode="deterministic_real_persisted_BBS_not_live_Gemini",
        total=len(rows),
        groups=dict(groups),
        answered=len(answered),
        correct=sum(r["correct"] for r in answered),
        incorrect=sum(not r["correct"] for r in answered),
        partial=statuses["partial"],
        abstained_unsupported=statuses["abstained"] + statuses["unsupported"],
        clarification_required=statuses["clarification_required"],
        correct_dispositions=sum(r["correct"] for r in rows),
        grounded_citations=sum(r["grounded_citations"] for r in answered),
        wrong_missing_citations=sum(not r["grounded_citations"] for r in answered),
        intent_correct=sum(r["intent_correct"] for r in rows),
        tool_selection_correct=sum(r["tools_correct"] for r in rows),
        latency_ms=dict(
            median=median(r["latency_ms"] for r in rows), max=max(r["latency_ms"] for r in rows)
        ),
        gateway_calls=0,
        live_gemini="NOT_RUN_no_process_credentials_or_live_configuration",
        tokens=None,
        regressions=regressions,
        protected_input_hashes=len(hashes),
        hashes_unchanged=True,
        json_restart_exact=True,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    assert all(r["correct"] for r in rows), (
        "Inspect persisted scores/responses; do not change gold to fit output"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M4-05"))
    args = parser.parse_args()
    evaluate(Path.cwd().resolve(), args.output.resolve())
