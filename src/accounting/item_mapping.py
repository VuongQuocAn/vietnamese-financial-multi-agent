"""Mapping nhãn có kiểm soát; liên kết ô riêng, không xác minh financial facts."""

import unicodedata
from dataclasses import dataclass
from typing import Literal

from pydantic import Field
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    ResolutionStatus,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedPage,
    UnifiedRegion,
    UnifiedTable,
)

from .context_resolution import (
    ContextEvidence,
    evidence_from_unified_page,
    resolve_financial_context,
)
from .contracts import (
    FINANCIAL_NORMALIZATION_CONTRACT_VERSION,
    FinancialModel,
    FinancialNormalizationResult,
    FinancialValue,
)
from .statement_resolution import StatementType, StatementTypeResolution, resolve_statement_type


@dataclass(frozen=True)
class ItemRule:
    canonical_item_id: str
    statement_type: StatementType
    observed_source_code: str
    aliases: tuple[str, ...]
    evidence: str


# ID nội bộ, không phải mã kế toán chuẩn. Nhãn/mã đối chiếu ảnh BBS2025/5,7,8.
# Giữ ordinal: 140 và 141 cùng tên; bare label phải uncertain.
ITEM_CATALOG = (
    ItemRule(
        "b01.cash_equivalents",
        "B01",
        "110",
        ("I. Tiền và các khoản tương đương tiền", "Tiền và các khoản tương đương tiền"),
        "BBS2025/page5",
    ),
    ItemRule(
        "b01.short_term_receivables",
        "B01",
        "130",
        ("II. Các khoản phải thu ngắn hạn", "Các khoản phải thu ngắn hạn"),
        "BBS2025/page5",
    ),
    ItemRule(
        "b01.inventory_total", "B01", "140", ("III. Hàng tồn kho", "Hàng tồn kho"), "BBS2025/page5"
    ),
    ItemRule(
        "b01.inventory_gross", "B01", "141", ("1. Hàng tồn kho", "Hàng tồn kho"), "BBS2025/page5"
    ),
    ItemRule("b01.total_assets", "B01", "270", ("TỔNG CỘNG TÀI SẢN",), "BBS2025/page5"),
    ItemRule(
        "b01.total_liabilities",
        "B01",
        "300",
        ("C - NỢ PHẢI TRẢ", "C- NỢ PHẢI TRẢ", "C - Nợ phải trả", "NỢ PHẢI TRẢ"),
        "D-01:original-PDF:BBS2021/page7;BBS2025/page6",
    ),
    ItemRule(
        "b01.total_equity",
        "B01",
        "400",
        ("D - VỐN CHỦ SỞ HỮU", "D- VỐN CHỦ SỞ HỮU", "VỐN CHỦ SỞ HỮU"),
        "D-01:original-PDF:BBS2021/page7;BBS2025/page6",
    ),
    ItemRule(
        "b02.net_revenue",
        "B02",
        "10",
        (
            "3. Doanh thu thuần về bán hàng và cung cấp dịch vụ",
            "Doanh thu thuần về bán hàng và cung cấp dịch vụ",
        ),
        "BBS2025/page7",
    ),
    ItemRule(
        "b02.cost_of_sales",
        "B02",
        "11",
        ("4. Giá vốn hàng bán", "Giá vốn hàng bán"),
        "BBS2025/page7",
    ),
    ItemRule(
        "b02.gross_profit",
        "B02",
        "20",
        (
            "5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
            "Lợi nhuận gộp về bán hàng và cung cấp dịch vụ",
        ),
        "BBS2025/page7",
    ),
    ItemRule(
        "b02.profit_before_tax",
        "B02",
        "50",
        ("14. Tổng lợi nhuận kế toán trước thuế", "Tổng lợi nhuận kế toán trước thuế"),
        "BBS2025/page7",
    ),
    ItemRule(
        "b02.profit_after_tax",
        "B02",
        "60",
        (
            "17. Lợi nhuận sau thuế thu nhập doanh nghiệp",
            "16. Lợi nhuận sau thuế thu nhập doanh nghiệp",
            "Lợi nhuận sau thuế thu nhập doanh nghiệp",
        ),
        "BBS2025/page7;D-01:original-PDF:BBS2021/page8",
    ),
    ItemRule(
        "b03.operating_cash_flow",
        "B03",
        "20",
        ("Lưu chuyển tiền thuần từ hoạt động kinh doanh",),
        "BBS2025/page8",
    ),
    ItemRule(
        "b03.investing_cash_flow",
        "B03",
        "30",
        ("Lưu chuyển tiền thuần từ hoạt động đầu tư",),
        "BBS2025/page8",
    ),
    ItemRule(
        "b03.financing_cash_flow",
        "B03",
        "40",
        ("Lưu chuyển tiền thuần từ hoạt động tài chính",),
        "BBS2025/page8",
    ),
    ItemRule(
        "b03.closing_cash", "B03", "70", ("Tiền và tương đương tiền cuối năm",), "BBS2025/page8"
    ),
)


