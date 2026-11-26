"""Strict Chat Completions translation; the original Agent schema stays authoritative."""

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import unquote, urlsplit

import httpx

from .llm_contracts import LLMResponse, TextOutput, parse_json_output
from .llm_schema_validation import schema_issues
from .qwen_adapter import (
    ChatCompletionsAdapter,
    SchemaCompatibilityError,
    _error,
    _provider_metadata,
)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
# OpenAI standard USD rates per million input, cached input and output tokens.
OPENAI_PRICING = {
    DEFAULT_OPENAI_MODEL: (Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
}

_OMIT_KEY = "__dacntt_omitted"
_OMIT = {_OMIT_KEY: True}
_OMIT_SCHEMA = {
    "type": "object",
    "properties": {_OMIT_KEY: {"type": "boolean", "enum": [True]}},
    "required": [_OMIT_KEY],
    "additionalProperties": False,
}
# These schema keywords are either annotations or enforced by the original local schema.
_LOCAL = {
    "$schema",
    "default",
    "title",
    "examples",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "dependentRequired",
    "dependentSchemas",
}
_SIMPLE = {
    "type",
    "description",
    "enum",
    "const",
    "pattern",
    "format",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
}


def strict_openai_schema(schema):
    """Project the Agent schema onto the strict subset, leaving local checks intact."""
    wrap = "oneOf" in schema or "anyOf" in schema
    aliases, lifted = {}, {}

    def project(node, path):
        if not isinstance(node, dict):
            raise SchemaCompatibilityError(path, "unsupported_schema_node")
        if "$ref" in node:
            ref = node["$ref"]
            if ref == "#" and not wrap:
                return {"$ref": ref}
            ref_path = [*path, "$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
                raise SchemaCompatibilityError(ref_path, "unsupported_schema_reference")
            parts = unquote(ref[2:]).split("/")
            target = schema
            try:
                for part in parts:
                    token = part.replace("~1", "/").replace("~0", "~")
                    if isinstance(target, list) and token.isascii() and token.isdecimal():
                        index = int(token)
                        if str(index) != token:
                            raise ValueError
                        target = target[index]
                    else:
                        target = target[token]
            except (KeyError, TypeError, IndexError, ValueError):
                raise SchemaCompatibilityError(ref_path, "unresolved_schema_reference") from None
            if len(parts) > 2:
                # OpenAI resolves direct named definitions. Reserve the alias before projecting
                # its original target so that recursive references can use the same name.
                if ref not in aliases:
                    index = len(aliases)
                    name = f"__dacntt_ref_{index}"
                    while name in schema.get("$defs", {}) or name in aliases.values():
                        index += 1
                        name = f"__dacntt_ref_{index}"
                    aliases[ref] = name
                    lifted[name] = project(target, ref_path)
                ref = f"#/$defs/{aliases[ref]}"
            # The current sibling restrictions narrow the referenced definition.
            # They still run against their original reference/scope during local validation.
            return {"$ref": ref}
        result = {}
        for key, value in node.items():
            child_path = [*path, key]
            if key in _SIMPLE:
                if key == "enum" and not value:
                    raise SchemaCompatibilityError(child_path, "empty_enum")
                result[key] = value
            elif key in _LOCAL or key in {"required", "additionalProperties", "prefixItems"}:
                continue
            elif key in {"oneOf", "anyOf"} and "anyOf" not in result:
                result["anyOf"] = [
                    project(item, [*child_path, str(i)]) for i, item in enumerate(value)
                ]
            elif key in {"properties", "$defs"}:
                result[key] = {
                    name: project(item, [*child_path, name]) for name, item in value.items()
                }
            elif key == "items":
                if value is not False:
                    result[key] = project(value, child_path)
            else:
                raise SchemaCompatibilityError(child_path, "unsupported_schema_keyword")
        if "prefixItems" in node:
            options = [
                project(item, [*path, "prefixItems", str(i)])
                for i, item in enumerate(node["prefixItems"])
            ]
            if "items" in result:
                options.append(result["items"])
            elif node.get("items") is not False and node.get("maxItems", len(options) + 1) > len(
                options
            ):
                raise SchemaCompatibilityError([*path, "items"], "unbounded_tuple_tail")
            options = list({json.dumps(item, sort_keys=True): item for item in options}.values())
            result["items"] = options[0] if len(options) == 1 else {"anyOf": options}
        elif node.get("items") is False:
            result.update(items={"type": "string"}, maxItems=0)
        if "properties" in result or result.get("type") == "object" and "anyOf" not in result:
            properties = result.setdefault("properties", {})
            if node.get("additionalProperties") is not False or _OMIT_KEY in properties:
                raise SchemaCompatibilityError([*path, "additionalProperties"], "object_not_closed")
            required = node.get("required", [])
            for name, item in properties.items():
                if name not in required:
                    properties[name] = {"anyOf": [item, {"$ref": f"#/$defs/{_OMIT_KEY}"}]}
            result.update(type="object", additionalProperties=False, required=list(properties))
        if "anyOf" in result and result.get("type") == "object" and "properties" not in result:
            del result["type"]
        return result

    wire = project(schema, [])
    definitions = wire.pop("$defs", {})
    if _OMIT_KEY in definitions:
        raise SchemaCompatibilityError(["$defs", _OMIT_KEY], "reserved_schema_name")
    if wrap:
        wire = {
            "type": "object",
            "properties": {"result": wire},
            "required": ["result"],
            "additionalProperties": False,
        }
    if wire.get("type") != "object":
        raise SchemaCompatibilityError(["type"], "expected_root_object")
    wire["$defs"] = definitions | lifted | {_OMIT_KEY: _OMIT_SCHEMA}
    return wire


def _decode_omitted(node):
    if isinstance(node, dict):
        return {key: _decode_omitted(value) for key, value in node.items() if value != _OMIT}
    if isinstance(node, list):
        return [_decode_omitted(value) for value in node]
    return node


@dataclass(frozen=True)
class OpenAISettings:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    model: str

    @classmethod
    def from_environment(cls, environment=None):
        env = os.environ if environment is None else environment
        base_url = env.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip().rstrip("/")
        key = env.get("OPENAI_API_KEY", "").strip()
        model = env.get("DACNTT_LLM_MODEL", DEFAULT_OPENAI_MODEL).strip()
        if not key or not key.isascii() or any(c.isspace() for c in key):
            raise ValueError("openai_api_key_missing_or_invalid")
        try:
            url = urlsplit(base_url)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username is not None
                or url.password is not None
                or url.query
                or url.fragment
                or url.path != "/v1"
                or not model
            ):
                raise ValueError
            _ = url.port
        except ValueError:
            raise ValueError("openai_configuration_invalid") from None
        return cls(base_url, key, model)


class OpenAIAdapter(ChatCompletionsAdapter):
    provider = "openai"

    def _schema(self, spec):
        if spec.schema_ref is not None:
            if self.schema_registry is None:
                raise LookupError
            try:
                return self.schema_registry.schema_for(spec.schema_ref)
            except ValueError:
                raise LookupError from None
        if spec.json_schema is None:
            raise SchemaCompatibilityError(["output_spec", "json_schema"], "missing_strict_schema")
        return spec.json_schema

    def _payload(self, request):
        payload, timeout = self._message_payload(request)
        if "max_tokens" in payload:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
        spec = request.output_spec
        if spec is not None and spec.format == "json":
            schema = self._schema(spec)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_output",
                    "strict": True,
                    "schema": strict_openai_schema(schema),
                },
            }
            envelope = (
                " Bọc quyết định trong trường result."
                if "oneOf" in schema or "anyOf" in schema
                else ""
            )
            payload["messages"].append(
                {
                    "role": "system",
                    "content": (
                        "Tuân thủ response_format. Dùng đối tượng "
                        '{"__dacntt_omitted":true} khi muốn bỏ qua trường tùy chọn. '
                        "Giữ null tường minh nếu đó là giá trị của trường." + envelope
                    ),
                }
            )
        return payload, httpx.Timeout(min(60, timeout), read=timeout)

    @staticmethod
    def _http_error(raw):
        if raw.status_code == 400:
            try:
                param = raw.json()["error"].get("param")
            except (ValueError, AttributeError, KeyError, TypeError):
                param = None
            if isinstance(param, str) and (
                param == "response_format" or param.startswith("response_format.")
            ):
                return _error("schema_mismatch", origin="provider", http_code=400)
        return ChatCompletionsAdapter._http_error(raw)

    def _response(self, request, raw, base, payload):
        if self.settings.api_key in json.dumps(raw, ensure_ascii=False):
            return self._failed(base, "structured_output_invalid")
        _provider_metadata(request, raw, base)
        usage = base["usage"]
        cached = ((raw.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")
        if (
            type(cached) is int
            and usage.input_tokens is not None
            and 0 <= cached <= usage.input_tokens
        ):
            usage.cached_tokens = cached
        rates = OPENAI_PRICING.get(request.model.model)
        if rates and usage.input_tokens is not None and usage.output_tokens is not None:
            uncached = usage.input_tokens - (usage.cached_tokens or 0)
            amount = (
                rates[0] * uncached
                + rates[1] * (usage.cached_tokens or 0)
                + rates[2] * usage.output_tokens
            ) / 1_000_000
            base["cost"] = dict(
                status="available",
                source="estimated",
                amount=amount,
                currency="USD",
                price_source="openai-standard",
                pricing_version="gpt-4o-mini-standard-2026-11-23",
            )
        choices = raw.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            return self._failed(base, "structured_output_invalid")
        choice = choices[0]
        message = choice.get("message") or {}
        reason = choice.get("finish_reason")
        if reason == "content_filter" or message.get("refusal"):
            return LLMResponse(
                **base,
                status="refused",
                finish_reason="safety",
                error=_error("safety", origin="provider"),
            )
        spec = request.output_spec
        is_json = spec is not None and spec.format == "json"
        if reason == "length":
            return LLMResponse(
                **base,
                status="partial",
                finish_reason="length",
                output=parse_json_output("", schema_ref=spec.schema_ref)
                if is_json
                else TextOutput(format="text", text=""),
                error=_error("structured_output_invalid", origin="provider"),
            )
        text = message.get("content")
        if reason != "stop" or not isinstance(text, str) or not text.strip():
            return self._failed(base, "structured_output_invalid")
        if not is_json:
            output = TextOutput(format="text", text=text.strip())
        else:
            parsed = parse_json_output(text)
            if parsed.validation_status == "invalid_json":
                return self._failed(base, "structured_output_invalid")
            wire = payload["response_format"]["json_schema"]["schema"]
            issues = schema_issues(wire, parsed.payload)
            if issues:
                return self._failed(base, "schema_mismatch", issues)
            schema = self._schema(spec)
            value = (
                parsed.payload["result"]
                if "oneOf" in schema or "anyOf" in schema
                else parsed.payload
            )
            value = _decode_omitted(value)
            issues = schema_issues(schema, value)
            if issues:
                return self._failed(base, "schema_mismatch", issues)
            output = parse_json_output(
                json.dumps(value, ensure_ascii=False), schema_ref=spec.schema_ref
            )
        return LLMResponse(**base, status="success", finish_reason="stop", output=output)

    @staticmethod
    def _failed(base, category, issues=()):
        error = _error(category, origin="provider").model_copy(
            update=dict(validation_issues=list(issues))
        )
        return LLMResponse(**base, status="error", finish_reason="error", error=error)
