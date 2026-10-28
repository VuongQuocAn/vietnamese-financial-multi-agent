"""Nhận diện từng trang từ title; không suy ranh giới hoặc kế thừa nhãn trang."""

import re
import unicodedata
from collections.abc import Iterable
from typing import Literal

from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    ResolutionStatus,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedPage,
)

from .context_resolution import ContextEvidence, evidence_from_unified_page
from .contracts import FinancialContext, FinancialModel

StatementType = Literal["B01", "B02", "B03", "B09"]


class StatementCandidate(FinancialModel):
    value: FinancialContext
    signal: Literal["title", "form_code", "mention"]
    evidence: ContextEvidence
    status: ResolutionStatus
    issues: list[str]


class StatementTypeResolution(FinancialModel):
    statement_type: StatementType | None = None
    status: ResolutionStatus
    candidates: list[StatementCandidate]
    evidence: list[ContextEvidence]
    issues: list[str]
    financial_fact_verified: Literal[False] = False


class DocumentStatementTypes(FinancialModel):
    # Chỉ inventory các loại đã resolved ở trang, không là nhãn toàn tài liệu.
    pages: list[StatementTypeResolution]
    statement_types: list[StatementType]
    completeness_verified: Literal[False] = False


_TITLES = {
    "B01": r"bảng cân đối kế toán|báo cáo tình hình tài chính",
    "B02": r"báo cáo kết quả hoạt động kinh doanh",
    "B03": r"báo cáo lưu chuyển tiền tệ",
    "B09": r"(?:bản )?thuyết minh báo cáo tài chính",
}
_SUFFIX = r"(?: (?:hợp nhất|riêng))?(?: \(tiếp theo\))?"
_CODE = r"\bb(?:01|02|03|09)\b"
_FORM = rf"mẫu(?: số)?\s*:?\s*({_CODE})(?:\s*[-–]\s*dn)?"


def resolve_statement_type(evidence: Iterable[ContextEvidence]) -> StatementTypeResolution:
    """Evidence phải thuộc một trang; title toàn dòng, code cần title cùng loại.

    Mention giữ candidate yếu; không lấn át title. Title/form mâu thuẫn,
    hoặc title/form chưa accepted/thiếu provenance đều chặn resolved.
    """
    items = list(evidence)
    candidates = []
    for item in items:
        for line in item.raw_text.splitlines():
            text = " ".join(unicodedata.normalize("NFC", line).casefold().split()).strip(" :")
            signals = []
            for label, pattern in _TITLES.items():
                if re.search(rf"\b(?:{pattern})\b", text):
                    title = re.fullmatch(rf"(?:{pattern}){_SUFFIX}", text)
                    signals.append((label, "title" if title else "mention"))
            for match in re.finditer(_CODE, text):
                form = re.fullmatch(_FORM, text)
                signals.append((match[0].upper(), "form_code" if form else "mention"))
            for label, signal in signals:
                issues = ["mention_not_title"] if signal == "mention" else []
                if item.status != "resolved":
                    issues.append("text_not_resolved")
                if not item.provenance:
                    issues.append("missing_provenance")
                candidates.append(
                    StatementCandidate(
                        value=FinancialContext(statement_type=label),
                        signal=signal,
                        evidence=item,
                        status="uncertain" if issues else "resolved",
                        issues=issues,
                    )
                )
    titles = {c.value.statement_type for c in candidates if c.signal == "title"}
    for candidate in candidates:
        if candidate.signal == "form_code" and candidate.value.statement_type not in titles:
            candidate.issues.append("form_code_without_matching_title")
            candidate.status = "uncertain"
    decisive = [c for c in candidates if c.signal != "mention"]
    considered = decisive or candidates
    labels = {c.value.statement_type for c in considered}
    issues = list(dict.fromkeys(issue for c in considered for issue in c.issues))
    if len(labels) > 1:
        issues.append("conflicting_candidates")
    # Caller không thể resolve một PDF nhiều trang bằng cách nối evidence.
    pages = {ref.anchor.page.model_dump_json() for item in items for ref in item.provenance}
    if len(pages) > 1:
        issues.append("mixed_page_scope")
    if not candidates:
        issues.append("missing_evidence")
    status = "unresolved" if not candidates else "uncertain" if issues else "resolved"
    return StatementTypeResolution(
        statement_type=next(iter(labels)) if status == "resolved" else None,
        status=status,
        candidates=candidates,
        evidence=items,
        issues=issues,
    )


def recognize_document_statements(pages: Iterable[UnifiedPage]) -> DocumentStatementTypes:
    """Tổng hợp độc lập từng trang; không tuyên bố inventory đầy đủ hoặc propagate."""
    results = [resolve_statement_type(evidence_from_unified_page(page)) for page in pages]
    return DocumentStatementTypes(
        pages=results,
        statement_types=sorted({r.statement_type for r in results if r.statement_type is not None}),
    )
