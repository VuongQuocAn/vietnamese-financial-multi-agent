"""Engineering checks cho phép đo offline; không chứng minh chất lượng tài chính."""

import importlib.util
import sys
import types
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/profile_model_context.py"
spec = importlib.util.spec_from_file_location("context_profile", SCRIPT)
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


def test_per_call_budget_boundaries_and_missing_measurement(monkeypatch, tmp_path):
    # Calls tuần tự cùng 5K input/2K output đều FIT; không cộng thành 14K context.
    calls = [(5000, 2000), (5000, 2000)]
    assert [profile.classify(p, r, 8192) for p, r in calls] == ["FIT", "FIT"]
    assert profile.classify(7192, 1000, 8192) == "NEAR_LIMIT"
    assert profile.classify(7193, 1000, 8192) == "OVERFLOW"
    assert profile.classify(None, 1000, 8192) == "UNKNOWN"
    assert profile.stats([100, 200])["p95"] == 195

    class MissingTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            assert kwargs == {"local_files_only": True}
            raise OSError("Tokenizer unavailable offline")

    monkeypatch.setitem(
        sys.modules, "transformers", types.SimpleNamespace(AutoTokenizer=MissingTokenizer)
    )
    tokenizer, metadata = profile.load_tokenizer(profile.MODELS[2], tmp_path, False)
    assert tokenizer is None
    assert metadata["tokenizer_available"] is False
    assert metadata["measurement_status"] == "unavailable"


def test_actual_adapter_render_and_consistent_chat_template():
    request = dict(
        contract_version="llm_gateway_v1",
        request_id="profiling-test",
        model=dict(provider="gemini", model="gemini-3.5-flash-lite"),
        messages=[dict(role="system", content="Giữ nguồn."), dict(role="user", content="Kỳ nào?")],
        generation=dict(temperature=0.0, max_output_tokens=900, top_p=None),
        output_spec=dict(format="json"),
    )
    payload = profile.provider_payload(request)
    assert profile.provider_messages(payload) == request["messages"]
    assert payload["config"]["response_mime_type"] == "application/json"
    assert payload["config"]["max_output_tokens"] == 900

    class TemplateTokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs == dict(tokenize=True, add_generation_prompt=True, enable_thinking=False)
            return list("".join(m["role"] + m["content"] for m in messages)) + [0, 1, 2]

    tokenizer = TemplateTokenizer()
    messages = profile.provider_messages(payload)
    assert profile.render_count(tokenizer, messages) == profile.render_count(tokenizer, messages)
    assert profile.render_count(tokenizer, messages) > sum(len(m["content"]) for m in messages)


def test_components_and_architecture_specific_kv():
    messages = [
        dict(
            role="system",
            content=profile.serialize(
                dict(
                    instruction="grounded",
                    graph_context=[dict(relation="used_in", citations=[dict(pdf_page=7)])],
                    conversation_context="kỳ trước",
                    analysis_schema=dict(type="object"),
                )
            ),
        )
    ]
    parts = profile.component_fragments(messages)
    assert all(parts[k] for k in ("instructions", "graph", "citations", "conversation", "schema"))
    config = dict(
        num_hidden_layers=40,
        num_key_value_heads=8,
        hidden_size=5120,
        num_attention_heads=40,
        head_dim=128,
    )
    assert profile.kv_bytes(config, 8192) == 1342177280
    config["num_hidden_layers"] = 36
    assert profile.kv_bytes(config, 8192) == 1207959552
