"""Focused arithmetic/gate controls; synthetic evidence không là financial gold."""

from decimal import ROUND_UP, Decimal, localcontext

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.evidence import (
    SnapshotCatalog,
    build_graph,
    rebuild_snapshot_metrics,
)
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    FinancialCalculationResponse,
    FinancialCalculator,
)

from .test_m4_execution import fixture


def rebuild(data):
    definition = data["metrics"][0].definition
    data["metrics"] = rebuild_snapshot_metrics(
        [
            (
                definition,
                {
                    r.role: f.context.period
                    for r, f in zip(definition.compatibility.operands, data["facts"], strict=True)
                },
            )
        ],
        data["descriptors"][0],
        data["facts"],
    )
    data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])


def numbers(data, left, right):
    for fact, review, value in zip(
        data["facts"], data["source_reviews"], (left, right), strict=True
    ):
        fact.value.normalized_value = Decimal(value)
        # M1/M4 SourceReview chấp nhận số nguyên VND trong PDF, giữ Decimal
        # representation gốc (kể cả trailing zeros) trong trace.
        fact.value.raw_value = format(Decimal(value).to_integral_value(), "f")
        review.raw_value = fact.value.raw_value
    rebuild(data)
    return data


def calculate(data, **guards):
    return FinancialCalculator(SnapshotCatalog(**data)).calculate_financial_metric(
        CalculateFinancialMetricRequest(metric_id=data["metrics"][0].metric_id, **guards)
    )


@pytest.mark.parametrize("document", [0, 1])
@pytest.mark.parametrize(
    "formula,left,right,expected",
    [
        ("gross_margin", "250", "1000", "25.00"),
        ("gross_margin", "-50", "200", "-25.00"),
        ("gross_margin", "0", "200", "0.00"),
        ("debt_to_assets", "1200", "1000", "120.00"),
        ("revenue_yoy", "120", "100", "20.00"),
        ("revenue_yoy", "80", "100", "-20.00"),
        ("revenue_yoy", "0", "100", "-100.00"),
    ],
)
def test_formulas_and_exact_lineage(formula, left, right, expected, document):
    data = numbers(fixture(formula, document), left, right)
    before = [m.model_dump_json() for m in [*data["facts"], *data["metrics"]]]
    result = calculate(data)
    assert result.status == "computed", result.reasons
    assert result.result == expected and result.output_unit == "percent"
    assert not result.financial_fact_verified
    assert result.trace.formula.definition_digest() == result.formula_digest
    assert result.trace.approval.definition_sha256 == result.formula_digest
    assert result.formula_version == result.trace.formula.version
    assert [o.value for o in result.trace.operands] == [left, right]
    assert result.evidence.closure.calculation_eligible
    assert result.evidence.reviewed_lineage.lineage.completeness == "complete"
    assert all(c.source.reference.provenance_level == "page" for c in result.evidence.citations)
    for traced, original in zip(result.trace.operands, data["metrics"][0].operands, strict=True):
        assert traced.observation == original.observation
        assert traced.source_fact_node_id == original.source_fact_node_id
    assert before == [m.model_dump_json() for m in [*data["facts"], *data["metrics"]]]
    assert data["metrics"][0].result is None


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("201", "20000", "1.00"),
        ("203", "20000", "1.02"),
        ("-201", "20000", "-1.00"),
        ("-203", "20000", "-1.02"),
        ("12345678901234567890123456789", "98765432109876543210987654321", "12.50"),
        ("250.000000", "1000.000000", "25.00"),
        ("1", "6", "16.67"),
    ],
)
def test_precision_final_rounding_and_restart(left, right, expected, tmp_path):
    data = numbers(fixture(), left, right)
    calculator = FinancialCalculator(SnapshotCatalog(**data))
    request = CalculateFinancialMetricRequest(metric_id=data["metrics"][0].metric_id)
    with localcontext() as ambient:
        ambient.prec, ambient.rounding = 5, ROUND_UP
        result = calculator.calculate_financial_metric(request)
    assert result.status == "computed", result.reasons
    assert result.result == expected
    artifact = tmp_path / "execution.json"
    artifact.write_text(result.model_dump_json(), encoding="utf-8")
    restored = FinancialCalculationResponse.model_validate_json(
        artifact.read_text(encoding="utf-8")
    )
    # Disk-rehydrate every model, including persisted graph and policies/approvals.
    fresh = {
        k: [type(v).model_validate_json(v.model_dump_json()) for v in value]
        if isinstance(value, list)
        else type(value).model_validate_json(value.model_dump_json())
        for k, value in data.items()
    }
    restarted = FinancialCalculator(SnapshotCatalog(**fresh))
    assert restarted.calculate_financial_metric(restored.request) == restored
    result.trace.operands[0].value = "999"
    result.evidence.operands.clear()
    data["facts"].clear()
    assert calculator.calculate_financial_metric(request) == restored


