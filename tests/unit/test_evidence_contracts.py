"""Synthetic contract invariants; không phải đánh giá accuracy tài chính."""

from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.accounting.contracts import (
    FinancialContext,
    FinancialSourceReference,
    FinancialValue,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFinancialFact,
    EvidenceAnchor,
    FinancialOperand,
    OperandRequirement,
    OperationCompatibilitySpec,
    PeriodPair,
    assess_compatibility,
    assess_fact_consistency,
)


def fact(document="synthetic-report-2025", snapshot="attempt-1", period="2024"):
    return CanonicalFinancialFact(
        document_id=document,
        snapshot_id=snapshot,
        local_observation_id="row10-prior",
        company_id="synthetic-company",
        canonical_item_id="b02.net_revenue",
        semantic_role="revenue",
        source_item_code="10",
        value=FinancialValue(
            raw_value="1.234,00", normalized_value=Decimal("1234.00"), unit="VND", status="resolved"
        ),
        context=FinancialContext(
            period=period,
            period_type="fiscal_year",
            currency="VND",
            scale=Decimal("1"),
            reporting_scope="separate",
            statement_type="B02",
            raw_item_label="Doanh thu thuần",
        ),
        sources=[
            EvidenceAnchor(
                document_id=document,
                snapshot_id=snapshot,
                reference=FinancialSourceReference(
                    anchor=SourceAnchor(
                        page=RawPageIdentity(
                            symbol="SYNTHETIC", year="2025", page=7, image="page7.png"
                        ),
                        status="resolved",
                    ),
                    source_pointer="/tables/0/cells/12",
                ),
            )
        ],
    )


def scenario(yoy=False):
    # Examples explicit trong task, không đăng ký financial rule catalog mới.
    spec = OperationCompatibilitySpec(
        operation_id="yoy_revenue" if yoy else "gross_margin",
        rule_reference="M3-01/task-examples",
        operands=[
            OperandRequirement(
                role="left",
                canonical_item_id="b02.net_revenue",
                semantic_role="revenue",
                statement_type="B02",
            ),
            OperandRequirement(
                role="right",
                canonical_item_id="b02.net_revenue" if yoy else "b02.gross_profit",
                semantic_role="revenue" if yoy else "gross_profit",
                statement_type="B02",
            ),
        ],
        period_relation="ordered_pair" if yoy else "same",
        period_pairs=[PeriodPair(left="2024", right="2025", period_type="fiscal_year")]
        if yoy
        else [],
        document_relation="any",
    )
    left, right = fact(), fact(period="2025" if yoy else "2024")
    right.local_observation_id = "row20-current"
    if not yoy:
        right.canonical_item_id = "b02.gross_profit"
        right.semantic_role = "gross_profit"
    return spec, [
        FinancialOperand(role="left", fact=left),
        FinancialOperand(role="right", fact=right),
    ]


def test_cross_document_same_period_observations_are_independent():
    # BBS_2024 và cột so sánh BBS_2025: chỉ fixture, không đọc/chạy PDF thật.
    report2024 = fact(document="synthetic-BBS_2024")
    report2024.sources[0].reference.anchor.page.year = "2024"
    comparative2024 = fact(document="synthetic-BBS_2025")
    before = deepcopy([report2024, comparative2024])
    assert report2024.semantic_key() == comparative2024.semantic_key()
    assert report2024.observation_identity() != comparative2024.observation_identity()
    assert report2024.sources[0].source_key() != comparative2024.sources[0].source_key()
    assert len({report2024.observation_identity(), comparative2024.observation_identity()}) == 2
    assert fact(snapshot="attempt-2").observation_identity() != fact().observation_identity()
    assert fact(period="2025").semantic_key() != comparative2024.semantic_key()
    consolidated = comparative2024.model_copy(deep=True)
    consolidated.context.reporting_scope = "consolidated"
    assert consolidated.semantic_key() != comparative2024.semantic_key()
    assert [report2024, comparative2024] == before


