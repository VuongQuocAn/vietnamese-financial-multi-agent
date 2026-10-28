"""Synthetic engineering regressions, never financial accuracy measurements."""

import copy
import json
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.accounting import (
    ArithmeticCheck,
    AssessableEvidence,
    assess_automated_records,
    assess_evidence_for_task,
    evaluate_arithmetic_rules,
    evaluate_automated_records,
    evaluate_automated_relationships,
    evidence_from_automated_records,
    validate_automated_extraction,
)
from vietnamese_financial_multi_agent.accounting.quality import QualityAssessment

from .test_arithmetic import inputs as arithmetic_inputs
from .test_automated_extraction import sample as extraction_sample
from .test_relationships import record as relationship_record
from .test_relationships import sample as relationship_value


@pytest.fixture
def sample():
    return extraction_sample.__wrapped__()


def records(sample):
    image, record, _ = sample
    return [dict(record, provenance={}, extraction=validate_automated_extraction(image, record))]


def test_canonical_page_retrieval_without_checks_or_verification(sample):
    rs = records(sample)
    original = copy.deepcopy(rs)
    result = assess_automated_records(rs)
    assert result.summary_counts == {"usable": 2}
    assert result.items[0].evidence.extraction.provenance[0].provenance_level == "page"
    assert not result.financial_fact_verified
    assert all(not i.evidence.extraction.financial_fact_verified for i in result.items)
    assert QualityAssessment.model_validate_json(result.model_dump_json()) == result
    assert rs == original


def test_raw_outside_catalog_preserved(sample):
    image, record, payload = sample
    payload["tables"][0]["cells"][0]["text"] = "Synthetic unmapped item"
    rs = [dict(record, extraction=validate_automated_extraction(image, record))]
    result = assess_automated_records(rs)
    assert result.summary_counts == {"usable_with_caveat": 2}
    assert result.reason_counts == {"missing_canonical_mapping": 2}
    assert all(i.evidence.canonical_item_id is None for i in result.items)
    assert all(link["status"] == "unresolved" for link in rs[0]["extraction"]["links"])


@pytest.mark.parametrize("field,expected", [("period", "missing_period"), ("unit", "missing_unit")])
def test_missing_context(sample, field, expected):
    e = evidence_from_automated_records(records(sample))[0]
    if field == "period":
        e.extraction.context.period = None
    else:
        e.extraction.value.unit = None
    result = assess_evidence_for_task([e])
    assert expected in result.reason_counts
    assert result.items[0].decision == (
        "insufficient" if field == "period" else "usable_with_caveat"
    )


def test_missing_provenance_not_grounded(sample):
    e = evidence_from_automated_records(records(sample))[0]
    e.extraction.provenance = []
    assert assess_evidence_for_task([e]).items[0].decision == "insufficient"


def test_scoped_conflict_and_partial_report(sample):
    first, other_period = evidence_from_automated_records(records(sample))
    conflict = first.model_copy(deep=True)
    conflict.evidence_id += "/duplicate"
    conflict.extraction.value.normalized_value = Decimal("999")
    result = assess_evidence_for_task([first, conflict, other_period], "report_generation")
    assert [i.decision for i in result.items] == ["conflicted", "conflicted", "usable"]
    assert result.decision == "usable_with_caveat"
    comparison = assess_evidence_for_task([first, conflict], "analytical_qa")
    assert comparison.decision == "conflicted"
    assert assess_evidence_for_task([first, conflict]).decision == "conflicted"


@pytest.mark.parametrize("field", ["unit", "scale", "currency", "reporting_scope"])
def test_analytical_compatibility(sample, field):
    values = evidence_from_automated_records(records(sample))
    if field == "unit":
        values[1].extraction.value.unit = "USD"
    else:
        setattr(
            values[1].extraction.context,
            field,
            {"scale": Decimal("1000"), "currency": "USD", "reporting_scope": "separate"}[field],
        )
    result = assess_evidence_for_task(values, "analytical_qa")
    assert result.decision == "insufficient"
    assert all(i.decision == "usable" for i in result.items)


def test_partial_evidence_and_unsupported_rule(sample):
    e = evidence_from_automated_records(records(sample))[0]
    result = assess_evidence_for_task([e], "analytical_qa", required_evidence_ids=["absent"])
    assert result.decision == "insufficient"
    assert result.items[0].decision == "usable"
    result = assess_evidence_for_task([e], "accounting_analysis", require_check=True)
    assert result.reason_counts == {"unsupported_rule": 1}
    assert result.items[0].decision == "usable"


