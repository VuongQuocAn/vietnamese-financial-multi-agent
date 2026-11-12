"""Small opt-in Qwen smoke from frozen local references; never retries."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from evaluate_composition_graph import bbs_catalog
from evaluate_generalization import pipeline
from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_contracts import LLMRequest
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class ProviderStopped(BaseException):
    """Escape application fallback immediately after an unavailable API."""


class SmokeGateway:
    def __init__(self, gateway, output):
        self.gateway, self.output, self.events = gateway, output, []
        self.case = "preflight"

    def generate(self, request):
        event = dict(case=self.case, request=request.export(), status="started")
        self.events.append(event)
        save(self.output / "provider-events.json", self.events)
        start = perf_counter()
        response = self.gateway.generate(request)
        event.update(
            response=response.export(),
            status=response.status,
            latency_ms=(perf_counter() - start) * 1000,
        )
        save(self.output / "provider-events.json", self.events)
        if response.error and response.error.category in {
            "provider_unavailable",
            "timeout",
            "authentication",
            "authorization",
        }:
            raise ProviderStopped(response.error.category)
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if (
        not args.allow_live
        or not 1 <= len(args.cases) <= 4
        or len(set(args.cases)) != len(args.cases)
    ):
        parser.error("--allow-live and 1–4 distinct cases required")
    refs = json.loads(args.references.read_text(encoding="utf-8"))
    cases = [next(q for q in refs if q["id"] == key) for key in args.cases]
    root = Path.cwd()
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence/QWEN-GEN-02"):
        parser.error("output must stay in task ignored evidence directory")
    output.mkdir(parents=True, exist_ok=False)
    runtime = {
        p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "src").rglob("*.py")
    }
    state = dict(
        status="IN_PROGRESS",
        started_utc=datetime.now(UTC).isoformat(),
        reference_sha256=hashlib.sha256(args.references.read_bytes()).hexdigest(),
        cases=[dict(id=q["id"], status="NOT_RUN") for q in cases],
    )
    configured = create_text_gateway(root, provider="qwen", config_file=args.config)
    gateway = SmokeGateway(configured.gateway, output)
    try:
        preflight = gateway.generate(
            LLMRequest(
                contract_version="llm_gateway_v1",
                request_id="qwen-gen-02-preflight",
                model=configured.model,
                messages=[dict(role="user", content="Reply OK.")],
                generation=dict(temperature=0.0, max_output_tokens=8),
                constraints=dict(timeout_seconds=30.0),
            )
        )
        if preflight.status not in {"success", "partial"}:
            state["status"] = "PREFLIGHT_CONTENT_ERROR"
            return
        catalogs, services = bbs_catalog(root), {}
        for q, row in zip(cases, state["cases"], strict=True):
            if q["label"] not in services:
                services[q["label"]], _ = pipeline(root, q["label"], output / "inputs", catalogs)
            service = services[q["label"]]
            service.gateway = gateway
            service.repository = VerifiedClaimRepository(output / q["id"] / "ledger")
            doc = service.documents[0]
            snapshot = next(
                d.snapshot_id
                for d in service.catalog.descriptors
                if d.document_id == doc.document_id
            )
            # Financial selection and document source selection have different
            # snapshot namespaces. Notes search all verified composition pins.
            intent, _ = document_intent(q["question"])
            request = FinancialQARequest(
                question=q["question"],
                document_id=doc.document_id,
                company_id=doc.company_id,
                snapshot_id=None if intent == "document" else snapshot,
                model=configured.model,
                m5_lite=True,
                m6_lite=True,
                m7_lite=True,
                force_refresh=True,
                allow_gateway=True,
                execution_mode="auto",
                max_provider_calls=6,
                request_timeout_seconds=300,
            )
            gateway.case = q["id"]
            row["status"] = "STARTED"
            save(output / "results.json", state)
            response = service.run(request)
            save(
                output / (q["id"] + ".json"),
                dict(
                    request=request.model_dump(mode="json"),
                    response=response.model_dump(mode="json"),
                    ledger=[e.model_dump(mode="json") for e in service.repository.list_all()],
                ),
            )
            row.update(status="COMPLETED", answer_status=response.status)
            print(q["id"], response.status, response.trace.native_decisions, flush=True)
            save(output / "results.json", state)
        state["status"] = "COMPLETED_PENDING_REVIEW"
    except ProviderStopped as exc:
        state.update(
            status="PAUSED — WAITING FOR OWNER", error=str(exc), interrupted_case=gateway.case
        )
        print("PAUSED", gateway.case, str(exc), flush=True)
    finally:
        configured.close()
        state.update(
            finished_utc=datetime.now(UTC).isoformat(),
            provider_attempts=len(gateway.events),
            runtime_unchanged=all(
                hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha
                for p, sha in runtime.items()
            ),
        )
        save(output / "results.json", state)
        save(output / "runtime-hashes.json", runtime)


if __name__ == "__main__":
    main()
