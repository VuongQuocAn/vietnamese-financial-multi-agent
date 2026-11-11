"""Shared QA credential rotation, using the existing local Free Tier pool."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from google import genai
from google.genai import types

from ..core.gemini_adapter import GeminiAdapter
from ..core.llm_gateway import _failure
from ..core.llm_quota_budget import Reservation
from .metadata_service import POOL_CREDENTIAL, POOL_SCOPE, FreeTierKeyPool, MetadataGeminiAdapter


class QAGeminiAdapter(GeminiAdapter):
    """Use JSON MIME generation; Planner owns typed schema and DAG validation."""


class QACredentialError(ValueError):
    """Chỉ code cố định; không đưa nội dung secret/path/provider exception ra log."""


@dataclass(frozen=True)
class QACredential:
    key: str = field(repr=False)
    source: str
    key_count: int
    key_index: int


def _credentials(project_root, *, key_file=None, environment=None):
    environment = os.environ if environment is None else environment
    direct = environment.get("GEMINI_API_KEY", "").strip()
    configured_file = key_file or environment.get("GEMINI_API_KEY_FILE")
    if key_file is None and direct:
        content, source = direct, "environment"
    else:
        path = Path(configured_file or "src/api/api_key/api_gemini.txt")
        if not path.is_absolute():
            path = Path(project_root) / path
        source = "configured_file" if configured_file else "local_default_file"
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            raise QACredentialError("key_file_unreadable") from None
    # Giữ đúng format/dedup của compose_metadata_service, kể cả file có headers.
    keys = list(dict.fromkeys(re.findall(r"(?m)^\s*(AIza[0-9A-Za-z_-]{35})\s*$", content)))
    if not 1 <= len(keys) <= 32:
        raise QACredentialError("key_format_invalid")
    return keys, source


def resolve_qa_credential(project_root, *, key_file=None, key_index=0, environment=None):
    keys, source = _credentials(project_root, key_file=key_file, environment=environment)
    if not 0 <= key_index < len(keys):
        raise QACredentialError("key_index_out_of_range")
    return QACredential(keys[key_index], source, len(keys), key_index)


class QARotatingAdapter:
    """One pool for Supervisor/Specialists/M6/M7; indices never imply projects."""

    def __init__(self, pool):
        self.pool = pool
        self.events = []

    def __call__(self, request):
        with self.pool.lock:
            result = self.pool.generate(
                request,
                project_ref=POOL_SCOPE,
                credential_ref=POOL_CREDENTIAL,
                reservation=Reservation(
                    token_upper_bound=sum(len(m.content) for m in request.messages)
                    + (request.generation.max_output_tokens or 8192),
                    token_basis="caller_attested_upper_bound",
                ),
            )
            self.events.extend(dict(request_id=request.request_id, **a) for a in self.pool.attempts)
            response = result.response or _failure(request, "provider_unavailable")
            if result.reason != "provider_response":
                response = response.model_copy(deep=True)
                if response.error:
                    # The pool already exhausted eligible credentials or hit the
                    # shared application cap. Do not retry the same pool outside it.
                    response.error.retryability = "not_retryable"
            return response

    def close(self):
        self.pool.close()


def create_qa_adapter(project_root, *, key_file=None, key_index=0, pool_root=None):
    credential = resolve_qa_credential(project_root, key_file=key_file, key_index=key_index)
    keys, _ = _credentials(project_root, key_file=key_file)
    adapters = []
    try:
        for key in keys:
            client = genai.Client(
                api_key=key,
                vertexai=False,
                http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
            )
            adapters.append(MetadataGeminiAdapter(client, schema_registry=None))
        root = Path(pool_root or os.environ.get("QA_GEMINI_POOL_ROOT", "artifacts/qa-key-pool"))
        if not root.is_absolute():
            root = Path(project_root) / root
        root.mkdir(parents=True, exist_ok=True)
        pool = FreeTierKeyPool(
            adapters,
            SimpleNamespace(root=root),
            max_attempts=len(adapters),
            cooldown=int(os.environ.get("QA_GEMINI_COOLDOWN_SECONDS", 60)),
            model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        )
        pool.selected = key_index
    except Exception:
        for adapter in adapters:
            adapter.close()
        raise QACredentialError("gemini_client_initialization_failed") from None
    return QARotatingAdapter(pool), credential
