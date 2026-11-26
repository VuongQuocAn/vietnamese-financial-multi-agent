"""Run V2 from a natural question or the locked six-question experiment."""

import argparse
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from threading import Condition, Lock
from time import perf_counter
from uuid import uuid4

import httpx
from dotenv import dotenv_values
from vietnamese_financial_multi_agent.agents.eo_v2 import MODEL, EvidenceObligationAgent
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.openai_adapter import OpenAIAdapter, OpenAISettings
from vietnamese_financial_multi_agent.tools.eo_v2_evidence import (
    DocumentResolver,
    EvidenceWorkspace,
)
from vietnamese_financial_multi_agent.tools.hybrid_rag import HybridRAGTool

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts/evidence"
PILOT = EVIDENCE / "OPENAI-GENERALIZATION-PILOT-01"
BACKUP = ROOT.with_name("multi_agent")
LIMIT = Decimal("0.10")
INPUT_PRICE = Decimal("0.00000015")
OUTPUT_PRICE = Decimal("0.00000060")
URL = "https://api.openai.com/v1"
CASES = {"VFB-SH-0105", "VFB-SH-0142", "VFB-MH-0052", "VFB-MH-0176", "VFB-NR-0048", "VFB-NR-0181"}
CODE = [
    "src/agents/eo_v2.py",
    "src/tools/eo_v2_evidence.py",
    "scripts/run_agent_v2.py",
    "src/agents/NR_FORMULA_GUIDE.md",
    "src/agents/MH_EVIDENCE_GUIDE.md",
]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def save(path, value, secret=""):
    data = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if secret and secret in data:
        raise ValueError("credential_detected_in_trace")
    with path.open("x", encoding="utf-8") as stream:
        stream.write(data)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def runtime():
    return {
        str(path.relative_to(ROOT)): sha(path)
        for path in sorted((ROOT / "src").rglob("*.py"))
        if path.relative_to(ROOT).as_posix() not in CODE
    }


def load_selected():
    original = read(PILOT / "selection.json")
    selected = [
        {key: row[key] for key in ("id", "type", "question")}
        for row in original["selected"]
        if row["id"] in CASES
    ]
    assert len(selected) == 6 and {row["id"] for row in selected} == CASES
    assert all(sum(row["type"] == kind for row in selected) == 2 for kind in ("SH", "MH", "NR"))
    return selected


def assets(root):
    os.environ.update(
        RAG_PROJECTION_ROOT=str(root / "artifacts/evidence/RAG-CHUNK-01/run-02"),
        RAG_INDEX_ROOT=str(root / "artifacts/evidence/RAG-HYBRID-01/index-01"),
        RAG_MODEL_CACHE=str(root / "artifacts/models/huggingface"),
        HF_HUB_OFFLINE="1",
    )


class Budget:
    def __init__(self, limit=LIMIT):
        self.limit = limit
        self.lock = Lock()
        self.condition = Condition(self.lock)
        self.total = Decimal("0")
        self.unknown_usage_bound = Decimal("0")
        self.reserved = Decimal("0")
        self.stop = None

    def reserve(self, data, limit):
        # Count each UTF-8 byte plus framing as a conservative upper bound on input tokens.
        maximum = (len(data) + 1024) * INPUT_PRICE + limit * OUTPUT_PRICE
        with self.condition:
            while (
                not self.stop
                and self.reserved
                and self.total + self.unknown_usage_bound + maximum
                <= self.limit
                < self.total + self.unknown_usage_bound + self.reserved + maximum
            ):
                self.condition.wait()
            if (
                self.stop
                or self.total + self.unknown_usage_bound + self.reserved + maximum > self.limit
            ):
                self.stop = self.stop or "budget_limit"
                raise httpx.RequestError(self.stop)
            self.reserved += maximum
        return maximum

    def finish(self, maximum, usage, status):
        with self.condition:
            self.reserved -= maximum
            self.condition.notify_all()
            if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
                cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                actual = (Decimal(usage["prompt_tokens"]) - Decimal(cached) / 2) * INPUT_PRICE
                actual += usage["completion_tokens"] * OUTPUT_PRICE
                self.total += actual
                return str(actual)
            if status is None or status == 200:
                self.unknown_usage_bound += maximum
        return None


