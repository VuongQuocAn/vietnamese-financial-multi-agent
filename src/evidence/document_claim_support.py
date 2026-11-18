"""Source-shaped propositions. A retrieved hit supplies no verification authority."""

import re

from ..evidence.search import normalize_search

OCR_CAVEAT = "Trích từ bản nhận dạng đã lưu, với vị trí chứng cứ ở cấp độ nguồn ghi nhận."
SOURCE_LIMIT = "Nội dung phản ánh tài liệu đã lưu."


def declared_list_count(texts):
    for text in texts:
        match = re.search(r"\((\d{1,2})\)\s+điều kiện", text, flags=re.I)
        if match:
            return int(match[1])
    return None


def is_list_item(text):
    return bool(re.match(r"^\s*(?:[-–•]\s*|\([a-z0-9]+\)\s*)", text, flags=re.I))


def complete_declared_list(texts):
    declared = declared_list_count(texts)
    return declared is None or sum(is_list_item(t) for t in texts) == declared


def document_projection(record, *, literal=False):
    if record.kind == "text":
        return {"text": record.raw_text} if record.raw_text and len(record.raw_text) <= 6000 else {}
    if literal:
        # Full saved table, including excluded aggregates. Never a cropped top-k row set.
        table = record.source_metadata.get("original_table")
        if (
            table
            and not record.structural_issues
            and not record.source_metadata.get("ragged_row_indices")
        ):
            return {"literal_table": table}
        return {}
    # Only labeled, indexed rows. Unplaced totals and numeric cells are excluded.
    labels = [cell.text for _, cell in _label_cells(record)]
    return {"labels": labels} if labels and sum(map(len, labels)) <= 6000 else {}


def _label_cells(record):
    column = getattr(record.structure, "label_column", 0)
    return [
        (i, cell)
        for i, cell in enumerate(getattr(record.structure, "cells", []))
        if cell.row is not None
        and getattr(cell, "column", getattr(cell, "col", None)) == column
        and cell.text
    ]


def document_citations(record, citations, *, literal=False):
    if record.kind == "text":
        return citations
    if literal:
        return citations
    primary = {a.reference.source_pointer for a in record.sources if a.reference}
    labels = {
        getattr(cell, "source_pointer", None) or f"{pointer}/cells/{i}"
        for i, cell in _label_cells(record)
        for pointer in primary
    }
    return [
        c
        for c in citations
        if c.source.reference and c.source.reference.source_pointer in primary | labels
    ]


def _contains(text, query):
    return f" {normalize_search(query)} " in f" {normalize_search(text)} "


def excerpt_topic_matches(text, query):
    """Literal retrieval matching only; M6 owns semantic relevance."""
    return _contains(text, query)


def source_assertion(requirement, projections):
    """Return exact quotations, protected display and optional explicit relationship."""
    if not projections or any(not value for value in projections):
        return None
    if (
        requirement.kind == "exact_text"
        and len(projections) == 1
        and projections[0].get("literal_table")
    ):
        table = projections[0]["literal_table"]
        rows = [
            row
            for row in table.get("rows", [])
            if row and isinstance(row[0], str) and _contains(row[0], requirement.query)
        ]
        if len(rows) != 1 or not all(isinstance(c, str) and c.strip() for c in rows[0]):
            return None
        # Literal row plus original headers: no numerical interpretation,
        # selection or canonical promotion. M6 replays the same pinned table.
        quotes = [" | ".join(table.get("columns", [])), " | ".join(rows[0])]
        if table.get("title"):
            quotes.insert(0, table["title"])
        if not all(quotes):
            return None
        return quotes, "Tài liệu ghi «" + " ; ".join(quotes) + "»", None
    if requirement.kind == "table_labels":
        if len(projections) != 1:
            return None
        labels = projections[0].get("labels", [])
        if labels and any(_contains(label, requirement.query) for label in labels):
            return (
                labels,
                " | ".join(labels),
                None,
            )
        return None
    texts = [p.get("text", "") for p in projections]
    if not all(texts):
        return None
    if requirement.kind == "entity_role":
        if len(texts) != 1:
            return None
        match = re.fullmatch(r"([^:\n]+):\s*([^:\n]+)", texts[0].strip())
        if match and normalize_search(match[1]) in {
            requirement.target,
            requirement.target + " bieu",
        }:
            return texts, f"Tài liệu ghi «{texts[0]}».", match[2]
        return None
    # Exact source text may be quoted independently of whether it answers a goal.
    if requirement.kind != "source_excerpt" and len(texts) != 1:
        return None
    return texts, "Tài liệu ghi «" + " ".join(texts) + "»", None


def consecutive(citations):
    """Require the same page, original artifact and contiguous source pointers."""
    if any(not refs for refs in citations):
        return False
    refs = [group[0].source.reference for group in citations]
    if any(ref is None for ref in refs):
        return False
    if len(refs) == 1:
        return True
    pointers = [
        re.fullmatch(r"(/(?:text_elements|context)/)(\d+)", r.source_pointer or "") for r in refs
    ]
    return (
        all(pointers)
        and len({p[1] for p in pointers}) == 1
        and all(r.anchor.page == refs[0].anchor.page for r in refs)
        and [int(p[2]) for p in pointers]
        == list(range(int(pointers[0][2]), int(pointers[0][2]) + len(refs)))
    )