def test_raw_unmapped_missing_identity_and_exact_decimal_roundtrip():
    f = fact()
    original = f.model_dump_json()
    assert CanonicalFinancialFact.model_validate_json(original) == f
    assert '"1234.00"' in original
    assert f.sources[0].reference.provenance_level == "page"
    assert assess_fact_consistency(f).status == "consistent"
    for field in ("document_id", "snapshot_id", "canonical_item_id", "company_id"):
        missing = f.model_copy(deep=True)
        setattr(missing, field, None)
        assert assess_fact_consistency(missing).status == "unresolved"
    raw = f.model_copy(deep=True)
    raw.canonical_item_id = None
    raw.context = FinancialContext(raw_item_label="Chỉ tiêu ngoài catalog")
    assert raw.semantic_key() is None
    assert raw.value.raw_value == "1.234,00"
    assert raw.context.period is None  # Không lấy year=2025 trên anchor.
    payload = f.model_dump(mode="python")
    payload["financial_fact_verified"] = True
    with pytest.raises(ValidationError):
        CanonicalFinancialFact.model_validate(payload)
    payload = f.model_dump_json().replace('"1234.00"', "1234.0")
    with pytest.raises(ValidationError):
        CanonicalFinancialFact.model_validate_json(payload)


def test_provenance_consistency_does_not_promote_selectors_or_mutate_source():
    f = fact()
    before = f.model_dump_json()
    assert assess_fact_consistency(f).status == "consistent"
    assert f.model_dump_json() == before
    for field in ("document_id", "snapshot_id"):
        other = f.model_copy(deep=True)
        setattr(other.sources[0], field, "other")
        result = assess_fact_consistency(other)
        assert result.status == "inconsistent"
        assert "source_identity_mismatch" in {i.code for i in result.issues}
    other = f.model_copy(deep=True)
    other.sources[0].reference.provenance_level = "cell"
    assert assess_fact_consistency(other).status == "inconsistent"
    anchor = other.sources[0].reference.anchor
    anchor.table_id, anchor.cell_id = "table1", "cell12"
    assert assess_fact_consistency(other).status == "consistent"
    anchor.status = "uncertain"
    assert assess_fact_consistency(other).status == "unresolved"
    other.sources[0].reference = None
    assert assess_fact_consistency(other).status == "unresolved"
    assert f.model_dump_json() == before


@pytest.mark.parametrize("yoy", [False, True])
def test_operation_examples_compatible_metadata_only(yoy):
    spec, operands = scenario(yoy)
    before = deepcopy(operands)
    result = assess_compatibility(spec, operands)
    assert result.status == "compatible"
    assert result.reasons == []
    assert result.financial_fact_verified is False
    assert result.operands[0].observation == operands[0].fact.observation_identity()
    assert operands == before


@pytest.mark.parametrize(
    ("field", "value", "status", "reason"),
    [
        ("reporting_scope", "consolidated", "incompatible", "reporting_scope_mismatch"),
        ("reporting_scope", None, "undetermined", "missing_reporting_scope"),
        ("period", None, "undetermined", "missing_period"),
        ("period_type", None, "undetermined", "missing_period_type"),
        ("scale", Decimal("1000"), "undetermined", "scale_mismatch"),
        ("currency", "USD", "incompatible", "currency_mismatch"),
        ("canonical_item_id", "b02.other", "incompatible", "canonical_item_id_mismatch"),
        ("semantic_role", "other", "incompatible", "semantic_role_mismatch"),
        ("company_id", "other-company", "incompatible", "company_id_mismatch"),
        ("document_id", None, "undetermined", "missing_document_id"),
        ("unit", "other-unit", "undetermined", "unit_mismatch"),
    ],
)
def test_operation_mismatches_and_missing_context(field, value, status, reason):
    spec, operands = scenario()
    f = operands[1].fact
    target = (
        f.value if field == "unit" else f.context if field in FinancialContext.model_fields else f
    )
    setattr(target, field, value)
    result = assess_compatibility(spec, operands)
    assert result.status == status
    assert reason in {r.code for r in result.reasons}


def test_period_role_and_document_constraints_are_operation_specific():
    spec, operands = scenario(yoy=True)
    operands[1].fact.context.period = "2024"
    assert assess_compatibility(spec, operands).status == "incompatible"
    operands[1].fact.context.period = "2025"
    operands[1].fact.context.period_type = None
    assert assess_compatibility(spec, operands).status == "undetermined"
    operands[1].fact.context.period_type = "fiscal_year"
    spec.period_pairs = []
    assert assess_compatibility(spec, operands).status == "undetermined"
    spec, operands = scenario()
    operands[1].role = "left"
    assert assess_compatibility(spec, operands).status == "incompatible"
    spec, operands = scenario()
    operands[1].fact.document_id = "another-report"
    assert assess_compatibility(spec, operands).status == "compatible"
    spec.document_relation = "same"
    assert assess_compatibility(spec, operands).status == "incompatible"
    assert assess_compatibility(spec, operands[:1]).status == "undetermined"
