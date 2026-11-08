"""Nhận diện câu hỏi baseline; catalog là allowlist, không là nguồn số liệu."""

import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..accounting.item_mapping import ITEM_CATALOG


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


FORMULA_ALIASES = {
    "gross_margin": ("biên lợi nhuận gộp", "tỷ suất lợi nhuận gộp", "gross margin"),
    "debt_to_assets": (
        "tỷ lệ nợ trên tài sản",
        "tỷ lệ nợ trên tổng tài sản",
        "tỷ lệ nợ phải trả trên tổng tài sản",
        "nợ phải trả trên tổng tài sản",
        "debt-to-assets",
        "hệ số nợ trên tổng tài sản",
    ),
    "revenue_yoy": ("tăng trưởng doanh thu", "revenue yoy", "doanh thu tăng trưởng"),
}
FORMULA_LABELS = {
    "gross_margin": "Biên lợi nhuận gộp",
    "debt_to_assets": "Tỷ lệ nợ phải trả trên tổng tài sản",
    "revenue_yoy": "Tăng trưởng doanh thu",
}
# Bổ sung cách hỏi thông dụng vào catalog hiện có, không giới hạn năm chỉ tiêu.
EXTRA_ALIASES = {
    "b01.total_assets": ("tổng tài sản",),
    "b01.total_liabilities": ("tổng nợ", "nợ phải trả"),
    "b02.net_revenue": ("doanh thu", "doanh thu thuần"),
    "b02.gross_profit": ("lợi nhuận gộp",),
    "b03.operating_cash_flow": (
        "dòng tiền thuần từ hoạt động kinh doanh",
        "dòng tiền từ hoạt động kinh doanh",
    ),
}
ITEM_RULES = {r.canonical_item_id: r for r in ITEM_CATALOG}


class QAUnderstanding(FinancialModel):
    intent: Literal["direct_fact", "calculated_metric", "evidence_explanation", "unsupported"]
    canonical_item_id: str | None = None
    formula_id: str | None = None
    company_alias: str | None = None
    reporting_year: int | None = Field(default=None, ge=1900, le=2200)
    reporting_scope: Literal["separate", "consolidated"] | None = None
    period: str | None = None


def _matches(text, aliases):
    """Longest non-overlapping phrases; shared labels giữ nhiều IDs để hỏi lại."""
    spans = []
    for key, names in aliases.items():
        for name in names:
            phrase = normalize(name)
            for match in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text):
                spans.append((match.start(), match.end(), key))
    return {
        key
        for start, end, key in spans
        if not any(a <= start and end <= b and b - a > end - start for a, b, _ in spans)
    }


def natural_formula(text):
    """Recognize growth intent independent of company/year words between its terms."""
    if re.search(r"\bdoanh thu\b.*\b(tang hay giam|tang hoac giam)\b.*\bnam truoc\b", text):
        return "revenue_yoy"
    return None


def understand(question: str) -> tuple[QAUnderstanding, list[str]]:
    text = normalize(question)
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", text))
    parsed = QAUnderstanding(
        intent="unsupported",
        reporting_year=int(next(iter(years))) if len(years) == 1 else None,
        reporting_scope="consolidated"
        if "hop nhat" in text
        else "separate"
        if "rieng" in text
        else None,
    )
    if re.search(r"\b(quy|thang|ban nien)\b", re.sub(r"\bquy dinh\b", "", text)):
        return parsed, ["non_annual_period_unsupported"]
    dates = re.findall(r"\b(\d{1,2})/(\d{1,2})/((?:19|20|21)\d{2})\b", question)
    iso_dates = re.findall(r"\b((?:19|20|21)\d{2})-(\d{2})-(\d{2})\b", question)
    if dates or iso_dates:
        try:
            periods = {date(int(y), int(m), int(d)).isoformat() for d, m, y in dates}
            periods.update(date(int(y), int(m), int(d)).isoformat() for y, m, d in iso_dates)
        except ValueError:
            return parsed, ["invalid_period"]
        if len(periods) != 1:
            return parsed, ["multiple_periods_unsupported"]
        parsed.period = next(iter(periods))
    elif parsed.reporting_year and "dau nam" in text:
        parsed.period = f"{parsed.reporting_year}-01-01"
    # Một baseline đơn mục tiêu; không diễn giải phép so sánh thành một fact.
    if len(years) > 1 or "lien tai lieu" in text:
        return parsed, ["cross_document_comparison_blocked_D03_B10"]
    if any(p in text for p in ("so sanh", "chenh lech")):
        if len(years) == 1 and "cung bao cao" in text:
            return parsed, ["semantic_intent_requires_gateway"]
        return parsed, ["cross_document_comparison_blocked_D03_B10"]
    if any(
        p in text
        for p in (
            "roe",
            "roa",
            "ebitda",
            "du bao",
            "du doan",
            "gia co phieu",
            "thanh toan hien hanh",
            "bien loi nhuan rong",
            "ty suat sinh loi",
            "tren von chu so huu",
        )
    ):
        return parsed, ["unsupported_question_or_formula"]
    evidence = any(
        p in text
        for p in (
            "nguon o dau",
            "nguon nao",
            "nguon goc",
            "nguon cua",
            "nguon so lieu",
            "dan nguon",
            "trang nao",
            "trang may",
            "bang chung",
            "cong thuc",
            "lay so",
            "so lieu nao",
            "nhung so lieu",
            "tin cay",
            "dua tren",
            "tinh tu",
            "chung minh",
        )
    )
    formulas = _matches(text, FORMULA_ALIASES)
    if inferred := natural_formula(text):
        formulas.add(inferred)
    if not formulas and any(
        p in text
        for p in (
            "doanh thu tai chinh",
            "doanh thu khac",
            "doanh thu gop",
            "tang bao nhieu",
            "giam bao nhieu",
            "trung binh",
            "von hoa",
        )
    ):
        return parsed, ["unsupported_question_or_formula"]
    items = _matches(
        text, {key: (*r.aliases, key, *EXTRA_ALIASES.get(key, ())) for key, r in ITEM_RULES.items()}
    )
    if len(formulas) > 1 or (not formulas and len(items) > 1):
        return parsed, ["multiple_or_ambiguous_targets"]
    if formulas:
        parsed.formula_id = next(iter(formulas))
        parsed.intent = "evidence_explanation" if evidence else "calculated_metric"
    elif items:
        parsed.canonical_item_id = next(iter(items))
        parsed.intent = "evidence_explanation" if evidence else "direct_fact"
    elif evidence:
        parsed.intent = "evidence_explanation"
    # Không lấy một operand trong câu hỏi tỷ số chưa duyệt làm direct QA.
    if not formulas and any(p in text for p in ("ty le", "ty suat", "he so", "phan tram")):
        return parsed.model_copy(update={"intent": "unsupported"}), ["unsupported_formula"]
    if "hop nhat" in text and "rieng" in text:
        return parsed, ["ambiguous_reporting_scope"]
    return parsed, []
