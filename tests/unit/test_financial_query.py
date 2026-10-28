"""Synthetic runtime/query regressions; not financial accuracy evidence."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.accounting import (
    evidence_from_automated_records,
    validate_automated_extraction,
)
from vietnamese_financial_multi_agent.accounting import financial_runtime as runtime
from vietnamese_financial_multi_agent.accounting.automated_extraction import extract_financial_page
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import IngestionPage
from vietnamese_financial_multi_agent.tools.financial_query import (
    EvidenceSelector,
    FinancialQuery,
    answer_query,
)

from .test_automated_extraction import sample as extraction_sample


@pytest.fixture
def sample():
    image, record, payload = extraction_sample.__wrapped__()
    payload["tables"][0]["cells"][0]["text"] = "Synthetic uncatalogued label"
    record["extraction"] = validate_automated_extraction(image, record)
    evidence = evidence_from_automated_records([record])
    selector = EvidenceSelector("synthetic-test", 7, "B02", "11", "2025")
    return image, record, evidence, selector


def test_raw_retrieval_is_grounded_and_immutable(sample):
    _, record, evidence, s = sample
    original = deepcopy((record, evidence))
    answer = answer_query(FinancialQuery("test", (s,)), evidence)
    assert answer["status"] == "answered"
    assert answer["value"] == "1234"
    assert "missing_canonical_mapping" in answer["reasons"]
    assert answer["facts"][0]["citations"][0]["anchor"]["page"]["page"] == 7
    assert not answer["financial_fact_verified"]
    assert (record, evidence) == original


@pytest.mark.parametrize("change", [dict(page=8), dict(document_id="other"), dict(period="2023")])
def test_exact_source_and_period_selection(sample, change):
    _, _, evidence, s = sample
    result = answer_query(FinancialQuery("test", (replace(s, **change),)), evidence)
    assert result["status"] == "abstained" and not result["facts"]


def test_comparison_and_missing_operand(sample):
    _, _, evidence, s = sample
    query = FinancialQuery("test", (s, replace(s, period="2024")), "difference")
    assert answer_query(query, evidence)["value"] == "3579"
    partial = answer_query(query, evidence[:1])
    assert partial["status"] == "partial" and partial["value"] is None
    assert len(partial["facts"]) == 1


@pytest.mark.parametrize("field,value", [("scale", Decimal("1000")), ("period_type", "as_of")])
def test_incompatible_calculation_context(sample, field, value):
    _, _, evidence, s = sample
    setattr(evidence[1].extraction.context, field, value)
    answer = answer_query(
        FinancialQuery("test", (s, replace(s, period="2024")), "difference"), evidence
    )
    assert answer["status"] == "partial" and answer["value"] is None


def test_conflicting_recovery_does_not_overwrite(sample):
    _, _, evidence, s = sample
    changed = evidence[0].model_copy(deep=True)
    changed.evidence_id += "/recovery/other-request"
    changed.extraction.value.normalized_value += Decimal("1")
    answer = answer_query(FinancialQuery("test", (s,)), [*evidence, changed])
    assert answer["status"] == "abstained"
    assert "conflicting_values" in answer["reasons"]


def test_readable_recovery_can_replace_missing_observation_for_query(sample):
    _, _, evidence, s = sample
    old = evidence[0].model_copy(deep=True)
    old.evidence_id += "/old-unreadable"
    old.extraction.value.normalized_value = None
    old.extraction.value.raw_value = "-"
    answer = answer_query(FinancialQuery("test", (s,)), [old, *evidence])
    assert answer["value"] == "1234"
    assert old.extraction.value.normalized_value is None


def test_label_variation_does_not_block_same_source_code_and_value(sample):
    _, _, evidence, s = sample
    duplicate = evidence[0].model_copy(deep=True)
    duplicate.evidence_id += "/another-row"
    duplicate.extraction.context.raw_item_label = "1. Synthetic uncatalogued label"
    answer = answer_query(FinancialQuery("test", (s,)), [*evidence, duplicate])
    assert answer["value"] == "1234"


def test_runtime_keeps_good_page_after_provider_failure(sample, monkeypatch, tmp_path):
    _, record, _, _ = sample
    failed = deepcopy(record)
    failed["source"]["page"]["page"] = 8
    failed["extraction"] = dict(issues=["invalid_extraction_response"], links=[])
    failed["response"] = None
    monkeypatch.setattr(runtime, "run_automated_pdf", lambda *a, **k: [record, failed])
    answer = runtime.process_financial_pdf(
        tmp_path / "sample.pdf", symbol="TEST", year="2025", pages=[7, 8]
    )
    assert len(answer["evidence"]) == 2
    assert answer["page_issues"] == {8: ["invalid_extraction_response"]}
    assert len(answer["records"]) == 2


def test_recovery_one_request_and_original_preservation(sample, monkeypatch, tmp_path):
    image, record, evidence, s = sample
    monkeypatch.setattr(runtime, "load_pages", lambda *a, **k: [IngestionPage(image, {})])
    calls = []

    def extract(*args, **kwargs):
        calls.append(kwargs)
        return deepcopy(record)

    monkeypatch.setattr(runtime, "extract_financial_page", extract)
    original = deepcopy(evidence)
    result = runtime.recover_financial_target(
        tmp_path / "sample.pdf",
        selector=s,
        target="Read synthetic code 11",
        evidence=evidence,
        symbol="TEST",
        year="2025",
        service=object(),
    )
    assert len(calls) == 1 and calls[0]["target"] == "Read synthetic code 11"
    assert evidence == original and len(result["evidence"]) == 4
    assert result["target_recovered"]
    assert result["record"]["recovery_request"]["target"] == "Read synthetic code 11"


def test_recovery_binding_and_request_guard(sample, monkeypatch, tmp_path):
    image, record, evidence, s = sample
    monkeypatch.setattr(runtime, "load_pages", lambda *a, **k: [IngestionPage(image, {})])
    args = dict(
        target="code 11", evidence=evidence, symbol="TEST", year="2025", cached_record=record
    )
    with pytest.raises(ValueError, match="document_mismatch"):
        runtime.recover_financial_target(
            tmp_path / "test.pdf", selector=replace(s, document_id="other"), **args
        )
    with pytest.raises(ValueError, match="request_mismatch"):
        runtime.recover_financial_target(tmp_path / "test.pdf", selector=s, **args)


def test_target_is_sent_through_existing_structured_gateway(sample):
    image, _, _, _ = sample
    requests = []

    class Service:
        def generate(self, request, **kwargs):
            requests.append((request, kwargs))
            return SimpleNamespace(response=None)

    result = extract_financial_page(
        Service(), IngestionPage(image, {}), credential_ref="mock", target="code 11"
    )
    assert len(requests) == 1
    request, kwargs = requests[0]
    assert "Target: code 11" in request.messages[0].content
    assert request.output_spec.schema_ref.schema_id == "urn:financial-extraction"
    assert kwargs["cache_allowed"]
    assert result["extraction"]["issues"] == ["invalid_extraction_response"]


@pytest.mark.parametrize("raw", ["-", "9.999"])
def test_failed_or_conflicting_recovery_retains_original(sample, monkeypatch, tmp_path, raw):
    image, record, evidence, selector = sample
    changed = deepcopy(record)
    changed["response"]["output"]["payload"]["tables"][0]["cells"][2]["text"] = raw
    changed["extraction"] = validate_automated_extraction(image, changed)
    monkeypatch.setattr(runtime, "load_pages", lambda *a, **k: [IngestionPage(image, {})])
    monkeypatch.setattr(runtime, "extract_financial_page", lambda *a, **k: changed)
    original = deepcopy(evidence)
    result = runtime.recover_financial_target(
        tmp_path / "test.pdf",
        selector=selector,
        target="code 11",
        evidence=evidence,
        symbol="TEST",
        year="2025",
        service=object(),
    )
    assert not result["target_recovered"]
    assert evidence == original and len(result["evidence"]) == 4
    query = FinancialQuery("test", (selector,))
    if raw == "-":
        assert answer_query(query, result["evidence"])["value"] == "1234"
    else:
        assert answer_query(query, result["evidence"])["value"] is None


def test_match_requires_endpoint_check(sample):
    _, _, evidence, s = sample
    result = answer_query(FinancialQuery("test", (s, replace(s, period="2024")), "match"), evidence)
    assert result["value"] is None and "unsupported_rule" in result["reasons"]
