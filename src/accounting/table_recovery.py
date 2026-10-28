"""Liên kết candidate Gemini với bằng chứng đối chiếu thủ công từng vùng ảnh.

Không tự coi Gemini hoặc OCR là ground truth. ManualReview do caller tạo sau khi
đọc ảnh, không được sinh từ candidate; đây không phải xác minh tự động.
"""

import io
import re
from collections import Counter
from typing import Literal

from PIL import Image
from pydantic import Field
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedPage,
)
from vietnamese_financial_multi_agent.document_processing.vision_ocr import (
    QUALITY_REF,
    VerifiedPageImage,
    extract_structured,
    image_source,
    valid_bbox,
    validate_components,
    vision_schema_registry,
)

from .context_resolution import ContextEvidence, resolve_financial_context
from .contracts import (
    FinancialModel,
    FinancialNormalizationResult,
    FinancialSourceReference,
    FinancialValue,
)
from .item_mapping import ITEM_CATALOG, map_item_label


class ReviewedCell(FinancialModel):
    text: str
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    bbox: list[int]


class ManualReview(FinancialModel):
    """Ảnh, text, hàng/cột và bbox đã được reviewer đọc độc lập từ ảnh."""

    image_sha256: str
    reviewer: str
    statement_type: Literal["B01", "B02", "B03"]
    statement: ReviewedCell
    unit: ReviewedCell
    label: ReviewedCell
    code: ReviewedCell
    header: ReviewedCell
    value: ReviewedCell


class LinkDecision(FinancialModel):
    status: Literal["accepted", "unresolved"] = "unresolved"
    issues: list[str] = Field(default_factory=list)
    source_item_code: str | None = None
    recovery_model: str | None = None
    recovery_request_id: str | None = None
    manual_review: ManualReview | None = None
    result: FinancialNormalizationResult | None = None


def recover_table_structure(service, image: VerifiedPageImage, *, credential_ref: str, model: str):
    """Candidate qua Gateway service; schema/layout không chứng nhận nội dung ảnh."""
    return extract_structured(
        service, image, credential_ref=credential_ref, model=model, component_mode=True
    )


