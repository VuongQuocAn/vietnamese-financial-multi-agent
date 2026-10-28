"""Fixtures synthetic kiểm tra engineering, không là financial accuracy."""

from vietnamese_financial_multi_agent.accounting import (
    ContextEvidence,
    FinancialSourceReference,
    StatementTypeResolution,
    evidence_from_unified_page,
    recognize_document_statements,
    resolve_statement_type,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    ComponentQuality,
    UnifiedPage,
    UnifiedRegion,
)


def evidence(text, *, page=1, status="resolved"):
    return ContextEvidence(
        raw_text=text,
        status=status,
        provenance=[
            FinancialSourceReference(
                anchor=SourceAnchor(
                    page=RawPageIdentity(symbol="TEST", year="2099", page=page, image="test.png"),
                    status="uncertain",
                ),
                source_pointer="/text_elements/0",
            )
        ],
    )


def unified_page(text, number=1, accepted=True):
    return UnifiedPage(
        identity=evidence("", page=number).provenance[0].anchor.page,
        source_type="png",
        source_sha256="synthetic",
        source_references={},
        schema_valid=True,
        text_regions=[
            UnifiedRegion(
                source_pointer="/text_elements/0",
                text=text,
                status="accepted" if accepted else "unresolved",
                quality=ComponentQuality(
                    text_accepted=accepted,
                    downstream_usable=accepted,
                    usable_for=["text_evidence"] if accepted else [],
                ),
                provenance_level="page",
                source_component={"text": text},
            )
        ],
        tables=[],
        classification={},
        issues=[],
        processing_history=[],
    )


def test_four_titles_and_supported_aliases():
    for title, label in (
        ("BẢNG CÂN ĐỐI KẾ TOÁN", "B01"),
        ("BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT", "B01"),
        ("BÁO CÁO TÌNH HÌNH TÀI CHÍNH", "B01"),
        ("BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", "B02"),
        ("BÁO CÁO LƯU CHUYỂN TIỀN TỆ", "B03"),
        ("THUYẾT MINH BÁO CÁO TÀI CHÍNH", "B09"),
        ("BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH", "B09"),
        ("BẢN THUYẾT MINH BÁO CÁO TÀI CHÍNH RIÊNG", "B09"),
    ):
        result = resolve_statement_type([evidence(title)])
        assert (result.status, result.statement_type) == ("resolved", label)


def test_form_code_requires_matching_title():
    title = evidence("Bảng cân đối kế toán")
    code = evidence("MẪU SỐ B01 - DN")
    assert resolve_statement_type([title, code]).statement_type == "B01"
    for text in ("B01", "MẪU SỐ B01 - DN", "Mẫu B03-DN"):
        result = resolve_statement_type([evidence(text)])
        assert result.status == "uncertain"
        assert result.statement_type is None


def test_conflicting_form_and_title_abstain_in_both_orders():
    items = [evidence("Bảng cân đối kế toán"), evidence("Mẫu số B02 - DN")]
    for ordered in (items, items[::-1]):
        result = resolve_statement_type(ordered)
        assert result.status == "uncertain"
        assert result.statement_type is None
        assert "conflicting_candidates" in result.issues
        assert {c.value.statement_type for c in result.candidates} == {"B01", "B02"}


def test_multiple_titles_never_choose_first():
    items = [evidence("Bảng cân đối kế toán"), evidence("Báo cáo kết quả hoạt động kinh doanh")]
    for ordered in (items, items[::-1]):
        result = resolve_statement_type(ordered)
        assert result.status == "uncertain"
        assert result.statement_type is None


def test_narrative_contents_and_quotes_are_weak():
    for text in (
        "Chuẩn mực số 24 - Báo cáo lưu chuyển tiền tệ.",
        "Công ty lập bảng cân đối kế toán theo quy định.",
        "BẢNG CÂN ĐỐI KẾ TOÁN ........ 5",
        '"BÁO CÁO LƯU CHUYỂN TIỀN TỆ"',
    ):
        result = resolve_statement_type([evidence(text)])
        assert result.status == "uncertain"
        assert result.statement_type is None
        assert "mention_not_title" in result.issues


def test_notes_title_not_overridden_by_narrative_reference():
    result = resolve_statement_type(
        [
            evidence("THUYẾT MINH BÁO CÁO TÀI CHÍNH"),
            evidence("Chuẩn mực số 24 - Báo cáo lưu chuyển tiền tệ."),
        ]
    )
    assert (result.status, result.statement_type) == ("resolved", "B09")
    assert result.candidates[1].status == "uncertain"
    assert result.candidates[1].issues == ["mention_not_title"]


def test_missing_and_filename_or_generic_words_do_not_supply_evidence():
    for items in ([], [evidence("Tài sản, doanh thu, tiền")], [evidence("BBS_B01_2025.pdf")]):
        result = resolve_statement_type(items)
        assert (result.status, result.statement_type) == ("unresolved", None)


def test_missing_provenance_and_unaccepted_m1_text_abstain():
    for item in (
        ContextEvidence(raw_text="Bảng cân đối kế toán", provenance=[]),
        evidence("Bảng cân đối kế toán", status="unresolved"),
        evidence("Bảng cân đối kế toán", status="uncertain"),
    ):
        result = resolve_statement_type([item])
        assert result.status == "uncertain"
        assert result.statement_type is None
        assert result.candidates[0].evidence == item


def test_unified_provenance_raw_text_and_m1_status_preserved():
    for accepted in (True, False):
        page = unified_page("  BẢNG CÂN ĐỐI KẾ TOÁN  \n", accepted=accepted)
        before = page.model_dump_json()
        items = evidence_from_unified_page(page)
        result = resolve_statement_type(items)
        candidate = result.candidates[0]
        assert result.status == ("resolved" if accepted else "uncertain")
        assert candidate.evidence == items[0]
        assert candidate.evidence.raw_text == page.text_regions[0].text
        ref = candidate.evidence.provenance[0]
        assert ref.anchor.page == page.identity
        assert ref.anchor.observed_bbox is None
        assert ref.anchor.element_id is ref.anchor.table_id is ref.anchor.cell_id is None
        assert ref.source_pointer == "/text_elements/0"
        assert page.model_dump_json() == before
        assert result.financial_fact_verified is False
        assert StatementTypeResolution.model_validate_json(result.model_dump_json()) == result


def test_document_inventory_does_not_inherit_to_continuation():
    result = recognize_document_statements(
        [
            unified_page("Bảng cân đối kế toán"),
            unified_page("Tiếp theo\nTài sản", 2),
            unified_page("Báo cáo kết quả hoạt động kinh doanh", 3),
        ]
    )
    assert result.statement_types == ["B01", "B02"]
    assert result.pages[1].status == "unresolved"
    assert result.pages[1].statement_type is None
    assert result.completeness_verified is False
    own_title = resolve_statement_type([evidence("BẢNG CÂN ĐỐI KẾ TOÁN (Tiếp theo)", page=2)])
    assert own_title.statement_type == "B01"


def test_mixed_pages_rejected_and_duplicate_support_allowed():
    a = evidence("Bảng cân đối kế toán")
    assert resolve_statement_type([a, a]).statement_type == "B01"
    result = resolve_statement_type([a, evidence("Tài sản", page=2)])
    assert result.status == "uncertain"
    assert result.statement_type is None
    assert "mixed_page_scope" in result.issues
