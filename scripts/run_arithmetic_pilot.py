"""Replay bounded PDF-bound M2-04b cache; no network client or credential needed."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from vietnamese_financial_multi_agent.accounting import (
    evaluate_automated_records,
    run_automated_pdf,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Fail before reading/rendering if output exists; never overwrite artifacts.
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [
        args.cache_root / folder / f"page-{page}.json"
        for page, folder in [(5, "retry"), (7, "retry"), (8, "live")]
    ]
    cache = {
        page: json.loads(path.read_text(encoding="utf-8"))
        for page, path in zip((5, 7, 8), paths, strict=True)
    }
    before = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    records = run_automated_pdf(
        args.pdf,
        symbol="BBS",
        year="2025",
        pages=[5, 7, 8],
        cached_records=cache,
    )
    if any(record["extraction"]["issues"] for record in records):
        raise ValueError("cached_extraction_has_page_issues")
    annotations = evaluate_automated_records(records)
    counts = {}
    for record, annotation in zip(records, annotations, strict=True):
        statement = record["extraction"]["statement_type"]
        counts[statement] = dict(Counter(check["status"] for check in annotation["checks"]))
    after = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if before != after:
        raise ValueError("source_changed")
    output = dict(
        source_sha256=before,
        source_unchanged=True,
        live_calls=0,
        cache_sha256=[hashlib.sha256(path.read_bytes()).hexdigest() for path in paths],
        counts=counts,
        annotations=annotations,
    )
    (args.output / "arithmetic.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
