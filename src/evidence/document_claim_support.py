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


def document_projection(record):
    if record.kind == "text":
        return {"text": record.raw_text} if record.raw_text and len(record.raw_text) <= 6000 else {}
    # Only labeled, indexed rows. Unplaced totals and numeric cells are excluded.
    labels = [cell.text for _, cell in _label_cells(record)]
    return {"labels": labels} if labels and sum(map(len, labels)) <= 6000 else {}


def _label_cells(record):
    column = getattr(record.structure, "label_column", 0)
    return [
        (i, cell)
        for i, cell in enumerate(getattr(record.structure, "cells", []))
        if cell.row is not None and cell.column == column and cell.text
    ]


def document_citations(record, citations):
    if record.kind == "text":
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
    """Keep noun phrases intact; permit an explicit predicate before its subject.

    This establishes relevance of a verbatim quotation, never an inferred claim.
    Reordered predicates must occur in the same sentence as the exact subject.
    """
    if _contains(text, query):
        return True
    parts = re.split(r"\s+và\s+", query, flags=re.I)
    if len(parts) > 1:
        return all(_contains(text, part) for part in parts)
    match = re.match(r"^(khấu hao|phân bổ|ghi nhận)\s+(.+)$", query, flags=re.I)
    return bool(match) and any(
        _contains(sentence, match[1]) and _contains(sentence, match[2])
        for sentence in re.split(r"[.;\n]", text)
    )


def source_assertion(requirement, projections):
    """Return exact quotations, protected display and optional explicit relationship."""
    if not projections or any(not value for value in projections):
        return None
    if requirement.kind == "table_labels":
        if len(projections) != 1:
            return None
        labels = projections[0].get("labels", [])
        if (
            labels
            and all(_contains(label, "tiền") for label in labels)
            and any(_contains(label, requirement.query) for label in labels)
        ):
            return (
                labels,
                "Các khoản mục đọc được trong bảng tiền gồm " + ", ".join(labels) + ".",
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
        if (
            match
            and normalize_search(match[1]) in {requirement.target, requirement.target + " bieu"}
            and re.fullmatch(r"[^\W\d_]+(?: +[^\W\d_]+){1,5}", match[2])
            and all(word[0].isupper() for word in match[2].split())
        ):
            return texts, f"Tài liệu ghi «{texts[0]}».", match[2]
        return None
    # Opinion needs the complete qualified opinion section. Search alone cannot
    # certify its boundaries or any omitted qualifications.
    topic_matches = (
        excerpt_topic_matches(" ".join(texts), requirement.query)
        if requirement.kind == "source_excerpt"
        else _contains(texts[0], requirement.query)
    )
    if requirement.target == "y kien kiem toan" or not topic_matches:
        return None
    if requirement.target == "nhan vien quan ly chu chot":
        if not texts[-1].rstrip().endswith(".") or any(
            t.rstrip().endswith(".") for t in texts[:-1]
        ):
            return None
    elif requirement.kind == "source_excerpt":
        # A heading alone does not answer what a note says. Keep complete,
        # contiguous verbatim source text; no synthesized financial relation.
        if len(" ".join(texts)) < len(requirement.query) + 30 or not texts[-1].rstrip().endswith(
            (".", ";", ":")
        ):
            return None
    elif len(texts) != 1:
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