def execute_case(resolver, row, out, settings, hybrid, budget, paired=False, formula_guide=True):
    target = out / row["id"]
    target.mkdir()
    pair_root = target
    if paired:
        target = pair_root / "shared"
        target.mkdir()
    wire = []
    started = perf_counter()
    agent = None
    try:
        sources = EvidenceWorkspace(resolver, hybrid)
        with httpx.HTTPTransport(retries=0, trust_env=False) as transport:

            def send(request):
                body = json.loads(request.content)
                if request.url != httpx.URL(URL + "/chat/completions") or body["model"] != MODEL:
                    raise httpx.RequestError("different_provider_or_model")
                reserve = budget.reserve(request.content, body["max_completion_tokens"])
                index = len(wire) + 1
                call_start = perf_counter()
                raw, parsed, status = None, None, None
                try:
                    save(target / f"{index:02d}-request.json", body, settings.api_key)
                    raw = transport.handle_request(request)
                    raw.read()
                    status = raw.status_code
                    if settings.api_key.encode() in raw.content:
                        raise httpx.RequestError("credential_detected_in_response")
                    (target / f"{index:02d}-response.json").write_bytes(raw.content)
                    try:
                        parsed = raw.json()
                    except ValueError:
                        parsed = {}
                    model = parsed.get("model")
                    if (
                        status in {401, 403, 429}
                        or (status is not None and status >= 500)
                        or (status == 200 and model not in {MODEL, "gpt-4o-mini-2024-07-18"})
                    ):
                        with budget.lock:
                            budget.stop = f"incompatible_provider_response_{status}"
                        raise httpx.RequestError(budget.stop)
                    return raw
                finally:
                    usage = (parsed or {}).get("usage")
                    cost = budget.finish(reserve, usage, status)
                    wire.append(
                        dict(
                            index=index,
                            http_status=status,
                            model=(parsed or {}).get("model"),
                            usage=usage,
                            seconds=perf_counter() - call_start,
                            cost_usd=cost,
                        )
                    )

            with httpx.Client(transport=httpx.MockTransport(send), trust_env=False) as client:
                gateway = SharedLLMGateway({"openai": OpenAIAdapter(settings, client=client)})
                agent = EvidenceObligationAgent(
                    gateway,
                    sources,
                    row["question"],
                    uuid4().hex,
                    row.get("filing"),
                    formula_guide=formula_guide and not paired,
                )
                if not paired:
                    result = agent.run()
                else:
                    agent.prepare()
                    shared = agent.snapshot()
                    shared.update(item=row, api=wire, seconds=perf_counter() - started)
                    save(target / "result.json", shared, settings.api_key)
                    # Each branch owns its mutable request-local workspace, obligations and trace.
                    other = deepcopy(
                        agent, {id(gateway): gateway, id(resolver): resolver, id(hybrid): hybrid}
                    )
                    other.request_id = uuid4().hex
                    other.formula_guide = True
                    results = {}
                    for label, branch in (("A", agent), ("B", other)):
                        target = pair_root / label
                        target.mkdir()
                        wire = []
                        branch_start = perf_counter()
                        try:
                            branch_result = branch.run_prepared()
                        except Exception as error:
                            branch_result = branch.snapshot()
                            detail = (
                                str(error).replace(settings.api_key, "[redacted]")
                                if settings.api_key
                                else str(error)
                            )
                            branch_result.update(
                                status="technical_failure",
                                error=type(error).__name__,
                                detail=detail,
                            )
                        branch_result.update(
                            item=row,
                            api=wire,
                            seconds=perf_counter() - branch_start,
                            branch=label,
                            shared="../shared/result.json",
                        )
                        save(target / "result.json", branch_result, settings.api_key)
                        results[label] = branch_result["status"]
                        print(
                            f"{row['id']} {label} {branch_result['status']} {len(wire)} calls",
                            flush=True,
                        )
                    return results
    except Exception as error:
        result = agent.snapshot() if agent else {}
        detail = str(error)
        if settings.api_key:
            detail = detail.replace(settings.api_key, "[redacted]")
        result.update(status="technical_failure", error=type(error).__name__, detail=detail)
        print(f"{row['id']} {type(error).__name__}", flush=True)
    result.update(item=row, api=wire, seconds=perf_counter() - started)
    save(target / "result.json", result, settings.api_key)
    print(f"{row['id']} {result['status']} {len(wire)} calls {result['seconds']:.1f}s", flush=True)
    return result


