"""Key-file-only Free Tier composition; existing Gateway/adapter/cache, no core changes."""

import json
import os
import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from google import genai
from google.genai import errors, types

from ..core.gemini_adapter import GeminiAdapter
from ..core.llm_cache import CachedLLMService
from ..core.llm_contracts import GatewayError
from ..core.llm_gateway import SharedLLMGateway
from ..core.llm_quota_budget import GuardResult, QuotaLimits, Reservation
from ..document_processing.metadata_preflight import (
    DEFAULT_METADATA_MODEL,
    metadata_schema_registry,
)
from .document_store import atomic_json, safe_path

POOL_SCOPE = "web-local-free-pool"  # Local accounting/cache namespace, NOT a Google project.
POOL_CREDENTIAL = "key-pool"


class MetadataGeminiAdapter(GeminiAdapter):
    """A metadata batch is one user turn containing text and multiple page parts."""

    def __init__(self, client, *, schema_registry):
        self._sdk_client = client
        self._key_error, self._retry_after = False, None
        proxy = SimpleNamespace(
            models=SimpleNamespace(generate_content=self._generate_content),
            close=getattr(client, "close", lambda: None),
        )
        super().__init__(proxy, schema_registry=schema_registry)

    def _generate_content(self, **kwargs):
        try:
            return self._sdk_client.models.generate_content(**kwargs)
        except errors.APIError as error:
            body = error.details.get("error", {}) if isinstance(error.details, dict) else {}
            details = body.get("details", []) if isinstance(body, dict) else []
            for detail in details if isinstance(details, list) else []:
                if not isinstance(detail, dict):
                    continue
                if error.code == 400 and detail.get("reason") in (
                    "API_KEY_INVALID",
                    "API_KEY_EXPIRED",
                    "API_KEY_SERVICE_BLOCKED",
                ):
                    self._key_error = True
                delay = detail.get("retryDelay", "")
                if (
                    error.code == 429
                    and isinstance(delay, str)
                    and re.fullmatch(r"\d+(?:\.\d+)?s", delay)
                ):
                    self._retry_after = float(delay[:-1])
            raise

    def __call__(self, request):
        self._key_error, self._retry_after = False, None
        response = super().__call__(request)
        if response.error:
            if self._key_error:
                response.error.category = response.error.code = "authentication"
            if self._retry_after is not None:
                response.error.retry_after_seconds = self._retry_after
        return response

    def _config(self, request):
        contents, config = super()._config(request)
        if all(content.role == "user" for content in contents):
            contents = [
                types.Content(
                    role="user", parts=[part for content in contents for part in content.parts]
                )
            ]
        return contents, config


@dataclass
class KeyState:
    adapter: GeminiAdapter = field(repr=False)
    disabled: bool = False
    cooldown_until: float = 0
    recent_requests: list[float] = field(default_factory=list)
    error_category: str | None = None


