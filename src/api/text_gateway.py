"""Composition text-only: chọn provider/model bên ngoài logic M5/M6/M7."""

import os
from dataclasses import dataclass

from ..core.gemini_adapter import DEFAULT_GEMINI_MODEL
from ..core.llm_contracts import ModelIdentity
from ..core.llm_gateway import SharedLLMGateway
from ..core.qwen_adapter import QwenAdapter, QwenSettings
from .qa_gateway import create_qa_adapter


@dataclass
class TextGateway:
    gateway: SharedLLMGateway
    model: ModelIdentity
    adapter: object

    def close(self):
        self.adapter.close()


def create_text_gateway(project_root, *, provider=None, config_file=None, schema_registry=None):
    provider = provider or os.environ.get("TEXT_LLM_PROVIDER", "gemini")
    if provider == "qwen":
        settings = QwenSettings.from_environment(project_root, config_file=config_file)
        adapter = QwenAdapter(settings, schema_registry=schema_registry)
        model = ModelIdentity(provider="qwen", model=settings.model)
    elif provider == "gemini":
        model = ModelIdentity(
            provider="gemini", model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        )
        adapter, _ = create_qa_adapter(project_root)
    else:
        raise ValueError("text_provider_unsupported")
    return TextGateway(
        SharedLLMGateway({provider: adapter}, schema_registry=schema_registry), model, adapter
    )
