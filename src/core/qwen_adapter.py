"""Transport OpenAI-compatible cho Qwen text; không retry/fallback/Vision."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .llm_contracts import (
    Cost,
    GatewayError,
    JSONOutput,
    LLMResponse,
    ResponseProvenance,
    TextOutput,
    Usage,
    parse_json_output,
    parse_llm_request,
)


@dataclass(frozen=True)
class QwenSettings:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    model: str

    @classmethod
    def from_environment(cls, project_root, *, config_file=None):
        try:
            path = Path(config_file or os.environ.get("QWEN_API_INFO_FILE", "api_info.json"))
            if not path.is_absolute():
                path = Path(project_root) / path
            data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
            values = [
                os.environ.get(env, data.get(key, "")).strip()
                for env, key in (
                    ("QWEN_BASE_URL", "BASE_URL"),
                    ("QWEN_API_KEY", "API_KEY"),
                    ("QWEN_MODEL_NAME", "MODEL_NAME"),
                )
            ]
            settings = cls(*values)
            parsed = urlsplit(settings.base_url)
            local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
            if (
                not all(values)
                or not parsed.netloc
                or (parsed.scheme != "https" and not local)
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path.rstrip("/") != "/v1"
            ):
                raise ValueError
            return settings
        except (OSError, ValueError, AttributeError, TypeError):
            raise ValueError("qwen_configuration_invalid") from None


def _error(category, *, origin="adapter", http_code=None):
    allowed = {400, 401, 403, 408, 429, 500, 502, 503, 504}
    return GatewayError(
        category=category,
        code=category,
        origin=origin,
        retryability="not_retryable",
        provider_error_code=(f"http_{http_code}" if http_code in allowed else "other")
        if http_code is not None
        else None,
    )


class QwenAdapter:
    def __init__(self, settings, *, schema_registry=None, client=None):
        self.settings, self.schema_registry = settings, schema_registry
        self.client = client or httpx.Client(follow_redirects=False)

    def close(self):
        self.client.close()

    def _payload(self, request):
        if request.model.provider != "qwen" or request.model.model != self.settings.model:
            raise LookupError
        if any(message.images for message in request.messages):
            raise ValueError  # Gemini Vision/OCR có composition riêng, không route sang Qwen.
        generation = request.generation.export()
        if any(value is None for value in generation.values()):
            raise ValueError
        rename = {"max_output_tokens": "max_tokens", "stop_sequences": "stop"}
        payload = {rename.get(k, k): v for k, v in generation.items()}
        payload.update(
            model=request.model.model,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            stream=False,
            chat_template_kwargs={"enable_thinking": False},
        )
        spec = request.output_spec
        if spec is not None and spec.format == "json":
            payload["response_format"] = {"type": "json_object"}
            if spec.schema_ref is not None:
                if self.schema_registry is None:
                    raise LookupError
                try:
                    schema = self.schema_registry.schema_for(spec.schema_ref)
                except ValueError:
                    raise LookupError from None
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "gateway_output",
                        "schema": schema,
                    },
                }
                if "strict" in spec.model_fields_set:
                    if spec.strict is None:
                        raise ValueError
                    payload["response_format"]["json_schema"]["strict"] = spec.strict
        timeout = 60.0
        if request.constraints is not None:
            if "timeout_seconds" in request.constraints.model_fields_set:
                if request.constraints.timeout_seconds is None:
                    raise ValueError
                timeout = request.constraints.timeout_seconds
        return payload, timeout

    def __call__(self, request):
        request = parse_llm_request(request)
        base = dict(
            contract_version="llm_gateway_v1",
            request_id=request.request_id,
            correlation=request.correlation,
            provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
            usage=Usage(status="unknown", source="unknown"),
            cost=Cost(status="unknown", source="unknown"),
        )
        try:
            payload, timeout = self._payload(request)
        except LookupError:
            failure = _error("invalid_configuration")
        except (ValueError, TypeError):
            failure = _error("invalid_request")
        else:
            try:
                raw = self.client.post(
                    self.settings.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.settings.api_key},
                    json=payload,
                    timeout=timeout,
                )
                if raw.status_code != 200:
                    code = raw.status_code
                    category = {
                        400: "invalid_request",
                        401: "authentication",
                        403: "authorization",
                        408: "timeout",
                        429: "rate_limit",
                        504: "timeout",
                    }.get(code, "provider_unavailable")
                    failure = _error(category, origin="provider", http_code=code)
                else:
                    return self._map_response(request, raw.json(), base)
            except httpx.TimeoutException:
                failure = _error("timeout")
            except httpx.HTTPError:
                failure = _error("provider_unavailable")
            except Exception:
                failure = _error("internal")
        return LLMResponse(**base, status="error", finish_reason="error", error=failure)

    @staticmethod
    def _map_response(request, raw, base):
        usage = raw.get("usage") or {}
        counters = {
            target: usage[source]
            for source, target in (
                ("prompt_tokens", "input_tokens"),
                ("completion_tokens", "output_tokens"),
                ("total_tokens", "total_tokens"),
            )
            if usage.get(source) is not None
        }
        if counters:
            base["usage"] = Usage(status="available", source="provider_reported", **counters)
        if raw.get("model"):
            base["provenance"] = ResponseProvenance(
                requested_model=request.model,
                metadata_source="provider_reported",
                provider_reported_model=raw["model"],
            )
        choices = raw["choices"]
        if len(choices) != 1:
            raise ValueError
        choice = choices[0]
        if choice["finish_reason"] == "content_filter" or choice["message"].get("refusal"):
            return LLMResponse(
                **base,
                status="refused",
                finish_reason="safety",
                error=_error("safety", origin="provider"),
            )
        text = choice["message"]["content"]
        if (
            choice["finish_reason"] not in {"stop", "length"}
            or not isinstance(text, str)
            or not text.strip()
            or "<think>" in text
            or choice["message"].get("reasoning_content")
        ):
            raise ValueError
        spec = request.output_spec
        output = (
            parse_json_output(text, schema_ref=spec.schema_ref, allow_markdown_fence=True)
            if spec is not None and spec.format == "json"
            else TextOutput(format="text", text=text)
        )
        partial = choice["finish_reason"] == "length"
        malformed = isinstance(output, JSONOutput) and output.validation_status == "invalid_json"
        return LLMResponse(
            **base,
            output=output,
            status="partial" if partial else "malformed" if malformed else "success",
            finish_reason="length" if partial else "stop",
            error=_error("structured_output_invalid") if malformed else None,
        )
