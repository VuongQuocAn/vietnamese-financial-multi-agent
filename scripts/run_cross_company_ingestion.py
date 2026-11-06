"""GEN-01: bounded research composition of production M1–M4, no M5–M8.

Manifest metadata is independently read from PDF, never inferred from filename.
All evidence stays in a new ignored output directory. No credential rotation.
"""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from google import genai
from google.genai import types
from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    EXTRACTION_REF,
    ExtractedPage,
)
from vietnamese_financial_multi_agent.accounting.financial_runtime import process_financial_pdf
from vietnamese_financial_multi_agent.accounting.quality import (
    assess_evidence_for_task,
    evidence_from_automated_records,
)
from vietnamese_financial_multi_agent.api.document_store import atomic_json
from vietnamese_financial_multi_agent.api.metadata_service import (
    POOL_CREDENTIAL,
    FreeTierKeyPool,
    MetadataGeminiAdapter,
    MetadataLLMService,
)
from vietnamese_financial_multi_agent.api.qa_gateway import resolve_qa_credential
from vietnamese_financial_multi_agent.core.llm_quota_budget import QuotaLimits
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry
from vietnamese_financial_multi_agent.document_processing.financial_discovery import (
    DISCOVERY_REF,
    PagePrediction,
    discover_financial_pages,
)
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import MODEL
from vietnamese_financial_multi_agent.evidence import (
    SnapshotDescriptor,
    build_graph,
    evidence_from_persisted_result,
    facts_from_persisted_result,
    validate_graph,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class BoundedService:
    """Persist a conservative send reservation BEFORE each one-attempt SDK call."""

    def __init__(self, service, output):
        self.service, self.output = service, output
        self.state = load(output / "budget.json")
        self.stage, self.document, self.stage_limit, self.stage_calls = "", "", 0, 0

    def phase(self, document, stage, limit):
        self.document, self.stage = document, stage
        self.stage_limit, self.stage_calls = limit, 0

    def generate(self, request, **kwargs):
        if self.state["reserved_attempts"] >= 60 or self.stage_calls >= self.stage_limit:
            return SimpleNamespace(response=None)
        # Respect the existing pool's minute quota without provider retries.
        pool = self.service.pool
        while True:
            recent = [r for r in pool.ledger["recent"] if r["time"] > time.time() - 61]
            bound = kwargs["reservation"].token_upper_bound
            if not recent or (
                len(recent) < pool.limits.rpm
                and sum(r["tokens"] for r in recent) + bound <= pool.limits.tpm
            ):
                break
            time.sleep(min(5, max(0.1, min(r["time"] for r in recent) + 61 - time.time())))
        self.stage_calls += 1
        self.state["reserved_attempts"] += 1
        atomic_json(self.output / "budget.json", self.state)
        started = time.monotonic()
        result = self.service.generate(request, **kwargs)
        record = dict(
            document=self.document,
            stage=self.stage,
            request_id=request.request_id,
            seconds=round(time.monotonic() - started, 3),
            attempts=self.service.last_attempts,
            status=result.response.status if result.response else None,
            reason=result.guard_result.reason if result.guard_result else "cache_hit",
        )
        with (self.output / "requests.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        print(
            json.dumps({k: record[k] for k in ("document", "stage", "seconds", "status")}),
            flush=True,
        )
        return result


def ingest(entry, output, service):
    folder = output / entry["name"]
    folder.mkdir(exist_ok=False)
    source = Path(entry["path"])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    snapshot = str(uuid4())
    result = dict(
        document_id=f"sha256:{digest}",
        attempt_id=snapshot,
        metadata=entry["metadata"],
        company_id=entry["company_id"],
        model=MODEL,
        inventory=[],
        records=[],
        quality=None,
        stages=[],
    )
    options = dict(
        symbol=entry["source_symbol"],
        year=str(entry["metadata"]["reporting_year"]),
        service=service,
        credential_ref=POOL_CREDENTIAL,
        model=MODEL,
    )
    service.phase(entry["name"], "discovery", 15)
    started = time.monotonic()

    def persist_page(page):
        result["inventory"].append(page)
        atomic_json(folder / "result.json", result)

    discover_financial_pages(source, **options, on_page=persist_page)
    result["stages"].append(dict(stage="discovery", seconds=time.monotonic() - started))
    # Budget prioritizes automatically discovered primary forms. Unclassified pages
    # remain selected in inventory but explicitly deferred, never silently excluded.
    selected = [p for p in result["inventory"] if p["statement_type"] in {"B01", "B02", "B03"}]
    selected.sort(key=lambda p: (p["statement_type"], p["page"]))
    service.phase(entry["name"], "extraction", 8)
    started = time.monotonic()
    for page in selected:
        if service.stage_calls >= service.stage_limit:
            break
        part = process_financial_pdf(source, **options, pages=[page["page"]])
        result["records"].extend(part["records"])
        atomic_json(folder / "result.json", result)
    result["stages"].append(dict(stage="extraction", seconds=time.monotonic() - started))
    extracted = {r["source"]["page"]["page"] for r in result["records"]}
    for page in result["inventory"]:
        page["extraction_status"] = (
            "attempted"
            if page["page"] in extracted
            else "deferred_budget"
            if page["selected"]
            else "not_selected"
        )
    valid = [
        r
        for r in result["records"]
        if "invalid_extraction_response" not in r["extraction"]["issues"]
    ]
    quality = assess_evidence_for_task(evidence_from_automated_records(valid))
    result["quality"] = quality.model_dump(mode="json")
    result["source_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == digest
    atomic_json(folder / "result.json", result)
    prepare(folder, result)


def prepare(folder, result):
    started = time.monotonic()
    facts = facts_from_persisted_result(result, company_id=result["company_id"])
    # The document adapter requires payload-bearing records. Provider failures
    # stay in result.json; they cannot supply text/table evidence.
    valid_result = dict(
        result,
        records=[
            r
            for r in result["records"]
            if "invalid_extraction_response" not in r["extraction"]["issues"]
        ],
    )
    evidence = evidence_from_persisted_result(valid_result)
    graph = build_graph(facts, evidence)
    validation = validate_graph(graph, facts, evidence)
    descriptor = SnapshotDescriptor(
        document_id=result["document_id"],
        pdf_sha256=result["document_id"].removeprefix("sha256:"),
        snapshot_id=result["attempt_id"],
        origin="original_extraction",
    )
    for name, value in (
        ("facts", [f.model_dump(mode="json") for f in facts]),
        ("evidence", [e.model_dump(mode="json") for e in evidence]),
        ("graph", graph.model_dump(mode="json")),
        ("graph-validation", validation.model_dump(mode="json")),
        ("descriptor", descriptor.model_dump(mode="json")),
    ):
        atomic_json(folder / f"{name}.json", value)
    summary = dict(
        facts=len(facts),
        evidence=len(evidence),
        graph_nodes=len(graph.nodes),
        graph_edges=len(graph.edges),
        graph_statuses=dict(Counter(a.status for a in validation.nodes + validation.edges)),
        mapped=dict(Counter(f.canonical_item_id for f in facts)),
        quality=result["quality"]["summary_counts"],
        preparation_seconds=time.monotonic() - started,
        financial_fact_verified=False,
    )
    atomic_json(folder / "summary.json", summary)
    print(json.dumps(dict(document=folder.name, **summary)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--continue-live", action="store_true", help="Reuse durable budget; skip saved documents"
    )
    parser.add_argument("--replay-from", type=Path, help="Offline re-normalization into new output")
    parser.add_argument(
        "--recover-invalid",
        action="store_true",
        help="One recovery per failed extracted page, same task budget",
    )
    args = parser.parse_args()
    entries = load(args.manifest)
    output = args.output.resolve()
    if not output.is_relative_to((Path.cwd() / "artifacts/evidence").resolve()):
        parser.error("output must be under artifacts/evidence")
    if not args.live:
        for entry in entries:
            folder = output / entry["name"]
            if args.replay_from:
                folder.mkdir(parents=True, exist_ok=False)
                result = load(args.replay_from / entry["name"] / "result.json")
                started = time.monotonic()
                cached = {r["source"]["page"]["page"]: r for r in result["records"]}
                part = process_financial_pdf(
                    Path(entry["path"]),
                    symbol=entry["source_symbol"],
                    year=str(entry["metadata"]["reporting_year"]),
                    pages=list(cached),
                    cached_records=cached,
                )
                result = dict(
                    result,
                    metadata=entry["metadata"],
                    records=part["records"],
                    quality=part["quality"].model_dump(mode="json"),
                )
                result["stages"].append(
                    dict(stage="normalization_replay", seconds=time.monotonic() - started)
                )
                atomic_json(folder / "result.json", result)
            else:
                result = load(folder / "result.json")
            prepare(folder, result)
        return
    # Exclusive marker prevents a restart from resetting the task budget.
    output.mkdir(parents=True, exist_ok=True)
    if args.continue_live:
        if (output / "live.started").read_text(encoding="utf-8") != MODEL:
            parser.error("live model binding mismatch")
        if load(output / "budget.json")["limit"] != 60:
            parser.error("task budget mismatch")
    else:
        with (output / "live.started").open("x", encoding="utf-8") as stream:
            stream.write(MODEL)
        atomic_json(output / "budget.json", dict(limit=60, reserved_attempts=0))
    credential = resolve_qa_credential(Path.cwd())
    schemas = LocalSchemaRegistry(
        [
            (DISCOVERY_REF, PagePrediction.model_json_schema()),
            (EXTRACTION_REF, ExtractedPage.model_json_schema()),
        ]
    )
    client = genai.Client(
        api_key=credential.key,
        vertexai=False,
        http_options=types.HttpOptions(
            timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    pool = FreeTierKeyPool(
        [MetadataGeminiAdapter(client, schema_registry=schemas)],
        SimpleNamespace(root=output),
        schemas=schemas,
        limits=QuotaLimits(rpm=15, tpm=250000, rpd=60),
        max_attempts=1,
    )
    try:
        service = BoundedService(MetadataLLMService(pool, schemas), output)
        for entry in entries:
            folder = output / entry["name"]
            if args.continue_live and (folder / "result.json").is_file():
                prepare(folder, load(folder / "result.json"))
            else:
                ingest(entry, output, service)
            if args.recover_invalid:
                recovered_folder = output / "recovery" / entry["name"]
                if (recovered_folder / "result.json").exists():
                    continue  # A bounded recovery has already been persisted.
                result = load(folder / "result.json")
                failed = [
                    r
                    for r in result["records"]
                    if "invalid_extraction_response" in r["extraction"]["issues"]
                    or any(
                        any(
                            count > 1
                            for count in Counter(
                                (c["row"], c["column"]) for c in [*t["headers"], *t["cells"]]
                            ).values()
                        )
                        for t in (
                            ((r.get("response") or {}).get("output") or {}).get("payload") or {}
                        ).get("tables", [])
                    )
                ]
                if not failed:
                    continue
                recovered_folder.mkdir(parents=True, exist_ok=False)
                service.phase(entry["name"], "recovery", len(failed))
                result["source_attempt_id"] = result["attempt_id"]
                result["attempt_id"] = str(uuid4())
                for record in failed:
                    number = record["source"]["page"]["page"]
                    part = process_financial_pdf(
                        Path(entry["path"]),
                        symbol=entry["source_symbol"],
                        year=str(entry["metadata"]["reporting_year"]),
                        pages=[number],
                        service=service,
                        credential_ref=POOL_CREDENTIAL,
                        model=MODEL,
                    )
                    result["records"] = [
                        part["records"][0] if r["source"]["page"]["page"] == number else r
                        for r in result["records"]
                    ]
                valid = [
                    r
                    for r in result["records"]
                    if "invalid_extraction_response" not in r["extraction"]["issues"]
                ]
                result["quality"] = assess_evidence_for_task(
                    evidence_from_automated_records(valid)
                ).model_dump(mode="json")
                atomic_json(recovered_folder / "result.json", result)
                prepare(recovered_folder, result)
    finally:
        pool.close()


if __name__ == "__main__":
    main()
