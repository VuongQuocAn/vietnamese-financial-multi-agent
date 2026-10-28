"""Replay PDF-bound cache for M2-06; no network client or credentials."""

import argparse
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from vietnamese_financial_multi_agent.accounting import (
    RELATIONSHIP_RULES,
    evaluate_automated_relationships,
    run_automated_pdf,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = {
        page: args.cache_root / folder / f"page-{page}.json"
        for page, folder in [(5, "retry"), (7, "retry"), (8, "live")]
    }
    cache = {page: json.loads(path.read_text(encoding="utf-8")) for page, path in paths.items()}
    before = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    records = run_automated_pdf(
        args.pdf, symbol="BBS", year="2025", pages=list(paths), cached_records=cache
    )
    if any(r["extraction"]["issues"] for r in records):
        raise ValueError("cached_extraction_has_page_issues")
    original = deepcopy(records)
    checks = evaluate_automated_relationships(records)
    if records != original or before != hashlib.sha256(args.pdf.read_bytes()).hexdigest():
        raise ValueError("source_or_extraction_changed")
    counts = dict(Counter(check.status for check in checks))
    report = dict(
        source_sha256=before,
        source_unchanged=True,
        extraction_unchanged=True,
        accepted_extractions=sum(
            link["status"] == "accepted_extraction"
            for record in records
            for link in record["extraction"]["links"]
        ),
        active_rules=[r.rule_id for r in RELATIONSHIP_RULES if not r.unavailable_reason],
        unavailable_rules={
            r.rule_id: r.unavailable_reason for r in RELATIONSHIP_RULES if r.unavailable_reason
        },
        additional_pages=0,
        gemini_calls=0,
        counts=counts,
        cache_sha256={
            str(page): hashlib.sha256(path.read_bytes()).hexdigest() for page, path in paths.items()
        },
        checks=[check.model_dump(mode="json") for check in checks],
    )
    (args.output / "relationships.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(counts))
    for check in checks:
        print(
            check.rule_id,
            check.period,
            check.status,
            check.difference,
            sorted(
                {
                    ref.anchor.page.page
                    for i in check.inputs
                    for ref in i.value.extraction.provenance
                }
            ),
            check.missing_inputs,
            check.issues,
        )


if __name__ == "__main__":
    main()
