"""Pilot-only frozen input and bounded live run; Gold is never sent to runtime."""

import argparse
import json
import re
import subprocess
import traceback
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from run_e2e_arch02 import sha
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.tools.python_execution import PythonExecutor
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

GROUPS = ("single_hop", "multi_hop", "numerical")
DIFFICULTIES = ("easy", "medium", "hard")


def pilot_inputs(storage):
    """Explicit allowlist: never discover/open full.jsonl or its metadata."""
    return [storage / "ViFinBench/benchmark" / g / "pilot.jsonl" for g in GROUPS]


def select_cases(storage):
    metadata = json.loads((storage / "ViFinBench/benchmark/document_metadata.json").read_bytes())
    cases = []
    for group, path in zip(GROUPS, pilot_inputs(storage), strict=True):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()]
        assert len(rows) == 15 and len({r["id"] for r in rows}) == 15
        for difficulty in DIFFICULTIES:
            row = next(r for r in rows if r["difficulty"] == difficulty)
            question = row["question"]
            documents = row.get("input_documents")
            if documents is None:
                # SH only: issuer aliases and year from question/input metadata, never evidence.
                years = {int(y) for y in re.findall(r"\b20\d{2}\b", question)}
                documents = [
                    alias
                    for alias, meta in metadata.items()
                    if meta["fiscal_year"] in years
                    and any(name.casefold() in question.casefold() for name in meta["aliases"])
                ]
            if len(documents) != 1:
                raise ValueError(f"input_document_not_unique:{row['id']}")
            cases.append(
                dict(
                    id=row["id"],
                    group=group,
                    difficulty=difficulty,
                    question=question,
                    document_alias=documents[0],
                )
            )
    return cases


def prepare(root, storage, output):
    cases = select_cases(storage)
    output.mkdir(parents=True, exist_ok=False)
    (output / "provider").mkdir()
    (output / "results").mkdir()
    atomic_json(output / "questions-only.json", cases)
    sources = {
        p.relative_to(storage).as_posix(): sha(p)
        for alias in {c["document_alias"] for c in cases}
        for p in (storage / "ViFinBench/refined" / Path(*alias.split("_"))).rglob("*.json")
    }
    atomic_json(
        output / "receipt.json",
        dict(
            baseline_sha=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            prepared_at_utc=datetime.now(UTC).isoformat(),
            selection="first item per difficulty per group, before Gold inspection",
            runtime_hashes={
                p.relative_to(root).as_posix(): sha(p) for p in (root / "src").rglob("*.py")
            },
            runner_sha256=sha(Path(__file__)),
            source_hashes=sources,
            pilot_hashes={p.relative_to(storage).as_posix(): sha(p) for p in pilot_inputs(storage)},
            question_manifest_sha256=sha(output / "questions-only.json"),
            settings=dict(total_call_cap=90, per_question_cap=10, timeout_seconds=300, retries=0),
        ),
    )
    print(json.dumps(dict(prepared=len(cases), ids=[c["id"] for c in cases])), flush=True)


