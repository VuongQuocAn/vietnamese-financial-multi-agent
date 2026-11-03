"""Bounded persisted BBS checks and explicit synthetic corruptions; zero LLM/OCR."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from evaluate_m4_02_retrieval import hydrate
from evaluate_m4_03_calculator import independent_check
from evaluate_m6_01_conversion import digest, save_new
from vietnamese_financial_multi_agent.agents import PlannerContext
from vietnamese_financial_multi_agent.agents.cash_flow_earnings_quality_specialist import (
    ITEM_LABELS as FLOW_LABELS,
)
from vietnamese_financial_multi_agent.agents.liquidity_leverage_specialist import (
    ITEM_LABELS as BALANCE_LABELS,
)
from vietnamese_financial_multi_agent.agents.profitability_specialist import (
    ITEM_LABELS,
    METRIC_LABELS,
)
from vietnamese_financial_multi_agent.agents.specialist_common import SpecialistEvidence, _number
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.evidence.retrieval import RetrievalReference
from vietnamese_financial_multi_agent.tools import (
    FinancialCalculationResponse,
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)
from vietnamese_financial_multi_agent.verification import (
    CandidateClaim,
    ClaimProvenance,
    DeterministicFinancialValidator,
    ValidationResult,
    VerificationInput,
)


def protected(root, output):
    previous = json.loads(
        (root / "artifacts/evidence/M6-01-conversion/hashes-after.json").read_text(encoding="utf-8")
    )
    paths = set(previous)
    paths.update(
        p.relative_to(root).as_posix()
        for p in (root / "artifacts/evidence").rglob("*")
        if p.is_file() and not p.is_relative_to(output)
    )
    paths.add("web/next-env.d.ts")
    return {p: digest(root / p) for p in sorted(paths)}


def batch_for(evidence, *, calculation=None):
    """Explicit persisted-source rendering, not Gemini output or independent gold."""
    refs = (
        [
            RetrievalReference(kind="fact", observation=o.observation)
            for o in calculation.trace.operands
        ]
        if calculation
        else [evidence.reference]
    )
    phrase = "tại ngày" if "-" in evidence.period else "kỳ"
    content = f"{evidence.label} {phrase} {evidence.period} là {_number(evidence.value)}" + (
        "%." if calculation else f" {evidence.unit}."
    )
    claim = CandidateClaim(
        candidate_id="persisted-source",
        kind="approved_metric" if calculation else "fact",
        content=content,
        company_id=evidence.company_id,
        document_id=evidence.document_id,
        snapshot_id=evidence.snapshot_id,
        period=evidence.period,
        fact_references=refs,
        metric_ids=[calculation.metric_id] if calculation else [],
        supporting_evidence_ids=[evidence.evidence_id],
        citations=evidence.citations,
        calculation=calculation,
        caveats=evidence.caveats,
        supporting_evidence=[evidence],
        provenance=ClaimProvenance(
            m5_candidate_id="persisted-source",
            origins=[],
            origin_roles=[],
            supporting_references=[evidence.reference],
        ),
    )
    return VerificationInput(
        source_version="financial_multi_agent_orchestration_v1",
        source_result_sha256="0" * 64,
        question="Persisted-source deterministic evaluation",
        context=PlannerContext(),
        orchestration_status="completed",
        claims=[claim],
    )


def evaluate(root: Path, output: Path):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    before = protected(root, output)
    save_new(output / "hashes-before.json", before)
    print(f"Pinned {len(before)} inputs; hydrating canonical evidence", flush=True)
    data, scopes, recovery = hydrate(root)
    catalog = SnapshotCatalog(**data)
    validator = DeterministicFinancialValidator(catalog)
    retrieval = FinancialRetrievalTools(catalog)
    rows = []
    references = {}

    def run(case_id, group, batch, expected_checks=None, independent=None):
        original = batch.model_dump_json()
        result = validator.validate(batch)
        assert ValidationResult.model_validate_json(result.model_dump_json()) == result, case_id
        assert batch.model_dump_json() == original and not result.financial_fact_verified
        assert result.conflicts == batch.conflicts, case_id
        for claim in result.claims:
            by_id = {c.check_id: c for c in claim.checks}
            if expected_checks:
                for check_id, status in expected_checks.items():
                    assert by_id[check_id].status == status, (case_id, check_id, by_id[check_id])
            oracle = (
                independent.get(claim.candidate_id)
                if isinstance(independent, dict)
                else independent
            )
            if oracle is not None:
                assert by_id["numeric"].expected["value"] == oracle, case_id
            # This table summarizes numeric assertions only, never claim acceptance.
            numeric = by_id.get("numeric")
            rows.append(
                dict(
                    case_id=case_id,
                    candidate_id=claim.candidate_id,
                    group=group,
                    kind=claim.claim_kind,
                    numeric_status=numeric.status if numeric else "undetermined",
                    check_counts=dict(Counter(c.status for c in claim.checks)),
                    fails=[c.reason_code for c in claim.checks if c.status == "fail"],
                    undetermined=[
                        c.reason_code for c in claim.checks if c.status == "undetermined"
                    ],
                    caveats=claim.caveats,
                    expected_checks=expected_checks or {},
                    independent_value=oracle,
                )
            )
        save_new(output / f"result-{case_id}.json", result.model_dump(mode="json"))
        return result

    # Accepted M4 calculations supply trace payloads; expected arithmetic is recomputed
    # independently from canonical operands without using the validator or M4 arithmetic.
    executions = json.loads(
        (root / "artifacts/evidence/M4-03-final/executions.json").read_text(encoding="utf-8")
    )
    labels = {**ITEM_LABELS, **FLOW_LABELS, **BALANCE_LABELS}
    metrics = {m.metric_id: m for m in data["metrics"]}
    for i, wire in enumerate(executions, 1):
        calc = FinancialCalculationResponse.model_validate_json(json.dumps(wire))
        independent = independent_check(metrics[calc.metric_id], data["facts"])
        assert calc.result == independent
        role = {
            "gross_margin": "revenue",
            "debt_to_assets": "assets",
            "revenue_yoy": "current_revenue",
        }[calc.formula_id]
        op = next(o for o in calc.trace.operands if o.role == role)
        evidence = SpecialistEvidence(
            evidence_id="persisted-metric",
            kind="metric",
            reference=RetrievalReference(kind="metric", record_id=calc.metric_id),
            company_id=op.company_id,
            document_id=calc.document_id,
            snapshot_id=calc.snapshot_id,
            period=op.context.period,
            operand_periods=calc.evidence.record.request.operand_periods,
            label=METRIC_LABELS.get(calc.formula_id, "Tỷ lệ nợ phải trả trên tổng tài sản"),
            value=calc.result,
            unit="percent",
            citations=calc.evidence.citations,
            caveats=calc.caveats,
            calculation=calc,
        )
        batch = batch_for(evidence, calculation=calc)
        run(
            f"metric-{i:02}",
            "persisted_source_candidate",
            batch,
            dict(
                numeric="pass",
                formula="pass",
                calculation_result="pass",
                calculation_trace="pass",
                calculation_lineage="pass",
                context="pass",
            ),
            independent,
        )
        references.setdefault(calc.formula_id, batch)
    # Two facts per year/snapshot: B02 revenue and a signed B03 cash flow.
    selections = [(s["document_id"], s["snapshot_id"], year) for year, s in scopes.items()]
    selections.append((recovery.document_id, recovery.snapshot_id, 2022))
    for i, (document, snapshot, year) in enumerate(selections, 1):
        for item in ("b02.net_revenue", "b03.operating_cash_flow"):
            facts = [
                f
                for f in data["facts"]
                if (f.document_id, f.snapshot_id, f.canonical_item_id, f.context.period)
                == (document, snapshot, item, str(year))
            ]
            assert len(facts) == 1
            fact = facts[0]
            match = retrieval.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=document,
                    snapshot_id=snapshot,
                    local_observation_id=fact.local_observation_id,
                )
            ).matches[0]
            evidence = SpecialistEvidence(
                evidence_id="persisted-fact",
                kind="fact",
                reference=match.reference,
                company_id=fact.company_id,
                document_id=document,
                snapshot_id=snapshot,
                period=str(year),
                label=labels[item],
                canonical_item_id=item,
                value=str(fact.value.normalized_value),
                unit=fact.value.unit,
                scale=str(fact.context.scale),
                citations=match.citations,
                caveats=[],
            )
            batch = batch_for(evidence)
            run(
                f"fact-{i:02}-{item.split('.')[0]}",
                "persisted_source_candidate",
                batch,
                dict(numeric="pass", context="pass", provenance="pass"),
                evidence.value,
            )
            if year == 2025 and item == "b02.net_revenue":
                references["fact"] = batch
            if year == 2024 and item == "b02.net_revenue":
                references["scope2024"] = batch
    saved = json.loads(
        (root / "artifacts/evidence/M6-01-conversion/summary.json").read_text(encoding="utf-8")
    )
    for row in saved["rows"]:
        batch = VerificationInput.model_validate_json(
            (root / f"artifacts/evidence/M6-01-conversion/batch-{row['id']}.json").read_text(
                encoding="utf-8"
            )
        )
        oracle = {}
        for claim in batch.claims:
            if claim.metric_ids:
                oracle[claim.candidate_id] = independent_check(
                    metrics[claim.metric_ids[0]], data["facts"]
                )
            else:
                facts = [
                    f
                    for f in data["facts"]
                    if f.observation_identity() == claim.fact_references[0].observation
                ]
                assert len(facts) == 1
                oracle[claim.candidate_id] = str(facts[0].value.normalized_value)
            assert _number(oracle[claim.candidate_id]) in claim.content, row["id"]
        result = run("saved-" + row["id"], row["group"], batch, independent=oracle)
        if "synthetic" not in row["group"]:
            for claim in result.claims:
                assert not [c for c in claim.checks if c.status == "fail"], (row["id"], claim)
                assert next(c for c in claim.checks if c.check_id == "numeric").status == "pass"

    for control, source, check, expected in (
        ("value", "fact", "numeric", "fail"),
        ("period", "fact", "context", "fail"),
        ("document", "fact", "context", "fail"),
        ("snapshot", "fact", "context", "fail"),
        ("item", "fact", "item", "fail"),
        ("currency", "fact", "unit_scale", "fail"),
        ("scope", "scope2024", "reporting_scope", "fail"),
        ("metric_value", "gross_margin", "numeric", "fail"),
        ("metric_result", "gross_margin", "calculation_result", "fail"),
        ("formula", "gross_margin", "formula", "fail"),
        ("operand", "debt_to_assets", "calculation_trace", "fail"),
        ("lineage", "revenue_yoy", "calculation_lineage", "fail"),
        ("missing_calculation", "gross_margin", "formula", "undetermined"),
        ("missing_fact", "fact", "numeric", "undetermined"),
        ("ambiguous_snapshot", "fact", "context", "undetermined"),
        ("interpretation", "gross_margin", "semantic_conclusion", "undetermined"),
    ):
        batch = references[source].model_copy(deep=True)
        claim = batch.claims[0]
        if control == "value":
            claim.content = claim.content.replace(
                _number(claim.supporting_evidence[0].value),
                _number(Decimal(claim.supporting_evidence[0].value) + 1),
            )
        elif control == "period":
            claim.content = claim.content.replace(claim.period, "2020")
        elif control == "document":
            claim.document_id = references["scope2024"].claims[0].document_id
        elif control == "snapshot":
            claim.snapshot_id = recovery.snapshot_id
        elif control == "item":
            claim.content = claim.content.replace("Doanh thu thuần", "Lợi nhuận gộp")
        elif control == "currency":
            claim.content = claim.content.replace("VND", "USD")
        elif control == "scope":
            batch.context.reporting_scope = "consolidated"
        elif control == "metric_value":
            claim.content = claim.content.replace(_number(claim.calculation.result), "99,99")
        elif control == "metric_result":
            claim.calculation.result = "99.99"
        elif control == "formula":
            claim.calculation.formula_digest = "tampered"
        elif control == "operand":
            claim.calculation.trace.operands[0].value = "999"
        elif control == "lineage":
            claim.calculation.evidence.reviewed_lineage.lineage.operands.clear()
        elif control == "missing_calculation":
            claim.calculation = None
        elif control == "missing_fact":
            claim.fact_references = []
        elif control == "ambiguous_snapshot":
            claim.snapshot_id = ""
        else:
            claim.kind = "supported_interpretation"
            claim.content += " Chứng tỏ doanh nghiệp hoạt động hiệu quả hơn."
        run("control-" + control, "synthetic_corruption_on_persisted_BBS", batch, {check: expected})
    # No implicit original/recovery selection when an actual catalog query omits snapshot.
    selection = catalog.select(recovery.document_id, None)
    assert selection.status == "ambiguous"
    after = protected(root, output)
    assert before == after, "Protected source or Web files changed"
    save_new(output / "hashes-after.json", after)
    by_kind = defaultdict(Counter)
    for row in rows:
        by_kind[row["kind"]][row["numeric_status"]] += 1
    summary = dict(
        claim_rows=len(rows),
        groups=dict(Counter(r["group"] for r in rows)),
        numeric_by_kind={k: dict(v) for k, v in by_kind.items()},
        check_counts=dict(sum((Counter(r["check_counts"]) for r in rows), Counter())),
        protected_hashes=len(before),
        protected_unchanged=True,
        actual_llm_calls=0,
        original_recovery_selection=selection.status,
        financial_fact_verified=False,
        limitations="Persisted-source agreement and synthetic sensitivity, not financial accuracy.",
        rows=rows,
    )
    save_new(output / "summary.json", summary)
    print(
        json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False),
        flush=True,
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evaluate(Path.cwd().resolve(), args.output.resolve())
