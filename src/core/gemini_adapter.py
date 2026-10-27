"""Gemini Developer API transport; không retry/key rotation hoặc tin schema attestations."""

import math
import os
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from .llm_contracts import (
    Cost,
    ErrorCategory,
    GatewayError,
    JSONOutput,
    LLMRequest,
    LLMResponse,
    ResponseProvenance,
    TextOutput,
    Usage,
    parse_json_output,
    parse_llm_request,
)
from .llm_schema_validation import LocalSchemaRegistry

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_PROVIDER = "gemini"


def _error(category: ErrorCategory, *, origin="adapter", http_code=None) -> GatewayError:
    allowed = {400, 401, 403, 408, 429, 500, 502, 503, 504}
    return GatewayError(
        category=category,
        code=category,
        retryability="unknown",
        origin=origin,
        provider_error_code=(f"http_{http_code}" if http_code in allowed else "other")
        if http_code is not None
        else None,
    )


def _base(request: LLMRequest) -> dict[str, Any]:
    return dict(
        contract_version="llm_gateway_v1",
        request_id=request.request_id,
        correlation=request.correlation,
        provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
        usage=Usage(status="unknown", source="unknown"),
        cost=Cost(status="unknown", source="unknown"),
    )


class GeminiAdapter:
    def __init__(self, client: Any, *, schema_registry: LocalSchemaRegistry | None = None) -> None:
        self._client = client
        self._schema_registry = schema_registry

    @classmethod
    def from_environment(
        cls, *, schema_registry: LocalSchemaRegistry | None = None
    ) -> "GeminiAdapter":
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is required")
        try:
            client = genai.Client(
                api_key=key,
                vertexai=False,
                http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
            )
        except Exception:
            raise ValueError("Gemini client configuration failed") from None
        return cls(client, schema_registry=schema_registry)

    def close(self) -> None:
        self._client.close()

    def _config(
        self, request: LLMRequest
    ) -> tuple[list[types.Content], types.GenerateContentConfig]:
        if request.model.provider != GEMINI_PROVIDER:
            raise ValueError("Unsupported provider")
        generation = request.generation.export()
        if any(value is None for value in generation.values()):
            raise ValueError("Explicit null generation parameter unsupported")
        if generation.get("temperature", 0) > 2:
            raise ValueError("Unsupported temperature")
        # v1 không biểu diễn developer precedence trên Gemini; reject thay vì merge im lặng.
        if any(message.role == "developer" for message in request.messages):
            raise ValueError("Developer role unsupported")
        instructions, contents = [], []
        for message in request.messages:
            if message.role == "system":
                if contents:
                    raise ValueError("System instructions must precede conversation")
                instructions.append(types.Part(text=message.content))
            else:
                contents.append(
                    types.Content(
                        role="model" if message.role == "assistant" else "user",
                        parts=[types.Part(text=message.content)],
                    )
                )
        if not contents:
            raise ValueError("Conversation required")
        config = dict(generation)
        if instructions:
            config["system_instruction"] = types.Content(parts=instructions)
        constraints = request.constraints
        timeout = None
        if constraints is not None and "timeout_seconds" in constraints.model_fields_set:
            if constraints.timeout_seconds is None:
                raise ValueError("Explicit null timeout unsupported")
            timeout = max(1, math.ceil(constraints.timeout_seconds * 1000))
        config["http_options"] = types.HttpOptions(
            timeout=timeout, retry_options=types.HttpRetryOptions(attempts=1)
        )
        spec = request.output_spec
        if spec is not None and spec.format == "json":
            config["response_mime_type"] = "application/json"
            if spec.schema_ref is not None:
                if self._schema_registry is None:
                    raise LookupError("Schema registry required")
                try:
                    config["response_json_schema"] = self._schema_registry.schema_for(
                        spec.schema_ref
                    )
                except ValueError:
                    raise LookupError("Schema not registered") from None
        return contents, types.GenerateContentConfig(**config)

    def __call__(self, request: LLMRequest) -> LLMResponse:
        request = parse_llm_request(request)
        base = _base(request)
        try:
            contents, config = self._config(request)
        except LookupError:
            return LLMResponse(
                **base, status="error", finish_reason="error", error=_error("invalid_configuration")
            )
        except (ValueError, TypeError):
            return LLMResponse(
                **base, status="error", finish_reason="error", error=_error("invalid_request")
            )
        try:
            raw = self._client.models.generate_content(
                model=request.model.model, contents=contents, config=config
            )
        except (httpx.TimeoutException, TimeoutError):
            failure = _error("timeout")
        except errors.APIError as exc:
            code = exc.code
            category: ErrorCategory = {
                400: "invalid_request",
                401: "authentication",
                403: "authorization",
                408: "timeout",
                429: "rate_limit",
                500: "provider_unavailable",
                502: "provider_unavailable",
                503: "provider_unavailable",
                504: "timeout",
            }.get(code, "provider_unavailable")
            # HTTP 429 không đủ để phân biệt quota; chỉ dùng structured reason allowlist.
            body = exc.details.get("error", {}) if isinstance(exc.details, dict) else {}
            details = body.get("details", []) if isinstance(body, dict) else []
            details = details if isinstance(details, list) else []
            if code == 429 and any(
                isinstance(detail, dict)
                and detail.get("reason") in {"QUOTA_EXCEEDED", "DAILY_LIMIT_EXCEEDED"}
                for detail in details
            ):
                category = "quota_exceeded"
            failure = _error(category, origin="provider", http_code=code)
        except Exception:
            failure = _error("provider_unavailable")
        else:
            try:
                return self._map_response(request, raw, base)
            except Exception:
                failure = _error("internal")
        return LLMResponse(**base, status="error", finish_reason="error", error=failure)

    @staticmethod
    def _map_response(
        request: LLMRequest, raw: types.GenerateContentResponse, base: dict
    ) -> LLMResponse:
        if not isinstance(raw, types.GenerateContentResponse):
            raise ValueError("Invalid SDK response")
        usage = raw.usage_metadata
        if usage is not None:
            fields = {
                "input_tokens": usage.prompt_token_count,
                "output_tokens": usage.candidates_token_count,
                "total_tokens": usage.total_token_count,
                "cached_tokens": usage.cached_content_token_count,
                "reasoning_tokens": usage.thoughts_token_count,
            }
            counters = {key: value for key, value in fields.items() if value is not None}
            if counters:
                base["usage"] = Usage(status="available", source="provider_reported", **counters)
        if raw.model_version is not None:
            base["provenance"] = ResponseProvenance(
                requested_model=request.model,
                metadata_source="provider_reported",
                provider_reported_model=raw.model_version,
            )
        candidates = raw.candidates or []
        if raw.prompt_feedback is not None and raw.prompt_feedback.block_reason not in (
            None,
            types.BlockedReason.BLOCKED_REASON_UNSPECIFIED,
        ):
            return LLMResponse(
                **base,
                status="refused",
                finish_reason="safety",
                error=_error("safety", origin="provider"),
            )
        if len(candidates) != 1:
            raise ValueError("Expected one candidate")
        candidate = candidates[0]
        finish = candidate.finish_reason
        if finish in {
            types.FinishReason.SAFETY,
            types.FinishReason.BLOCKLIST,
            types.FinishReason.PROHIBITED_CONTENT,
            types.FinishReason.SPII,
            types.FinishReason.RECITATION,
        }:
            return LLMResponse(
                **base,
                status="refused",
                finish_reason="safety",
                error=_error("safety", origin="provider"),
            )
        if finish not in (types.FinishReason.STOP, types.FinishReason.MAX_TOKENS):
            raise ValueError("Unsupported finish reason")
        parts = candidate.content.parts if candidate.content is not None else []
        if not parts or any(part.text is None for part in parts):
            raise ValueError("Expected text parts")
        text = "".join(part.text for part in parts if not part.thought)
        if not text:
            raise ValueError("No generated text")
        spec = request.output_spec
        output = (
            parse_json_output(text, schema_ref=spec.schema_ref)
            if spec is not None and spec.format == "json"
            else TextOutput(format="text", text=text)
        )
        partial = finish == types.FinishReason.MAX_TOKENS
        malformed = isinstance(output, JSONOutput) and output.validation_status == "invalid_json"
        return LLMResponse(
            **base,
            output=output,
            status="partial" if partial else "malformed" if malformed else "success",
            finish_reason="length" if partial else "stop",
            error=_error("structured_output_invalid") if malformed else None,
        )
