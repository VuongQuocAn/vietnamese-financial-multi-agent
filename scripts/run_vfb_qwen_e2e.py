"""VFB-E2E-03: frozen questions-only input, one bounded Qwen E2E pass."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import (
    load_json_catalog,
    load_json_corpus_document,
)
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

# SH filing bindings are read from the company/year in the question, not Gold
# evidence pages/tables. MH/NR use their declared input_documents, checked below.
SELECTION = {
    "single_hop": [
        (16, "ADC_2021"),
        (80, "ARM_2023"),
        (69, "AME_2023"),
        (71, "BTW_2025"),
        (173, "C69_2025"),
    ],
    "multi_hop": [
        (18, "ADC_2021"),
        (35, "AMC_2022"),
        (46, "ALT_2023"),
        (68, "BBS_2025"),
        (78, "BED_2025"),
    ],
    "numerical": [
        (16, "ADC_2021"),
        (18, "CAG_2025"),
        (77, "AMC_2025"),
        (103, "AME_2023"),
        (178, "BCC_2022"),
    ],
}
PREFIXES = {"single_hop": "SH", "multi_hop": "MH", "numerical": "NR"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root, output):
    output.mkdir(parents=True, exist_ok=False)
    (output / "provider").mkdir()
    (output / "results").mkdir()
    cases, inputs = [], {}
    for group, choices in SELECTION.items():
        path = root / "ViFinBench/benchmark" / group / "full.jsonl"
        rows = {
            row["id"]: row for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())
        }
        pilot = path.with_name("pilot.jsonl")
        pilot_rows = list(map(json.loads, pilot.read_text(encoding="utf-8").splitlines()))
        pilot_questions = {r["question"] for r in pilot_rows}
        pilot_ids = {r["id"] for r in pilot_rows}
        inputs[str(path.relative_to(root))] = digest(path)
        inputs[str(pilot.relative_to(root))] = digest(pilot)
        for number, alias in choices:
            identifier = f"VFB-{PREFIXES[group]}-{number:04}"
            row = rows[identifier]
            assert row["question"] not in pilot_questions and identifier not in pilot_ids
            if group != "single_hop":
                assert row["input_documents"] == [alias]
            cases.append(
                dict(
                    id=identifier,
                    group=group,
                    difficulty=row["difficulty"],
                    question=row["question"],
                    document_alias=alias,
                )
            )
    atomic_json(output / "questions-only.json", cases)
    runtime = sorted((root / "src").rglob("*.py"))
    atomic_json(
        output / "implementation.json",
        dict(
            baseline_sha=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            committed=False,
            prepared_at_utc=datetime.now(UTC).isoformat(),
            benchmark_hashes=inputs,
            runtime_hashes={str(p.relative_to(root)): digest(p) for p in runtime},
            runner_sha256=digest(Path(__file__)),
            corpus="artifacts/evidence/VFB-IMPORT-03/full-final",
            question_manifest_sha256=digest(output / "questions-only.json"),
            settings=dict(
                provider="qwen",
                max_calls_per_question=6,
                total_call_cap=90,
                timeout_seconds=300,
                graph_enabled=True,
                retries=0,
            ),
        ),
    )
    print(json.dumps(dict(prepared=len(cases), ids=[c["id"] for c in cases])))


def run(root, output, identifiers):
    # No benchmark files or evaluation files are opened by the answering path.
    receipt = json.loads((output / "implementation.json").read_bytes())
    assert digest(output / "questions-only.json") == receipt["question_manifest_sha256"]
    for name, expected in receipt["runtime_hashes"].items():
        assert digest(root / name) == expected, name
    cases = json.loads((output / "questions-only.json").read_bytes())
    configured = create_text_gateway(root, provider="qwen")
    events_path = output / "provider-events.jsonl"
    used = len(events_path.read_text().splitlines()) if events_path.exists() else 0
    current = None

    def transport(request):
        nonlocal used
        if used >= receipt["settings"]["total_call_cap"]:
            return _failure(request, "quota_exceeded")
        used += 1
        started = perf_counter()
        event = dict(
            case_id=current,
            attempt=used,
            started_at_utc=datetime.now(UTC).isoformat(),
            request=request.model_dump(mode="json"),
        )
        # Durable attempt before I/O; payload contains no HTTP auth/configuration.
        atomic_json(output / "provider" / f"{used:03}-request.json", event)
        with events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(case_id=current, attempt=used, status="started")) + "\n")
        response = configured.adapter(request)
        event.update(
            response=response.model_dump(mode="json"),
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )
        atomic_json(output / "provider" / f"{used:03}.json", event)
        return response

    gateway = SharedLLMGateway({"qwen": transport})
    try:
        for case in cases:
            if identifiers and case["id"] not in identifiers:
                continue
            current = case["id"]
            result_path = output / "results" / f"{current}.json"
            if result_path.exists():
                raise ValueError("existing_result_not_overwritten")
            loaded = perf_counter()
            bundle = receipt.get("document_bundles", {}).get(case["document_alias"])
            catalog = (
                load_json_catalog(root / "ViFinBench/refined", root / bundle)
                if bundle
                else load_json_corpus_document(
                    root / "ViFinBench/refined", root / receipt["corpus"], case["document_alias"]
                )
            )
            load_seconds = perf_counter() - loaded
            descriptor = catalog.descriptors[0]
            companies = {f.company_id for f in catalog.facts if f.company_id}
            company = next(iter(companies)) if len(companies) == 1 else None
            # Unknown company stays unknown: never manufacture issuer from ticker.
            documents = (
                []
                if company is None
                else [
                    QADocument(
                        document_id=descriptor.document_id,
                        company_id=company,
                        company_aliases=[case["document_alias"].split("_")[0]],
                        reporting_year=int(case["document_alias"].split("_")[1]),
                    )
                ]
            )
            service = FinancialQAPipeline(
                catalog=catalog,
                gateway=gateway,
                documents=documents,
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
                m5_graph=True,
                force_refresh=True,
                max_provider_calls=receipt["settings"].get("max_calls_per_question", 6),
                request_timeout_seconds=300,
            )
            first_attempt = used
            started_at = datetime.now(UTC).isoformat()
            started = perf_counter()
            response = service.run(request)
            payload = dict(
                case=case,
                started_at_utc=started_at,
                request=request.model_dump(mode="json"),
                response=response.model_dump(mode="json"),
                load_seconds=round(load_seconds, 3),
                wall_seconds=round(perf_counter() - started, 3),
                transport_attempts=used - first_attempt,
            )
            atomic_json(result_path, payload)
            print(
                json.dumps(
                    dict(
                        id=current,
                        status=response.status,
                        calls=used - first_attempt,
                        tokens=response.trace.known_total_tokens,
                        seconds=payload["wall_seconds"],
                        agents=response.trace.executed_agents,
                        decisions=response.trace.native_decisions,
                        errors=response.trace.errors,
                    ),
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        configured.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/VFB-E2E-03/run-v1"))
    parser.add_argument("--ids", nargs="+")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    destination = (project_root / args.output).resolve()
    if not destination.is_relative_to(project_root / "artifacts/evidence/VFB-E2E-03"):
        parser.error("output must remain in VFB-E2E-03 artifacts")
    if args.mode == "prepare":
        prepare(project_root, destination)
    else:
        run(project_root, destination, args.ids)
