"""Hai cấp validation thuần bộ nhớ, không đọc file hoặc sửa OCR nguồn."""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from .raw_ocr import (
    OCRCheckbox,
    OCRPage,
    OCRSealSignatureRegion,
    OCRSignature,
    OCRTable,
)

FieldPath = tuple[str | int, ...]


class StructuralIssue(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    path: FieldPath
    message: str


class RawOCRStructuralError(ValueError):
    """Giữ bản sao payload lỗi; không đưa nội dung OCR vào thông báo/log mặc định."""

    def __init__(self, payload: Any, issues: list[StructuralIssue]):
        self.payload = deepcopy(payload)
        self.issues = issues
        super().__init__(f"Raw OCR structural validation failed: {len(issues)} issue(s)")


def parse_raw_ocr(payload: Any) -> OCRPage:
    """Đọc JSON object đã decode; lỗi bất kỳ element nào làm cả trang thất bại."""
    try:
        return OCRPage.model_validate(payload)
    except ValidationError as error:
        issues = []
        for detail in error.errors(include_input=False, include_url=False):
            path = detail["loc"]
            # Pydantic thêm union tag vào loc; bỏ tag để path trỏ đúng JSON nguồn.
            if len(path) > 2 and path[0] == "elements" and isinstance(path[1], int):
                path = path[:2] + path[3:]
            issues.append(StructuralIssue(code=detail["type"], path=path, message=detail["msg"]))
        raise RawOCRStructuralError(payload, issues) from None


class QualityIssue(BaseModel):
    """Tín hiệu cần review, không phải kết luận OCR sai hoặc đánh giá tài chính."""

    model_config = ConfigDict(frozen=True)
    code: str
    path: FieldPath
    message: str


def validate_quality(page: OCRPage) -> list[QualityIssue]:
    """Chạy sau structural validation; chỉ trả issues, không loại object hay sửa giá trị."""
    issues: list[QualityIssue] = []

    def add(code: str, path: FieldPath, message: str) -> None:
        issues.append(QualityIssue(code=code, path=path, message=message))

    def bbox(box: list[int], path: FieldPath) -> None:
        x1, y1, x2, y2 = box
        if x1 >= x2 or y1 >= y2:
            add("invalid_bbox_geometry", path, "Expected x1 < x2 and y1 < y2")
        if (
            min(x1, x2) < 0
            or min(y1, y2) < 0
            or max(x1, x2) > page.page.width
            or max(y1, y2) > page.page.height
        ):
            add("bbox_outside_page", path, "Coordinates exceed page dimensions")

    def check_id(value: str, seen: set[str], path: FieldPath) -> None:
        if value in seen:
            add("duplicate_id", path, "ID repeated within its containing collection")
        seen.add(value)

    for dimension in ("width", "height", "dpi"):
        if getattr(page.page, dimension) <= 0:
            add("invalid_page_dimension", ("page", dimension), "Expected a positive value")

    signatures = {e.id for e in page.elements if isinstance(e, OCRSignature)}
    texts = {e.id for e in page.elements if e.type == "text"}
    element_ids: set[str] = set()
    for i, element in enumerate(page.elements):
        path = ("elements", i)
        check_id(element.id, element_ids, path + ("id",))
        bbox(element.bbox, path + ("bbox",))
        if isinstance(element, (OCRSignature, OCRCheckbox)):
            if element.confidence is not None and not 0 <= element.confidence <= 1:
                add("confidence_out_of_range", path + ("confidence",), "Expected [0, 1] or null")
        if isinstance(element, OCRCheckbox):
            for j, reference in enumerate(element.label_text_ids):
                ref_path = path + ("label_text_ids", j)
                if not isinstance(reference, str):
                    add(
                        "unresolved_reference_type", ref_path, "Item schema is TBD; value preserved"
                    )
                elif reference not in texts:
                    add("unresolved_text_reference", ref_path, "No page text element with this ID")
        if isinstance(element, OCRSealSignatureRegion):
            bbox(element.seal_bbox, path + ("seal_bbox",))
            bbox(element.signature_bbox, path + ("signature_bbox",))
            if element.signature_id not in signatures:
                add(
                    "unresolved_signature_reference",
                    path + ("signature_id",),
                    "No signature element with this ID",
                )
        if not isinstance(element, OCRTable):
            continue
        positions: set[tuple[int, int]] = set()
        cell_ids: set[str] = set()
        for j, cell in enumerate(element.cells):
            cell_path = path + ("cells", j)
            check_id(cell.id, cell_ids, cell_path + ("id",))
            bbox(cell.bbox, cell_path + ("bbox",))
            position = (cell.row, cell.col)
            if position in positions:
                add("duplicate_cell_position", cell_path, "Row/col pair repeated in table")
            positions.add(position)
            for axis in ("row", "col"):
                if getattr(cell, axis) < 0:
                    add("negative_cell_position", cell_path + (axis,), "Negative row/col index")
            if cell.text == "":
                add(
                    "empty_cell_text",
                    cell_path + ("text",),
                    "Empty source text; may be intentional",
                )
            if cell.line_count != len(cell.lines):
                add(
                    "line_count_mismatch",
                    cell_path + ("line_count",),
                    "Count differs from lines length",
                )
            line_ids: set[str] = set()
            for k, line in enumerate(cell.lines):
                line_path = cell_path + ("lines", k)
                check_id(line.id, line_ids, line_path + ("id",))
                bbox(line.bbox, line_path + ("bbox",))
                if "cell_id" in line.model_fields_set and line.cell_id != cell.id:
                    add(
                        "cell_reference_mismatch",
                        line_path + ("cell_id",),
                        "Reference differs from containing cell ID",
                    )
        if positions:
            rows, cols = zip(*positions, strict=True)
            expected = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
            if len(positions) < expected:
                add(
                    "sparse_table",
                    path + ("cells",),
                    "Positions do not fill min/max rectangle; no missing cell inferred",
                )
    return issues
