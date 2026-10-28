"""Resolver context nhỏ, deterministic; không xác minh financial fact hoặc layout."""

import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    ResolutionStatus,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedPage,
)

from .contracts import FinancialContext, FinancialModel, FinancialSourceReference


class ContextEvidence(FinancialModel):
    raw_text: str
    provenance: list[FinancialSourceReference]
    # Trạng thái text M1, độc lập với độ chi tiết/độ tin cậy geometry của anchor.
    status: ResolutionStatus = "resolved"


class ContextCandidate(FinancialModel):
    value: FinancialContext
    evidence: ContextEvidence
    status: ResolutionStatus
    issues: list[str] = Field(default_factory=list)


class ContextFieldResolution(FinancialModel):
    status: ResolutionStatus
    candidates: list[ContextCandidate]
    issues: list[str]


class ContextResolution(FinancialModel):
    context: FinancialContext
    period: ContextFieldResolution
    unit: ContextFieldResolution
    reporting_scope: ContextFieldResolution
    # Kể cả text không match cũng được giữ cho review.
    evidence: list[ContextEvidence]
    financial_fact_verified: Literal[False] = False


_DATE = r"(\d{1,2})\s*(?:/|tháng)\s*(\d{1,2})\s*(?:/|năm)\s*(\d{4})"
_PERIOD_RULES = (
    (rf"kỳ kế toán từ (?:ngày )?{_DATE} đến (?:ngày )?{_DATE}", "date_range"),
    (rf"(?:cho )?năm tài chính kết thúc (?:vào )?ngày {_DATE}", "fiscal_year_end"),
    (rf"tại ngày {_DATE}", "as_of"),
    (r"(?:cho )?năm(?: tài chính)? (\d{4})", "fiscal_year"),
    (r"quý (iv|iii|ii|i|[1-4]) năm (\d{4})", "quarter"),
    (r"(\d{1,2}) tháng đầu năm (\d{4})", "year_to_month"),
)
_SCOPE = r"báo cáo tài chính (hợp nhất|riêng)"


def _iso(parts: tuple[str, ...]) -> str:
    day, month, year = map(int, parts)
    return date(year, month, day).isoformat()


def _period(text: str) -> tuple[FinancialContext, list[str]] | None:
    for pattern, kind in _PERIOD_RULES:
        if match := re.fullmatch(pattern, text):
            parts = match.groups()
            try:
                if kind == "date_range":
                    start, end = _iso(parts[:3]), _iso(parts[3:])
                    if start > end:
                        raise ValueError("Reversed interval")
                    value = f"{start}/{end}"
                elif kind in {"as_of", "fiscal_year_end"}:
                    value = _iso(parts)
                elif kind == "quarter":
                    date(int(parts[1]), 1, 1)
                    quarter = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}.get(parts[0], parts[0])
                    value = f"{parts[1]}-Q{quarter}"
                elif kind == "year_to_month":
                    date(int(parts[1]), 1, 1)
                    if not 1 <= int(parts[0]) <= 12:
                        raise ValueError("Invalid month count")
                    value = f"{parts[1]}-M01/M{int(parts[0]):02d}"
                else:
                    if not 1 <= int(parts[0]) <= 9999:
                        raise ValueError("Invalid year")
                    value = parts[0]
                return FinancialContext(period=value, period_type=kind), []
            except ValueError:
                return FinancialContext(), ["invalid_period"]
    return None


def _candidate(
    value: FinancialContext, evidence: ContextEvidence, issues: list[str]
) -> ContextCandidate:
    issues = list(issues)
    if evidence.status != "resolved":
        issues.append("text_not_resolved")
    if not evidence.provenance:
        issues.append("missing_provenance")
    return ContextCandidate(
        value=value, evidence=evidence, status="uncertain" if issues else "resolved", issues=issues
    )


def _resolve(candidates: list[ContextCandidate]) -> ContextFieldResolution:
    if not candidates:
        return ContextFieldResolution(
            status="unresolved", candidates=[], issues=["missing_evidence"]
        )
    issues = list(dict.fromkeys(issue for c in candidates for issue in c.issues))
    if len({c.value.model_dump_json() for c in candidates}) > 1:
        issues.append("conflicting_candidates")
    return ContextFieldResolution(
        status="uncertain" if issues else "resolved", candidates=candidates, issues=issues
    )


def resolve_financial_context(evidence: Iterable[ContextEvidence]) -> ContextResolution:
    """Resolve trong phạm vi caller chọn; không chọn năm/cột ưu tiên hoặc suy metadata."""
    evidence = list(evidence)
    periods, units, scopes = [], [], []
    for item in evidence:
        for line in item.raw_text.splitlines():
            text = " ".join(line.casefold().split()).strip(" .:;()")
            if parsed := _period(text):
                periods.append(_candidate(parsed[0], item, parsed[1]))
            if match := re.fullmatch(r"đơn vị(?: tính)?\s*:\s*(.+)", text):
                raw_unit = match[1]
                scales = {"đồng": "1", "vnd": "1", "nghìn đồng": "1000", "triệu đồng": "1000000"}
                value = FinancialContext()
                issues = ["unsupported_unit"]
                if raw_unit in scales:
                    value = FinancialContext(currency="VND", scale=Decimal(scales[raw_unit]))
                    issues = []
                units.append(_candidate(value, item, issues))
            for match in re.finditer(_SCOPE, text):
                # Mention trong câu/thuyết minh không chứng minh document scope.
                issues = [] if match.group() == text else ["scope_mention_not_title"]
                scope = "consolidated" if match[1] == "hợp nhất" else "separate"
                scopes.append(_candidate(FinancialContext(reporting_scope=scope), item, issues))
    period, unit, scope = map(_resolve, (periods, units, scopes))
    context = FinancialContext()
    for field in (period, unit, scope):
        if field.status == "resolved":
            context = context.model_copy(
                update=field.candidates[0].value.model_dump(exclude_none=True)
            )
    return ContextResolution(
        context=context, period=period, unit=unit, reporting_scope=scope, evidence=evidence
    )


def evidence_from_unified_page(page: UnifiedPage) -> list[ContextEvidence]:
    """Giữ raw IDs/selector và cấp provenance M1; không dùng geometry chưa verified."""
    result = []
    regions = [*page.text_regions, *(c for table in page.tables for c in table.cells)]
    for region in regions:
        if region.text is None:
            continue
        anchor = SourceAnchor(page=page.identity, status="uncertain")
        if region.provenance_level != "page":
            anchor.element_id = region.raw_element_id
            anchor.table_id = region.raw_table_id
            anchor.cell_id = region.raw_cell_id
        if region.quality.geometry_verified and region.geometry_status == "accepted":
            anchor.observed_bbox = region.bbox
        accepted = (
            region.status == "accepted"
            and region.quality.text_accepted
            and region.quality.downstream_usable
            and "text_evidence" in region.quality.usable_for
        )
        result.append(
            ContextEvidence(
                raw_text=region.text,
                provenance=[
                    FinancialSourceReference(
                        anchor=anchor,
                        source_pointer=region.source_pointer,
                        provenance_level=region.provenance_level,
                    )
                ],
                status="resolved" if accepted else "unresolved",
            )
        )
    return result