@pytest.mark.parametrize("reading", ["inferred", "unknown"])
def test_uncertain_raw_reading_is_not_promoted(sample, reading):
    image, record, payload = sample
    payload["tables"][0]["cells"][0]["text"] = "Synthetic unmapped item"
    payload["tables"][0]["cells"][2]["reading"] = reading
    result = assess_automated_records(
        [dict(record, extraction=validate_automated_extraction(image, record))]
    )
    assert result.items[0].decision == "insufficient"
    assert result.items[1].decision == "usable_with_caveat"


def test_integration_with_insufficient_arithmetic_and_relationships(sample):
    rs = records(sample)
    arithmetic = [
        ArithmeticCheck.model_validate_json(json.dumps(c))
        for r in evaluate_automated_records(rs)
        for c in r["checks"]
    ]
    # Relationship API requires PDF-bound source metadata; empty records yield
    # unavailable annotations, which must not block direct retrieval.
    relationships = evaluate_automated_relationships([])
    result = assess_automated_records(
        rs, arithmetic_checks=arithmetic, relationship_checks=relationships
    )
    assert result.summary_counts == {"usable": 2}
    assert json.loads(result.model_dump_json())["financial_fact_verified"] is False


def test_failed_arithmetic_is_contextual_annotation():
    values = arithmetic_inputs(profit="999")
    for v in values:
        v.context.raw_item_label = v.context.mapped_item_code
    checks = evaluate_arithmetic_rules(values)
    evidence = [
        AssessableEvidence(
            evidence_id=str(i), extraction=v, canonical_item_id=v.context.mapped_item_code
        )
        for i, v in enumerate(values)
    ]
    result = assess_evidence_for_task(evidence, arithmetic_checks=checks)
    assert all(i.decision == "usable_with_caveat" for i in result.items)
    assert result.reason_counts == {"arithmetic_mismatch": 3}
    assert all(not e.extraction.financial_fact_verified for e in evidence)


def test_inconsistent_relationship_and_irrelevant_check():
    rows = [relationship_value(), relationship_value("B03", "102")]
    for row in rows:
        row.extraction.context.raw_item_label = row.extraction.context.mapped_item_code
        for ref in row.extraction.provenance:
            ref.source_pointer = "/context/0"
    checks = evaluate_automated_relationships([relationship_record(row) for row in rows])
    evidence = [
        AssessableEvidence(
            evidence_id=str(i),
            extraction=row.extraction,
            canonical_item_id=row.extraction.context.mapped_item_code,
        )
        for i, row in enumerate(rows)
    ]
    direct = assess_evidence_for_task(evidence, relationship_checks=checks)
    assert direct.reason_counts == {"relationship_mismatch": 2}
    accounting = assess_evidence_for_task(
        evidence, "accounting_analysis", relationship_checks=checks, require_check=True
    )
    assert accounting.decision == "usable_with_caveat"
    unrelated = assess_evidence_for_task(
        [evidence[0]], "accounting_analysis", relationship_checks=checks, require_check=True
    )
    assert unrelated.decision == "insufficient"
    assert "unsupported_rule" in unrelated.reason_counts


def test_missing_unit_raw_fallback_is_usable_with_caveat(sample):
    image, record, payload = sample
    payload["context"] = payload["context"][:-1]
    result = assess_automated_records(
        [dict(record, extraction=validate_automated_extraction(image, record))]
    )
    assert all(i.decision == "usable_with_caveat" for i in result.items)
    assert all(i.evidence.extraction.value.unit is None for i in result.items)
    assert result.reason_counts == {"missing_unit": 2}


def test_missing_period_raw_fallback_is_insufficient(sample):
    image, record, payload = sample
    payload["tables"][0]["headers"][0]["text"] = "Unknown period"
    result = assess_automated_records(
        [dict(record, extraction=validate_automated_extraction(image, record))]
    )
    assert result.items[0].decision == "insufficient"
    assert result.items[0].evidence.extraction.context.period is None


def test_missing_number_is_not_conflict(sample):
    first = evidence_from_automated_records(records(sample))[0]
    absent = first.model_copy(deep=True)
    absent.evidence_id += "/missing"
    absent.extraction.value.normalized_value = None
    absent.extraction.value.raw_value = "-"
    result = assess_evidence_for_task([first, absent])
    assert [i.decision for i in result.items] == ["usable", "insufficient"]


def test_period_types_not_interchangeable(sample):
    values = evidence_from_automated_records(records(sample))
    values[1].extraction.context.period_type = "as_of"
    result = assess_evidence_for_task(values, "analytical_qa")
    assert result.decision == "insufficient"
    assert result.reason_counts == {"incompatible_period": 1}