class ItemCandidate(FinancialModel):
    canonical_item_id: str
    rule_id: str
    alias_id: str
    catalog_evidence: str


class ItemMapping(FinancialModel):
    raw_item_label: str
    canonical_item_id: str | None = None
    statement_type: StatementType | None = None
    statement_resolution: StatementTypeResolution | None = None
    status: ResolutionStatus
    candidates: list[ItemCandidate]
    evidence: ContextEvidence
    source_item_code: str | None = None
    source_code_evidence: ContextEvidence | None = None
    issues: list[str]
    value_link_status: ResolutionStatus = "unresolved"
    value_link_issues: list[str] = Field(default_factory=list)
    # Liên kết raw value theo từng cột; normalized_value luôn null trong M2-04.
    value_links: list[FinancialNormalizationResult] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def map_item_label(evidence: ContextEvidence, statement_type: StatementType | None) -> ItemMapping:
    """Caller xác nhận phạm vi statement; không suy mã nguồn từ danh mục."""
    candidates = []
    for rule in ITEM_CATALOG:
        if statement_type is not None and rule.statement_type != statement_type:
            continue
        for index, alias in enumerate(rule.aliases):
            if _text(evidence.raw_text) == _text(alias):
                candidates.append(
                    ItemCandidate(
                        canonical_item_id=rule.canonical_item_id,
                        rule_id=rule.canonical_item_id,
                        alias_id=f"{rule.canonical_item_id}/alias/{index}",
                        catalog_evidence=rule.evidence,
                    )
                )
    issues = []
    if not candidates:
        issues.append("unsupported_label_or_statement")
    if statement_type is None:
        issues.append("statement_not_resolved")
    if evidence.status != "resolved":
        issues.append("text_not_resolved")
    if not evidence.provenance:
        issues.append("missing_provenance")
    if len({c.canonical_item_id for c in candidates}) > 1:
        issues.append("ambiguous_label")
    status = "unresolved" if not candidates else "uncertain" if issues else "resolved"
    return ItemMapping(
        raw_item_label=evidence.raw_text,
        statement_type=statement_type,
        canonical_item_id=candidates[0].canonical_item_id if status == "resolved" else None,
        status=status,
        candidates=candidates,
        evidence=evidence,
        issues=issues,
        value_link_issues=["row_column_period_unit_not_established"],
    )


