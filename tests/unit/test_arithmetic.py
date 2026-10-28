"""Synthetic engineering cases; real-pilot evidence lives in docs/arithmetic-checks.md."""

import copy
from dataclasses import replace
from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.accounting import (
    ARITHMETIC_RULES,
    ArithmeticCheck,
    FinancialContext,
    FinancialNormalizationResult,
    FinancialSourceReference,
    FinancialValue,
    TolerancePolicy,
    evaluate_arithmetic_rules,
    evaluate_automated_records,
    run_automated_pdf,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)

from .test_automated_extraction import sample as image_record  # noqa: F401

RULE = next(rule for rule in ARITHMETIC_RULES if rule.rule_id == "b02.gross_profit")


def value(item, number, **context):
    return FinancialNormalizationResult(
        contract_version="financial_normalization_v1",
        value=FinancialValue(
            raw_value=number, normalized_value=Decimal(number), unit="VND", status="resolved"
        ),
        context=FinancialContext(
            **dict(
                dict(
                    mapped_item_code=f"b02.{item}",
                    period="2025",
                    period_type="fiscal_year",
                    statement_type="B02",
                    currency="VND",
                    scale=Decimal(1),
                ),
                **context,
            )
        ),
        provenance=[
            FinancialSourceReference(
                anchor=SourceAnchor(
                    page=RawPageIdentity(
                        symbol="TEST",
                        year="2025",
                        page=7,
                        image="synthetic-image",
                        source_ref="test-doc",
                    ),
                    status="uncertain",
                ),
                source_pointer=f"/synthetic/{item}",
            )
        ],
    )


def inputs(profit="300", **context):
    return [
        value("gross_profit", profit, **context),
        value("net_revenue", "1000", **context),
        value("cost_of_sales", "700", **context),
    ]


def evaluate(values, **kwargs):
    return evaluate_arithmetic_rules(values, [RULE], **kwargs)


@pytest.mark.parametrize(
    ("reported", "status", "difference"), [("300", "passed", "0"), ("290", "failed", "10")]
)
def test_pass_failure_and_immutable_lineage(reported, status, difference):
    rows = inputs(reported)
    before = copy.deepcopy(rows)
    check = evaluate(rows)[0]
    assert check.status == status
    assert check.computed_value == Decimal(300)
    assert check.reported_value == Decimal(reported)
    assert check.difference == Decimal(difference)
    assert check.tolerance == 0
    assert check.financial_fact_verified is False
    assert rows == before
    assert all(not row.financial_fact_verified for row in rows)
    assert [i.extraction for i in check.inputs] == rows
    assert [i.extraction.provenance for i in check.inputs] == [r.provenance for r in rows]
    assert ArithmeticCheck.model_validate_json(check.model_dump_json()) == check
    check.inputs[0].extraction.provenance.clear()
    assert rows == before


def test_missing_operand_and_missing_reported_are_not_zero():
    for index in (0, 2):
        rows = inputs()
        missing = rows.pop(index).context.mapped_item_code
        check = evaluate(rows)[0]
        assert check.status == "insufficient_data"
        assert check.missing_inputs == [missing]
        assert check.computed_value is None and check.difference is None


@pytest.mark.parametrize(
    "context",
    [
        {"period": "2024"},
        {"reporting_scope": "consolidated"},
        {"period_type": "as_of"},
    ],
)
def test_incompatible_context_never_combines(context):
    rows = inputs(reporting_scope="separate")
    rows[-1] = value("cost_of_sales", "700", reporting_scope="separate")
    rows[-1].context = rows[-1].context.model_copy(update=context)
    checks = evaluate(rows)
    assert len(checks) == 2
    assert all(c.status in {"insufficient_data", "not_applicable"} for c in checks)
    assert all(c.computed_value is None for c in checks)


def test_both_periods_evaluate_independently():
    checks = evaluate(inputs() + inputs("290", period="2024"))
    assert [(c.period, c.status) for c in checks] == [("2025", "passed"), ("2024", "failed")]


@pytest.mark.parametrize("scope", [None, "separate", "consolidated"])
def test_different_sources_are_never_assumed_same_scope(scope):
    rows = inputs(reporting_scope=scope)
    rows[-1].provenance[0].anchor.page.source_ref = "other-document"
    checks = evaluate(rows)
    assert all(c.status == "insufficient_data" for c in checks)
    assert [c.source_pages[0].source_ref for c in checks] == ["test-doc", "other-document"]


def test_unknown_scope_is_not_combined_with_known_scope():
    rows = inputs()
    rows[-1].context.reporting_scope = "separate"
    assert all(c.status == "insufficient_data" for c in evaluate(rows))


