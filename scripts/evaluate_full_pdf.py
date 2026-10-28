"""Replay automatic PDF selection and score independently checked local references.

No live calls; private inputs and outputs stay outside Git under artifacts/.
"""

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.accounting.financial_runtime import process_financial_pdf
from vietnamese_financial_multi_agent.accounting.relationships import (
    evaluate_automated_relationships,
)
from vietnamese_financial_multi_agent.tools.financial_query import (
    EvidenceSelector,
    FinancialQuery,
    answer_query,
)


def fold_label(text):
    text = "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c)
    ).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text).split())


def score_reference(reference, evidence, quality):
    """One-to-one scoring; duplicate predictions cannot inflate recall.

    Scope is every numeric prediction on reference pages, including unknown codes.
    Correct = value/sign + exact page/statement/code/period + source label association.
    Units and grounding are reported separately; invalid reference is rejected.
    """
    cells = reference["cells"]
    if not cells or not all(c["independently_checked"] for c in cells):
        raise ValueError("independently_checked_reference_required")

    def key(c):
        return c["page"], c["statement"], c["code"], c["period"]

    refs = {key(c): c for c in cells}
    if len(refs) != len(cells):
        raise ValueError("duplicate_reference_cell")
    pages = {c["page"] for c in cells}
    groups = defaultdict(list)
    predictions = []
    decisions = {i.evidence.evidence_id: i.decision for i in quality.items}
    for e in evidence:
        r, anchors = e.extraction, e.extraction.provenance
        page = e.source_metadata["source"]["page"]["page"]
        if page not in pages:
            continue
        k = page, r.context.statement_type, e.source_item_code, r.context.period
        groups[k].append(e)
        if r.value.normalized_value is not None:
            predictions.append((k, e, anchors))
    correct = period_ok = unit_ok = grounded = usable = 0
    matched, errors = set(), []
    for k, e, anchors in predictions:
        r, c = e.extraction, refs.get(k)
        if c:
            period_ok += 1
            unit_ok += r.context.currency == c["unit"] and r.context.scale == Decimal(c["scale"])
        grounding_ok = (
            bool(anchors)
            and all(
                a.anchor.page.source_ref == reference["document_id"] and a.anchor.page.page == k[0]
                for a in anchors
            )
            and e.source_metadata["source"]["page"]["source_ref"] == reference["document_id"]
        )
        grounded += grounding_ok
        usable += decisions[e.evidence_id] in {"usable", "usable_with_caveat"}
        issues = []
        if not c:
            issues.append("wrong_period_or_statement_or_item")
        elif c["kind"] != "numeric":
            issues.append("unexpected_numeric_cell")
        else:
            if r.value.normalized_value != Decimal(c["value"]):
                issues.append("wrong_numeric_value")
                if r.value.normalized_value * Decimal(c["value"]) < 0:
                    issues.append("wrong_sign")
            if fold_label(c["label_contains"]) not in fold_label(r.context.raw_item_label or ""):
                issues.append("wrong_item_association")
        if len(groups[k]) > 1:
            issues.append("duplicate_conflict")
        if not grounding_ok:
            issues.append("source_provenance_problem")
        if issues:
            errors.append(dict(key=k, issues=issues, evidence_id=e.evidence_id))
        else:
            correct += 1
            matched.add(k)
    numeric = [c for c in cells if c["kind"] == "numeric"]
    missing = [key(c) for c in numeric if key(c) not in matched]
    dash = [c for c in cells if c["kind"] == "dash"]
    dash_preserved = sum(
        len(groups[key(c)]) == 1
        and groups[key(c)][0].extraction.value.raw_value.strip() in {"-", "–", "—"}
        and groups[key(c)][0].extraction.value.normalized_value is None
        for c in dash
    )
    dash_as_missing = sum(
        len(groups[key(c)]) == 1 and groups[key(c)][0].extraction.value.normalized_value is None
        for c in dash
    )
    return dict(
        reference_numeric=len(numeric),
        reference_dash=len(dash),
        predicted_numeric=len(predictions),
        correct_numeric=correct,
        matched_reference=len(matched),
        numeric_precision=correct / len(predictions) if predictions else None,
        numeric_recall=len(matched) / len(numeric) if numeric else None,
        period_correct=period_ok,
        unit_correct=unit_ok,
        grounded=grounded,
        direct_qa_usable=usable,
        correctness_denominator=len(predictions),
        dash_preserved=dash_preserved,
        dash_as_missing=dash_as_missing,
        missing_or_incorrect_reference=missing,
        prediction_errors=errors,
        error_counts=dict(Counter(i for e in errors for i in e["issues"])),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = (Path(__file__).resolve().parents[1] / "artifacts").resolve()
    if not args.output.resolve().is_relative_to(root):
        parser.error("output must be under artifacts/")
    config = json.loads(args.spec.read_text(encoding="utf-8"))
    reference = json.loads(args.reference.read_text(encoding="utf-8"))

    def read_cache(paths):
        return {int(p): json.loads(Path(f).read_text(encoding="utf-8")) for p, f in paths.items()}

    start = perf_counter()
    runtime = process_financial_pdf(
        args.pdf,
        symbol=config["symbol"],
        year=config["year"],
        cached_records=read_cache(config["cache"]),
        discovery_cache=read_cache(config["discovery_cache"]),
    )
    relationships = evaluate_automated_relationships(runtime["records"])
    report = dict(
        metrics=score_reference(reference, runtime["evidence"], runtime["quality"]),
        inventory=runtime["inventory"],
        records=runtime["records"],
        evidence=[e.model_dump(mode="json") for e in runtime["evidence"]],
        quality=runtime["quality"].model_dump(mode="json"),
        page_issues=runtime["page_issues"],
        queries=[
            answer_query(
                FinancialQuery(
                    q["query_id"],
                    tuple(EvidenceSelector(**s) for s in q["operands"]),
                    q.get("operation", "retrieve"),
                ),
                runtime["evidence"],
                relationship_checks=relationships,
            )
            for q in config.get("queries", [])
        ],
        gemini_calls=0,
        elapsed_seconds=perf_counter() - start,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(metrics=report["metrics"], elapsed_seconds=report["elapsed_seconds"])))


if __name__ == "__main__":
    main()
