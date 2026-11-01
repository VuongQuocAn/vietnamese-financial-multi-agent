"""D-06 generic cases; synthetic consistency is not real financial accuracy."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.accounting import (
    item_mapping,
    map_item_label,
)
from vietnamese_financial_multi_agent.accounting.item_mapping import ITEM_CATALOG
from vietnamese_financial_multi_agent.accounting.quality import QualityIssue
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFinancialFact,
    EvidenceAnchor,
    SnapshotDescriptor,
    SourceValidation,
    TaskQualityContext,
    evaluate_source_validations,
)

from .test_arithmetic import value
from .test_financial_item_mapping import evidence


def descriptor(digest="a", snapshot="projection-v2"):
    return SnapshotDescriptor(
        document_id="sha256:" + digest * 64,
        pdf_sha256=digest * 64,
        snapshot_id=snapshot,
        origin="normalized_projection",
    )


def fact(item, number, desc=None):
    desc = desc or descriptor()
    rule = next(r for r in ITEM_CATALOG if r.canonical_item_id == item)
    row = value(
        "unused",
        number,
        statement_type=rule.statement_type,
        mapped_item_code=item,
        raw_item_label=rule.aliases[0],
        period="2030-12-31" if rule.statement_type == "B01" else "2030",
        period_type="as_of" if rule.statement_type == "B01" else "fiscal_year",
    )
    for ref in row.provenance:
        ref.anchor.page.source_ref = desc.document_id
        ref.anchor.page.page = 1 if item != "b01.total_assets" else 2
        ref.anchor.page.image = "sha256:" + "c" * 64
        ref.source_pointer = f"/synthetic/{rule.observed_source_code}"
    return CanonicalFinancialFact(
        document_id=desc.document_id,
        snapshot_id=desc.snapshot_id,
        local_observation_id=item,
        canonical_item_id=item,
        source_item_code=rule.observed_source_code,
        semantic_role=rule.semantic_role,
        value=row.value,
        context=row.context,
        sources=[
            EvidenceAnchor(document_id=desc.document_id, snapshot_id=desc.snapshot_id, reference=r)
            for r in row.provenance
        ],
    )


def balance(desc=None):
    return [
        fact(i, n, desc)
        for i, n in (
            ("b01.total_assets", "100"),
            ("b01.total_liabilities", "60"),
            ("b01.total_equity", "40"),
            ("b01.total_funding", "100"),
        )
    ]


def evaluate(rows, rule="b01.assets_liabilities_equity", desc=None, period="2030-12-31"):
    return next(
        c
        for c in evaluate_source_validations(desc or descriptor(), rows, period=period)
        if c.rule_id == rule
    )


@pytest.mark.parametrize(
    "statement,code,label,expected",
    [
        ("B02", "01", "1. Doanh thu bán hàng và cung cấp dịch vụ", "b02.sales_revenue"),
        ("B03", "01", "1. Doanh thu bán hàng và cung cấp dịch vụ", None),
        ("B01", "310", " I.  NỢ NGẮN HẠN : ", "b01.short_term_liabilities"),
        ("B01", "100", "A — Tài sản ngắn hạn.", "b01.current_assets"),
        ("B03", "50", "Lưu chuyển tiền thuần trong kỳ", "b03.net_cash_flow"),
        ("B03", "60", "Tiền và tương đương tiền đầu kỳ", "b03.opening_cash"),
        ("B01", "60", "Tiền và tương đương tiền đầu kỳ", None),
        ("B01", "310", "Nợ ngắn hạn khác", None),
        ("B01", "999", "Chỉ tiêu hợp lệ chưa hỗ trợ", None),
        ("B01", "400", "Tổng cộng nguồn vốn", None),
    ],
)
def test_mapping_requires_statement_code_and_bounded_alias(statement, code, label, expected):
    result = map_item_label(evidence(label), statement, source_code=code)
    assert result.canonical_item_id == expected
    assert result.mapping_version == "financial-item-mapping-v2"
    if expected:
        assert result.semantic_role
    assert map_item_label(evidence("Nợ ngắn hạn"), "B01").canonical_item_id is None


def test_conflicting_rule_does_not_choose_candidate(monkeypatch):
    original = next(r for r in ITEM_CATALOG if r.canonical_item_id == "b01.current_assets")
    monkeypatch.setattr(
        item_mapping,
        "ITEM_CATALOG",
        (*ITEM_CATALOG, replace(original, canonical_item_id="b01.conflicting_assets")),
    )
    mapped = map_item_label(evidence("Tài sản ngắn hạn"), "B01", source_code="100")
    assert mapped.status == "uncertain" and mapped.canonical_item_id is None
    assert "ambiguous_label" in mapped.issues


def test_unapproved_equity_subtotal_does_not_conflict_with_total():
    subtotal = map_item_label(evidence("I. Vốn chủ sở hữu"), "B01", source_code="410")
    assert subtotal.status == "unresolved" and not subtotal.candidates
    total = map_item_label(evidence("D - VỐN CHỦ SỞ HỮU"), "B01", source_code="400")
    assert total.canonical_item_id == "b01.total_equity"


@pytest.mark.parametrize("digest", ["a", "b"])
def test_two_documents_generic_balance_and_immutable_citations(digest):
    desc = descriptor(digest)
    rows = balance(desc)
    before = deepcopy(rows)
    result = evaluate(rows, desc=desc)
    assert result.status == "consistent" and result.check["difference"] == "0"
    assert len(result.operands) == 3
    assert {o.snapshot_id for o in result.operands} == {desc.snapshot_id}
    assert {s.reference.anchor.page.page for o in result.operands for s in o.sources} == {1, 2}
    assert "scope_unconfirmed" in result.caveats
    assert rows == before
    assert not result.financial_fact_verified
    assert SourceValidation.model_validate_json(result.model_dump_json()) == result
    rows[1].value.normalized_value = Decimal(61)
    inconsistent = evaluate(rows, desc=desc)
    assert inconsistent.status == "inconsistent" and inconsistent.check["difference"] == "1"


def test_missing_funding_does_not_block_separate_liabilities_identity():
    rows = balance()[:-1]
    check = evaluate(rows, "b01.balance_identity")
    assert check.status == "insufficient" and check.missing_inputs == ["b01.total_funding"]
    assert check.check is None
    assert evaluate(rows).status == "consistent"


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("period", "missing"),
        ("snapshot", "missing"),
        ("document", "missing"),
        ("unit", "operand_contexts_do_not_join"),
        ("scale", "operand_contexts_do_not_join"),
        ("null", "value_unresolved"),
        ("duplicate", "duplicate_canonical_candidates"),
        ("source", "source_binding_missing_or_conflict"),
        ("quality", "quality_blocked"),
        ("extraction", "extraction_issue"),
        ("type", "period_type_not_applicable"),
    ],
)
def test_invalid_inputs_fail_closed(mutation, reason):
    rows = balance()
    operand = rows[1]
    if mutation == "period":
        operand.context.period = "2029-12-31"
    elif mutation == "snapshot":
        operand.snapshot_id = "parent-snapshot"
    elif mutation == "document":
        operand.document_id = descriptor("b").document_id
    elif mutation == "unit":
        operand.value.unit = "USD"
    elif mutation == "scale":
        operand.context.scale = Decimal(1000)
    elif mutation == "null":
        operand.value.normalized_value = None
    elif mutation == "duplicate":
        rows.append(deepcopy(operand))
    elif mutation == "source":
        operand.sources[0].snapshot_id = "parent-snapshot"
    elif mutation == "quality":
        operand.quality_context = [
            TaskQualityContext(
                task_type="direct_qa",
                decision="conflicted",
                evidence_ids=[operand.local_observation_id],
            )
        ]
    elif mutation == "extraction":
        operand.resolution_issues.append(QualityIssue(code="m2_extraction_issue", detail="layout"))
    elif mutation == "type":
        operand.context.period_type = "fiscal_year_end"
    result = evaluate(rows)
    assert result.status == "insufficient"
    if reason == "missing":
        assert "b01.total_liabilities" in result.missing_inputs
    else:
        assert any(reason in r for r in result.reasons)
    assert result.check is None or result.check["difference"] is None


def test_revenue_deductions_are_distinct_and_never_inferred_zero():
    rows = [
        fact(i, n)
        for i, n in (
            ("b02.sales_revenue", "100"),
            ("b02.revenue_deductions", "7"),
            ("b02.net_revenue", "93"),
        )
    ]
    result = evaluate(rows, "b02.net_revenue", period="2030")
    assert result.status == "consistent"
    assert result.check["computed_value"] == "93"
    assert result.check["inputs"][-1]["sign"] == -1
    rows[1].value.normalized_value = None
    assert evaluate(rows, "b02.net_revenue", period="2030").status == "insufficient"


def test_cash_flow_sum_and_exchange_guard():
    rows = [
        fact(i, n)
        for i, n in (
            ("b03.net_cash_flow", "6"),
            ("b03.operating_cash_flow", "10"),
            ("b03.investing_cash_flow", "-3"),
            ("b03.financing_cash_flow", "-1"),
            ("b03.opening_cash", "8"),
            ("b03.closing_cash", "14"),
        )
    ]
    assert evaluate(rows, "b03.net_cash_flow", period="2030").status == "consistent"
    rows[0].value.normalized_value = Decimal(7)
    assert evaluate(rows, "b03.net_cash_flow", period="2030").status == "inconsistent"
    cash = evaluate(rows, "b03.cash_reconciliation", period="2030")
    assert cash.status == "insufficient"
    assert "b03.exchange_effect" in cash.missing_inputs
    assert cash.check is None


def test_asset_decomposition_uses_shared_arithmetic_and_semantic_guards():
    rows = [
        fact(i, n)
        for i, n in (
            ("b01.total_assets", "100"),
            ("b01.current_assets", "70"),
            ("b01.noncurrent_assets", "30"),
        )
    ]
    for row in rows:
        row.sources[0].reference.anchor.page.page = 1
    result = evaluate(rows, "b01.total_assets")
    assert result.status == "consistent" and result.residual == Decimal(0)
    rows[1].semantic_role = "current_liabilities"
    blocked = evaluate(rows, "b01.total_assets")
    assert blocked.status == "insufficient"
    assert "semantic_role_conflict:b01.current_assets" in blocked.reasons


def test_cross_statement_endpoint_requires_source_evidence():
    rows = [fact("b01.cash_equivalents", "9"), fact("b03.closing_cash", "9")]
    rows[1].source_metadata = {
        "unit_semantics": {"raw_unit_context": ["Cho năm tài chính kết thúc ngày 31/12/2030"]}
    }
    rows[1].sources[0].reference.source_pointer = "/context/0"
    result = evaluate(rows, "b01_b03.closing_cash")
    assert result.status == "consistent" and result.residual == Decimal(0)
    rows[1].source_metadata = {}
    blocked = evaluate(rows, "b01_b03.closing_cash")
    assert blocked.status == "insufficient" and "b03.closing_cash" in blocked.missing_inputs