def _link_values(
    item: ItemMapping,
    label: UnifiedRegion,
    table: UnifiedTable,
    evidence: dict[str, ContextEvidence],
    page_context: list[ContextEvidence],
) -> None:
    # Cả bảng phải accepted. Text-only schema không được nâng thành layout evidence.
    positioned = [(c.row, c.column) for c in table.cells]
    if (
        table.status != "accepted"
        or not table.layout_accepted
        or any(r is None or c is None or r < 0 or c < 0 for r, c in positioned)
        or len(set(positioned)) != len(positioned)
        or any(c.layout_status != "accepted" or not c.quality.layout_accepted for c in table.cells)
        or label.row == 0
        or label.column != 0
    ):
        item.value_link_issues = ["table_layout_not_accepted"]
        return
    headers = [c for c in table.cells if c.row == 0]
    codes = [
        c
        for c in headers
        if c.text and _text(c.text) == "mã số" and evidence[c.source_pointer].status == "resolved"
    ]
    if len(codes) == 1:
        cells = [c for c in table.cells if c.row == label.row and c.column == codes[0].column]
        if (
            len(cells) == 1
            and cells[0].text
            and evidence[cells[0].source_pointer].status == "resolved"
        ):
            item.source_item_code = cells[0].text
            item.source_code_evidence = evidence[cells[0].source_pointer]
            expected = {
                r.observed_source_code
                for r in ITEM_CATALOG
                if r.canonical_item_id == item.canonical_item_id
            }
            if expected and item.source_item_code not in expected:
                item.status = "uncertain"
                item.canonical_item_id = None
                item.issues.append("source_code_conflict")
    if item.status != "resolved":
        item.value_link_issues = ["item_not_resolved"]
        return
    unit = resolve_financial_context(page_context)
    if unit.unit.status != "resolved":
        item.value_link_issues = ["unit_not_resolved"]
        return
    links = []
    for header in headers:
        period = resolve_financial_context([evidence[header.source_pointer]])
        if period.period.status != "resolved":
            continue
        cells = [c for c in table.cells if c.row == label.row and c.column == header.column]
        if (
            len(cells) != 1
            or not cells[0].text
            or evidence[cells[0].source_pointer].status != "resolved"
        ):
            item.value_link_issues = ["value_cell_not_resolved"]
            return
        value_evidence = evidence[cells[0].source_pointer]
        context = period.context.model_copy(
            update={
                "currency": unit.context.currency,
                "scale": unit.context.scale,
                "statement_type": item.statement_type,
                "raw_item_label": item.raw_item_label,
                "mapped_item_code": item.canonical_item_id,
            }
        )
        refs = [
            *item.evidence.provenance,
            *value_evidence.provenance,
            *evidence[header.source_pointer].provenance,
        ]
        refs.extend(ref for c in unit.unit.candidates for ref in c.evidence.provenance)
        if item.source_code_evidence:
            refs.extend(item.source_code_evidence.provenance)
        links.append(
            FinancialNormalizationResult(
                contract_version=FINANCIAL_NORMALIZATION_CONTRACT_VERSION,
                value=FinancialValue(
                    raw_value=cells[0].text,
                    status="unresolved",
                    issues=["numeric_normalization_deferred"],
                ),
                context=context,
                provenance=refs,
            )
        )
    item.value_links = links
    item.value_link_status = "resolved" if links else "unresolved"
    item.value_link_issues = [] if links else ["column_period_not_resolved"]


def map_financial_items(page: UnifiedPage) -> list[ItemMapping]:
    """Từng trang M1; không kế thừa loại, chọn kỳ đầu hoặc ghép OCR lân cận.

    Cells dạng chữ là label candidates; header hỗ trợ được loại. Layout chưa đủ
    vẫn giữ candidates/unknowns, không tuyên bố đã nhận diện mọi hàng trong bảng.
    """
    items = evidence_from_unified_page(page)
    statement = resolve_statement_type(items)
    evidence = {e.provenance[0].source_pointer: e for e in items}
    pointers = [r.source_pointer for r in page.text_regions]
    pointers.extend(c.source_pointer for t in page.tables for c in t.cells)
    duplicate_pointers = len(pointers) != len(set(pointers))
    results = []
    for table in page.tables:
        for cell in table.cells:
            if not cell.text or not any(c.isalpha() for c in cell.text):
                continue
            if cell.row == 0 or (cell.column is not None and cell.column != 0):
                continue
            if _text(cell.text) in {
                "chỉ tiêu",
                "mã",
                "số",
                "thuyết",
                "minh",
                "mã số",
                "thuyết minh",
            }:
                continue
            label_evidence = next(
                e
                for e in items
                if e.raw_text == cell.text and e.provenance[0].source_pointer == cell.source_pointer
            )
            item = map_item_label(label_evidence, statement.statement_type)
            item.statement_resolution = statement
            if duplicate_pointers:
                item.status = "uncertain" if item.candidates else "unresolved"
                item.canonical_item_id = None
                item.issues.append("duplicate_source_pointer")
            else:
                _link_values(item, cell, table, evidence, items)
            results.append(item)
    return results
