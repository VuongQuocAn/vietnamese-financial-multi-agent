"""Replay three PDF-bound cached pages for M2-07, without network or credentials."""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from vietnamese_financial_multi_agent.accounting import (
    ArithmeticCheck,
    assess_evidence_for_task,
    evaluate_automated_records,
    evaluate_automated_relationships,
    evidence_from_automated_records,
    run_automated_pdf,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = {
        p: args.cache_root / folder / f"page-{p}.json"
        for p, folder in [(5, "retry"), (7, "retry"), (8, "live")]
    }
    hashes = {str(p): hashlib.sha256(path.read_bytes()).hexdigest() for p, path in paths.items()}
    cache = {p: json.loads(path.read_text(encoding="utf-8")) for p, path in paths.items()}
    before = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    records = run_automated_pdf(
        args.pdf, symbol="BBS", year="2025", pages=list(paths), cached_records=cache
    )
    original = deepcopy(records)
    arithmetic = [
        ArithmeticCheck.model_validate_json(json.dumps(c))
        for r in evaluate_automated_records(records)
        for c in r["checks"]
    ]
    relationships = evaluate_automated_relationships(records)
    evidence = evidence_from_automated_records(records)
    direct = assess_evidence_for_task(
        evidence, arithmetic_checks=arithmetic, relationship_checks=relationships
    )

    def select(statement, code, period=None):
        return [
            e
            for e in evidence
            if e.extraction.context.statement_type == statement
            and e.source_item_code == code
            and (period is None or e.extraction.context.period == period)
        ]

    scenarios = {}
    scenarios["net_revenue_2025"] = assess_evidence_for_task(select("B02", "10", "2025"))
    scenarios["uncatalogued_cash_flow_50"] = assess_evidence_for_task(select("B03", "50", "2025"))
    scenarios["gross_profit_comparison"] = assess_evidence_for_task(
        select("B02", "20"), "analytical_qa"
    )
    gross = select("B02", "10", "2025") + select("B02", "11", "2025") + select("B02", "20", "2025")
    scenarios["gross_profit_arithmetic"] = assess_evidence_for_task(
        gross, "accounting_analysis", arithmetic_checks=arithmetic, require_check=True
    )
    cash = select("B01", "110", "2025-12-31") + select("B03", "70", "2025")
    scenarios["closing_cash_relationship"] = assess_evidence_for_task(
        cash, "accounting_analysis", relationship_checks=relationships, require_check=True
    )
    scenarios["partial_comparison"] = assess_evidence_for_task(
        select("B02", "20", "2025"), "analytical_qa", required_evidence_ids=["missing_prior_period"]
    )
    conflict = select("B02", "20", "2025")[0].model_copy(deep=True)
    conflict.evidence_id += "/synthetic-conflict"
    conflict.extraction.value.normalized_value += Decimal("1")
    conflict.extraction.value.raw_value = str(conflict.extraction.value.normalized_value)
    scenarios["synthetic_conflict_only"] = assess_evidence_for_task(
        [*select("B02", "20", "2025"), conflict, *select("B02", "10", "2025")], "report_generation"
    )
    numeric = [e for e in evidence if e.extraction.value.normalized_value is not None]
    report = dict(
        source_sha256=before,
        cache_sha256=hashes,
        gemini_calls=0,
        additional_pages=0,
        accepted_extractions=sum(
            link["status"] == "accepted_extraction"
            for r in records
            for link in r["extraction"]["links"]
        ),
        raw_value_slots=len(evidence),
        raw_numeric_items=len(numeric),
        canonical_numeric_items=sum(e.canonical_item_id is not None for e in numeric),
        uncatalogued_numeric_items=sum(e.canonical_item_id is None for e in numeric),
        direct_counts=direct.summary_counts,
        reason_counts=direct.reason_counts,
        limited_reason_counts=dict(
            Counter(
                issue.code
                for i in direct.items
                if i.decision in {"insufficient", "conflicted"}
                for issue in i.issues
            )
        ),
        scenarios={name: s.model_dump(mode="json") for name, s in scenarios.items()},
        direct=direct.model_dump(mode="json"),
    )
    assert records == original
    assert before == hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    assert hashes == {
        str(p): hashlib.sha256(path.read_bytes()).hexdigest() for p, path in paths.items()
    }
    report.update(source_unchanged=True, extraction_unchanged=True)
    (args.output / "quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"scenarios", "direct"}}, indent=2)
    )
    print(
        json.dumps({name: (s.decision, s.reason_counts) for name, s in scenarios.items()}, indent=2)
    )


if __name__ == "__main__":
    main()
