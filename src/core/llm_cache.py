"""Cache bộ nhớ opt-in; chỉ gọi Gateway qua quota guard, không I/O hoặc logs."""

import hashlib
import json
import math
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Literal

from .llm_contracts import (
    Cost,
    JSONOutput,
    LLMRequest,
    LLMResponse,
    Usage,
    parse_llm_request,
    parse_llm_response,
)
from .llm_quota_budget import GuardResult, QuotaBudgetGuard, Reservation
from .llm_schema_validation import LocalSchemaRegistry

CACHE_KEY_VERSION = "llm_response_cache_v1"


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cache_key(
    request: LLMRequest,
    *,
    tenant_ref: str,
    project_ref: str,
    configuration_revision: str,
    schema_registry: LocalSchemaRegistry | None = None,
) -> str:
    """Identity nội bộ; caller không xuất digest hoặc raw content vào diagnostics."""
    request = parse_llm_request(request)
    content = request.export()
    content.pop("request_id")
    content.pop("correlation", None)
    reference = request.output_spec.schema_ref if request.output_spec else None
    fingerprint = None
    if reference is not None:
        if schema_registry is None:
            raise ValueError("Local schema registry required")
        fingerprint = _digest(schema_registry.schema_for(reference))
    return _digest(
        {
            "key_version": CACHE_KEY_VERSION,
            "tenant": tenant_ref,
            "project": project_ref,
            "configuration_revision": configuration_revision,
            "request": content,
            "schema_fingerprint": fingerprint,
        }
    )


@dataclass(frozen=True)
class CachedResult:
    response: LLMResponse | None = field(repr=False)
    cache_status: Literal["hit", "miss", "expired", "bypassed"]
    # Guard admission chỉ chứng minh Gateway đã được gọi; không biết adapter có gửi API.
    provider_called: bool | None
    guard_result: GuardResult | None = field(default=None, repr=False)
    historical_usage: Usage | None = field(default=None, repr=False)
    historical_cost: Cost | None = field(default=None, repr=False)
    age_seconds: float | None = None
    ttl_remaining_seconds: float | None = None
    key_version: str = CACHE_KEY_VERSION

    @property
    def cache_hit(self) -> bool:
        return self.cache_status == "hit"


@dataclass
class _Entry:
    response: LLMResponse = field(repr=False)
    created: float


class CachedLLMService:
    """Một instance/scope ứng dụng đã xác nhận; aliases không được chứa key values.

    configuration_revision gộp adapter/config/model revision, đổi instance khi đổi
    binding/config. credential_refs là allowlist do composition layer xác nhận cùng
    project/tenant và quyền chia sẻ cache; không suy scope từ credential values.
    """

    def __init__(
        self,
        guard: QuotaBudgetGuard,
        *,
        tenant_ref: str,
        project_ref: str,
        credential_refs: frozenset[str],
        configuration_revision: str,
        scope_confirmed: bool = False,
        schema_registry: LocalSchemaRegistry | None = None,
        ttl_seconds: float = 60,
        max_entries: int = 128,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if (
            not math.isfinite(ttl_seconds)
            or ttl_seconds <= 0
            or type(max_entries) is not int
            or max_entries <= 0
            or not tenant_ref
            or not project_ref
            or not configuration_revision
        ):
            raise ValueError("Invalid cache configuration")
        self._guard = guard
        self._tenant, self._project = tenant_ref, project_ref
        self._credentials = frozenset(credential_refs)
        self._revision, self._confirmed = configuration_revision, scope_confirmed is True
        self._schemas = schema_registry
        self._ttl, self._max_entries, self._clock = ttl_seconds, max_entries, clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = Lock()
        self._epoch = 0

    def clear(self) -> None:
        """Invalidate toàn scope, kể cả writes từ calls đang chạy."""
        with self._lock:
            self._entries.clear()
            self._epoch += 1

    def invalidate(self, request: LLMRequest) -> None:
        key = self._key(request)
        with self._lock:
            self._entries.pop(key, None)
            self._epoch += 1

    def _key(self, request: LLMRequest) -> str:
        return cache_key(
            request,
            tenant_ref=self._tenant,
            project_ref=self._project,
            configuration_revision=self._revision,
            schema_registry=self._schemas,
        )

    def _cacheable(self, request: LLMRequest, response: LLMResponse) -> bool:
        if (
            response.status != "success"
            or response.error is not None
            or response.request_id != request.request_id
            or response.correlation != request.correlation
            or response.provenance.requested_model != request.model
        ):
            return False
        output, spec = response.output, request.output_spec
        if output is None or (spec is not None and output.format != spec.format):
            return False
        if isinstance(output, JSONOutput):
            reference = spec.schema_ref if spec else None
            if output.schema_ref != reference:
                return False
            if reference is not None:
                # Không tin attestation từ provider; kiểm chứng lại đúng schema local.
                return (
                    output.validation_status == "schema_valid"
                    and self._schemas is not None
                    and self._schemas.is_valid(reference, output.payload)
                )
            return output.validation_status == "json_valid"
        return bool(output.text.strip())

    def generate(
        self,
        request: LLMRequest,
        *,
        credential_ref: str,
        reservation: Reservation,
        cache_allowed: bool = False,
    ) -> CachedResult:
        request = parse_llm_request(request).model_copy(deep=True)
        key = None
        if cache_allowed is True and self._confirmed and credential_ref in self._credentials:
            try:
                key = self._key(request)
            except ValueError:
                pass  # Thiếu schema local: bypass, Guard/Gateway vẫn quyết định request.
        status = "bypassed" if key is None else "miss"
        with self._lock:
            epoch = self._epoch
            now = self._clock()
            entry = self._entries.get(key) if key is not None else None
            if entry is not None:
                age = now - entry.created
                if 0 <= age < self._ttl:
                    self._entries.move_to_end(key)
                    response = entry.response.model_copy(deep=True)
                    historical_usage, historical_cost = response.usage, response.cost
                    response.request_id = request.request_id
                    response.correlation = request.correlation
                    response.provenance.requested_model = request.model
                    response.usage = Usage(
                        status="available",
                        source="calculated",
                        total_tokens=0,
                        input_tokens=0,
                        output_tokens=0,
                    )
                    response.cost = Cost(status="not_available", source="unknown")
                    return CachedResult(
                        parse_llm_response(response),
                        "hit",
                        False,
                        historical_usage=historical_usage,
                        historical_cost=historical_cost,
                        age_seconds=age,
                        ttl_remaining_seconds=self._ttl - age,
                    )
                del self._entries[key]
                status = "expired"
        result = self._guard.generate(
            request.model_copy(deep=True),
            project_ref=self._project,
            credential_ref=credential_ref,
            reservation=reservation,
        )
        if key is not None and result.admitted and result.response is not None:
            response = parse_llm_response(result.response).model_copy(deep=True)
            if self._cacheable(request, response):
                with self._lock:
                    # Không ghi output dưới schema/config khác với lúc tạo request.
                    if epoch == self._epoch and key == self._key(request):
                        now = self._clock()
                        for old_key in list(self._entries):
                            if now - self._entries[old_key].created >= self._ttl:
                                del self._entries[old_key]
                        self._entries[key] = _Entry(response, now)
                        self._entries.move_to_end(key)
                        while len(self._entries) > self._max_entries:
                            self._entries.popitem(last=False)
        return CachedResult(
            result.response, status, None if result.admitted else False, guard_result=result
        )
