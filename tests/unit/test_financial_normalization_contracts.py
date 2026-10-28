"""Synthetic fixtures kiểm tra contract, không đánh giá financial accuracy."""

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from vietnamese_financial_multi_agent.accounting import (
    FinancialNormalizationResult,
    FinancialValue,
    financial_normalization_json_schema,
    validate_financial_quality,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedRegion,
)


@pytest.fixture
def payload():
    return {
        "contract_version": "financial_normalization_v1",
        "value": {
            "raw_value": " 1.234.567 ",
            "normalized_value": Decimal("123456789012345678901234567890.123456789000"),
            "unit": "VND",
            "status": "resolved",
        },
        "context": {
            "period": "2025",
            "period_type": "annual",
            "currency": "VND",
            "scale": Decimal("1000"),
            "reporting_scope": "consolidated",
            "statement_type": "B01",
            "raw_item_label": "Chỉ tiêu synthetic",
            "mapped_item_code": None,
        },
        "provenance": [
            {
                "anchor": {
                    "page": {
                        "symbol": "SYNTHETIC",
                        "year": "2025",
                        "page": 1,
                        "image": "synthetic/page.png",
                        "source_ref": "synthetic/unified.json",
                    },
                    "status": "unresolved",
                },
                "source_pointer": "/pages/0/tables/0/cells/0",
                "provenance_level": "page",
            }
        ],
    }


def test_json_round_trip_keeps_raw_and_decimal_precision(payload):
    result = FinancialNormalizationResult.model_validate(payload)
    exported = result.export_result()
    assert exported["value"]["raw_value"] == " 1.234.567 "
    assert exported["value"]["normalized_value"] == "123456789012345678901234567890.123456789000"
    assert exported["context"]["scale"] == "1000"
    restored = FinancialNormalizationResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.value.normalized_value.as_tuple() == result.value.normalized_value.as_tuple()


def test_raw_strings_are_never_parsed():
    for raw in ("1.234.567", "(1.234)", "-", "  0,00\n"):
        value = FinancialValue(raw_value=raw, status="unresolved")
        assert value.raw_value == raw
        assert value.normalized_value is None


def test_missing_context_and_values_are_quality_signals(payload):
    payload["value"] = {"raw_value": "", "status": "unresolved"}
    payload["context"] = {"period": None}
    payload["provenance"] = []
    result = FinancialNormalizationResult.model_validate(payload)
    before = result.model_dump_json()
    issues = validate_financial_quality(result)
    codes = {issue.code for issue in issues}
    assert {
        "missing_raw_value",
        "missing_normalized_value",
        "missing_unit",
        "missing_context",
        "missing_provenance",
        "value_not_resolved",
    } <= codes
    assert any(issue.path == ["context", "period"] for issue in issues)
    assert result.model_dump_json() == before


def test_unified_page_provenance_is_not_upgraded(payload):
    region = UnifiedRegion(
        source_pointer="/pages/0/tables/0/cells/0",
        text="1.234.567",
        status="accepted",
        quality={"text_accepted": True, "downstream_usable": True, "usable_for": ["text_evidence"]},
        source_component={"text": "1.234.567"},
    )
    reference = payload["provenance"][0]
    reference["source_pointer"] = region.source_pointer
    reference["provenance_level"] = region.provenance_level
    result = FinancialNormalizationResult.model_validate(payload)
    anchor = result.provenance[0].anchor
    assert anchor.cell_id is anchor.table_id is anchor.element_id is anchor.observed_bbox is None
    assert result.provenance[0].provenance_level == "page"
    assert {issue.code for issue in validate_financial_quality(result)} == {
        "page_level_provenance",
        "provenance_unverified",
    }


def test_invalid_types_versions_and_extras_are_rejected(payload):
    for path, bad in (
        (("contract_version",), "financial_normalization_v2"),
        (("value", "raw_value"), 123),
        (("value", "normalized_value"), 1.234),
        (("value", "normalized_value"), "1.234"),
        (("value", "normalized_value"), Decimal("NaN")),
        (("value", "status"), "verified"),
        (("context", "statement_type"), "B04"),
        (("context", "scale"), True),
        (("unexpected",), "extra"),
        (("financial_fact_verified",), True),
        (("provenance", 0, "anchor", "page", "page"), "1"),
    ):
        candidate = copy.deepcopy(payload)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = bad
        with pytest.raises(ValidationError):
            FinancialNormalizationResult.model_validate(candidate)


def test_json_decimal_requires_finite_string(payload):
    exported = FinancialNormalizationResult.model_validate(payload).export_result()
    for field, target in (("normalized_value", exported["value"]), ("scale", exported["context"])):
        original = target[field]
        for bad in (1.23, 123, True, "NaN", "Infinity", "1.234.567"):
            target[field] = bad
            with pytest.raises(ValidationError):
                FinancialNormalizationResult.model_validate_json(json.dumps(exported))
        target[field] = original


def test_cell_references_are_preserved_but_not_source_verified(payload):
    reference = payload["provenance"][0]
    reference["provenance_level"] = "cell"
    reference["anchor"].update(
        table_id="observed-table", cell_id="observed-cell", status="resolved"
    )
    result = FinancialNormalizationResult.model_validate(payload)
    assert result.provenance[0].anchor.cell_id == "observed-cell"
    assert not validate_financial_quality(result)
    assert result.financial_fact_verified is False
    del reference["anchor"]["table_id"]
    result = FinancialNormalizationResult.model_validate(payload)
    assert "inconsistent_provenance" in {i.code for i in validate_financial_quality(result)}


def test_schema_artifact_and_structural_validity_do_not_verify_facts(payload):
    schema = financial_normalization_json_schema()
    artifact = (
        Path(__file__).resolve().parents[2] / "schemas/financial_normalization_v1.schema.json"
    )
    assert json.loads(artifact.read_text(encoding="utf-8")) == schema
    Draft202012Validator.check_schema(schema)
    result = FinancialNormalizationResult.model_validate(payload)
    Draft202012Validator(schema).validate(result.export_result())
    assert result.financial_fact_verified is False
    assert result.value.status == "resolved"
    assert validate_financial_quality(result)  # Schema hợp lệ vẫn thiếu provenance evidence.
