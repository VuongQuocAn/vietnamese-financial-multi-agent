"""Contracts LLM thuần bộ nhớ; không SDK, I/O, credentials hoặc schema resolver."""

import base64
import binascii
import json
import math
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

LLM_CONTRACT_VERSION = "llm_gateway_v1"
Identifier = Annotated[
    str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeNumber = Annotated[float, Field(ge=0, allow_inf_nan=False)]


def _check_json(value: Any) -> None:
    """Từ chối objects/coercion, non-finite, surrogate; không normalize nội dung."""
    if isinstance(value, ContractModel):
        _check_json(value.model_dump(mode="python", exclude_unset=True, warnings=False))
    elif value is None or type(value) in (bool, int, Decimal):
        return
    elif type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Non-finite number")
    elif type(value) is str:
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("Invalid Unicode")
    elif type(value) is list:
        for item in value:
            _check_json(item)
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("Expected string key")
            _check_json(key)
            _check_json(item)
    else:
        raise ValueError("Expected JSON value")


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _decode(text: str) -> JsonValue:
    value = json.loads(text, object_pairs_hook=_pairs)
    _check_json(value)
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    @model_validator(mode="before")
    @classmethod
    def json_values(cls, value: Any) -> Any:
        _check_json(value)
        return value

    def export(self) -> dict[str, Any]:
        """Snapshot JSON; missing khác explicit null. Revalidate trước khi export."""
        snapshot = self.model_dump(mode="python", exclude_unset=True, warnings=False)
        validated = type(self).model_validate(snapshot)
        return validated.model_dump(mode="json", exclude_unset=True)

    def to_json(self) -> str:
        return json.dumps(
            self.export(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


class ModelIdentity(ContractModel):
    provider: Identifier
    model: Identifier


class Correlation(ContractModel):
    trace_id: Identifier | None = None
    parent_request_id: Identifier | None = None
    caller: Identifier | None = None


class InlineImage(ContractModel):
    """PNG bytes encoded as base64; never a path or remote URL."""

    mime_type: Literal["image/png"]
    data: str = Field(min_length=1, repr=False)

    @field_validator("data")
    @classmethod
    def valid_base64(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid image encoding") from None
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Expected PNG content")
        return value


class Message(ContractModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str = Field(min_length=1)
    images: list[InlineImage] = Field(default_factory=list, max_length=1)

    @model_validator(mode="after")
    def image_role(self) -> "Message":
        if self.images and self.role != "user":
            raise ValueError("Images require user role")
        return self

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Empty message")
        return value


class GenerationParameters(ContractModel):
    # None tường minh khác omitted; adapter sau này phải xử lý capability/null.
    temperature: NonNegativeNumber | None = None
    top_p: Annotated[float, Field(ge=0, le=1)] | None = None
    max_output_tokens: PositiveInt | None = None
    stop_sequences: list[Annotated[str, Field(min_length=1)]] | None = None
    seed: int | None = None


class RequestConstraints(ContractModel):
    timeout_seconds: Annotated[float, Field(gt=0)] | None = None


class SchemaReference(ContractModel):
    """Opaque identity, không tải URL/file hoặc khẳng định dialect được provider hỗ trợ."""

    schema_id: Identifier
    name: Identifier
    version: Identifier
    dialect: Literal["https://json-schema.org/draft/2020-12/schema"]


class OutputSpec(ContractModel):
    format: Literal["text", "json"]
    schema_ref: SchemaReference | None = None
    strict: bool | None = None

    @model_validator(mode="after")
    def consistent(self) -> "OutputSpec":
        if self.format == "text" and (self.schema_ref is not None or self.strict is not None):
            raise ValueError("Text cannot request schema enforcement")
        if self.strict is not None and self.schema_ref is None:
            raise ValueError("Strictness requires schema reference")
        return self


class LLMRequest(ContractModel):
    contract_version: Literal["llm_gateway_v1"]
    request_id: Identifier
    model: ModelIdentity
    messages: list[Message] = Field(min_length=1)
    generation: GenerationParameters
    output_spec: OutputSpec | None = None
    constraints: RequestConstraints | None = None
    correlation: Correlation | None = None


class TextOutput(ContractModel):
    format: Literal["text"]
    text: str


class SchemaValidation(ContractModel):
    """Attestation externe; không phải bằng chứng validator đã chạy trong M1-05."""

    schema_ref: SchemaReference
    validator_id: Identifier
    status: Literal["schema_valid", "schema_invalid"]


class JSONOutput(ContractModel):
    format: Literal["json"]
    raw_text: str
    payload: JsonValue
    validation_status: Literal[
        "json_valid", "invalid_json", "unverified", "schema_valid", "schema_invalid"
    ]
    schema_ref: SchemaReference | None = None
    validation: SchemaValidation | None = None

    @model_validator(mode="after")
    def consistent(self) -> "JSONOutput":
        try:
            decoded = _decode(self.raw_text)
        except (ValueError, RecursionError):
            if self.validation_status != "invalid_json" or self.payload is not None:
                raise ValueError("Invalid JSON requires invalid_json and null payload") from None
            if self.validation is not None:
                raise ValueError("Invalid JSON cannot have schema attestation") from None
            return self
        if self.validation_status == "invalid_json":
            raise ValueError("Valid JSON cannot be invalid_json")

        # JSON type identity: true != 1, arrays giữ thứ tự, object keys không quan trọng.
        def canonical(value: Any) -> str:
            return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)

        if canonical(decoded) != canonical(self.payload):
            raise ValueError("Payload differs from raw JSON")
        if self.validation_status in ("schema_valid", "schema_invalid"):
            if self.validation is None or self.schema_ref is None:
                raise ValueError("Schema status requires explicit attestation and reference")
            if (
                self.validation.schema_ref != self.schema_ref
                or self.validation.status != self.validation_status
            ):
                raise ValueError("Schema attestation mismatch")
        elif self.validation is not None:
            raise ValueError("Unexpected schema attestation")
        elif self.validation_status != ("unverified" if self.schema_ref else "json_valid"):
            raise ValueError("Schema reference requires unverified status")
        return self


def parse_json_output(raw_text: str, *, schema_ref: SchemaReference | None = None) -> JSONOutput:
    """Chỉ parse syntax; không bao giờ tự sinh schema_valid/schema_invalid."""
    try:
        payload = _decode(raw_text)
        status = "unverified" if schema_ref else "json_valid"
    except (ValueError, RecursionError):
        payload, status = None, "invalid_json"
    return JSONOutput(
        format="json",
        raw_text=raw_text,
        payload=payload,
        validation_status=status,
        schema_ref=schema_ref,
    )


class Usage(ContractModel):
    status: Literal["unknown", "not_available", "available"]
    source: Literal["unknown", "provider_reported", "calculated", "estimated"]
    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    total_tokens: NonNegativeInt | None = None
    cached_tokens: NonNegativeInt | None = None
    reasoning_tokens: NonNegativeInt | None = None

    @model_validator(mode="after")
    def consistent(self) -> "Usage":
        counters = [
            self.input_tokens,
            self.output_tokens,
            self.total_tokens,
            self.cached_tokens,
            self.reasoning_tokens,
        ]
        known = any(value is not None for value in counters)
        if self.status == "available":
            if not known or self.source == "unknown":
                raise ValueError("Available usage requires counters and source")
        elif known or self.source != "unknown":
            raise ValueError("Unavailable usage cannot claim counters or source")
        return self


class Cost(ContractModel):
    status: Literal["unknown", "not_available", "available"]
    source: Literal["unknown", "estimated", "provider_reported", "calculated"]
    amount: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)] | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    price_source: Identifier | None = None
    pricing_version: Identifier | None = None
    pricing_timestamp: (
        Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")] | None
    ) = None

    @field_validator("pricing_timestamp")
    @classmethod
    def valid_timestamp(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                raise ValueError("Expected valid UTC pricing timestamp") from None
        return value

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_money(cls, value: Any) -> Decimal | None:
        if value is None or type(value) is Decimal:
            return value
        if type(value) is str:
            try:
                return Decimal(value)
            except ArithmeticError:
                pass
        raise ValueError("Money requires Decimal or decimal string")

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal | None) -> str | None:
        return None if value is None else str(value)

    @model_validator(mode="after")
    def consistent(self) -> "Cost":
        if self.status == "available":
            if (
                self.amount is None
                or self.currency is None
                or self.source == "unknown"
                or self.price_source is None
            ):
                raise ValueError("Available cost requires amount, currency and provenance")
            if self.source in ("estimated", "calculated") and self.pricing_version is None:
                raise ValueError("Computed cost requires pricing version")
        elif self.source != "unknown" or any(
            v is not None
            for v in (
                self.amount,
                self.currency,
                self.price_source,
                self.pricing_version,
                self.pricing_timestamp,
            )
        ):
            raise ValueError("Unavailable cost cannot claim amount or provenance")
        return self


ErrorCategory = Literal[
    "invalid_request",
    "invalid_configuration",
    "authentication",
    "authorization",
    "rate_limit",
    "quota_exceeded",
    "provider_unavailable",
    "timeout",
    "network",
    "structured_output_invalid",
    "schema_mismatch",
    "safety",
    "internal",
    "unknown_provider",
]


class GatewayError(ContractModel):
    category: ErrorCategory
    code: ErrorCategory
    retryability: Literal["unknown", "retryable", "not_retryable"]
    origin: Literal["caller", "gateway", "adapter", "provider"]
    safe_message: Literal["LLM operation failed"] = "LLM operation failed"
    provider_error_code: (
        Literal[
            "http_400",
            "http_401",
            "http_403",
            "http_408",
            "http_429",
            "http_500",
            "http_502",
            "http_503",
            "http_504",
            "other",
        ]
        | None
    ) = None
    retry_after_seconds: NonNegativeNumber | None = None

    @model_validator(mode="after")
    def consistent(self) -> "GatewayError":
        if self.category != self.code:
            raise ValueError("Error category/code mismatch")
        if self.category == "quota_exceeded" and self.retryability == "retryable":
            raise ValueError("Quota requires policy decision, not transient retry")
        return self


class ResponseProvenance(ContractModel):
    requested_model: ModelIdentity
    effective_model: ModelIdentity | None = None
    provider_reported_model: Identifier | None = None
    metadata_source: Literal["unknown", "adapter_confirmed", "provider_reported"]

    @model_validator(mode="after")
    def consistent(self) -> "ResponseProvenance":
        if self.metadata_source == "unknown" and (
            self.effective_model is not None or self.provider_reported_model is not None
        ):
            raise ValueError("Unknown metadata cannot claim effective/reported model")
        if self.effective_model is not None and self.metadata_source != "adapter_confirmed":
            raise ValueError("Effective model requires adapter confirmation")
        if self.metadata_source == "adapter_confirmed" and self.effective_model is None:
            raise ValueError("Adapter confirmation requires effective model")
        if self.metadata_source == "provider_reported" and self.provider_reported_model is None:
            raise ValueError("Provider metadata requires reported model")
        return self


class LLMResponse(ContractModel):
    contract_version: Literal["llm_gateway_v1"]
    request_id: Identifier
    status: Literal["success", "error", "partial", "refused", "malformed"]
    provenance: ResponseProvenance
    usage: Usage
    cost: Cost
    output: Annotated[TextOutput | JSONOutput, Field(discriminator="format")] | None = None
    error: GatewayError | None = None
    finish_reason: Literal["stop", "length", "safety", "error", "unknown"]
    provider_response_id: Identifier | None = None
    correlation: Correlation | None = None

    @model_validator(mode="after")
    def consistent(self) -> "LLMResponse":
        bad_json = isinstance(self.output, JSONOutput) and self.output.validation_status in (
            "invalid_json",
            "schema_invalid",
        )
        if self.status == "success":
            if self.output is None or self.error is not None or bad_json:
                raise ValueError("Success requires valid output without error")
            if self.finish_reason not in ("stop", "unknown"):
                raise ValueError("Success finish reason conflict")
        elif self.status == "partial":
            if self.output is None or self.finish_reason not in ("length", "error", "unknown"):
                raise ValueError("Partial requires output and incomplete finish reason")
        elif self.status == "error":
            if self.error is None or self.output is not None or self.finish_reason != "error":
                raise ValueError("Error requires error details without output")
        elif self.status == "refused":
            if (
                self.error is None
                or self.error.category != "safety"
                or self.finish_reason != "safety"
            ):
                raise ValueError("Refusal requires safety error and finish reason")
            if self.output is not None:
                raise ValueError("Refusal cannot claim generated output")
        elif self.status == "malformed":
            expected = (
                "schema_mismatch"
                if (
                    isinstance(self.output, JSONOutput)
                    and self.output.validation_status == "schema_invalid"
                )
                else "structured_output_invalid"
            )
            if not bad_json or self.error is None or self.error.category != expected:
                raise ValueError("Malformed requires invalid structured output and matching error")
        return self


class ContractIssue(BaseModel):
    """Chỉ schema-owned paths; không chứa input, extra key hoặc exception context."""

    code: str
    path: tuple[str | int, ...]


class LLMContractError(ValueError):
    def __init__(self, issues: list[ContractIssue]):
        self.issues = issues
        super().__init__(f"LLM contract validation failed: {len(issues)} issue(s)")


T = TypeVar("T", bound=ContractModel)


def _parse(model: type[T], payload: Any) -> T:
    try:
        # JSON entrypoint rejects duplicate keys before Pydantic sees the object.
        if type(payload) is str:
            payload = _decode(payload)
        return model.model_validate(payload)
    except ValidationError as error:
        # Dynamic extra keys/discriminator values may contain secrets. Keep only known fields.
        fields = set()
        for value in globals().values():
            if isinstance(value, type) and issubclass(value, ContractModel):
                fields.update(value.model_fields)
        issues = [
            ContractIssue(
                code=item["type"],
                path=tuple(p if type(p) is int or p in fields else "<field>" for p in item["loc"]),
            )
            for item in error.errors(include_input=False, include_context=False, include_url=False)
        ]
    except (ValueError, TypeError, RecursionError):
        issues = [ContractIssue(code="invalid_json", path=())]
    raise LLMContractError(issues) from None


def parse_llm_request(payload: Any) -> LLMRequest:
    return _parse(LLMRequest, payload)


def parse_llm_response(payload: Any) -> LLMResponse:
    return _parse(LLMResponse, payload)


def llm_gateway_json_schema() -> dict[str, Any]:
    from pydantic import TypeAdapter

    schema = TypeAdapter(LLMRequest | LLMResponse).json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "urn:vietnamese-financial-multi-agent:llm_gateway_v1"
    return schema


__all__ = [
    "LLM_CONTRACT_VERSION",
    "LLMRequest",
    "LLMResponse",
    "ModelIdentity",
    "Correlation",
    "Message",
    "InlineImage",
    "GenerationParameters",
    "RequestConstraints",
    "SchemaReference",
    "OutputSpec",
    "TextOutput",
    "JSONOutput",
    "SchemaValidation",
    "Usage",
    "Cost",
    "GatewayError",
    "ErrorCategory",
    "ResponseProvenance",
    "ContractIssue",
    "LLMContractError",
    "parse_llm_request",
    "parse_llm_response",
    "parse_json_output",
    "llm_gateway_json_schema",
]
