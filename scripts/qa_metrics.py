"""Final-answer QA scoring from reviewed propositions, not pipeline verdicts.

Input keeps quoted answer spans, typed numeric slots and human source adjudication.
The scorer checks span presence and arithmetic equivalence; it is not an LLM judge.
Gold data and annotated private answers stay in ignored evidence directories.
"""

import argparse
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


def equivalent(prediction, gold):
    """Values are decimal strings transcribed from a quoted final-answer span.

    indicator/period are reviewed separately through the gold slot identity.
    scale converts money to VND, percent to ratio; rounding uses displayed
    precision in the prediction's own unit. No relative-error allowance.
    """
    units = {"VND": ("money", "1"), "percent": ("ratio", "0.01"), "ratio": ("ratio", "1")}
    dimension, factor = units[prediction["unit"]]
    gold_dimension, gold_factor = units[gold["unit"]]
    value = Decimal(prediction["value"])
    scale = Decimal(prediction.get("scale", "1")) * Decimal(factor)
    expected = Decimal(gold["value"]) * Decimal(gold.get("scale", "1")) * Decimal(gold_factor)
    if dimension != gold_dimension or scale <= 0:
        return False
    quantum = Decimal(1).scaleb(value.as_tuple().exponent)
    return (expected / scale).quantize(quantum, rounding=ROUND_HALF_UP) == value


def score(review):
    if review["status"] != "COMPLETED":
        return dict(status=review["status"], metrics=None)
    answer = review["answer"]
    gold = {g["id"]: g for g in review["gold"]}
    assert len(gold) == len(review["gold"]), "duplicate_gold_id"
    claims = review["claims"]
    assert len({c["id"] for c in claims}) == len(claims), "deduplicate_propositions_before_scoring"
    matched, numeric_matched = set(), set()
    correct = cited = citation_correct = citation_required = citation_covered = 0
    numeric_errors = 0
    for claim in claims:
        assert claim["quote"] and claim["quote"] in answer, "claim_must_quote_final_answer"
        assert claim["assessment"], "source_adjudication_required"
        ids = claim.get("gold_ids", [])
        assert all(key in gold for key in ids), "unknown_gold_id"
        valid = claim["correct"]
        for key in ids:
            if "value" in gold[key]:
                prediction = claim.get("numeric")
                valid = valid and prediction is not None and equivalent(prediction, gold[key])
        correct += int(valid)
        numeric_errors += int(not valid and "numeric" in claim)
        if valid:
            matched.update(ids)
            numeric_matched.update(key for key in ids if "value" in gold[key])
        if claim.get("citation_required", True):
            citation_required += 1
            citation_covered += int(valid and claim.get("citation_correct", False))
        if claim.get("cited", False):
            cited += 1
            citation_correct += int(valid and claim["citation_correct"])
    numeric_total = sum("value" in g for g in gold.values())
    precision = correct / len(claims) if claims else 0.0
    recall = len(matched) / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    all_correct = correct == len(claims)
    return dict(
        status="COMPLETED",
        counts=dict(
            correct_claims=correct,
            emitted_claims=len(claims),
            matched_gold=len(matched),
            required_gold=len(gold),
            correct_numeric=len(numeric_matched),
            required_numeric=numeric_total,
            correct_citations=citation_correct,
            cited_claims=cited,
            citation_covered=citation_covered,
            citation_required=citation_required,
        ),
        metrics=dict(
            numeric_accuracy=len(numeric_matched) / numeric_total if numeric_total else None,
            numeric_em=int(len(numeric_matched) == numeric_total and not numeric_errors)
            if numeric_total
            else None,
            claim_precision=precision,
            claim_recall=recall,
            claim_f1=f1,
            citation_accuracy=citation_correct / cited if cited else None,
            citation_completeness=citation_covered / citation_required
            if citation_required
            else None,
            answer_accuracy=int(
                len(matched) == len(gold)
                and all_correct
                and citation_covered == citation_required
                and review["constraints_met"]
            ),
        ),
        unmatched_gold=sorted(gold.keys() - matched),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    print(json.dumps(score(json.loads(args.review.read_text(encoding="utf-8-sig"))), indent=2))
