"""Server-side composition of the existing Gemini/Gateway/quota/cache stack."""

import hashlib
import json
import os
import re
from decimal import Decimal
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import Field

from ..core.gemini_adapter import GeminiAdapter
from ..core.llm_cache import CachedLLMService
from ..core.llm_gateway import SharedLLMGateway
from ..core.llm_quota_budget import GatewayBinding, ProjectPolicy, ProjectRegistry, QuotaBudgetGuard
from ..document_processing.metadata_preflight import MetadataModel, metadata_schema_registry
from .document_store import safe_path


class LiveSettings(MetadataModel):
    project_policy: ProjectPolicy
    accounting_scope: str = Field(min_length=1, max_length=100)
    fresh_exclusive_scope_confirmed: bool
    data_export_approved: bool
    pricing_confirmed: bool
    key_index: int = Field(ge=0)
    credential_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_spending_upper_bound: Decimal = Field(ge=0, allow_inf_nan=False)


def compose_metadata_service(store):
    """No implicit policy, quota, model selection or key rotation.

    A scope marker is consumed once and survives crashes. Operator must authorize
    a new conservative accounting scope after restart, including prior/unknown
    usage. Snapshots are evidence, never a durable replacement for quota guard.
    """
    config_path = os.environ.get("WEB_GEMINI_CONFIG")
    if not config_path:
        return None, None, {}
    client = None
    try:
        settings = LiveSettings.model_validate_json(
            Path(config_path).read_text(encoding="utf-8-sig")
        )
        policy = settings.project_policy
        if not all(
            (
                settings.fresh_exclusive_scope_confirmed,
                settings.data_export_approved,
                settings.pricing_confirmed,
                policy.mapping_confirmed,
            )
        ):
            raise ValueError
        if policy.provider != "gemini" or len(policy.credential_refs) != 1 or policy.budget is None:
            raise ValueError
        if os.environ.get("GEMINI_MODEL", policy.model) != policy.model:
            raise ValueError
        if settings.request_spending_upper_bound == 0 and policy.tier != "free":
            raise ValueError
        key_file = os.environ.get("GEMINI_API_KEY_FILE")
        if key_file:
            keys = re.findall(
                r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$",
                Path(key_file).read_text(encoding="utf-8-sig"),
            )
            key = keys[settings.key_index]
        else:
            key = os.environ.get("GEMINI_API_KEY", "").strip()
            if settings.key_index != 0:
                raise ValueError
        if not key or hashlib.sha256(key.encode()).hexdigest() != settings.credential_sha256:
            raise ValueError
        schemas = metadata_schema_registry()
        client = genai.Client(
            api_key=key,
            vertexai=False,
            http_options=types.HttpOptions(
                timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        adapter = GeminiAdapter(client, schema_registry=schemas)
        gateway = SharedLLMGateway({"gemini": adapter}, schema_registry=schemas)
        credential = policy.credential_refs[0]
        guard = QuotaBudgetGuard(
            ProjectRegistry([policy]),
            [
                GatewayBinding(
                    policy.account_ref,
                    policy.project_ref,
                    credential,
                    "gemini",
                    policy.model,
                    gateway,
                )
            ],
        )
        safe_path(store.root, "accounting-scopes").mkdir(exist_ok=True)
        digest = hashlib.sha256(settings.accounting_scope.encode()).hexdigest()
        marker = safe_path(store.root, "accounting-scopes", digest + ".json")
        with marker.open("x", encoding="utf-8") as stream:
            json.dump({"status": "consumed", "prior_usage_requires_operator_review": True}, stream)
        guard.initialize(confirmed_fresh_scope=True)
        service = CachedLLMService(
            guard,
            tenant_ref="web-metadata",
            project_ref=policy.project_ref,
            credential_refs=frozenset({credential}),
            configuration_revision="W-03-metadata-v1",
            scope_confirmed=True,
            schema_registry=schemas,
        )
        return (
            service,
            adapter,
            dict(
                credential_ref=credential,
                model=policy.model,
                reservation_money=dict(
                    spending_upper_bound=settings.request_spending_upper_bound,
                    currency=policy.budget.currency,
                    spending_basis="approved_upper_bound",
                ),
            ),
        )
    except Exception:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        # Fail closed; no exception string can expose key file contents or paths.
        return None, None, {}
