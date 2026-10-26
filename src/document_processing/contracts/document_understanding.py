"""Document Understanding v1: output riêng, không thay đổi Raw OCR."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .raw_ocr import OCRBoundingBox

DOCUMENT_UNDERSTANDING_CONTRACT_VERSION = "document_understanding_v1"
ResolutionStatus = Literal["resolved", "uncertain", "unresolved"]


class UnderstandingModel(BaseModel):
    """Output có schema do ứng dụng sở hữu; từ chối extras để lộ schema drift."""

    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)

    def export_result(self) -> dict[str, Any]:
        """Giữ missing khác explicit null; không tự thêm optional defaults."""
        return self.model_dump(mode="json", exclude_unset=True)


class RawPageIdentity(UnderstandingModel):
    symbol: str
    year: str
    page: int
    image: str
    # Caller cung cấp locator/run identity nếu có, không tự tạo hoặc resolve.
    source_ref: str | None = None


class UnderstandingIssue(UnderstandingModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    code: str
    path: list[str | int]
    message: str


class SourceAnchor(UnderstandingModel):
    page: RawPageIdentity
    element_id: str | None = None
    table_id: str | None = None
    cell_id: str | None = None
    line_id: str | None = None
    # Pixel [x1,y1,x2,y2] trên ảnh gốc; không chuyển hệ tọa độ.
    observed_bbox: OCRBoundingBox | None = None
    proposed_bbox: OCRBoundingBox | None = None
    status: ResolutionStatus


class DocumentClassification(UnderstandingModel):
    # None = chưa biết, không phải một report type thuộc taxonomy.
    label: str | None
    status: ResolutionStatus
    anchors: list[SourceAnchor]
    confidence: int | float | None = None


class UnderstoodTextRegion(UnderstandingModel):
    id: str
    text: str
    anchors: list[SourceAnchor]
    status: ResolutionStatus
    reading_order: int | None = None
    issues: list[UnderstandingIssue] | None = None


class UnderstoodCell(UnderstandingModel):
    id: str
    row: int
    col: int
    text: str
    anchors: list[SourceAnchor]
    status: ResolutionStatus
    rowspan: int | None = None
    colspan: int | None = None
    issues: list[UnderstandingIssue] | None = None


class UnderstoodTable(UnderstandingModel):
    id: str
    origin: Literal["ocr_table", "inferred_from_text"]
    anchors: list[SourceAnchor]
    cells: list[UnderstoodCell]
    status: ResolutionStatus
    issues: list[UnderstandingIssue] | None = None


class DocumentUnderstandingResult(UnderstandingModel):
    contract_version: Literal["document_understanding_v1"]
    raw_page: RawPageIdentity
    classification: DocumentClassification
    text_regions: list[UnderstoodTextRegion]
    tables: list[UnderstoodTable]
    issues: list[UnderstandingIssue]


def document_understanding_json_schema() -> dict[str, Any]:
    schema = DocumentUnderstandingResult.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = DOCUMENT_UNDERSTANDING_CONTRACT_VERSION
    return schema
