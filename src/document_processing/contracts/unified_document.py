"""Export trung gian M1-16; không thay raw OCR/DU v1 hoặc định nghĩa kế toán."""

from typing import Any, Literal

from pydantic import Field

from .document_understanding import RawPageIdentity, UnderstandingModel

ComponentStatus = Literal["accepted", "unresolved", "unavailable"]


class ComponentQuality(UnderstandingModel):
    text_accepted: bool = False
    layout_accepted: bool = False
    geometry_verified: bool = False
    # Chỉ cho text_evidence; không cam kết normalization hoặc financial accuracy.
    downstream_usable: bool = False
    usable_for: list[Literal["text_evidence"]] = Field(default_factory=list)


class UnifiedRegion(UnderstandingModel):
    # Selector trong nguồn JSON, TUYỆT ĐỐI không phải raw OCR ID.
    source_pointer: str
    raw_element_id: str | None = None
    raw_table_id: str | None = None
    raw_cell_id: str | None = None
    provenance_level: Literal["page", "element", "cell"] = "page"
    text: str | None
    status: ComponentStatus
    quality: ComponentQuality
    bbox: list[int] | None = None
    geometry_status: ComponentStatus = "unavailable"
    layout_status: ComponentStatus = "unavailable"
    row: int | None = None
    column: int | None = None
    # Giữ nguyên candidate text/layout/geometry/lines kể cả khi chưa dùng được.
    source_component: dict[str, Any]
    issues: list[str] = Field(default_factory=list)


class UnifiedTable(UnderstandingModel):
    source_pointer: str
    raw_table_id: str | None = None
    status: ComponentStatus
    layout_accepted: bool
    cells: list[UnifiedRegion]
    source_component: dict[str, Any]
    issues: list[str] = Field(default_factory=list)


class RecoveryDecision(UnderstandingModel):
    action: Literal[
        "table_reconstruction", "ocr_correction", "vision_crop_recovery", "human_review"
    ]
    reason: str
    source_pointer: str
    # MVP chỉ đề xuất; không tự gọi API/reconstruction/correction.
    executed: Literal[False] = False


class UnifiedPage(UnderstandingModel):
    identity: RawPageIdentity
    source_type: Literal["existing_ocr", "pdf", "png"]
    source_sha256: str
    source_references: dict[str, Any]
    schema_valid: bool
    acceptance_scope: Literal["component_structure_not_financial_accuracy"] = (
        "component_structure_not_financial_accuracy"
    )
    text_regions: list[UnifiedRegion]
    tables: list[UnifiedTable]
    classification: dict[str, Any]
    issues: list[dict[str, Any]]
    processing_history: list[str]
    recovery_decisions: list[RecoveryDecision] = Field(default_factory=list)


class UnifiedDocument(UnderstandingModel):
    contract_version: Literal["unified_document_v1"] = "unified_document_v1"
    pages: list[UnifiedPage]

    def export_result(self) -> dict[str, Any]:
        # Defaults thuộc export contract, không phụ thuộc nhánh đầu vào.
        return self.model_dump(mode="json")
