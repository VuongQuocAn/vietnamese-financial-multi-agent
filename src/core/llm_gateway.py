"""Gateway đồng bộ, provider-neutral; transport được inject, không retry/I/O ngầm."""

from collections.abc import Mapping
from typing import Protocol

from .llm_contracts import (
    Cost,
    ErrorCategory,
    GatewayError,
    JSONOutput,
    LLMRequest,
    LLMResponse,
    ResponseProvenance,
    Usage,
    parse_llm_request,
    parse_llm_response,
)


class LLMTransport(Protocol):
    def __call__(self, request: LLMRequest) -> LLMResponse:
        """Adapter chịu trách nhiệm timeout/capabilities; trả contract v1."""
        ...


def _failure(request: LLMRequest, category: ErrorCategory) -> LLMResponse:
    return LLMResponse(
        contract_version="llm_gateway_v1",
        request_id=request.request_id,
        status="error",
        finish_reason="error",
        provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
        correlation=request.correlation,
        usage=Usage(status="unknown", source="unknown"),
        cost=Cost(status="unknown", source="unknown"),
        error=GatewayError(
            category=category,
            code=category,
            retryability="unknown",
            origin="gateway",
        ),
    )


def _binding_error(request: LLMRequest, response: LLMResponse) -> ErrorCategory | None:
    if (
        response.request_id != request.request_id
        or response.provenance.requested_model != request.model
        or response.correlation != request.correlation
    ):
        return "internal"
    output = response.output
    if output is None:
        return None  # Lỗi/refusal không bắt buộc có output.
    spec = request.output_spec
    if spec is not None and output.format != spec.format:
        return "structured_output_invalid"
    if isinstance(output, JSONOutput):
        if output.schema_ref != (spec.schema_ref if spec is not None else None):
            return "schema_mismatch"
        # Contract chỉ kiểm tra attestation nhất quán, không chứng minh thực thi.
        # Chưa có trusted validator: không chấp nhận lời khai schema checked.
        if output.validation_status in ("schema_valid", "schema_invalid"):
            return "schema_mismatch"
    return None


class SharedLLMGateway:
    def __init__(self, transports: Mapping[str, LLMTransport]) -> None:
        self._transports = dict(transports)

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Invalid request ném safe LLMContractError; lỗi runtime trả safe response."""
        # Revalidate mutable models và giữ snapshot độc lập với caller/transport.
        bound = parse_llm_request(request).model_copy(deep=True)
        transport = self._transports.get(bound.model.provider)
        if transport is None:
            return _failure(bound, "invalid_configuration")
        try:
            candidate = transport(bound.model_copy(deep=True))
        except TimeoutError:
            return _failure(bound, "timeout")
        except Exception:
            return _failure(bound, "provider_unavailable")
        try:
            response = parse_llm_response(candidate).model_copy(deep=True)
        except Exception:
            return _failure(bound, "internal")
        category = _binding_error(bound, response)
        return _failure(bound, category) if category is not None else response
