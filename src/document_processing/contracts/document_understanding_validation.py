"""Validation thuần bộ nhớ; không đọc nguồn hoặc tự thay reference."""

from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from .document_understanding import (
    DocumentUnderstandingResult,
    RawPageIdentity,
    SourceAnchor,
    UnderstandingIssue,
)
from .raw_ocr import OCRPage, OCRTable
from .validation import StructuralIssue


class DocumentUnderstandingStructuralError(ValueError):
    def __init__(self, payload: Any, issues: list[StructuralIssue]):
        self.payload = deepcopy(payload)
        self.issues = issues
        super().__init__(
            f"Document Understanding structural validation failed: {len(issues)} issue(s)"
        )


def parse_document_understanding(payload: Any) -> DocumentUnderstandingResult:
    """Nhận JSON object đã decode; lỗi toàn result có field paths và bản sao payload."""
    try:
        return DocumentUnderstandingResult.model_validate(payload)
    except ValidationError as error:
        issues = [
            StructuralIssue(code=d["type"], path=d["loc"], message=d["msg"])
            for d in error.errors(include_input=False, include_url=False)
        ]
        raise DocumentUnderstandingStructuralError(payload, issues) from None


def validate_understanding_quality(
    result: DocumentUnderstandingResult, *, raw_page: OCRPage | None = None
) -> list[UnderstandingIssue]:
    """Không sửa result/raw. Bỏ qua đối chiếu raw nếu caller không truyền raw_page.

    Caller chịu trách nhiệm binding source_ref/run tới đúng raw_page truyền vào;
    Raw OCR v1 không có run identity để hàm tự xác minh binding này.
    """
    issues: list[UnderstandingIssue] = []

    def add(code: str, path: tuple, message: str) -> None:
        issues.append(UnderstandingIssue(code=code, path=list(path), message=message))

    def bbox(box: list[int] | None, path: tuple) -> None:
        if box is not None and (box[0] >= box[2] or box[1] >= box[3]):
            add("invalid_bbox_geometry", path, "Expected x1 < x2 and y1 < y2")

    def identifiers(objects: list, path: tuple) -> None:
        seen: set[str] = set()
        for i, obj in enumerate(objects):
            if not obj.id.strip():
                add("empty_id", path + (i, "id"), "Expected a non-empty ID")
            if obj.id in seen:
                add("duplicate_id", path + (i, "id"), "ID repeated within containing collection")
            seen.add(obj.id)

    def matches_raw(identity: RawPageIdentity) -> bool:
        assert raw_page is not None
        return all(
            getattr(identity, field) == getattr(raw_page.page, field)
            for field in ("symbol", "year", "page", "image")
        )

    if raw_page is not None and not matches_raw(result.raw_page):
        add("raw_page_mismatch", ("raw_page",), "Provided Raw OCR page has different identity")

    def resolve(anchor: SourceAnchor, path: tuple) -> None:
        """Mỗi bước chọn đúng một đối tượng trong container, không chọn match đầu."""
        assert raw_page is not None
        if not matches_raw(anchor.page):
            add("raw_page_mismatch", path + ("page",), "Anchor differs from provided Raw OCR page")
            return
        if anchor.table_id is not None and anchor.element_id not in (None, anchor.table_id):
            # Đã báo ở standalone; không dùng ID khác để fallback.
            return
        target_id = anchor.element_id if anchor.element_id is not None else anchor.table_id
        if target_id is None:
            return
        candidates = [e for e in raw_page.elements if e.id == target_id]
        kind = "element" if anchor.element_id is not None else "table"
        target = select(candidates, path, kind)
        if target is None:
            return
        if anchor.table_id is not None and not isinstance(target, OCRTable):
            add("reference_type_mismatch", path + ("table_id",), "Expected a Raw OCR table")
            return
        if anchor.cell_id is not None:
            if anchor.table_id is None or not isinstance(target, OCRTable):
                return
            target = select([c for c in target.cells if c.id == anchor.cell_id], path, "cell")
            if target is None:
                return
        if anchor.line_id is not None:
            if anchor.cell_id is None or anchor.table_id is None:
                return
            target = select(
                [line for line in target.lines if line.id == anchor.line_id], path, "line"
            )
            if target is None:
                return
        if anchor.observed_bbox is not None and anchor.observed_bbox != target.bbox:
            add(
                "observed_bbox_mismatch",
                path + ("observed_bbox",),
                "Bbox differs from Raw OCR source",
            )

    def select(candidates: list, path: tuple, kind: str) -> Any:
        if len(candidates) == 1:
            return candidates[0]
        code = "unresolved_source_reference" if not candidates else "ambiguous_source_reference"
        add(code, path + (kind + "_id",), "Expected exactly one source in its containing context")
        return None

    def anchor_quality(anchor: SourceAnchor, path: tuple) -> bool:
        start = len(issues)
        if anchor.page != result.raw_page:
            add("anchor_page_mismatch", path + ("page",), "Anchor must belong to result raw_page")
        for field in ("symbol", "year", "image", "source_ref"):
            value = getattr(anchor.page, field)
            if value is not None and not value.strip():
                add("empty_source_identity", path + ("page", field), "Empty source identity")
        for field in ("element_id", "table_id", "cell_id", "line_id"):
            value = getattr(anchor, field)
            if value is not None and not value.strip():
                add("empty_source_reference", path + (field,), "Empty source ID")
        for field in ("observed_bbox", "proposed_bbox"):
            bbox(getattr(anchor, field), path + (field,))
        if anchor.cell_id is not None and anchor.table_id is None:
            add("ambiguous_cell_reference", path + ("cell_id",), "cell_id requires table_id")
        if anchor.line_id is not None and (anchor.table_id is None or anchor.cell_id is None):
            add(
                "ambiguous_line_reference",
                path + ("line_id",),
                "line_id requires table_id and cell_id",
            )
        if anchor.table_id is not None and anchor.element_id not in (None, anchor.table_id):
            add("source_context_mismatch", path, "element_id must identify the containing table")
        has_id = anchor.element_id is not None or anchor.table_id is not None
        if not has_id:
            if anchor.observed_bbox is None or not anchor.page.image.strip():
                add(
                    "missing_provenance",
                    path,
                    "Expected OCR reference or observed source image region",
                )
            if anchor.status == "resolved":
                add(
                    "status_conflict",
                    path + ("status",),
                    "Image-only anchor must remain uncertain/unresolved",
                )
        if raw_page is not None:
            resolve(anchor, path)
        if anchor.status == "resolved" and len(issues) > start:
            if not any(i.code == "status_conflict" for i in issues[start:]):
                add(
                    "status_conflict",
                    path + ("status",),
                    "Resolved anchor has invalid source linkage",
                )
        return len(issues) == start and anchor.status == "resolved"

    def content(obj: Any, path: tuple) -> None:
        if not obj.anchors:
            add("missing_provenance", path + ("anchors",), "No source anchors supplied")
        valid = [anchor_quality(a, path + ("anchors", i)) for i, a in enumerate(obj.anchors)]
        if obj.status == "resolved" and (not valid or not all(valid)):
            add(
                "status_conflict",
                path + ("status",),
                "Resolved object requires resolved valid source anchors",
            )
        if hasattr(obj, "text") and not obj.text.strip():
            add("empty_text", path + ("text",), "Empty or whitespace-only text; content preserved")

    classification = result.classification
    # Unknown classification không cần bằng chứng nếu chưa có candidate.
    if classification.label is not None or classification.anchors:
        content(classification, ("classification",))
    if classification.label is not None and (
        not classification.label.strip() or classification.label.strip().casefold() == "unknown"
    ):
        add(
            "invalid_classification_label",
            ("classification", "label"),
            "Use null for unknown classification",
        )
    if classification.status == "resolved" and classification.label is None:
        add(
            "status_conflict",
            ("classification", "status"),
            "Resolved classification requires a label",
        )
    if classification.confidence is not None and not 0 <= classification.confidence <= 1:
        add("confidence_out_of_range", ("classification", "confidence"), "Expected [0, 1] or null")
    identifiers(result.text_regions, ("text_regions",))
    identifiers(result.tables, ("tables",))
    for i, region in enumerate(result.text_regions):
        path = ("text_regions", i)
        content(region, path)
        if region.reading_order is not None and region.reading_order < 0:
            add("negative_reading_order", path + ("reading_order",), "Expected non-negative order")
    for i, table in enumerate(result.tables):
        path = ("tables", i)
        content(table, path)
        if table.origin == "ocr_table" and not any(a.table_id is not None for a in table.anchors):
            add(
                "missing_ocr_table_reference",
                path + ("anchors",),
                "ocr_table origin requires table_id",
            )
        identifiers(table.cells, path + ("cells",))
        positions: set[tuple[int, int]] = set()
        for j, cell in enumerate(table.cells):
            cp = path + ("cells", j)
            content(cell, cp)
            for field in ("row", "col"):
                if getattr(cell, field) < 0:
                    add("negative_cell_position", cp + (field,), "Expected non-negative coordinate")
            position = (cell.row, cell.col)
            if position in positions:
                add("duplicate_cell_position", cp, "Position already used; may require review")
            positions.add(position)
            for field in ("rowspan", "colspan"):
                value = getattr(cell, field)
                if value is not None and value <= 0:
                    add("invalid_span", cp + (field,), "Expected positive span or unknown")
    return issues