@pytest.mark.parametrize(
    "field,new",
    [
        ("unit", "USD"),
        ("unit", None),
        ("scale", Decimal(1000)),
        ("scale", None),
        ("scale", Decimal(0)),
        ("currency", "USD"),
        ("period", None),
        ("period_type", None),
    ],
)
def test_missing_or_conflicting_metadata_prevents_arithmetic(field, new):
    rows = inputs()
    if field == "unit":
        rows[-1].value.unit = new
    else:
        rows[-1].context = rows[-1].context.model_copy(update={field: new})
    checks = evaluate(rows)
    assert all(c.status == "insufficient_data" for c in checks)
    assert all(c.computed_value is None for c in checks)


@pytest.mark.parametrize("number", ["700", "701"])
def test_duplicate_even_equal_values_are_conflicts(number):
    check = evaluate(inputs() + [value("cost_of_sales", number)])[0]
    assert check.status == "insufficient_data"
    assert "duplicate_item:b02.cost_of_sales" in check.issues
    assert len(check.inputs) == 4


def test_decimal_precision_and_float_rejection():
    rows = [
        value("gross_profit", "999999999999999999999999999999.1"),
        value("net_revenue", "999999999999999999999999999999.3"),
        value("cost_of_sales", "0.2"),
    ]
    with localcontext() as ctx:
        ctx.prec = 6
        check = evaluate(rows)[0]
    assert check.status == "passed" and check.difference == Decimal(0)
    with pytest.raises(ValidationError):
        FinancialValue(raw_value="0.1", normalized_value=0.1, status="resolved")
    with pytest.raises(ValidationError):
        TolerancePolicy(absolute=0.1, basis="float")


def test_explicit_absolute_tolerance_boundary_and_basis():
    policy = TolerancePolicy(absolute=Decimal("0.5"), basis="synthetic rounding to displayed unit")
    assert evaluate(inputs("299.5"), tolerance_policy=policy)[0].status == "passed"
    check = evaluate(inputs("299.49"), tolerance_policy=policy)[0]
    assert check.status == "failed"
    assert check.difference == Decimal("0.51")
    assert check.tolerance_basis == policy.basis
    with pytest.raises(ValidationError):
        TolerancePolicy(absolute=Decimal(-1), basis="invalid")


def test_unavailable_not_applicable_and_insufficient_distinct():
    unavailable = replace(RULE, unavailable_reason="catalog_missing:example")
    check = evaluate_arithmetic_rules(inputs(), [unavailable])[0]
    assert check.status == "insufficient_data" and check.computed_value is None
    assert evaluate([])[0].status == "not_applicable"
    checks = evaluate(inputs(period_type="quarter"))
    assert checks[0].status == "not_applicable"


@pytest.mark.parametrize("problem", ["no_provenance", "mixed_pages", "unresolved"])
def test_source_and_value_requirements(problem):
    rows = inputs()
    for row in rows:
        if problem == "no_provenance":
            row.provenance.clear()
        elif problem == "mixed_pages":
            other = row.provenance[0].model_copy(deep=True)
            other.anchor.page.page = 8
            row.provenance.append(other)
        else:
            row.value.status = "uncertain"
    assert evaluate(rows)[0].status == "insufficient_data"


def test_integration_pdf_cache_preserves_unmapped_and_outer_provenance(request, monkeypatch):
    image, record, payload = request.getfixturevalue("image_record")
    table = payload["tables"][0]
    table["rows"] = 5
    for row, label, code, number in [
        (2, "3. Doanh thu thuần về bán hàng và cung cấp dịch vụ", "10", "2.000"),
        (3, "5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ", "20", "766"),
        (4, "Nhãn ngoài catalog", "999", "50"),
    ]:
        for column, text in [(0, label), (1, code), (2, number), (3, number)]:
            table["cells"].append(dict(text=text, row=row, column=column, reading="observed"))
    record["provenance"] = {"pdf_sha256": "synthetic-pdf-hash", "page_number": 7}
    page = SimpleNamespace(image=image, source=record["provenance"])
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.accounting.automated_extraction.load_pages",
        lambda *a, **kw: [page],
    )
    from pathlib import Path

    records = run_automated_pdf(
        Path("synthetic.pdf"), symbol="TEST", year="2025", pages=[7], cached_records={7: record}
    )
    before = copy.deepcopy(records)
    output = evaluate_automated_records(records)[0]
    checks = [c for c in output["checks"] if c["rule_id"] == RULE.rule_id]
    assert [c["status"] for c in checks] == ["passed", "failed"]
    assert records == before
    assert output["provenance"] == record["provenance"]
    assert output["request_id"] == "synthetic-request"
    assert output["model"]["model"] == "mock"
    assert output["source"] == record["source"]
    assert any(
        link["raw_label"] == "Nhãn ngoài catalog" for link in records[0]["extraction"]["links"]
    )
    assert checks[0]["inputs"][0]["automated_link"]["status"] == "accepted_extraction"
    assert not any(c["financial_fact_verified"] for c in output["checks"])
    unusable = copy.deepcopy(records)
    for link in unusable[0]["extraction"]["links"]:
        link["status"], link["result"] = "unresolved", None
    assert all(
        c["status"] == "insufficient_data"
        for c in evaluate_automated_records(unusable)[0]["checks"]
    )
