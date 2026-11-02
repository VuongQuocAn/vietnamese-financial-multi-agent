"""Offline M4-02 BBS acceptance; chỉ đọc accepted artifacts, không Gateway/OCR."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_d01_coverage import compare_observations
from evaluate_d04_closure import save
from evaluate_d06_validation import SNAPSHOT, selected_facts
from evaluate_m4_01_eligibility import d06_regression, inputs, regression_queries
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    EvidenceGraph,
    ReportingScopeReview,
    SnapshotCatalog,
    SnapshotDescriptor,
)
from vietnamese_financial_multi_agent.evidence.execution_compatibility import (
    ExecutionCompatibilityApproval,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)
from vietnamese_financial_multi_agent.tools import (
    FinancialRetrievalTools,
    FinancialToolResponse,
    FindFinancialFactsRequest,
    GetFinancialFactRequest,
    GetFinancialMetricRequest,
    ListFinancialMetricsRequest,
)


def manifest(root):
    paths = set(load(root / "artifacts/evidence/D-07/hashes-before.json"))
    paths.update(
        p.relative_to(root).as_posix()
        for p in (root / "artifacts/evidence/D-07").rglob("*")
        if p.is_file()
    )
    paths.add("configs/m4-execution-policies.json")
    return {p: digest(root / p) for p in sorted(paths)}


def hydrate(root):
    data, scopes, target = inputs(root)
    data["graph"] = EvidenceGraph.model_validate_json(
        (root / "artifacts/evidence/D-04-review/graph.json").read_text(encoding="utf-8")
    )
    data["reporting_scope_reviews"] = [
        ReportingScopeReview.model_validate_json(json.dumps(r))
        for r in load(root / "artifacts/evidence/D-07/reporting-scope-reviews.json")
    ]
    policy = load(root / "configs/m4-execution-policies.json")
    data.update(
        approval=PreparationApproval(
            **load(root / "configs/d02-analytical-policies.json")["preparation_approval"]
        ),
        execution_approval=ExecutionCompatibilityApproval(**policy["execution_approval"]),
        formula_policies=[PreparedFormulaPolicy(**p) for p in policy["formula_policies"]],
        formula_approvals=[
            FormulaExecutionApproval(**a) for a in policy["formula_execution_approvals"]
        ],
    )
    return data, scopes, target


def exact(fact):
    return GetFinancialFactRequest(
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        local_observation_id=fact.local_observation_id,
    )


def partial_scope_regression(tools, scopes):
    snapshot = scopes[2024]["snapshot_id"]
    assert all(s["snapshot_id"] == snapshot for s in scopes.values())
    request = FindFinancialFactsRequest(
        snapshot_id=snapshot,
        canonical_item_id="b01.total_assets",
        statement_type="B01",
        period="2024-12-31",
        period_type="as_of",
        reporting_scope="separate",
    )
    result = tools.find_financial_facts(request)
    assert result.status == "found" and len(result.matches) == 1
    assert "partial_scope_coverage" in result.caveats
    assert "reporting_scope_unresolved" in result.reasons
    assert len(result.reporting_scopes) == 5
    assert sum(s.status == "unresolved" for s in result.reporting_scopes) == 4
    assert result.matches[0].reference.observation.document_id == scopes[2024]["document_id"]
    expected = tools.find_financial_facts(
        request.model_copy(update={"document_id": scopes[2024]["document_id"]})
    )
    assert expected.status == "found" and result.matches == expected.matches
    assert result.matches[0].record.context.reporting_scope is None
    assert FinancialToolResponse.model_validate_json(result.model_dump_json()) == result
    return result


def evaluate_partial_scope(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = manifest(root)
    save(output / "hashes-before.json", hashes)
    data, scopes, _ = hydrate(root)
    before = [f.model_dump_json() for f in data["facts"]]
    result = partial_scope_regression(FinancialRetrievalTools(SnapshotCatalog(**data)), scopes)
    save(output / "partial-scope.json", result.model_dump(mode="json"))
    assert before == [f.model_dump_json() for f in data["facts"]]
    after = manifest(root)
    assert after == hashes
    save(output / "hashes-after.json", after)
    summary = dict(
        regression_cases=1,
        status=result.status,
        matches=len(result.matches),
        unresolved_documents=4,
        partial_scope_coverage="partial_scope_coverage" in result.caveats,
        protected_input_hashes=len(hashes),
        input_hashes_unchanged=True,
        original_facts_unchanged=True,
        json_round_trip_exact=True,
        gateway_calls=0,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def evaluate(root, output, *, resume=False):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    # Re-running acceptance dùng output directory mới, không ghi đè evidence cũ.
    output.mkdir(parents=True, exist_ok=resume)
    hashes = manifest(root)
    if resume:
        assert hashes == load(output / "hashes-before.json"), "protected_input_changed"
    else:
        save(output / "hashes-before.json", hashes)
    print(f"Pinned {len(hashes)} protected inputs; loading accepted catalogs", flush=True)
    data, scopes, target = hydrate(root)
    before = [f.model_dump_json() for f in data["facts"]]
    catalog = SnapshotCatalog(**data)
    coverage = [
        CanonicalCoverage(
            **s,
            canonical_extraction="available",
            missing_canonical_items=["b01.short_term_liabilities"],
            inventory_reference="D-01/inventory.json",
        )
        for s in scopes.values()
    ]
    tools = FinancialRetrievalTools(catalog, coverage=coverage)
    if resume:
        exact_rows = load(output / "exact-facts.json")
        metrics = load(output / "metrics.json")
        cases = load(output / "cases.json")
        queries = load(output / "retrieval-regression.json")
        pairs = load(output / "cross-document.json")
        assert len(exact_rows) == len(data["facts"])
        assert [r["matches"][0]["record"]["metric_id"] for r in metrics] == [
            m.metric_id for m in data["metrics"]
        ]
        print(
            "Resuming completed fact/metric/case/query/pair checks with unchanged inputs",
            flush=True,
        )
    else:
        exact_rows = []
        for fact in data["facts"]:
            response = tools.get_financial_fact(exact(fact))
            match = response.matches[0]
            legacy = catalog.api.get_fact(fact.observation_identity())
            assert response.status == legacy.status
            assert match.record == fact and match.citations == legacy.matches[0].citations
            assert match.source_review == catalog.api.get_source_review(fact.observation_identity())
            assert FinancialToolResponse.model_validate_json(response.model_dump_json()) == response
            exact_rows.append(
                dict(
                    identity=fact.observation_identity().model_dump(),
                    status=response.status,
                    display=match.display_status,
                )
            )
            if len(exact_rows) % 250 == 0:
                print(f"Checked {len(exact_rows)} exact fact payloads", flush=True)
        save(output / "exact-facts.json", exact_rows)
        print(
            f"Exact facts/citations/quality/JSON: {len(exact_rows)}; checking metric gates",
            flush=True,
        )
        metrics = []
        old_rows = load(root / "artifacts/evidence/M4-01/verified/metrics.json")
        for metric, old in zip(data["metrics"], old_rows, strict=True):
            response = tools.get_financial_metric(
                GetFinancialMetricRequest(metric_id=metric.metric_id)
            )
            assert response.status == "found" and len(response.matches) == 1
            match = response.matches[0]
            assert match.record == metric and match.record.result_status == "not_computed"
            assert match.record.result is None
            assert match.closure.model_dump(mode="json") == old["closure"]
            assert match.reviewed_lineage.model_dump(mode="json") == old["reviewed_lineage"]
            assert match.closure.calculation_eligible
            for operand, accepted in zip(match.operands, old["operands"], strict=True):
                assert operand.binding.observation.model_dump() == accepted["observation"]
                assert operand.binding.source_fact_node_id == accepted["source_fact_node_id"]
                assert operand.facts.matches[0].record.model_dump(mode="json") == accepted["fact"]
                assert operand.source_review.model_dump(mode="json") == accepted["source_review"]
            assert [b.model_dump(mode="json") for b in match.accounting_bases] == old[
                "accounting_basis"
            ]
            assert match.citations == catalog.api.get_lineage(metric.metric_id).matches[0].citations
            assert FinancialToolResponse.model_validate_json(response.model_dump_json()) == response
            listed = tools.list_financial_metrics(
                ListFinancialMetricsRequest(
                    document_id=metric.request.document_id,
                    snapshot_id=metric.request.snapshot_id,
                    formula_id=metric.definition.name,
                )
            )
            assert listed.status == "found" and listed.matches == response.matches
            metrics.append(response.model_dump(mode="json"))
        save(output / "metrics.json", metrics)
        cases = []

        def record(case, request, expected):
            response = tools.find_financial_facts(request)
            assert response.status == expected, (case, response.status, response.reasons)
            cases.append(dict(case=case, response=response.model_dump(mode="json")))
            return response

        for year, scope in scopes.items():
            for item, statement, period in (
                ("b01.total_assets", "B01", f"{year}-12-31"),
                ("b01.total_liabilities", "B01", f"{year}-12-31"),
                ("b02.net_revenue", "B02", str(year)),
                ("b02.gross_profit", "B02", str(year)),
                ("b03.operating_cash_flow", "B03", str(year)),
            ):
                record(
                    f"{year}/{item}",
                    FindFinancialFactsRequest(
                        **scope, canonical_item_id=item, statement_type=statement, period=period
                    ),
                    "found",
                )
            scoped = FindFinancialFactsRequest(
                **scope,
                canonical_item_id="b01.total_assets",
                period=f"{year}-12-31",
                reporting_scope="separate",
            )
            record(f"{year}/scope-separate", scoped, "found" if year == 2024 else "unavailable")
            record(
                f"{year}/scope-consolidated",
                scoped.model_copy(update={"reporting_scope": "consolidated"}),
                "not_found" if year == 2024 else "unavailable",
            )
            expected_scope = next(
                r
                for r in load(root / "artifacts/evidence/D-07/scope-results.json")
                if r["year"] == year
            )["after"]
            assert catalog.get_reporting_scope(**scope).model_dump(mode="json") == expected_scope
        record(
            "mapping-gap",
            FindFinancialFactsRequest(
                **scopes[2024], canonical_item_id="b01.short_term_liabilities"
            ),
            "unavailable",
        )
        record(
            "multiple-periods",
            FindFinancialFactsRequest(**scopes[2023], canonical_item_id="b01.total_assets"),
            "ambiguous",
        )
        record(
            "multiple-snapshots",
            FindFinancialFactsRequest(
                document_id=target.document_id, canonical_item_id="b01.total_assets"
            ),
            "ambiguous",
        )
        record(
            "recovery-scope-not-inherited",
            FindFinancialFactsRequest(
                document_id=target.document_id,
                snapshot_id=target.snapshot_id,
                reporting_scope="separate",
            ),
            "unavailable",
        )
        blocked = next(
            f
            for f in data["facts"]
            if any(
                q.decision == "insufficient"
                for q in f.quality_context
                if q.task_type == "direct_qa"
            )
        )
        response = tools.get_financial_fact(exact(blocked))
        assert response.matches[0].display_status == "blocked"
        cases.append(dict(case="quality-insufficient", response=response.model_dump(mode="json")))
        cases.append(
            dict(
                case="partial-scope-coverage",
                response=partial_scope_regression(tools, scopes).model_dump(mode="json"),
            )
        )
        save(output / "cases.json", cases)
        print(
            f"Semantic/scope/negative cases: {len(cases)}; replaying accepted regressions",
            flush=True,
        )
        effective, queries = regression_queries(root, data, scopes, target)
        save(output / "retrieval-regression.json", queries)
        pairs = compare_observations(effective)
        assert pairs == load(root / "artifacts/evidence/D-02/cross-year-after-recovery.json")
        assert len(pairs) == 36 and all(p["status"] == "undetermined" for p in pairs)
        save(output / "cross-document.json", pairs)
    save(output / "d06-regression.json", d06_regression(root))
    # D-06 persisted mapping snapshot vẫn exact, không trộn với metric snapshots.
    corrected = selected_facts(root, "artifacts/evidence/D-06-final", SNAPSHOT)
    descriptors = [
        SnapshotDescriptor(**r) for r in load(root / "artifacts/evidence/D-06-final/snapshots.json")
    ]
    corrected_tools = FinancialRetrievalTools(
        SnapshotCatalog(descriptors, facts=[f for rows in corrected.values() for f in rows])
    )
    for rows in corrected.values():
        for fact in rows:
            assert corrected_tools.get_financial_fact(exact(fact)).matches[0].record == fact
    response = FinancialToolResponse.model_validate_json(
        json.dumps(next(c["response"] for c in cases if c["case"] == "quality-insufficient"))
    )
    blocked = next(
        f
        for f in data["facts"]
        if f.observation_identity() == response.matches[0].record.observation_identity()
    )
    # Restart re-hydrate từ disk; returned objects và caller catalog không sửa input.
    fresh, _, _ = hydrate(root)
    restarted = FinancialRetrievalTools(SnapshotCatalog(**fresh), coverage=coverage)
    assert restarted.get_financial_fact(exact(blocked)) == response
    for metric, expected in zip(fresh["metrics"], metrics, strict=True):
        request = GetFinancialMetricRequest(metric_id=metric.metric_id)
        assert restarted.get_financial_metric(request).model_dump(mode="json") == expected
    assert before == [f.model_dump_json() for f in data["facts"]]
    after_hashes = manifest(root)
    assert hashes == after_hashes
    save(output / "hashes-after.json", after_hashes)
    summary = dict(
        exact_facts=len(exact_rows),
        exact_corrected_facts=sum(len(r) for r in corrected.values()),
        fact_display=dict(Counter(r["display"] for r in exact_rows)),
        semantic_scope_negative_cases=len(cases),
        metrics=len(metrics),
        baseline_eligible=sum(
            r["matches"][0]["closure"]["calculation_eligible"]
            for r in metrics
            if r["matches"][0]["selected_snapshot"]["parent_snapshot_id"] is None
        ),
        recovery_eligible=sum(
            r["matches"][0]["closure"]["calculation_eligible"]
            for r in metrics
            if r["matches"][0]["selected_snapshot"]["parent_snapshot_id"] is not None
        ),
        computed_metrics=sum(r["matches"][0]["record"]["result"] is not None for r in metrics),
        closures_lineages_reviews_citations_exact=True,
        accepted_retrieval_queries=len(queries),
        cross_document_pairs_undetermined=len(pairs),
        reporting_scope_views_exact=5,
        d06_qa09_qa15_exact=True,
        json_restart_exact=True,
        protected_input_hashes=len(hashes),
        input_hashes_unchanged=True,
        gateway_calls=0,
        financial_fact_verified=False,
    )
    assert summary["baseline_eligible"] == 15 and summary["recovery_eligible"] == 3
    assert summary["computed_metrics"] == 0
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M4-02"))
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume saved checks only when all protected input hashes match",
    )
    parser.add_argument("--partial-scope-only", action="store_true")
    args = parser.parse_args()
    if args.partial_scope_only:
        if args.resume:
            parser.error("--partial-scope-only requires a fresh output directory")
        evaluate_partial_scope(Path.cwd().resolve(), args.output.resolve())
    else:
        evaluate(Path.cwd().resolve(), args.output.resolve(), resume=args.resume)
