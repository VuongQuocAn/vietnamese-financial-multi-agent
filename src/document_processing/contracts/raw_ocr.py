"""Contract raw_ocr_v1: cấu trúc nguồn, không sửa nội dung hoặc hình học OCR."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RAW_OCR_CONTRACT_VERSION = "raw_ocr_v1"

# List giữ representation JSON; độ dài là structural, hình học là quality.
OCRBoundingBox = Annotated[list[int], Field(min_length=4, max_length=4)]


class RawOCRModel(BaseModel):
    """Không coercion, không mất extra fields ở bất kỳ object đã định kiểu nào."""

    model_config = ConfigDict(strict=True, extra="allow", allow_inf_nan=False)


class OCRPageMetadata(RawOCRModel):
    symbol: str
    year: str
    page: int
    image: str
    width: int
    height: int
    dpi: int


class OCRTextLine(RawOCRModel):
    id: str
    type: Literal["text"]
    bbox: OCRBoundingBox
    text: str
    # Có thể thiếu; export_source loại default chưa được cung cấp, giữ null riêng.
    cell_id: str | None = None


class OCRTableCell(RawOCRModel):
    id: str
    row: int
    col: int
    bbox: OCRBoundingBox
    text: str
    line_count: int
    lines: list[OCRTextLine]


class OCRBaseElement(RawOCRModel):
    id: str
    bbox: OCRBoundingBox


class OCRText(OCRBaseElement):
    type: Literal["text"]
    text: str


class OCRTable(OCRBaseElement):
    type: Literal["table"]
    name: str
    crop: str
    cells: list[OCRTableCell]


class OCRCheckbox(OCRBaseElement):
    type: Literal["checkbox"]
    checked: bool
    choice: str
    confidence: int | float
    crop: str
    group_id: str
    label: str
    # M1-01 chỉ thấy array rỗng; chưa có bằng chứng để chốt item schema.
    label_text_ids: list[Any]


class OCRColorCrops(OCRBaseElement):
    crop: str
    black_view_crop: str
    red_view_crop: str
    blue_view_crop: str


class OCRSignature(OCRColorCrops):
    type: Literal["signature"]
    role: str
    signer_name: str
    kind: str
    confidence: int | float | None
    ink_view_crop: str


class OCRSeal(OCRColorCrops):
    type: Literal["seal"]
    seal_name: str


class OCRSealSignatureRegion(OCRColorCrops):
    type: Literal["seal_signature_region"]
    seal_bbox: OCRBoundingBox
    signature_bbox: OCRBoundingBox
    signature_id: str
    source: str


class OCRRedMark(OCRBaseElement):
    type: Literal["red_mark"]
    crop: str


OCRElement = Annotated[
    OCRText | OCRTable | OCRCheckbox | OCRSignature | OCRSeal | OCRSealSignatureRegion | OCRRedMark,
    Field(discriminator="type"),
]


class OCRDetectionView(RawOCRModel):
    width: int
    height: int
    scale_x_to_original: int | float
    scale_y_to_original: int | float


class OCRCheckboxDetection(RawOCRModel):
    native_proposals: int
    magnified_proposals: int
    accepted: int
    threshold: int | float
    proposal_threshold: int | float
    seconds: int | float


class OCRProvenance(RawOCRModel):
    architecture: str
    detection_view: OCRDetectionView
    layout_engine: str
    text_detector: str
    text_recognizer: str
    checkbox_detector: str
    checkbox_detector_source: str
    checkbox_detection: OCRCheckboxDetection
    signature_detector: str
    signature_full_page_threshold: int | float
    signature_context_roi_threshold: int | float
    # Chỉ null đã quan sát; giá trị khác cần review contract, không đoán schema.
    signature_fallback_detector: None
    signature_full_page_proposal_count: int
    signature_final_count: int
    signature_policy: str
    checkbox_policy: str
    seal_policy: str
    notes: list[str]
    page_seconds: int | float


class OCRPage(RawOCRModel):
    page: OCRPageMetadata
    elements: list[OCRElement]
    provenance: OCRProvenance

    def export_source(self) -> dict[str, Any]:
        """Xuất giá trị JSON nguồn, không thêm defaults hoặc contract version."""
        return self.model_dump(mode="json", exclude_unset=True)


def raw_ocr_json_schema() -> dict[str, Any]:
    """Một schema duy nhất, version ở metadata schema thay vì payload OCR."""
    schema = OCRPage.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = RAW_OCR_CONTRACT_VERSION
    return schema