@pytest.mark.parametrize("formula", ["gross_margin", "debt_to_assets", "revenue_yoy"])
@pytest.mark.parametrize("denominator", ["0", "-1"])
def test_denominator_and_nonnegative_guards(formula, denominator):
    result = calculate(numbers(fixture(formula), "100", denominator))
    assert result.status == "blocked" and result.result is None and result.trace is None
    assert "denominator_non_positive_or_missing" in result.reasons
    if formula != "gross_margin":
        negative = calculate(numbers(fixture(formula), "-1", "100"))
        assert negative.status == "blocked" and negative.result is None
        assert "nonnegative_operand_required" in negative.reasons


@pytest.mark.parametrize(
    "control",
    [
        "null",
        "missing",
        "nan",
        "snan",
        "infinity",
        "invalid_decimal",
        "unit",
        "currency",
        "scale",
        "period",
        "nonconsecutive",
        "document",
        "snapshot",
        "company",
        "formula_missing",
        "formula_digest",
        "formula_invalid",
        "formula_definition",
        "policy_missing",
        "execution_missing",
        "review",
        "basis",
        "lineage",
        "closure",
        "quality",
    ],
)
def test_public_api_negative_controls(control):
    data = fixture("revenue_yoy" if control == "nonconsecutive" else "gross_margin")
    f = data["facts"][1]
    if control == "null":
        f.value.normalized_value = None
    elif control == "missing":
        data["facts"].pop()
    elif control in {"nan", "snan", "infinity", "invalid_decimal"}:
        f.value.normalized_value = {
            "nan": Decimal("NaN"),
            "snan": Decimal("sNaN"),
            "infinity": Decimal("Infinity"),
            "invalid_decimal": "bad",
        }[control]
    elif control == "unit":
        f.value.unit = "USD"
    elif control == "currency":
        f.context.currency = "USD"
    elif control == "scale":
        f.context.scale = Decimal("1000")
    elif control in {"period", "nonconsecutive"}:
        f.context.period = "2020"
        data["source_reviews"][1].period = f.context.period
        rebuild(data)
    elif control == "document":
        f.document_id = fixture(document=1)["facts"][0].document_id
    elif control == "snapshot":
        f.snapshot_id = "other"
    elif control == "company":
        f.company_id = "another-company"
    elif control == "formula_missing":
        data["formula_approvals"] = []
    elif control == "formula_digest":
        data["formula_approvals"][0].definition_sha256 = "0" * 64
    elif control == "formula_invalid":
        data["formula_approvals"][0].purpose = "analytical_preparation"
    elif control == "formula_definition":
        data["metrics"][0].definition.expression = "revenue / gross_profit"
        rebuild(data)
    elif control == "policy_missing":
        data["formula_policies"] = []
    elif control == "execution_missing":
        data["execution_approval"] = None
    elif control == "review":
        data["source_reviews"] = []
    elif control == "basis":
        data["accounting_bases"] = []
    elif control == "lineage":
        data["graph"].edges = [e for e in data["graph"].edges if e.relation != "used_in"]
    elif control == "closure":
        data["descriptors"][0].parent_snapshot_id = "absent-parent"
    elif control == "quality":
        f.quality_context[0].decision = "insufficient"
    result = calculate(data)
    assert result.status in {"blocked", "invalid_inputs", "unavailable"}, (control, result)
    assert result.result is None and result.trace is None and result.reasons


def test_identity_guards_ambiguity_and_no_caller_eligibility():
    data = fixture()
    calculator = FinancialCalculator(SnapshotCatalog(**data))
    request = CalculateFinancialMetricRequest(metric_id=data["metrics"][0].metric_id)
    for changes in ({"metric_id": "unknown"}, {"document_id": "wrong"}, {"snapshot_id": "wrong"}):
        result = calculator.calculate_financial_metric(request.model_copy(update=changes))
        assert result.status == "unavailable" and result.result is None
    duplicate = data["metrics"][0].model_copy(deep=True)
    duplicate.preparation_blockers.append("conflicting_record")
    data["metrics"].append(duplicate)
    assert calculate(data).result is None
    # No public boolean/operand/formula argument can replace production eligibility.
    with pytest.raises(ValidationError):
        CalculateFinancialMetricRequest(metric_id=request.metric_id, calculation_eligible=True)
    data = fixture()
    data["execution_approval"] = None
    data["metrics"][0].preparation_blockers.clear()
    assert calculate(data).status == "blocked"


def test_arithmetic_failure_is_a_result_and_does_not_poison_next_request():
    data = numbers(fixture(), "1" + "0" * 40, "1")
    # Valid inputs/approval but quantization exceeds the approved 34-digit context.
    result = calculate(data)
    assert result.status == "invalid_inputs" and result.result is None and result.trace is None
    assert result.reasons == ["arithmetic_InvalidOperation"]
    assert calculate(numbers(fixture(), "250", "1000")).result == "25.00"
