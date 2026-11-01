"""Semantic projection rules v1; giữ raw table, không dùng company/layout identity."""

import re
import unicodedata
from decimal import Decimal

SEMANTICS_VERSION = "financial-table-semantics-v1"
# Catalog có version: mã phải đi cùng statement, label và source currency/scale.
PER_SHARE_ITEMS = {
    ("B02", "70"): "lai co ban tren co phieu",
}


def text_key(text):
    text = unicodedata.normalize("NFD", text or "").casefold().replace("đ", "d")
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def numeric_token_issues(raw, normalized=None):
    """Suspicious raw/null representations, never substitute a value."""
    token = (raw or "").strip()
    if token in {"", "-", "–", "—", "−", "N/A", "n/a"}:
        return ["null_numeric_conflict"] if normalized is not None else []
    if any(c.isalpha() for c in token):
        return ["unexpected_alphabetic_numeric_token"]
    if not re.fullmatch(
        r"-?(?:\d+|[1-9]\d{0,2}(?:\.\d{3})+)|\((?:\d+|[1-9]\d{0,2}(?:\.\d{3})+)\)", token
    ):
        return ["malformed_numeric_token"]
    return []


def column_roles(table):
    """Column position + period/header evidence; a numeric note is never a period."""
    from .context_resolution import ContextEvidence, resolve_financial_context

    roles = {}
    for header in table.headers:
        col = header.column
        text = text_key(header.text)
        if col in {table.label_column, table.code_column}:
            roles[col] = "column_header"
        elif "thuyet" in text or text in {"note", "notes", "reference", "note reference"}:
            roles[col] = "note_reference"
        else:
            raw = header.text or ""
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw):
                raw = "Tại ngày " + raw
            period = resolve_financial_context([ContextEvidence(raw_text=raw, provenance=[])])
            # Classification recognizes shape; provenance/period resolution is
            # still enforced by the validator, including uncertain headers.
            numeric_body = any(
                c.column == col and (c.text or "").strip() and not numeric_token_issues(c.text)
                for c in table.cells
            )
            roles[col] = (
                "financial_value" if period.period.candidates or numeric_body else "unknown"
            )
    return roles


def row_role(table, row, roles):
    cells = [c for c in table.cells if c.row == row]
    labels = [c.text for c in cells if c.column == table.label_column]
    codes = [c.text for c in cells if c.column == table.code_column]
    label = text_key(labels[0]) if len(labels) == 1 else ""
    code = (codes[0] or "").strip() if len(codes) == 1 else ""
    values = [c for c in cells if roles.get(c.column) == "financial_value"]
    observed_values = any(c.text and not numeric_token_issues(c.text) for c in values)
    valid_code = bool(re.fullmatch(r"\d{2,3}[a-zA-Z]?", code))
    if label and valid_code and values:
        return (
            "subtotal"
            if re.search(r"tong cong|tong loi nhuan|loi nhuan gop|^cong$", label)
            else "financial_item"
        )
    if (
        not valid_code
        and not observed_values
        and re.search(r"nguoi lap|ke toan truong|giam doc|ngay .*thang .*nam", label)
    ):
        return "signature_or_footer"
    if label in {"chi tieu", "ma so", "thuyet minh", "thuyet so"}:
        return "column_header"
    if label and not code and observed_values:
        return "financial_item"
    if label and not code and all(not (c.text or "").strip() for c in values):
        return "section_header"
    return "unknown"


def item_unit(statement, code, label, currency, scale):
    """Return semantic unit/scale/issues, keeping original unit text at source."""
    key = re.sub(r"^\d+[.)]\s*", "", text_key(label))
    expected = PER_SHARE_ITEMS.get((statement, (code or "").strip()))
    if expected == key and currency and scale == Decimal(1):
        return currency + "/share", scale, []
    if key in PER_SHARE_ITEMS.values() or re.search(r"\beps\b|/share|tren (mot )?co phieu", key):
        return None, None, ["item_unit_uncertain"]
    if "%" in key or key.startswith("ty le ") or key.startswith("thue suat"):
        return None, None, ["item_unit_uncertain"]
    return currency, scale, []
