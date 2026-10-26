"""Path Mapping v1: models và serialization, không truy cập filesystem."""

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from .document_understanding import SourceAnchor
from .validation import StructuralIssue

PATH_MAPPING_CONTRACT_VERSION = "path_mapping_v1"
PathCategory = Literal["raw_page_image", "ocr_page_json", "ocr_crop"]
PathStyle = Literal["posix", "windows"]
PathMappingStatus = Literal["not_checked", "resolved", "missing", "ambiguous", "unsafe", "unmapped"]


class PathMappingModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)

    def export_result(self) -> dict[str, Any]:
        """Giữ nguyên Unicode, source strings và missing khác explicit null."""
        return self.model_dump(mode="json", exclude_unset=True)


class PathReference(PathMappingModel):
    original_path: str
    category: PathCategory
    # Artifact/run locator do caller cung cấp; location là key/index trong artifact đó.
    source_ref: str
    source_location: list[str | int]
    anchor: SourceAnchor | None = None
    crop_view: Literal["original", "ink", "black", "red", "blue"] | None = None
    candidate_page_image: str | None = None


class PathRootMapping(PathMappingModel):
    mapping_id: str
    # Root đầy đủ được caller phê duyệt, không tìm marker ở giữa path.
    source_root: str
    path_style: PathStyle
    destination_root_key: str
    category: PathCategory
    containment_policy: Literal["lexical_then_runtime"]


class PathMappingRequest(PathMappingModel):
    contract_version: Literal["path_mapping_v1"]
    reference: PathReference
    mappings: list[PathRootMapping]


class PathMappingIssue(PathMappingModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    code: str
    path: list[str | int]
    message: str


class PathTarget(PathMappingModel):
    """Đích logic; runtime bind root key vào cấu hình local đã phê duyệt."""

    mapping_id: str
    root_key: str
    relative_suffix: str


class PathMappingResult(PathMappingModel):
    contract_version: Literal["path_mapping_v1"]
    reference: PathReference
    status: PathMappingStatus
    candidate_targets: list[PathTarget]
    confirmed_target: PathTarget | None = None
    # Đây là khai báo từ runtime; model không tự thực hiện/xác thực I/O.
    existence_check: Literal["not_checked", "exists", "missing"]
    containment_check: Literal["not_checked", "verified", "rejected"]
    issues: list[PathMappingIssue]


class PathMappingStructuralError(ValueError):
    def __init__(self, payload: Any, issues: list[StructuralIssue]):
        self.payload = deepcopy(payload)
        self.issues = issues
        super().__init__(f"Path mapping structural validation failed: {len(issues)} issue(s)")


def parse_path_mapping_request(payload: Any) -> PathMappingRequest:
    """Structural validation độc lập với lexical/quality validation."""
    try:
        return PathMappingRequest.model_validate(payload)
    except ValidationError as error:
        issues = [
            StructuralIssue(code=item["type"], path=item["loc"], message=item["msg"])
            for item in error.errors(include_input=False, include_url=False)
        ]
        raise PathMappingStructuralError(payload, issues) from None


def parse_path_mapping_result(payload: Any) -> PathMappingResult:
    """Parse cấu trúc output; caller chạy quality validator riêng trước sử dụng."""
    try:
        return PathMappingResult.model_validate(payload)
    except ValidationError as error:
        issues = [
            StructuralIssue(code=item["type"], path=item["loc"], message=item["msg"])
            for item in error.errors(include_input=False, include_url=False)
        ]
        raise PathMappingStructuralError(payload, issues) from None


def path_mapping_json_schema() -> dict[str, Any]:
    """Một artifact cho cả input và output; definitions chứa các model con."""
    schema = TypeAdapter(PathMappingRequest | PathMappingResult).json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = PATH_MAPPING_CONTRACT_VERSION
    return schema
