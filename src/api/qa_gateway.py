"""QA CLI composition: một credential, không rotation/retry hoặc thay Gateway."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from google import genai
from google.genai import types

from ..core.gemini_adapter import GeminiAdapter


class QAGeminiAdapter(GeminiAdapter):
    """Constrain Planner generation; typed Planner validation remains authoritative."""

    def _config(self, request):
        contents, config = super()._config(request)
        if (
            request.request_id.startswith("planner-")
            and request.output_spec is not None
            and request.output_spec.format == "json"
        ):
            from ..agents.planner_contracts import PlannerProposal

            config.response_json_schema = PlannerProposal.model_json_schema()
        return contents, config


class QACredentialError(ValueError):
    """Chỉ code cố định; không đưa nội dung secret/path/provider exception ra log."""


@dataclass(frozen=True)
class QACredential:
    key: str = field(repr=False)
    source: str
    key_count: int
    key_index: int


def resolve_qa_credential(project_root, *, key_file=None, key_index=0, environment=None):
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
    if not 0 <= key_index < len(keys):
        raise QACredentialError("key_index_out_of_range")
    return QACredential(keys[key_index], source, len(keys), key_index)


def create_qa_adapter(project_root, *, key_file=None, key_index=0):
    credential = resolve_qa_credential(project_root, key_file=key_file, key_index=key_index)
    try:
        client = genai.Client(
            api_key=credential.key,
            vertexai=False,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )
    except Exception:
        raise QACredentialError("gemini_client_initialization_failed") from None
    return QAGeminiAdapter(client), credential