def run(root, storage, output, ids, *, corpus=None, response_hook=None):
    receipt = json.loads((output / "receipt.json").read_bytes())
    assert sha(output / "questions-only.json") == receipt["question_manifest_sha256"]
    assert sha(Path(__file__)) == receipt["runner_sha256"]
    for key, base in (
        ("runtime_hashes", root),
        ("source_hashes", storage),
        ("pilot_hashes", storage),
    ):
        assert all(sha(base / p) == h for p, h in receipt[key].items()), key
    assert all(sha(storage / p) == h for p, h in receipt.get("imported_hashes", {}).items()), (
        "imported_hashes"
    )
    corpus = corpus or storage / "artifacts/evidence/VFB-IMPORT-03/full-final"
    cases = json.loads((output / "questions-only.json").read_bytes())
    if ids and set(ids) - {c["id"] for c in cases}:
        raise ValueError("id_not_in_frozen_pilot_sample")
    receipt["worker"] = PythonExecutor().preflight()
    atomic_json(output / "receipt.json", receipt)
    configured = create_text_gateway(root, provider="qwen")
    if response_hook is not None:
        configured.adapter.client.event_hooks["response"].append(response_hook)
    used = len(list((output / "provider").glob("*.json")))
    current, first = None, used

    def transport(request):
        nonlocal used
        if (
            used >= receipt["settings"]["total_call_cap"]
            or used - first >= receipt["settings"]["per_question_cap"]
        ):
            return _failure(request, "quota_exceeded")
        used += 1
        event = dict(
            case_id=current,
            attempt=used,
            started_at_utc=datetime.now(UTC).isoformat(),
            request=request.model_dump(mode="json"),
        )
        path = output / "provider" / f"{used:03}.json"
        atomic_json(path, event)  # Durable before network; no endpoint/auth is serialized.
        started = perf_counter()
        response = configured.adapter(request)
        event.update(
            response=response.model_dump(mode="json"),
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )
        atomic_json(path, event)
        print(json.dumps(dict(case=current, call=used, status=response.status)), flush=True)
        return response

    gateway = SharedLLMGateway({"qwen": transport})
    try:
        for case in cases:
            if ids and case["id"] not in ids:
                continue
            current = case["id"]
            result_path = output / "results" / f"{current}.json"
            if result_path.exists():
                raise ValueError("existing_result_not_overwritten")
            first, started = used, perf_counter()
            payload = dict(case=case, started_at_utc=datetime.now(UTC).isoformat())
            try:
                catalog = load_json_corpus_document(
                    storage / "ViFinBench/refined",
                    corpus,
                    case["document_alias"],
                )
                descriptor = catalog.descriptors[0]
                companies = {f.company_id for f in catalog.facts if f.company_id}
                assert len(companies) == 1, "unresolved_company"
                company = next(iter(companies))
                service = FinancialQAPipeline(
                    catalog=catalog,
                    gateway=gateway,
                    documents=[
                        QADocument(
                            document_id=descriptor.document_id,
                            company_id=company,
                            company_aliases=[case["document_alias"].split("_")[0]],
                            reporting_year=int(case["document_alias"].split("_")[1]),
                        )
                    ],
                    repository=VerifiedClaimRepository(output / "ledgers" / current),
                )
                request = FinancialQARequest(
                    request_id=current,
                    question=case["question"],
                    document_id=descriptor.document_id,
                    snapshot_id=descriptor.snapshot_id,
                    company_id=company,
                    model=configured.model,
                    allow_gateway=True,
                    execution_mode="auto",
                    integration_v2=True,
                    adaptive_coordinator=True,
                    m5_lite=True,
                    m6_lite=True,
                    m7_lite=True,
                    m5_graph=True,
                    force_refresh=True,
                    max_provider_calls=receipt["settings"]["per_question_cap"],
                    request_timeout_seconds=receipt["settings"]["timeout_seconds"],
                )
                payload["request"] = request.model_dump(mode="json")
                payload["load_seconds"] = round(perf_counter() - started, 3)
                run_started = perf_counter()
                payload["response"] = service.run(request).model_dump(mode="json")
                payload["pipeline_seconds"] = round(perf_counter() - run_started, 3)
            except Exception:
                payload["exception"] = traceback.format_exc()
            payload.update(
                wall_seconds=round(perf_counter() - started, 3), transport_attempts=used - first
            )
            atomic_json(result_path, payload)
            response = payload.get("response", {})
            print(
                json.dumps(
                    dict(
                        id=current,
                        status=response.get("status", "runner_exception"),
                        calls=used - first,
                        seconds=payload["wall_seconds"],
                        citations=len(response.get("citations", [])),
                    ),
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        configured.close()
        events = [json.loads(p.read_bytes()) for p in sorted((output / "provider").glob("*.json"))]
        receipt.update(
            calls=used,
            completed_responses=sum("response" in e for e in events),
            known_tokens=sum(
                e.get("response", {}).get("usage", {}).get("total_tokens") or 0 for e in events
            ),
            unknown_usage=sum(
                e.get("response", {}).get("usage", {}).get("total_tokens") is None for e in events
            ),
            sources_unchanged=all(
                sha(storage / p) == h for p, h in receipt["source_hashes"].items()
            ),
            runtime_unchanged=all(sha(root / p) == h for p, h in receipt["runtime_hashes"].items()),
            pilot_unchanged=all(sha(storage / p) == h for p, h in receipt["pilot_hashes"].items()),
            imported_unchanged=all(
                sha(storage / p) == h for p, h in receipt.get("imported_hashes", {}).items()
            ),
        )
        atomic_json(output / "receipt.json", receipt)
        assert (
            receipt["sources_unchanged"]
            and receipt["runtime_unchanged"]
            and receipt["pilot_unchanged"]
            and receipt["imported_unchanged"]
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    storage, output = args.storage_root.resolve(), args.output.resolve()
    if not output.is_relative_to(storage / "artifacts/evidence/E2E-VAL-01"):
        parser.error("output must remain in E2E-VAL-01 evidence storage")
    if args.mode == "prepare":
        prepare(root, storage, output)
    else:
        run(root, storage, output, args.ids)


if __name__ == "__main__":
    main()