def execute_group(rows, resolver, out, settings, budget, paired=False, formula_guide=True):
    hybrid = HybridRAGTool()
    try:
        for row in rows:
            if budget.stop:
                break
            execute_case(resolver, row, out, settings, hybrid, budget, paired, formula_guide)
    finally:
        hybrid.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pilot", action="store_true")
    mode.add_argument("--manifest", type=Path)
    mode.add_argument("--question")
    parser.add_argument("--paired-guide", action="store_true")
    parser.add_argument("--no-formula-guide", action="store_true")
    parser.add_argument("--filing")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--assets", type=Path, default=BACKUP)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--budget", type=Decimal, default=LIMIT)
    parser.add_argument("--workers", type=int, default=3, choices=(1, 2, 3, 4))
    args = parser.parse_args()
    if not Decimal("0") < args.budget <= Decimal("0.60"):
        parser.error("Budget must be positive and at most 0.60 USD.")
    if (args.pilot or args.manifest) and args.filing:
        parser.error("--filing is only available with --question")
    if args.paired_guide and not args.manifest:
        parser.error("--paired-guide requires --manifest")
    root = args.assets.resolve()
    metadata = args.metadata or ROOT / "ViFinBench/benchmark/document_metadata.json"
    if not metadata.is_file():
        parser.error(f"Provide document metadata at {metadata} or use --metadata.")
    corpus = root / "artifacts/evidence/VFB-IMPORT-03/full-final"
    resolver = DocumentResolver(metadata, root / "ViFinBench/refined", corpus)
    assets(root)
    env = dotenv_values(ROOT / ".env", interpolate=False)
    settings = OpenAISettings.from_environment(
        {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY") or "",
            "OPENAI_BASE_URL": URL,
            "DACNTT_LLM_MODEL": MODEL,
        }
    )
    assert HybridRAGTool().available
    if args.pilot or args.manifest:
        rows = (
            load_selected()
            if args.pilot
            else [
                {key: row[key] for key in ("id", "type", "question")}
                for row in read(args.manifest)["selected"]
            ]
        )
        assert (len(rows) == 9 if args.paired_guide else 1 <= len(rows) <= 90) and len(
            {r["id"] for r in rows}
        ) == len(rows)
        assert all(r["type"] in {"NR"} if args.paired_guide else {"SH", "MH", "NR"} for r in rows)
        paths = {metadata.resolve(), corpus / "catalog-index.json"}
        for key in resolver.metadata:
            symbol, year = key.split("_")
            paths.update((corpus / key).rglob("*.json"))
            paths.update((corpus / key).rglob("*.jsonl"))
            paths.update((resolver.refined / symbol / year).glob("page_*.json"))
        for path in (Path(os.environ["RAG_INDEX_ROOT"]), Path(os.environ["RAG_PROJECTION_ROOT"])):
            paths.update(p for p in path.rglob("*") if p.is_file())
        pinned = {p: sha(p) for p in sorted(paths)}
    else:
        rows = [dict(id="qa", filing=args.filing, question=args.question)]
        pinned = {metadata.resolve(): sha(metadata.resolve())}
    default = EVIDENCE / "AGENT-V2-05-LIVE" / ("live" if args.pilot else uuid4().hex[:12])
    out = (args.output or default).resolve()
    out.mkdir(parents=True, exist_ok=False)
    cfg = dict(
        commit=git("rev-parse", "HEAD"),
        branch=git("branch", "--show-current"),
        model=MODEL,
        workers=args.workers,
        budget_usd=str(args.budget),
        cases=rows,
        paired_guide=args.paired_guide,
        formula_guide=not args.no_formula_guide,
        metadata_sha256=sha(metadata),
        source_files={
            (path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name): digest
            for path, digest in pinned.items()
        },
        implementation={name: sha(ROOT / name) for name in CODE},
        v1=runtime(),
    )
    save(out / "batch-lock.json", cfg, settings.api_key)
    budget = Budget(args.budget)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        jobs = [
            executor.submit(
                execute_group,
                rows[i :: args.workers],
                resolver,
                out,
                settings,
                budget,
                args.paired_guide,
                not args.no_formula_guide,
            )
            for i in range(args.workers)
        ]
        for job in jobs:
            job.result()
    if args.question:
        result = read(out / "qa/result.json")
        print(result.get("answer") or "Chua du bang chung de tra loi.", flush=True)
    outputs = {
        p.relative_to(out).as_posix(): sha(p)
        for p in sorted(out.rglob("*.json"))
        if p.name != "batch-lock.json"
    }
    save(
        out / "completion.json",
        dict(
            stop=budget.stop,
            known_cost_usd=str(budget.total),
            unknown_usage_upper_usd=str(budget.unknown_usage_bound),
            outputs=outputs,
            v1_preserved=cfg["v1"] == runtime(),
            sources_preserved=all(sha(p) == h for p, h in pinned.items()),
            code_preserved=all(sha(ROOT / p) == h for p, h in cfg["implementation"].items()),
        ),
        settings.api_key,
    )


if __name__ == "__main__":
    main()
