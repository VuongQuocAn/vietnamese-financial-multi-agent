"""Offline BBS18 execution/replay và accepted regressions; zero Gateway/OCR."""

import argparse
import json
from collections import Counter
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from pathlib import Path

from evaluate_d04_closure import save
from evaluate_m4_02_retrieval import evaluate as evaluate_retrieval
from evaluate_m4_02_retrieval import hydrate, manifest
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    FinancialCalculationResponse,
    FinancialCalculator,
    FinancialMetricMatch,
)


def protected_inputs(root):
    hashes = manifest(root)
    for folder in ("M4-01/verified", "M4-02-final", "M4-02-scope-fix-final"):
        hashes.update(
            (p.relative_to(root).as_posix(), digest(p))
            for p in (root / "artifacts/evidence" / folder).rglob("*")
            if p.is_file()
        )
    return dict(sorted(hashes.items()))


def independent_check(metric, facts):
    """Đọc exact facts từ persisted repositories, không gọi arithmetic của tools."""
    bound = {}
    for operand in metric.operands:
        matches = [f for f in facts if f.observation_identity() == operand.observation]
        assert len(matches) == 1
        bound[operand.role] = matches[0].value.normalized_value
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        if metric.definition.name == "gross_margin":
            expected = bound["gross_profit"] / bound["revenue"] * Decimal("100")
        elif metric.definition.name == "debt_to_assets":
            expected = bound["liabilities"] / bound["assets"] * Decimal("100")
        else:
            expected = (
                (bound["current_revenue"] - bound["prior_revenue"])
                / bound["prior_revenue"]
                * Decimal("100")
            )
        return str(expected.quantize(Decimal("0.01")))


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = protected_inputs(root)
    save(output / "hashes-before.json", hashes)
    print(f"Pinned {len(hashes)} protected inputs; hydrating accepted evidence", flush=True)
    data, scopes, target = hydrate(root)
    original = [m.model_dump_json() for m in [*data["facts"], *data["metrics"]]]
    calculator = FinancialCalculator(SnapshotCatalog(**data))
    accepted = load(root / "artifacts/evidence/M4-02-final/metrics.json")
    year_by_document = {s["document_id"]: year for year, s in scopes.items()}
    responses, rows, checks = [], [], []
    for metric, old in zip(data["metrics"], accepted, strict=True):
        request = CalculateFinancialMetricRequest(
            metric_id=metric.metric_id,
            document_id=metric.request.document_id,
            snapshot_id=metric.request.snapshot_id,
        )
        response = calculator.calculate_financial_metric(request)
        assert response.status == "computed", (metric.metric_id, response.reasons)
        expected_evidence = FinancialMetricMatch.model_validate_json(json.dumps(old["matches"][0]))
        assert response.evidence == expected_evidence
        assert response.evidence.record.result is None
        assert response.evidence.record.result_status == "not_computed"
        assert response.evidence.closure.calculation_eligible
        assert response.evidence.reviewed_lineage.lineage.completeness == "complete"
        assert response.trace.approval.definition_sha256 == response.formula_digest
        assert response.trace.formula.definition_digest() == response.formula_digest
        expected = independent_check(metric, data["facts"])
        assert response.result == expected
        checks.append(
            dict(metric_id=metric.metric_id, independent=expected, output=response.result)
        )
        is_recovery = metric.request.snapshot_id == target.snapshot_id
        if is_recovery:
            assert metric.request.document_id == target.document_id
            assert all(
                o.observation.snapshot_id == target.snapshot_id
                and o.observation.document_id == target.document_id
                for o in response.trace.operands
            )
            assert all(
                c.source.snapshot_id == target.snapshot_id for c in response.evidence.citations
            )
        pages = sorted({c.source.reference.anchor.page.page for c in response.evidence.citations})
        rows.append(
            dict(
                year=year_by_document[metric.request.document_id],
                selection="recovery" if is_recovery else "original",
                metric_id=metric.metric_id,
                document_id=metric.request.document_id,
                snapshot_id=metric.request.snapshot_id,
                formula=response.formula_id,
                formula_version=response.formula_version,
                formula_digest=response.formula_digest,
                approval_reference=response.trace.approval.decision_reference,
                operands=[o.model_dump(mode="json") for o in response.trace.operands],
                result=response.result,
                output_unit=response.output_unit,
                source_pages=pages,
                status=response.status,
            )
        )
        responses.append(response.model_dump(mode="json"))
        print(
            f"{rows[-1]['year']}/{rows[-1]['selection']}/{response.formula_id}: "
            f"{response.result}% p{pages}",
            flush=True,
        )
    assert len(responses) == 18
    assert Counter(r["formula"] for r in rows) == {
        "gross_margin": 6,
        "debt_to_assets": 6,
        "revenue_yoy": 6,
    }
    save(output / "executions.json", responses)
    save(output / "results.json", rows)
    save(output / "independent-arithmetic.json", checks)
    # Restart from persisted source records plus serialized execution artifacts.
    fresh, _, _ = hydrate(root)
    restarted = FinancialCalculator(SnapshotCatalog(**fresh))
    for wire in load(output / "executions.json"):
        saved = FinancialCalculationResponse.model_validate_json(json.dumps(wire))
        assert restarted.calculate_financial_metric(saved.request) == saved
    print("18/18 exact JSON restart/recompute and independent arithmetic PASS", flush=True)
    fresh["execution_approval"] = None
    blocked_calculator = FinancialCalculator(SnapshotCatalog(**fresh))
    controls = []
    for wire in responses[:3]:
        saved = FinancialCalculationResponse.model_validate_json(json.dumps(wire))
        blocked = blocked_calculator.calculate_financial_metric(saved.request)
        assert blocked.status == "blocked" and blocked.result is None and blocked.trace is None
        controls.append(blocked.model_dump(mode="json"))
    save(output / "negative-controls.json", controls)
    assert original == [m.model_dump_json() for m in [*data["facts"], *data["metrics"]]]
    print("Reusing M4-02 evaluator for full bounded accepted regressions", flush=True)
    evaluate_retrieval(root, output / "retrieval-regression")
    regression = load(output / "retrieval-regression/summary.json")
    after = protected_inputs(root)
    assert after == hashes
    save(output / "hashes-after.json", after)
    summary = dict(
        computed=18,
        formulas=dict(Counter(r["formula"] for r in rows)),
        baseline_computed=15,
        recovery_computed=3,
        independent_arithmetic_checks=len(checks),
        real_negative_controls=len(controls),
        reviewed_lineage_citations_exact=True,
        json_restart_recompute_exact=True,
        original_facts_metrics_unchanged=True,
        protected_input_hashes=len(hashes),
        input_hashes_unchanged=True,
        regression=regression,
        gateway_calls=0,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M4-03"))
    args = parser.parse_args()
    evaluate(Path.cwd().resolve(), args.output.resolve())
