"""Transport OpenAI-compatible cho Qwen text; không retry/fallback/Vision."""

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .llm_contracts import (
    Cost,
    GatewayError,
    JSONOutput,
    LLMResponse,
    ResponseProvenance,
    SchemaIssue,
    TextOutput,
    Usage,
    parse_json_output,
    parse_llm_request,
)
from .llm_schema_validation import schema_issues


@lru_cache(maxsize=1)
def _tokenizer_assets(directory):
    """Load only the two local assets verified against the five server errors."""
    from jinja2 import Environment
    from tokenizers import Tokenizer

    assets = {}
    for name, digest in (
        ("tokenizer.json", "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"),
        (
            "tokenizer_config.json",
            "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101",
        ),
    ):
        data = (Path(directory) / name).read_bytes()
        if sha256(data).hexdigest() != digest:
            raise ValueError("qwen_tokenizer_unverified")
        assets[name] = data.decode("utf-8")
    tokenizer = Tokenizer.from_str(assets["tokenizer.json"])
    template = Environment().from_string(
        json.loads(assets["tokenizer_config.json"])["chat_template"]
    )
    return tokenizer, template


def qwen_input_tokens(messages):
    tokenizer, template = _tokenizer_assets(
        os.environ.get("QWEN_TOKENIZER_DIR", "models/qwen3-tokenizer")
    )
    # This suffix matches Step 1/server. It also conservatively includes the
    # empty-think framing when the operator enables Thinking on the same template.
    rendered = template.render(messages=messages, add_generation_prompt=True, enable_thinking=False)
    return len(tokenizer.encode(rendered, add_special_tokens=False).ids)


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


class ContextBudgetExceeded(ValueError):
    pass


class SchemaCompatibilityError(ValueError):
    def __init__(self, path, code):
        self.diagnostic = SchemaIssue(
            code=code, path=[], schema_path=[part[:64] for part in path[-16:]]
        )


def _provider_metadata(request, raw, base):
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


class ChatCompletionsAdapter:
    def __init__(self, settings, *, schema_registry=None, client=None):
        self.settings, self.schema_registry = settings, schema_registry
        self.client = client or httpx.Client(follow_redirects=False)

    def close(self):
        self.client.close()

    def _message_payload(self, request):
        if request.model.provider != self.provider or request.model.model != self.settings.model:
            raise LookupError
        if any(message.images or message.role == "developer" for message in request.messages):
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
        )
        timeout = 60.0
        if request.constraints is not None:
            if "timeout_seconds" in request.constraints.model_fields_set:
                if request.constraints.timeout_seconds is None:
                    raise ValueError
                timeout = request.constraints.timeout_seconds
        return payload, timeout

    def _check_budget(self, payload):
        pass

    def _response(self, request, raw, base, payload):
        return self._map_response(request, raw, base)

    @staticmethod
    def _http_error(raw):
        code = raw.status_code
        category = {
            400: "invalid_request",
            401: "authentication",
            403: "authorization",
            408: "timeout",
            429: "rate_limit",
            504: "timeout",
        }.get(code, "provider_unavailable")
        return _error(category, origin="provider", http_code=code)

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
            self._check_budget(payload)
        except ContextBudgetExceeded:
            failure = _error("context_budget_exceeded")
        except SchemaCompatibilityError as issue:
            failure = _error("schema_mismatch").model_copy(
                update=dict(validation_issues=[issue.diagnostic])
            )
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
                    failure = self._http_error(raw)
                else:
                    return self._response(request, raw.json(), base, payload)
            except httpx.TimeoutException:
                failure = _error("timeout")
            except httpx.HTTPError:
                failure = _error("provider_unavailable")
            except Exception:
                failure = _error("internal")
        return LLMResponse(**base, status="error", finish_reason="error", error=failure)