class FreeTierKeyPool:
    """Guard-compatible composition for keys whose Google project binding is unknown.

    Count every gateway attempt against ONE application cap, including rotated
    attempts. Never manufacture confirmed ProjectPolicy mappings for unknown keys.
    Provider limits still apply; these caps are not assertions of provider quota.
    Only counters survive restart, never secrets or per-key content.
    """

    def __init__(
        self,
        adapters,
        store,
        *,
        limits=None,
        max_attempts=3,
        cooldown=60,
        clock=time.time,
        schemas=None,
    ):
        self.keys = [KeyState(adapter) for adapter in adapters]
        self.store = store
        self.limits = limits or QuotaLimits(rpm=15, tpm=250000, rpd=500)
        if not self.keys or not 1 <= max_attempts <= 32 or not 1 <= cooldown <= 86400:
            raise ValueError("Invalid key pool limits")
        self.max_attempts, self.cooldown, self.clock = max_attempts, cooldown, clock
        self.lock, self.selected = RLock(), 0
        self.attempts = []
        self.ledger_path = safe_path(store.root, "free-tier-usage.json")
        self.ledger = (
            json.loads(self.ledger_path.read_text())
            if self.ledger_path.exists()
            else {"day": "", "count": 0, "recent": [], "last_time": 0}
        )
        self.gateway = SharedLLMGateway({"gemini": self._dispatch}, schema_registry=schemas)

    def _dispatch(self, request):
        return self.keys[self.selected].adapter(request)

    def close(self):
        for key in self.keys:
            try:
                key.adapter.close()
            except Exception:
                pass

    def status(self):
        now = self.clock()
        return [
            dict(
                key_index=index,
                available=not key.disabled and key.cooldown_until <= now,
                recent_requests=sum(t > now - 60 for t in key.recent_requests),
                cooldown_seconds=max(0, key.cooldown_until - now),
                error_category=key.error_category,
            )
            for index, key in enumerate(self.keys)
        ]

    def _admit(self, reservation):
        now = self.clock()
        if now < self.ledger["last_time"]:
            return None, "clock_invalid"
        day = datetime.fromtimestamp(now, ZoneInfo("America/Los_Angeles")).date().isoformat()
        if day != self.ledger["day"]:
            self.ledger.update(day=day, count=0)
        recent = [r for r in self.ledger["recent"] if r["time"] > now - 60]
        self.ledger["recent"] = recent
        if self.ledger["count"] >= self.limits.rpd:
            return None, "application_daily_limit"
        if (
            len(recent) >= self.limits.rpm
            or sum(r["tokens"] for r in recent) + reservation.token_upper_bound > self.limits.tpm
        ):
            return None, "application_rate_limit"
        charge = dict(time=now, tokens=reservation.token_upper_bound)
        self.ledger.update(count=self.ledger["count"] + 1, last_time=now)
        recent.append(charge)
        atomic_json(self.ledger_path, self.ledger)  # Reserve BEFORE a potentially billable request.
        return charge, None

    def generate(self, request, *, project_ref, credential_ref, reservation):
        with self.lock:
            self.attempts = []
            reservation = Reservation.model_validate(reservation)
            if (
                project_ref != POOL_SCOPE
                or credential_ref != POOL_CREDENTIAL
                or request.model.provider != "gemini"
                or request.model.model != DEFAULT_METADATA_MODEL
            ):
                return GuardResult(False, "invalid_configuration")
            attempted = set()
            last_response = None
            while len(attempted) < min(self.max_attempts, len(self.keys)):
                now = self.clock()
                eligible = [
                    i
                    for i in range(len(self.keys))
                    if i not in attempted
                    and not self.keys[i].disabled
                    and self.keys[i].cooldown_until <= now
                ]
                if not eligible:
                    break
                index = self.selected if self.selected in eligible else eligible[0]
                charge, reason = self._admit(reservation)
                if reason:
                    return GuardResult(
                        bool(attempted),
                        reason,
                        response=last_response,
                        error=GatewayError(
                            category="quota_exceeded",
                            code="quota_exceeded",
                            origin="gateway",
                            retryability="not_retryable",
                        ),
                    )
                self.selected = index
                key = self.keys[index]
                key.recent_requests = [t for t in key.recent_requests if t > now - 60] + [now]
                attempted.add(index)
                response = self.gateway.generate(request)
                last_response = response
                error = response.error
                category = error.category if error else None
                key.error_category = category
                self.attempts.append(
                    dict(
                        key_index=index,
                        error_category=category,
                        usage=response.usage.export(),
                        provider_reported_model=response.provenance.provider_reported_model,
                    )
                )
                total = response.usage.total_tokens
                if response.usage.source == "provider_reported" and total is not None:
                    charge["tokens"] = total
                    atomic_json(self.ledger_path, self.ledger)
                if category in ("authentication", "authorization"):
                    key.disabled = True
                elif category in ("rate_limit", "quota_exceeded"):
                    key.cooldown_until = self.clock() + max(
                        self.cooldown, error.retry_after_seconds or 0
                    )
                else:
                    # Successful key stays selected. Timeout/server errors do not
                    # cause speculative duplicate requests on other credentials.
                    return GuardResult(True, "provider_response", response=response)
                self.selected = (index + 1) % len(self.keys)
            return GuardResult(
                bool(attempted),
                "key_pool_unavailable",
                response=last_response,
                error=GatewayError(
                    category="rate_limit",
                    code="rate_limit",
                    origin="gateway",
                    retryability="not_retryable",
                ),
            )


class MetadataLLMService(CachedLLMService):
    def __init__(self, pool, schemas):
        self.pool, self.last_attempts = pool, []
        super().__init__(
            pool,
            tenant_ref="local-single-user",
            project_ref=POOL_SCOPE,
            credential_refs=frozenset({POOL_CREDENTIAL}),
            configuration_revision="W-03-auto-first-v2",
            scope_confirmed=True,
            schema_registry=schemas,
        )

    def generate(self, *args, **kwargs):
        with self.pool.lock:
            self.pool.attempts = []
            result = super().generate(*args, **kwargs)
            self.last_attempts = deepcopy(self.pool.attempts)  # Cache hit has zero new attempts.
            return result


def compose_metadata_service(store):
    """Only a key file (or existing single-key env) is needed; no manual project/scope."""
    adapters = []
    try:
        if os.environ.get("GEMINI_MODEL", DEFAULT_METADATA_MODEL) != DEFAULT_METADATA_MODEL:
            raise ValueError("Model not approved for this Free Tier composition")
        key_file = os.environ.get("GEMINI_API_KEY_FILE")
        if key_file:
            path = Path(key_file)
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("Key file too large")
            content = path.read_text(encoding="utf-8-sig")
        else:
            content = os.environ.get("GEMINI_API_KEY", "")
        keys = list(dict.fromkeys(re.findall(r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$", content)))
        if not 1 <= len(keys) <= 32:
            raise ValueError("No usable key configuration")
        schemas = metadata_schema_registry()
        for key in keys:
            client = genai.Client(
                api_key=key,
                vertexai=False,
                http_options=types.HttpOptions(
                    timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)
                ),
            )
            adapters.append(MetadataGeminiAdapter(client, schema_registry=schemas))
        pool = FreeTierKeyPool(
            adapters,
            store,
            schemas=schemas,
            limits=QuotaLimits(
                rpm=int(os.environ.get("WEB_GEMINI_RPM", 15)),
                tpm=int(os.environ.get("WEB_GEMINI_TPM", 250000)),
                rpd=int(os.environ.get("WEB_GEMINI_RPD", 500)),
            ),
            max_attempts=int(os.environ.get("WEB_GEMINI_MAX_ATTEMPTS", 3)),
            cooldown=int(os.environ.get("WEB_GEMINI_COOLDOWN_SECONDS", 60)),
        )
        return MetadataLLMService(pool, schemas), pool, dict(credential_ref=POOL_CREDENTIAL)
    except Exception:
        for adapter in adapters:
            try:
                adapter.close()
            except Exception:
                pass
        return None, None, {}
