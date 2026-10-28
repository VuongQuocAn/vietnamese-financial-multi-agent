"""Regression tests for denominators; synthetic fixtures are not accuracy evidence."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
from vietnamese_financial_multi_agent.accounting.quality import assess_evidence_for_task

from .test_financial_query import sample

spec = importlib.util.spec_from_file_location(
    "full_pdf_evaluation", Path(__file__).resolve().parents[2] / "scripts/evaluate_full_pdf.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


@pytest.fixture
def inputs():
    _, _, evidence, _ = sample.__wrapped__()
    cells = [
        dict(
            page=7,
            statement="B02",
            code="11",
            label_contains="uncatalogued label",
            period=period,
            value=value,
            kind="numeric",
            unit="VND",
            scale="1",
            independently_checked=True,
        )
        for period, value in (("2025", "1234"), ("2024", "-2345"))
    ]
    return dict(document_id="synthetic-test", cells=cells), evidence


def score(reference, evidence):
    return evaluation.score_reference(reference, evidence, assess_evidence_for_task(evidence))


def test_complete_and_missing_reference_keep_fixed_recall_denominator(inputs):
    ref, evidence = inputs
    complete = score(ref, evidence)
    assert complete["numeric_precision"] == complete["numeric_recall"] == 1
    missing = score(ref, evidence[:1])
    assert missing["numeric_precision"] == 1
    assert missing["numeric_recall"] == 0.5
    assert missing["reference_numeric"] == 2


@pytest.mark.parametrize("error", ["sign", "period", "label", "source"])
def test_misassociation_and_source_errors_are_not_correct(inputs, error):
    ref, evidence = inputs
    evidence = deepcopy(evidence)
    if error == "sign":
        evidence[0].extraction.value.normalized_value *= -1
    elif error == "period":
        evidence[0].extraction.context.period = "2023"
    elif error == "label":
        evidence[0].extraction.context.raw_item_label = "different item"
    else:
        evidence[0].extraction.provenance[0].anchor.page.source_ref = "different-source"
    result = score(ref, evidence)
    assert result["numeric_precision"] == result["numeric_recall"] == 0.5
    assert result["predicted_numeric"] == 2


def test_duplicates_and_unchecked_reference_cannot_inflate_score(inputs):
    ref, evidence = inputs
    duplicate = evidence[0].model_copy(deep=True, update={"evidence_id": "duplicate"})
    result = score(ref, [*evidence, duplicate])
    assert result["predicted_numeric"] == 3 and result["matched_reference"] == 1
    assert result["error_counts"]["duplicate_conflict"] == 2
    ref["cells"][0]["independently_checked"] = False
    with pytest.raises(ValueError, match="independently_checked"):
        score(ref, evidence)