class QwenAdapter(ChatCompletionsAdapter):
    provider = "qwen"

    def _payload(self, request):
        payload, timeout = self._message_payload(request)
        spec = request.output_spec
        if spec is not None and spec.format == "json":
            schema = spec.json_schema
            if spec.schema_ref is not None:
                if self.schema_registry is None:
                    raise LookupError
                try:
                    schema = self.schema_registry.schema_for(spec.schema_ref)
                except ValueError:
                    raise LookupError from None
                if "strict" in spec.model_fields_set:
                    if spec.strict is None:
                        raise ValueError
            if schema is not None:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "agent_output", "strict": True, "schema": schema},
                }
            payload["messages"].insert(
                0,
                {
                    "role": "system",
                    "content": json.dumps(
                        {
                            "instruction": "Chỉ trả một giá trị JSON theo cấu trúc được yêu cầu, không Markdown hoặc giải thích bên ngoài. Tuân thủ output_schema nếu được cấp; không thêm trường ngoài schema.",
                            "output_schema": schema,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            )
        return payload, timeout

    def _check_budget(self, payload):
        try:
            input_tokens = qwen_input_tokens(payload["messages"])
            context_tokens = int(os.environ.get("QWEN_CONTEXT_TOKENS", "16384"))
            if context_tokens < 3384:
                raise ValueError("qwen_context_invalid")
        except (ImportError, OSError, ValueError):
            raise LookupError from None
        if input_tokens > context_tokens - 2500 - 884:
            raise ContextBudgetExceeded
        payload["max_tokens"] = min(payload.get("max_tokens", 2500), 2500)

    @staticmethod
    def _map_response(request, raw, base):
        _provider_metadata(request, raw, base)
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
        text = choice["message"].get("content")
        # vLLM may separate reasoning_content, or return the template's think
        # block inline (the opening tag may already be in the prompt). Only the
        # final channel is eligible for JSON validation or downstream claims.
        if isinstance(text, str):
            text = text.strip()
            if "</think>" in text:
                text = text.split("</think>", 1)[1].strip()
            if "<think>" in text:
                text = ""
        if (
            choice["finish_reason"] not in {"stop", "length"}
            or not isinstance(text, str)
            or not text.strip()
        ):
            if choice["finish_reason"] == "length":
                spec = request.output_spec
                return LLMResponse(
                    **base,
                    status="partial",
                    finish_reason="length",
                    output=(
                        parse_json_output("", schema_ref=spec.schema_ref)
                        if spec is not None and spec.format == "json"
                        else TextOutput(format="text", text="")
                    ),
                    error=_error("structured_output_invalid"),
                )
            return LLMResponse(
                **base,
                status="error",
                finish_reason="error",
                error=_error("structured_output_invalid"),
            )
        spec = request.output_spec
        output = (
            parse_json_output(text, schema_ref=spec.schema_ref, allow_markdown_fence=True)
            if spec is not None and spec.format == "json"
            else TextOutput(format="text", text=text)
        )
        partial = choice["finish_reason"] == "length"
        malformed = isinstance(output, JSONOutput) and output.validation_status == "invalid_json"
        issues = (
            schema_issues(spec.json_schema, output.payload)
            if isinstance(output, JSONOutput)
            and not malformed
            and spec is not None
            and spec.json_schema is not None
            else []
        )
        if issues:
            return LLMResponse(
                **base,
                status="error",
                finish_reason="error",
                error=_error("schema_mismatch").model_copy(update=dict(validation_issues=issues)),
            )
        if malformed:
            # Preserve failure semantics without retaining untrusted completion text.
            output = parse_json_output("", schema_ref=spec.schema_ref)
        return LLMResponse(
            **base,
            output=output,
            status="partial" if partial else "malformed" if malformed else "success",
            finish_reason="length" if partial else "stop",
            error=_error("structured_output_invalid").model_copy(
                update=dict(validation_issues=[SchemaIssue(code="invalid_json", path=[])])
            )
            if malformed
            else None,
        )
