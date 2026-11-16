"""Small source-preserving context rules for refined financial tables."""

import hashlib
import re

from ..accounting.automated_extraction import column_period_evidence
from ..accounting.context_resolution import resolve_financial_context
from ..accounting.extraction_semantics import text_key


def projected(item, text):
    return item.model_copy(update={"raw_text": text})


def context_lines(items):
    """Keep pointers to original text, including when selecting an exact phrase."""
    result = []
    for item in items:
        for line in item.raw_text.splitlines():
            result.append(projected(item, line))
            annual = re.search(r"(?:cho )?năm tài chính kết thúc(?: vào)? ngày .+$", line, re.I)
            if annual:
                result.append(projected(item, annual.group()))
            title = re.match(r"báo cáo tài chính (hợp nhất|riêng)\b", line, re.I)
            if title:
                result.append(projected(item, title.group()))
            # Presentation currency declaration, not merely bookkeeping currency.
            if re.search(r"báo cáo tài chính.*trình bày bằng.*đồng việt nam", line, re.I):
                result.append(projected(item, "Đơn vị tính: đồng"))
    return result


def company_binding(items):
    for item in items:
        line = item.raw_text.splitlines()[0].strip()
        if re.match(r"CÔNG TY (?:CỔ PHẦN|CP|TNHH)\b", line):
            return "json-company:" + hashlib.sha256(text_key(line).encode()).hexdigest(), item
    return None, None


def filing_cover(items, text_only_pages):
    """Skip auditor/signature front sheets only with an explicit filing cover."""
    first = [i for i in items if i.provenance[0].anchor.page.page == 1]
    if company_binding(first)[0]:
        return first
    candidates = []
    for page in sorted(text_only_pages & {2, 3, 4, 5}):
        context = [i for i in items if i.provenance[0].anchor.page.page == page]
        company, _ = company_binding(context)
        title = any(
            re.fullmatch(r"báo cáo tài chính(?: hợp nhất| riêng)?", i.raw_text.strip(), re.I)
            for i in context
        )
        if company and title and resolve_financial_context(context).period.status == "resolved":
            candidates.append((company, context))
    # Multiple issuers in front matter must not be silently selected.
    if len({company for company, _ in candidates}) == 1:
        return candidates[0][1]
    return first


def header_context(header, page_context, statement, document_context):
    items = []
    for line in header.raw_text.splitlines():
        # A date must label the column, not be buried in a duration/contract note.
        date = re.match(r"(?:tại ngày\s+)?(\d{1,2}/\d{1,2}/\d{4})(?=$|\s|[(-])", line, re.I)
        if date:
            items.append(projected(header, "Tại ngày " + date[1]))
        year = re.match(r"(năm(?: tài chính)? \d{4})(?=$|\s|\()", line, re.I)
        if year:
            items.append(projected(header, year[1]))
        relative = re.fullmatch(
            r"(số cuối năm|số đầu năm|năm nay|năm trước)(?:\s*\([^)]*\))?", line.strip(), re.I
        )
        if relative:
            kind = "B01" if text_key(relative[1]).startswith("so ") else "B02"
            if statement in {"B01", "B02", "B03"}:
                kind = statement
            candidates = page_context
            resolved = resolve_financial_context(candidates)
            if resolved.period.status != "resolved":
                candidates = document_context
            # Annual end is enough to derive a calendar-year stock boundary.
            if kind == "B01":
                candidates = [
                    projected(
                        i,
                        re.sub(
                            r"(?:cho )?năm tài chính kết thúc(?: vào)? ngày",
                            "Tại ngày",
                            i.raw_text,
                            flags=re.I,
                        ),
                    )
                    for i in candidates
                ]
            items.append(column_period_evidence(projected(header, relative[1]), candidates, kind))
        items.append(header)
    return resolve_financial_context(items)


def header_unit(header):
    key = text_key(header.raw_text)
    for token, raw in [
        ("trieu dong", "triệu đồng"),
        ("nghin dong", "nghìn đồng"),
        ("vnd", "VND"),
        ("vnđ", "VND"),
    ]:
        if re.search(r"\b" + token + r"\b", key):
            return resolve_financial_context([projected(header, "Đơn vị tính: " + raw)])
    return resolve_financial_context([])


def stock_page_context(items, statement):
    if statement != "B01":
        return items
    return [
        projected(
            i,
            "Tại " + i.raw_text
            if re.fullmatch(r"ngày \d{1,2} tháng \d{1,2} năm \d{4}", i.raw_text, re.I)
            else i.raw_text,
        )
        for i in items
    ]
