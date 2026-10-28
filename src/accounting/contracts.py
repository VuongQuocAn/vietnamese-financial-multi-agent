"""Financial Normalization v1; chỉ biểu diễn dữ liệu, không suy luận kế toán."""

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, WithJsonSchema, field_validator
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    ResolutionStatus,
    SourceAnchor,
)

FINANCIAL_NORMALIZATION_CONTRACT_VERSION = "financial_normalization_v1"
# Wire format chỉ nhận chuỗi Decimal; không dùng JSON number qua float.
ExactDecimal = Annotated[
    Decimal, WithJsonSchema({"type": "string", "description": "Finite Decimal encoded as a string"})
]


def _require_exact_decimal(value: Any, info: ValidationInfo) -> Any:
    if info.mode == "json" and value is not None:
        if not isinstance(value, str):
            raise ValueError(f"JSON {info.field_name} must be a Decimal string or null")
        try:
            return Decimal(value)
        except InvalidOperation as error:
            raise ValueError("Invalid Decimal string") from error
    return value


class FinancialModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class FinancialValue(FinancialModel):
    raw_value: str
    normalized_value: ExactDecimal | None = None
    unit: str | None = None
    status: ResolutionStatus
    issues: list[str] = Field(default_factory=list)

    _exact_value = field_validator("normalized_value", mode="before")(_require_exact_decimal)


class FinancialContext(FinancialModel):
    # Vocabulary/chuẩn hóa kỳ, đơn vị và scale thuộc M2-02; v1 giữ metadata caller.
    period: str | None = None
    period_type: str | None = None
    currency: str | None = None
    scale: ExactDecimal | None = None
    reporting_scope: Literal["separate", "consolidated"] | None = None
    statement_type: Literal["B01", "B02", "B03", "B09"] | None = None
    raw_item_label: str | None = None
    mapped_item_code: str | None = None

    # Cùng quy tắc wire Decimal với normalized_value, không thêm parser số.
    _exact_scale = field_validator("scale", mode="before")(_require_exact_decimal)


class FinancialSourceReference(FinancialModel):
    anchor: SourceAnchor
    # JSON selector trong unified_document_v1, không phải raw ID hay evidence xác minh.
    source_pointer: str | None = None
    provenance_level: Literal["page", "element", "cell"] = "page"


class FinancialNormalizationResult(FinancialModel):
    contract_version: Literal["financial_normalization_v1"]
    value: FinancialValue
    context: FinancialContext
    provenance: list[FinancialSourceReference]
    # Resolved chỉ là trạng thái biểu diễn; M2-01 không xác minh financial fact.
    financial_fact_verified: Literal[False] = False

    def export_result(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def financial_normalization_json_schema() -> dict[str, Any]:
    schema = FinancialNormalizationResult.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = FINANCIAL_NORMALIZATION_CONTRACT_VERSION
    return schema
