"""Synthetic fake chỉ dành cho tests/examples; không SDK hoặc network."""

from collections.abc import Callable

from .llm_contracts import (
    Cost,
    GatewayError,
    LLMRequest,
    LLMResponse,
    ResponseProvenance,
    TextOutput,
    Usage,
    parse_json_output,
)


class FakeLLMTransport:
    """Handler tùy chọn mô phỏng failures/mismatch; mặc định trả synthetic output."""

    def __init__(
        self,
        handler: Callable[[LLMRequest], LLMResponse] | None = None,
        *,
        text: str = "Synthetic example",
        json_text: str = '{"synthetic":true}',
    ) -> None:
        self._handler = handler
        self._text = text
        self._json_text = json_text

    def __call__(self, request: LLMRequest) -> LLMResponse:
        if self._handler is not None:
            return self._handler(request)
        spec = request.output_spec
        output = (
            parse_json_output(self._json_text, schema_ref=spec.schema_ref)
            if spec is not None and spec.format == "json"
            else TextOutput(format="text", text=self._text)
        )
        malformed = getattr(output, "validation_status", None) == "invalid_json"
        return LLMResponse(
            contract_version="llm_gateway_v1",
            request_id=request.request_id,
            provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
            correlation=request.correlation,
            status="malformed" if malformed else "success",
            finish_reason="stop",
            output=output,
            error=(
                GatewayError(
                    category="structured_output_invalid",
                    code="structured_output_invalid",
                    origin="adapter",
                    retryability="not_retryable",
                )
                if malformed
                else None
            ),
            usage=Usage(status="unknown", source="unknown"),
            cost=Cost(status="unknown", source="unknown"),
        )
