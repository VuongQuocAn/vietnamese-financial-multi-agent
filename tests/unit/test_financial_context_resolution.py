"""Fixtures synthetic; không phải phép đo chất lượng tài chính trên dataset."""

from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.accounting import (
    ContextEvidence,
    ContextResolution,
    FinancialSourceReference,
    evidence_from_unified_page,
    resolve_financial_context,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    ComponentQuality,
    UnifiedPage,
    UnifiedRegion,
    UnifiedTable,
)


def evidence(text, **kwargs):
    return ContextEvidence(
        raw_text=text,
        provenance=[
            FinancialSourceReference(
                anchor=SourceAnchor(
                    page=RawPageIdentity(symbol="TEST", year="2099", page=1, image="test.png"),
                    status="uncertain",
                ),
                source_pointer="/text_elements/0",
            )
        ],
        **kwargs,
    )


def test_period_formats_preserve_distinct_semantics():
    cases = [
        ("Năm 2025", "2025", "fiscal_year"),
        ("Cho năm tài chính kết thúc ngày 31/12/2025", "2025-12-31", "fiscal_year_end"),
        ("Tại ngày 31 tháng 12 năm 2025", "2025-12-31", "as_of"),
        ("Quý III năm 2025", "2025-Q3", "quarter"),
        ("9 tháng đầu năm 2025", "2025-M01/M09", "year_to_month"),
        ("Kỳ kế toán từ 01/01/2025 đến 31/12/2025", "2025-01-01/2025-12-31", "date_range"),
    ]
    for text, period, kind in cases:
        result = resolve_financial_context([evidence(text)])
        assert result.period.status == "resolved"
        assert (result.context.period, result.context.period_type) == (period, kind)


def test_units_and_decimal_json_round_trip():
    for raw, scale in (
        ("đồng", "1"),
        ("VND", "1"),
        ("nghìn đồng", "1000"),
        ("triệu đồng", "1000000"),
    ):
        result = resolve_financial_context([evidence(f"Đơn vị tính: {raw}")])
        assert result.unit.status == "resolved"
        assert result.context.currency == "VND"
        assert result.context.scale == Decimal(scale)
        assert ContextResolution.model_validate_json(result.model_dump_json()) == result
    assert resolve_financial_context([evidence("Đơn vị: nghìn đồng")]).context.scale == Decimal(
        "1000"
    )


def test_scope_title_vs_narrative_mention():
    for text, expected in (("HỢP NHẤT", "consolidated"), ("RIÊNG", "separate")):
        result = resolve_financial_context([evidence(f"BÁO CÁO TÀI CHÍNH {text}")])
        assert result.reporting_scope.status == "resolved"
        assert result.context.reporting_scope == expected
    result = resolve_financial_context(
        [evidence("Công ty lập báo cáo tài chính hợp nhất theo quy định.")]
    )
    assert result.reporting_scope.status == "uncertain"
    assert result.context.reporting_scope is None
    assert "scope_mention_not_title" in result.reporting_scope.issues


def test_missing_evidence_and_metadata_do_not_supply_context():
    for items in ([], [evidence("TEST hợp nhất 2099.png")], [evidence("Không có thông tin")]):
        result = resolve_financial_context(items)
        assert all(
            f.status == "unresolved" for f in (result.period, result.unit, result.reporting_scope)
        )
        assert all(v is None for v in result.context.model_dump().values())


def test_conflicts_and_different_period_types_never_choose_first():
    for texts, field in (
        (["Năm 2025", "Năm 2024"], "period"),
        (["Tại ngày 31/12/2025", "Cho năm tài chính kết thúc ngày 31/12/2025"], "period"),
        (["Đơn vị: đồng", "Đơn vị: triệu đồng"], "unit"),
        (["Báo cáo tài chính riêng", "Báo cáo tài chính hợp nhất"], "reporting_scope"),
    ):
        for ordered in (texts, list(reversed(texts))):
            result = resolve_financial_context(map(evidence, ordered))
            resolved_field = getattr(result, field)
            assert resolved_field.status == "uncertain"
            assert "conflicting_candidates" in resolved_field.issues
            assert len(resolved_field.candidates) == 2
            assert all(v is None for v in result.context.model_dump().values())


def test_raw_provenance_and_duplicate_support_are_preserved():
    item = evidence("  Đơn vị tính: NGHÌN ĐỒNG  \n")
    before = item.model_dump_json()
    result = resolve_financial_context([item, item])
    assert result.unit.status == "resolved"
    assert result.unit.candidates[0].evidence.raw_text == item.raw_text
    assert result.unit.candidates[0].evidence.provenance == item.provenance
    assert item.model_dump_json() == before
    assert len(result.unit.candidates) == 2
    assert result.financial_fact_verified is False


def test_invalid_dates_ranges_and_unknown_units_do_not_resolve():
    for text in (
        "Tại ngày 31/02/2025",
        "Kỳ kế toán từ 31/12/2025 đến 01/01/2025",
        "13 tháng đầu năm 2025",
    ):
        result = resolve_financial_context([evidence(text)])
        assert result.period.status == "uncertain"
        assert result.context.period is None
    result = resolve_financial_context([evidence("Đơn vị: USD"), evidence("Đơn vị: đồng")])
    assert result.unit.status == "uncertain"
    assert result.context.currency is None


def test_unaccepted_text_or_missing_provenance_cannot_resolve():
    for item in (
        evidence("Năm 2025", status="unresolved"),
        ContextEvidence(raw_text="Năm 2025", provenance=[]),
    ):
        result = resolve_financial_context([item])
        assert result.period.status == "uncertain"
        assert result.context.period is None
        assert result.period.candidates[0].evidence == item


@pytest.mark.parametrize("native", [True, False])
def test_unified_adapter_preserves_level_ids_and_unaccepted_candidates(native):
    identity = evidence("").provenance[0].anchor.page
    region = UnifiedRegion(
        source_pointer="/text_elements/0",
        raw_element_id=None if native else "observed-id",
        text="Tại ngày 31/12/2025",
        status="accepted",
        quality=ComponentQuality(
            text_accepted=True, downstream_usable=True, usable_for=["text_evidence"]
        ),
        provenance_level="page" if native else "element",
        source_component={"text": "original"},
    )
    cell = region.model_copy(
        update={"text": "Năm 2024", "status": "unresolved", "source_pointer": "/tables/0/cells/0"}
    )
    page = UnifiedPage(
        identity=identity,
        source_type="png" if native else "existing_ocr",
        source_sha256="test",
        source_references={},
        schema_valid=True,
        text_regions=[region],
        tables=[
            UnifiedTable(
                source_pointer="/tables/0",
                status="unresolved",
                layout_accepted=False,
                cells=[cell],
                source_component={},
            )
        ],
        classification={},
        issues=[],
        processing_history=[],
    )
    before = page.model_dump_json()
    items = evidence_from_unified_page(page)
    anchor = items[0].provenance[0].anchor
    assert anchor.page == identity
    assert anchor.observed_bbox is None
    assert anchor.element_id == region.raw_element_id
    assert anchor.cell_id is None
    assert items[0].provenance[0].provenance_level == region.provenance_level
    assert items[1].status == "unresolved"
    assert resolve_financial_context(items[:1]).period.status == "resolved"
    assert resolve_financial_context(items).period.status == "uncertain"
    assert page.model_dump_json() == before
