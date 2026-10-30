"""Synthetic engineering cases; không thay thế đánh giá tài chính trên nguồn thật."""

import unicodedata

from vietnamese_financial_multi_agent.accounting import (
    ITEM_CATALOG,
    ContextEvidence,
    FinancialSourceReference,
    ItemMapping,
    map_financial_items,
    map_item_label,
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


def evidence(text, **changes):
    return ContextEvidence(
        raw_text=text,
        provenance=[
            FinancialSourceReference(
                anchor=SourceAnchor(
                    page=RawPageIdentity(symbol="TEST", year="2099", page=1, image="synthetic.png"),
                    status="uncertain",
                ),
                source_pointer="/tables/0/cells/0",
            )
        ],
    ).model_copy(update=changes)


def test_d01_equity_total_does_not_map_unapproved_subtotal_or_other_statement():
    result = map_item_label(evidence("D - VỐN CHỦ SỞ HỮU"), "B01")
    assert result.canonical_item_id == "b01.total_equity"
    assert result.candidates[0].catalog_evidence.startswith("D-01:original-PDF:")
    assert map_item_label(evidence("I. Vốn chủ sở hữu"), "B01").canonical_item_id is None
    assert map_item_label(evidence("D - VỐN CHỦ SỞ HỮU"), "B02").canonical_item_id is None


def page():
    quality = ComponentQuality(
        text_accepted=True,
        layout_accepted=True,
        downstream_usable=True,
        usable_for=["text_evidence"],
    )

    def region(text, pointer, row=None, column=None):
        return UnifiedRegion(
            text=text,
            source_pointer=pointer,
            row=row,
            column=column,
            status="accepted",
            quality=quality,
            layout_status="accepted",
            source_component={"text": text},
        )

    matrix = [
        ["CHỈ TIÊU", "Mã số", "Năm 2025", "Năm 2024"],
        ["4. Giá vốn hàng bán", "11", "1.234", "567"],
    ]
    return UnifiedPage(
        identity=evidence("").provenance[0].anchor.page,
        source_type="png",
        source_sha256="synthetic",
        source_references={},
        schema_valid=True,
        text_regions=[
            region(t, f"/text/{i}")
            for i, t in enumerate(
                [
                    "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH",
                    "Đơn vị tính: VND",
                ]
            )
        ],
        tables=[
            UnifiedTable(
                source_pointer="/tables/0",
                status="accepted",
                layout_accepted=True,
                source_component={},
                cells=[
                    region(t, f"/tables/0/cells/{r * 4 + c}", r, c)
                    for r, row in enumerate(matrix)
                    for c, t in enumerate(row)
                ],
            )
        ],
        classification={},
        issues=[],
        processing_history=[],
    )


def test_catalog_exact_aliases_and_unicode_whitespace():
    for rule in ITEM_CATALOG:
        for alias in rule.aliases:
            raw = unicodedata.normalize("NFD", "  " + alias.upper().replace(" ", "\n ") + "  ")
            result = map_item_label(evidence(raw), rule.statement_type)
            assert rule.canonical_item_id in {c.canonical_item_id for c in result.candidates}
            assert result.raw_item_label == raw
            assert result.source_item_code is None


def test_similar_labels_do_not_match_by_substring():
    for label, statement in [
        ("A - TÀI SẢN NGẮN HẠN", "B01"),
        ("1. Doanh thu bán hàng và cung cấp dịch vụ", "B02"),
        ("Lợi nhuận trước thuế", "B02"),
        ("Lưu chuyển tiền thuần trong năm", "B03"),
        ("Tiền và tương đương tiền đầu năm", "B03"),
    ]:
        assert map_item_label(evidence(label), statement).status == "unresolved"
    before = map_item_label(evidence("14. Tổng lợi nhuận kế toán trước thuế"), "B02")
    after = map_item_label(evidence("17. Lợi nhuận sau thuế thu nhập doanh nghiệp"), "B02")
    assert before.canonical_item_id != after.canonical_item_id


def test_wrong_or_missing_statement_and_b09_abstain():
    for kind in ("B01", "B03", "B09"):
        assert map_item_label(evidence("Giá vốn hàng bán"), kind).status == "unresolved"
    result = map_item_label(evidence("Giá vốn hàng bán"), None)
    assert result.status == "uncertain" and result.canonical_item_id is None


def test_unknown_and_ambiguous_inventory():
    assert map_item_label(evidence("Chỉ tiêu chưa hỗ trợ"), "B01").status == "unresolved"
    result = map_item_label(evidence("Hàng tồn kho"), "B01")
    assert result.status == "uncertain" and result.canonical_item_id is None
    assert len(result.candidates) == 2
    total = map_item_label(evidence("III. Hàng tồn kho"), "B01")
    gross = map_item_label(evidence("1. Hàng tồn kho"), "B01")
    assert total.canonical_item_id != gross.canonical_item_id


def test_preserves_provenance_and_does_not_promote_unaccepted_text():
    raw = evidence("Giá vốn hàng bán", status="unresolved")
    result = map_item_label(raw, "B02")
    assert result.evidence == raw and result.status == "uncertain"
    assert result.value_links == [] and result.value_link_status == "unresolved"
    assert map_item_label(evidence(raw.raw_text, provenance=[]), "B02").status == "uncertain"
    assert ItemMapping.model_validate_json(result.model_dump_json()) == result
    assert result.financial_fact_verified is False


def test_unresolved_table_rejects_numeric_and_source_code_adjacency():
    source = page()
    source.tables[0].status = "unresolved"
    result = map_financial_items(source)[0]
    assert result.status == "resolved"
    assert result.source_item_code is None and result.value_links == []
    assert "table_layout_not_accepted" in result.value_link_issues


def test_all_period_columns_link_separately_without_verified_financial_fact():
    source = page()
    before = source.model_dump_json()
    result = map_financial_items(source)[0]
    assert result.canonical_item_id == "b02.cost_of_sales"
    assert result.source_item_code == "11"
    assert result.source_code_evidence.raw_text == "11"
    assert result.value_link_status == "resolved"
    assert [(v.context.period, v.value.raw_value) for v in result.value_links] == [
        ("2025", "1.234"),
        ("2024", "567"),
    ]
    for link in result.value_links:
        assert link.value.normalized_value is None and link.value.status == "unresolved"
        assert link.context.currency == "VND" and str(link.context.scale) == "1"
        assert link.financial_fact_verified is False
        assert len(link.provenance) >= 5
    assert source.model_dump_json() == before


def test_missing_or_duplicate_coordinates_and_unaccepted_cell_layout_abstain():
    for mode in ("missing", "duplicate", "unaccepted"):
        source = page()
        if mode == "missing":
            source.tables[0].cells[6].row = None
        elif mode == "duplicate":
            source.tables[0].cells[6].column = 1
        else:
            source.tables[0].cells[6].layout_status = "unresolved"
        assert map_financial_items(source)[0].value_links == []


def test_no_period_or_unit_does_not_use_page_year_or_first_column():
    for mode in ("period", "unit"):
        source = page()
        if mode == "period":
            source.tables[0].cells[2].text = "Kỳ này"
            source.tables[0].cells[3].text = "Kỳ trước"
        else:
            source.text_regions.pop()
        result = map_financial_items(source)[0]
        assert result.value_links == [] and result.value_link_status == "unresolved"


def test_source_code_conflict_does_not_override_label():
    source = page()
    source.tables[0].cells[5].text = "20"
    result = map_financial_items(source)[0]
    assert result.status == "uncertain" and result.canonical_item_id is None
    assert result.source_item_code == "20" and result.value_links == []
    assert "source_code_conflict" in result.issues


def test_duplicate_source_pointer_prevents_binding():
    source = page()
    source.tables[0].cells[6].source_pointer = source.tables[0].cells[4].source_pointer
    result = map_financial_items(source)[0]
    assert result.canonical_item_id is None and result.value_links == []
    assert result.raw_item_label == "4. Giá vốn hàng bán"
    assert "duplicate_source_pointer" in result.issues


def test_unresolved_statement_or_value_cell_cannot_create_links():
    source = page()
    source.text_regions[0].text = "BÁO CÁO TÀI CHÍNH"
    assert map_financial_items(source)[0].value_links == []
    source = page()
    source.tables[0].cells[7].status = "unresolved"
    result = map_financial_items(source)[0]
    assert result.value_links == [] and result.value_link_status == "unresolved"