def link_reviewed_candidate(
    page: UnifiedPage, image: VerifiedPageImage, recovery: dict, review: ManualReview
) -> LinkDecision:
    """Chỉ chấp nhận một link khi candidate trùng bản đọc ảnh độc lập từng vùng.

    Caller chịu trách nhiệm tính độc lập và danh tính reviewer. Không sửa đầu vào.
    """
    errors = []
    try:
        image.inline()
        with Image.open(io.BytesIO(image.content), formats=["PNG"]) as decoded:
            decoded.load()
            if decoded.size != (image.width, image.height):
                return LinkDecision(issues=["image_dimensions_mismatch"])
    except (ValueError, OSError):
        return LinkDecision(issues=["image_digest_mismatch"])
    if page.identity != image.identity or review.image_sha256 != image.sha256:
        errors.append("image_page_mismatch")
    if not image.identity.source_ref or not image.identity.source_ref.strip():
        return LinkDecision(issues=[*errors, "source_reference_missing"])
    if page.source_type in {"pdf", "png"} and (
        page.source_references.get("image_sha256") != image.sha256
        or page.identity.image != f"sha256:{image.sha256}"
    ):
        errors.append("image_binding_unverified")
    if page.source_type == "existing_ocr" and not page.source_references.get("identity_checked"):
        errors.append("image_binding_unverified")
    if not review.reviewer.strip():
        errors.append("reviewer_missing")
    reviewed = [
        review.statement,
        review.unit,
        review.label,
        review.code,
        review.header,
        review.value,
    ]
    if any(
        not c.text.strip() or not valid_bbox(c.bbox, image.width, image.height) for c in reviewed
    ):
        errors.append("missing_region_evidence")
    if review.label.row != review.code.row or review.label.row != review.value.row:
        errors.append("row_conflict")
    if review.value.column != review.header.column or review.header.row == review.value.row:
        errors.append("period_column_conflict")
    if len({review.label.column, review.code.column, review.value.column}) != 3:
        errors.append("column_conflict")
    if not errors:
        row_boxes = [review.label.bbox, review.code.bbox, review.value.bbox]
        if max(b[1] for b in row_boxes) >= min(b[3] for b in row_boxes):
            errors.append("row_geometry_conflict")
        if not (
            review.label.bbox[2] <= review.code.bbox[0]
            and review.code.bbox[2] <= review.value.bbox[0]
            and review.header.bbox[3] <= review.value.bbox[1]
            and review.header.bbox[0] < review.value.bbox[2]
            and review.value.bbox[0] < review.header.bbox[2]
        ):
            errors.append("column_geometry_conflict")
    response = recovery.get("response") or {}
    raw_output = response.get("output") or {}
    payload = raw_output.get("payload")
    model = ((response.get("provenance") or {}).get("requested_model") or {}).get("model")
    request_id = response.get("request_id")
    if (recovery.get("source") or {}).get("image_sha256") != image.sha256:
        errors.append("candidate_source_mismatch")
    if (
        response.get("status") != "success"
        or response.get("finish_reason") != "stop"
        or raw_output.get("format") != "json"
        or not isinstance(model, str)
        or not model.strip()
        or not isinstance(request_id, str)
        or not request_id.strip()
        or not vision_schema_registry().is_valid(QUALITY_REF, payload)
    ):
        return LinkDecision(issues=[*errors, "invalid_candidate_response"])
    output = validate_components(payload, image, source=image_source(image))
    tables = output.get("tables") or []
    matches = []
    for table in tables:
        cells = table.get("cells", [])
        positions = Counter(
            (c.get("layout", {}).get("row"), c.get("layout", {}).get("column")) for c in cells
        )
        selected = []
        for expected in (review.label, review.code, review.header, review.value):
            found = [
                c
                for c in cells
                if (c.get("layout", {}).get("row"), c.get("layout", {}).get("column"))
                == (expected.row, expected.column)
            ]
            if positions[(expected.row, expected.column)] != 1 or len(found) != 1:
                break
            cell = found[0]
            if (
                cell.get("text") != expected.text
                or cell.get("status") != "accepted"
                or cell.get("layout", {}).get("status") != "accepted"
            ):
                break
            selected.append(cell)
        if len(selected) == 4:
            matches.append(table)
    if len(matches) != 1:
        errors.append("candidate_conflict_missing_or_duplicate")

    # Existing OCR là nguồn text độc lập với Gemini. Row OCR chỉ là kiểm tra
    # bổ sung, không thay thế đối chiếu vùng ảnh của reviewer.
    witnesses = []
    if page.source_type == "existing_ocr":
        label_text = re.sub(r"^\s*\d+\.\s*", "", review.label.text).casefold()
        label_text = " ".join(label_text.split())
        for table in page.tables:
            grouped = {}
            for cell in table.cells:
                row = cell.source_component.get("row")
                if (
                    type(row) is int
                    and cell.status == "accepted"
                    and cell.quality.text_accepted
                    and cell.provenance_level == "cell"
                    and cell.raw_table_id == table.raw_table_id
                    and cell.raw_element_id == table.raw_table_id
                    and cell.raw_cell_id
                ):
                    grouped.setdefault(row, []).append(cell)
            for cells in grouped.values():
                labels = [
                    c for c in cells if c.text and " ".join(c.text.casefold().split()) == label_text
                ]
                codes = [c for c in cells if c.text == review.code.text]
                values = [c for c in cells if c.text == review.value.text]
                if (
                    len(labels) == len(codes) == len(values) == 1
                    and len({c.source_pointer for c in (labels[0], codes[0], values[0])}) == 3
                    and len({c.raw_cell_id for c in (labels[0], codes[0], values[0])}) == 3
                ):
                    witnesses.append((labels[0], codes[0], values[0]))
    if len(witnesses) != 1:
        errors.append("independent_ocr_witness_missing_or_ambiguous")

    def evidence(cell):
        # Image-region anchor is not an OCR cell reference; no fabricated cell ID.
        return ContextEvidence(
            raw_text=cell.text,
            provenance=[
                FinancialSourceReference(
                    anchor=SourceAnchor(
                        page=page.identity, status="uncertain", observed_bbox=cell.bbox
                    ),
                    provenance_level="page",
                )
            ],
        )

    statement_text = review.statement.text.casefold()
    titles = {
        "B01": "bảng cân đối kế toán",
        "B02": "báo cáo kết quả hoạt động kinh doanh",
        "B03": "báo cáo lưu chuyển tiền tệ",
    }
    if titles[review.statement_type] not in statement_text:
        errors.append("statement_not_supported")
    item = map_item_label(evidence(review.label), review.statement_type)
    if item.status != "resolved":
        errors.append("item_unresolved")
    expected_codes = {
        r.observed_source_code
        for r in ITEM_CATALOG
        if r.canonical_item_id == item.canonical_item_id
    }
    if review.code.text not in expected_codes:
        errors.append("source_code_conflict")
    period = resolve_financial_context([evidence(review.header)])
    unit = resolve_financial_context([evidence(review.unit)])
    if period.period.status != "resolved":
        errors.append("period_unresolved")
    if unit.unit.status != "resolved":
        errors.append("unit_unresolved")
    if errors:
        return LinkDecision(issues=errors)
    context = period.context.model_copy(
        update={
            "currency": unit.context.currency,
            "scale": unit.context.scale,
            "statement_type": review.statement_type,
            "raw_item_label": review.label.text,
            "mapped_item_code": item.canonical_item_id,
        }
    )
    refs = [evidence(cell).provenance[0] for cell in reviewed]
    refs.extend(
        FinancialSourceReference(
            anchor=SourceAnchor(
                page=page.identity,
                element_id=cell.raw_element_id,
                table_id=cell.raw_table_id,
                cell_id=cell.raw_cell_id,
                status="uncertain",
            ),
            source_pointer=cell.source_pointer,
            provenance_level=cell.provenance_level,
        )
        for cell in witnesses[0]
    )
    return LinkDecision(
        status="accepted",
        source_item_code=review.code.text,
        recovery_model=model,
        recovery_request_id=request_id,
        manual_review=review.model_copy(deep=True),
        result=FinancialNormalizationResult(
            contract_version="financial_normalization_v1",
            value=FinancialValue(
                raw_value=review.value.text,
                status="unresolved",
                issues=["numeric_normalization_deferred"],
            ),
            context=context,
            provenance=refs,
        ),
    )
