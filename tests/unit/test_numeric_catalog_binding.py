"""Catalog label binding controls; no source reviews or semantic approvals inferred."""

from decimal import Decimal

from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime
from vietnamese_financial_multi_agent.verification.numeric import extract_assertion, parse_number

from .test_financial_validators import batch_for
from .test_m4_execution import fixture


def inputs():
    data = fixture()
    batch = batch_for(data)
    fact = data["facts"][0]
    fact.canonical_item_id = fact.context.mapped_item_code = "b02.revenue_deductions"
    fact.context.raw_item_label = "2. Các khoản giảm trừ doanh thu"
    data["source_reviews"][0].raw_label = fact.context.raw_item_label
    evidence = batch.claims[0].supporting_evidence[0]
    evidence.canonical_item_id = fact.canonical_item_id
    evidence.label = fact.context.raw_item_label
    return data, batch, fact


def test_equivalent_numbers_and_source_row_label_bind_the_same_fact():
    data, batch, fact = inputs()
    value = Decimal(fact.value.normalized_value)
    grouped = format(value, ",.2f").translate(str.maketrans({",": ".", ".": ","}))
    for number in (str(value), grouped, format(value, ".0f") + ",00"):
        batch.claims[0].content = f"2. Các khoản giảm trừ doanh thu kỳ 2030 là {number} VND."
        assertion = extract_assertion(batch.claims[0].content)
        assert assertion.target == fact.canonical_item_id
        assert assertion.value == value
        verdict = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0].outcome.final
        assert verdict.decision == "ACCEPT", verdict.reason_codes


def test_wrong_value_unit_period_and_item_still_fail_numeric_binding():
    data, batch, fact = inputs()
    value = Decimal(fact.value.normalized_value)
    controls = [
        (f"Các khoản giảm trừ doanh thu kỳ 2030 là {value + 1} VND.", "numeric_value_mismatch"),
        (f"Các khoản giảm trừ doanh thu kỳ 2030 là {value} USD.", "currency_unit_scale_mismatch"),
        (f"Các khoản giảm trừ doanh thu kỳ 2029 là {value} VND.", "content_period_mismatch"),
        (f"Doanh thu thuần kỳ 2030 là {value} VND.", "financial_item_mismatch"),
    ]
    for content, error in controls:
        batch.claims[0].content = content
        verdict = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0].outcome.final
        assert verdict.decision != "ACCEPT"
        assert error in {c.reason_code for c in verdict.validation.checks}


def test_ambiguous_catalog_labels_and_malformed_quantities_are_not_guessed():
    assert extract_assertion("Hàng tồn kho kỳ 2030 là 123 VND.") is None
    assert extract_assertion("Chỉ tiêu không xác định kỳ 2030 là 123 VND.") is None
    assert extract_assertion("2. Các khoản giảm trừ doanh thu kỳ 2030 là 1.23.456 VND.") is None
    assert extract_assertion("Các khoản giảm trừ doanh thu kỳ 2030 là 123 VND và 999 VND.") is None
    assert parse_number("1.23.456") is None
