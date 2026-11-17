"""Replay a closed JSON table domain; no canonical facts or accounting inference."""

import re
from datetime import date
from decimal import Decimal

from .search import normalize_search


def _amount(text):
    # One unambiguous Vietnamese integer representation. Missing is never zero.
    if not isinstance(text, str) or not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)", text):
        return None
    return Decimal(text.replace(".", ""))


def table_assertion(requirement, projections):
    """A named-entity extremum with source header, complete rows and closing total.

    Unsupported layouts/entities fail closed. The excluded aggregate rows remain
    in quotations and the replayed source, including 'other' and the total.
    """
    if len(projections) != 1 or not requirement.selection_period:
        return None
    table = projections[0].get("selection_table", {})
    title, columns, rows = table.get("title", ""), table.get("columns", []), table.get("rows", [])
    query = normalize_search(requirement.query)
    if not query or f" {query} " not in f" {normalize_search(title)} ":
        return None
    if not 1 < len(columns) <= 12 or not 1 < len(rows) <= 100:
        return None
    if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
        return None
    matches = []
    for i, header in enumerate(columns):
        dates = re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", header)
        try:
            periods = {date(int(y), int(m), int(d)).isoformat() for d, m, y in dates}
        except ValueError:
            return None
        if periods == {requirement.selection_period} and re.search(r"\bVND\b", header):
            matches.append(i)
    if len(matches) != 1 or matches[0] == 0:
        return None
    column = matches[0]
    domain, amounts, quotes = [], [], [title, columns[column]]
    for index, row in enumerate(rows):
        label, raw = row[0], row[column]
        value = _amount(raw)
        if not isinstance(label, str) or value is None:
            return None
        text = normalize_search(label)
        quotes.append(f"{label}: {raw}")
        if text in {"cong", "tong cong", "tong"}:
            if index != len(rows) - 1 or value != sum(amounts):
                return None
        else:
            if index == len(rows) - 1:
                return None  # A closing total is required; no partial continuation.
            amounts.append(value)
            if re.fullmatch(r"(?:cac )?(?:khach hang|doi tuong|don vi) khac", text):
                continue
            if not re.match(r"^(?:cong ty|ngan hang|ctcp|ong|ba)\s+\S", text):
                return None  # Do not silently omit an unclassified competitor.
            domain.append((label, value, raw))
    if not domain or len({normalize_search(row[0]) for row in domain}) != len(domain):
        return None
    wording = normalize_search(requirement.label)
    if not re.search(r"\b(lon nhat|nho nhat)\b", wording):
        return None
    smallest = "nho nhat" in wording
    value = (min if smallest else max)(row[1] for row in domain)
    winners = [row for row in domain if row[1] == value]
    names = "; ".join(row[0] for row in winners)
    comparator = "nhỏ nhất" if smallest else "lớn nhất"
    content = (
        f"Trong bảng «{title}», tại {requirement.selection_period}, "
        f"đối tượng được nêu tên riêng có số dư {comparator} là {names}: "
        f"{winners[0][2]} VND. So sánh toàn bộ {len(domain)} đối tượng nêu tên riêng "
        "trong bảng; loại dòng tổng và nhóm đối tượng khác."
    )
    return quotes, content, None
