"""Đo context offline từ traces; chỉ tải tokenizer/config, không có model inference.

Môi trường riêng: transformers>=4.51,<5 (không cần torch).
Chạy từ repo root: python scripts/profile_model_context.py --download-tokenizers
Chạy lại offline sau lần tải đầu: bỏ --download-tokenizers.
Artifacts chứa payload tài chính chỉ ghi vào artifacts/evidence/MODEL-CTX-01.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

MODELS = ("Qwen/Qwen3-14B", "Qwen/Qwen3-8B", "meta-llama/Llama-3.1-8B-Instruct")
MODEL_REVISIONS = {
    MODELS[0]: "40c069824f4251a91eefaf281ebe4c544efd3e18",
    MODELS[1]: "b968826d9c46dd6066d109eabc6255188de91218",
    MODELS[2]: "0e9e39f249a16976918f6564b8830bc894c89659",
}
LIMITS = (8192, 16384, 32768)
COMPONENTS = (
    "instructions",
    "question",
    "conversation",
    "financial_facts",
    "calculated_metrics",
    "graph",
    "citations",
    "schema",
    "other",
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def serialize(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify(prompt: int | None, reserve: int, limit: int, margin=0.10) -> str:
    if prompt is None:
        return "UNKNOWN"
    required = prompt + reserve
    return (
        "OVERFLOW"
        if required > limit
        else "NEAR_LIMIT"
        if required > limit * (1 - margin)
        else "FIT"
    )


def stats(values) -> dict:
    values = sorted(values)
    if not values:
        return {"n": 0, "min": None, "median": None, "p95": None, "max": None, "mean": None}
    index = (len(values) - 1) * 0.95
    lo, hi = math.floor(index), math.ceil(index)
    return dict(
        n=len(values),
        min=values[0],
        median=statistics.median(values),
        p95=values[lo] + (values[hi] - values[lo]) * (index - lo),
        max=values[-1],
        mean=statistics.mean(values),
    )


def stage_for(request_id: str) -> str:
    for prefix, stage in (
        ("m5-lite-supervisor-", "supervisor"),
        ("m6-lite-", "m6_semantic"),
        ("m7-lite-", "m7_composer"),
    ):
        if request_id.startswith(prefix):
            return stage
    if request_id.startswith("m5-lite-"):
        return request_id.removeprefix("m5-lite-").rsplit("-", 1)[0]
    return request_id.rsplit("-", 1)[0]


def sample_paths(root: Path):
    base = root / "artifacts/evidence"
    # Một repetition cố định, không cherry-pick theo kích thước hoặc verdict.
    paths = [
        (f"EF02-{case}-{arm}", base / "EF-CORE-02/runs" / f"{case}-r1-{arm}.json", arm == "on")
        for case in ("A1", "B2", "C1", "D1", "E2", "F2")
        for arm in ("off", "on")
    ]
    paths += [
        (f"PERIOD-{case}", base / "CORE-PERIOD-01/runs" / f"{case}.json", True)
        for case in ("L2-confirmation", "L3", "L5")
    ]
    paths += [
        (f"EF03-{case}", base / "EF-CORE-03/runs" / f"{case}.json", True)
        for case in ("C1-C-retry1", "D1-C-final-retry1", "B2-C-retry1")
    ]
    paths += [("EF03-semantic-probe", base / "EF-CORE-03/semantic-probe.json", True)]
    paths.append(
        (
            "CORE-FLOW-Q6-multispecialist",
            base / "CORE-FLOW-01/live-initial/provider-events.json",
            False,
        )
    )
    return paths


def provider_payload(request: dict) -> dict:
    """Dùng adapter thực, không tạo client hoặc gửi request.

    Trace model_dump gồm null default; bỏ null generation/constraints đã được logger
    materialize. Adapter sẽ từ chối explicit null nên chúng không thể là cấu hình
    gốc của request thành công. Giữ nguyên từng byte message content.
    """
    from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
    from vietnamese_financial_multi_agent.core.llm_contracts import LLMRequest

    wire = copy.deepcopy(request)
    for key in ("generation", "constraints"):
        if isinstance(wire.get(key), dict):
            wire[key] = {k: v for k, v in wire[key].items() if v is not None}
    contents, config = GeminiAdapter(None)._config(LLMRequest.model_validate(wire))
    return dict(
        model=wire["model"]["model"],
        contents=[c.model_dump(mode="json", exclude_none=True) for c in contents],
        config=config.model_dump(mode="json", exclude_none=True),
    )


def provider_messages(payload: dict) -> list[dict]:
    messages = []
    system = payload["config"].get("system_instruction")
    if system:
        messages.append(
            dict(role="system", content="".join(p.get("text", "") for p in system["parts"]))
        )
    for content in payload["contents"]:
        if any(set(p) != {"text"} for p in content["parts"]):
            raise ValueError("Profiling này chỉ nhận text; không ước lượng image tokens")
        messages.append(
            dict(
                role="assistant" if content["role"] == "model" else "user",
                content="".join(p["text"] for p in content["parts"]),
            )
        )
    return messages


def render_count(tokenizer, messages, *, thinking=False) -> int:
    return len(
        tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, enable_thinking=thinking
        )
    )


def component_for(key: str, inherited: str) -> str:
    if key in {
        "citations",
        "source_metadata",
        "sources",
        "provenance",
        "source_reference",
        "bindings",
    }:
        return "citations"
    if key in {"schema", "analysis_schema", "$defs", "response_contract"}:
        return "schema"
    if key in {"conversation_context", "conversation_history", "history"}:
        return "conversation"
    if key in {"graph_context", "graph_projection"}:
        return "graph"
    if key in {"instruction", "prompt_version", "objective"}:
        return "instructions"
    if key in {"user_question", "question"}:
        return "question"
    if key in {
        "calculation_display",
        "reasoning_calculation",
        "current_metric_executions",
        "calculation",
        "calculations",
        "operations",
        "numeric_choices",
    }:
        return "calculated_metrics"
    if key in {"evidence", "facts", "verified_claims", "supporting_evidence", "inventory"}:
        return "financial_facts"
    return inherited


def component_fragments(messages: list[dict]) -> dict:
    """Các leaf JSON độc lập, citations ưu tiên tách khỏi graph/facts.

    Chi phí tokenize riêng lẻ KHÔNG cộng thành total: JSON keys/punctuation và
    BPE boundaries khác. Full graph là một view chồng lặp riêng trong graph_details.
    """
    fragments = {key: [] for key in COMPONENTS}

    def walk(value, category):
        if isinstance(value, dict):
            for key, val in value.items():
                selected = component_for(key, category)
                if selected in {"schema", "citations", "conversation"} and selected != category:
                    fragments[selected].append(serialize(val))
                else:
                    walk(val, selected)
        elif isinstance(value, list):
            for val in value:
                walk(val, category)
        else:
            fragments[category].append(serialize(value))

    for message in messages:
        default = "instructions" if message["role"] == "system" else "question"
        if message["role"] == "assistant":
            default = "conversation"
        try:
            value = json.loads(message["content"])
        except ValueError:
            fragments[default].append(message["content"])
        else:
            walk(value, default if not isinstance(value, (dict, list)) else "other")
    return fragments


def graph_details(messages: list[dict], response: dict) -> dict:
    graphs, citations = [], []

    def walk(value):
        if isinstance(value, dict):
            for key, val in value.items():
                if key == "graph_context":
                    graphs.extend(val if isinstance(val, list) else [val])
                if key in {"citations", "source_metadata"}:
                    citations.append(serialize(val))
                walk(val)
        elif isinstance(value, list):
            for val in value:
                walk(val)

    for message in messages:
        try:
            walk(json.loads(message["content"]))
        except ValueError:
            pass
    relations = Counter(g.get("relation", "unknown") for g in graphs if isinstance(g, dict))
    endpoints = {
        serialize(e.get("reference", e))
        for g in graphs
        if isinstance(g, dict)
        for e in g.get("endpoints", [])
    }
    raw_output = (response.get("output") or {}).get("raw_text", "") or ""
    # Có nhắc handle là proxy sử dụng, không phải chứng minh usefulness/causality.
    referenced = [
        g.get("id")
        for g in graphs
        if isinstance(g, dict) and g.get("id") and ('"' + g["id"] + '"') in raw_output
    ]
    return dict(
        projection=graphs,
        relation_types=dict(relations),
        unique_nodes=len(endpoints),
        unique_edges=len({serialize(g) for g in graphs}),
        explicit_graph_handles=referenced,
        citation_occurrences=len(citations),
        unique_citation_payloads=len(set(citations)),
    )


def kv_bytes(config: dict, tokens: int) -> int:
    return (
        tokens
        * config["num_hidden_layers"]
        * config["num_key_value_heads"]
        * config.get("head_dim", config["hidden_size"] // config["num_attention_heads"])
        * 2
        * 2
    )


def load_tokenizer(model: str, cache: Path, download: bool):
    from transformers import AutoTokenizer

    model_dir = cache / model.replace("/", "--")
    metadata = dict(model=model, tokenizer_available=False, measurement_status="unavailable")
    access_path = model_dir / "access-status.json"
    if not download and access_path.exists():
        return None, json.loads(access_path.read_bytes())
    try:
        if download:
            from huggingface_hub import hf_hub_download

            revision = MODEL_REVISIONS[model]
            model_dir.mkdir(parents=True, exist_ok=True)
            for name in ("tokenizer.json", "tokenizer_config.json", "config.json"):
                hf_hub_download(model, name, revision=revision, local_dir=model_dir, token=False)
            save(model_dir / "revision.json", dict(model=model, revision=revision))
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        metadata.update(
            tokenizer_available=True,
            measurement_status="exact_local",
            revision=json.loads((model_dir / "revision.json").read_bytes())["revision"],
            files={p.name: digest(p.read_bytes()) for p in model_dir.glob("*.json")},
            chat_template_sha256=digest(tokenizer.chat_template.encode()),
        )
        return tokenizer, metadata
    except Exception as exc:
        # Không ghi exception URL/token/header hoặc tìm tokenizer thay thế.
        metadata["error_type"] = type(exc).__name__
        if download:
            save(access_path, metadata)
        return None, metadata


def fetch_llama_config(path: Path) -> None:
    """Đọc arch_args từ source Meta chính thức; không dùng tokenizer bên thứ ba."""
    from urllib.request import urlopen

    repo = "meta-llama/llama-models"
    with urlopen(
        f"https://api.github.com/repos/{repo}/commits?path=models/sku_list.py&per_page=1",
        timeout=30,
    ) as response:
        revision = json.load(response)[0]["sha"]
    url = f"https://raw.githubusercontent.com/{repo}/{revision}/models/sku_list.py"
    with urlopen(url, timeout=30) as response:
        source = response.read()
    tree = ast.parse(source)
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "llama3_1_instruct_models"
    )
    call = function.body[0].value.elts[0]
    values = next(k.value for k in call.keywords if k.arg == "arch_args")
    args = {
        k.value: v.value
        for k, v in zip(values.keys, values.values, strict=True)
        if isinstance(v, ast.Constant)
    }
    config = dict(
        num_hidden_layers=args["n_layers"],
        num_key_value_heads=args["n_kv_heads"],
        hidden_size=args["dim"],
        num_attention_heads=args["n_heads"],
        head_dim=args["dim"] // args["n_heads"],
        sliding_window=None,
        source_url=url,
        source_sha256=digest(source),
        revision=revision,
    )
    save(path, config)
    path.with_suffix(".source.py").write_bytes(source)


def run(root: Path, download: bool) -> None:
    out = root / "artifacts/evidence/MODEL-CTX-01"
    cache = out / "tokenizers"
    tokenizers, metadata = {}, {}
    for model in MODELS:
        tokenizers[model], metadata[model] = load_tokenizer(model, cache, download)
        print(model, metadata[model]["measurement_status"], flush=True)
    import transformers

    save(
        out / "tokenizer-metadata.json",
        dict(transformers_version=transformers.__version__, models=metadata),
    )
    rows, sources, scenarios = [], {}, []
    seen = set()
    for scenario_id, path, graph_enabled in sample_paths(root):
        original = path.read_bytes()
        sources[str(path.relative_to(root))] = digest(original)
        source = json.loads(original)
        if scenario_id == "CORE-FLOW-Q6-multispecialist":
            selected, active = [], False
            question = ""
            for event in source:
                request = event["request"]
                if stage_for(request["request_id"]) == "supervisor":
                    user = next(m["content"] for m in request["messages"] if m["role"] == "user")
                    active = user.startswith("Dựa trên những dữ liệu hiện có")
                    if active:
                        question = user
                if active:
                    selected.append(event)
            source = dict(events=selected, question=question)
            assert len(selected) == 5
        events = source["events"]
        scenarios.append(
            dict(
                scenario_id=scenario_id,
                graph_enabled=graph_enabled,
                source=str(path.relative_to(root)),
                event_count=len(events),
                question=source.get("question"),
                conversation_present=bool(source.get("conversation_context")),
            )
        )
        for event in events:
            request = event["request"]
            # Không đếm lại cùng captured call; retries khác ID vẫn là observations riêng.
            identity = (request["request_id"], digest(serialize(request).encode()))
            if identity in seen:
                continue
            seen.add(identity)
            provider = provider_payload(request)
            messages = provider_messages(provider)
            assert messages == [
                dict(role=m["role"], content=m["content"]) for m in request["messages"]
            ]
            reserve = request["generation"]["max_output_tokens"]
            usage = event["response"].get("usage", {})
            graph = graph_details(messages, event["response"])
            row = dict(
                scenario_id=scenario_id,
                source=str(path.relative_to(root)),
                request_id=request["request_id"],
                agent=stage_for(request["request_id"]),
                graph_enabled=graph_enabled,
                provider_model=request["model"],
                message_count=len(messages),
                roles=[m["role"] for m in messages],
                prompt_source="reconstructed_provider_request_from_captured_gateway",
                prompt_sha256=digest(serialize(provider).encode()),
                model_reported_input_tokens=usage.get("input_tokens"),
                completion_tokens_observed=usage.get("output_tokens"),
                reasoning_tokens_observed=usage.get("reasoning_tokens"),
                max_output_tokens_configured=reserve,
                reserved_output_tokens=reserve,
                response_status=event["response"]["status"],
                provider_attempts=[
                    {k: attempt.get(k) for k in ("usage", "error_category", "provider_error_code")}
                    for attempt in source.get("provider_attempts", [])
                    if attempt.get("request_id") == request["request_id"]
                ],
                graph={k: v for k, v in graph.items() if k != "projection"},
                models={},
            )
            save(out / "payloads" / f"{request['request_id']}.json", provider)
            fragments = component_fragments(messages)
            for model, tokenizer in tokenizers.items():
                measured = dict(
                    tokenizer_available=tokenizer is not None,
                    measurement_status="exact_local" if tokenizer else "unavailable",
                    prompt_tokens_rendered=None,
                    context_required=None,
                    fit={str(n): "UNKNOWN" for n in LIMITS},
                )
                if tokenizer is not None:
                    count = render_count(tokenizer, messages)
                    costs = {
                        k: sum(len(tokenizer.encode(s, add_special_tokens=False)) for s in vals)
                        for k, vals in fragments.items()
                    }
                    graph_tokens = (
                        len(
                            tokenizer.encode(
                                serialize(graph["projection"]), add_special_tokens=False
                            )
                        )
                        if graph["projection"]
                        else 0
                    )
                    measured.update(
                        prompt_tokens_rendered=count,
                        context_required=count + reserve,
                        components=costs,
                        component_percentages={k: v / count * 100 for k, v in costs.items()},
                        unallocated_boundary_difference=count - sum(costs.values()),
                        graph_projection_tokens=graph_tokens,
                        fit={str(n): classify(count, reserve, n) for n in LIMITS},
                    )
                    if model.startswith("Qwen/"):
                        thinking_count = render_count(tokenizer, messages, thinking=True)
                        measured.update(
                            thinking_prompt_tokens_rendered=thinking_count,
                            thinking_extra_reserve=4096,
                            thinking_fit_sensitivity={
                                str(n): classify(thinking_count, reserve + 4096, n) for n in LIMITS
                            },
                        )
                row["models"][model] = measured
            rows.append(row)
    summary = {}
    for model in MODELS:
        by_agent = {}
        for agent in sorted({r["agent"] for r in rows}):
            calls = [r for r in rows if r["agent"] == agent]
            counts = [
                r["models"][model]["prompt_tokens_rendered"]
                for r in calls
                if r["models"][model]["prompt_tokens_rendered"] is not None
            ]
            by_agent[agent] = dict(
                request_count=len(calls),
                input=stats(counts),
                observed_output=stats(
                    [
                        r["completion_tokens_observed"]
                        for r in calls
                        if r["completion_tokens_observed"] is not None
                    ]
                ),
                reserve=stats([r["reserved_output_tokens"] for r in calls]),
                fit={
                    str(n): dict(Counter(r["models"][model]["fit"][str(n)] for r in calls))
                    for n in LIMITS
                },
            )
        summary[model] = by_agent
    save(out / "scenarios.json", scenarios)
    save(out / "per-call.json", rows)
    save(out / "statistics.json", summary)
    unchanged = all(digest((root / p).read_bytes()) == sha for p, sha in sources.items())
    save(out / "source-integrity.json", dict(files=sources, unchanged=unchanged))
    assert unchanged
    llama_config = out / "configs/llama-official.json"
    if download and not llama_config.exists():
        fetch_llama_config(llama_config)
    vram = {}
    for model, params in zip(MODELS, (14.8e9, 8.2e9, 8.03e9), strict=True):
        config_path = cache / model.replace("/", "--") / "config.json"
        if model.startswith("meta-llama/") and not config_path.exists():
            config_path = llama_config
        if not config_path.exists():
            vram[model] = dict(status="unavailable", reason="official config unavailable")
            continue
        config = json.loads(config_path.read_bytes())
        weights = params * 0.5 / 2**30
        vram[model] = dict(
            status="estimate",
            config=config,
            parameters_approx=params,
            weights_4bit_lower_bound_gib=weights,
            weights_with_overhead_gib=[weights * 1.1, weights * 1.3],
            runtime_reserve_gib=[1.5, 3.0],
            kv_bytes_per_token=kv_bytes(config, 1),
            windows={
                str(n): dict(
                    kv_gib=kv_bytes(config, n) / 2**30,
                    total_range_gib=[
                        weights * 1.1 + 1.5 + kv_bytes(config, n) / 2**30,
                        weights * 1.3 + 3.0 + kv_bytes(config, n) / 2**30,
                    ],
                )
                for n in LIMITS
            },
        )
    save(out / "vram.json", vram)
    print(f"{len(scenarios)} scenarios / {len(rows)} calls; source hashes unchanged={unchanged}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--download-tokenizers", action="store_true")
    args = parser.parse_args()
    run(args.root.resolve(), args.download_tokenizers)
