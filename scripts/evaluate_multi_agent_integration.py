"""E2E-GEN-01: one frozen Qwen pass, durable traces, fail-stop and owner resume."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from evaluate_composition_graph import bbs_catalog
from evaluate_generalization import pipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_contracts import LLMRequest
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProviderStopped(BaseException):
    """Bypass runtime Exception fallbacks so no next provider call can be made."""


def must_stop(response):
    error = response.error
    return bool(
        error
        and (
            error.category
            in {
                "provider_unavailable",
                "timeout",
                "authentication",
                "authorization",
                "invalid_configuration",
                "rate_limit",
            }
            or error.provider_error_code == "http_400"
        )
    )


class TracedGateway:
    def __init__(self, gateway, output, events=()):
        self.gateway, self.output = gateway, output
        self.events = list(events)
        self.case = "preflight"

    def generate(self, request):
        event = dict(case=self.case, request=request.export(), status="started")
        self.events.append(event)
        save(self.output / "provider-events.json", self.events)
        started = perf_counter()
        response = self.gateway.generate(request)
        event.update(
            response=response.export(),
            status=response.status,
            latency_ms=(perf_counter() - started) * 1000,
        )
        save(self.output / "provider-events.json", self.events)
        print(
            self.case,
            response.status,
            response.error.category if response.error else "",
            flush=True,
        )
        if must_stop(response):
            raise ProviderStopped(response.error.export())
        return response


def request_for(reference, service, model, configuration):
    doc = service.documents[0]
    assert doc.document_id == reference["document_id"]
    return FinancialQARequest(
        question=reference["question"],
        document_id=doc.document_id,
        company_id=doc.company_id,
        # None allows the composition's verified document pins, not a financial
        # snapshot ID accidentally used in the document namespace.
        snapshot_id=reference["request_snapshot_id"],
        model=model,
        **configuration,
    )


def run(root, base, config, *, resume=False):
    def read(name):
        return json.loads((base / name).read_text(encoding="utf-8"))

    freeze = read("freeze.json")
    references = read("references.json")
    assert len(references) == len({q["id"] for q in references}) == 12
    assert all(digest(base / p) == sha for p, sha in freeze["files"].items())
    assert all(digest(root / p) == sha for p, sha in freeze["protected"].items())
    if resume:
        state = read("results.json")
        assert state["status"] == "PAUSED — WAITING FOR OWNER"
        assert not any(r["status"] == "STARTED" for r in state["cases"])
        events = read("provider-events.json")
    else:
        assert not (base / "run-manifest.json").exists(), "one pass only; use owner resume"
        state = dict(
            status="IN_PROGRESS",
            cases=[dict(id=q["id"], status="NOT_RUN") for q in references],
        )
        events = []
    configured = create_text_gateway(root, provider="qwen", config_file=config)
    # Compare credentials/config without ever writing their contents or URL.
    settings = configured.adapter.settings
    identity = hashlib.sha256(
        json.dumps([settings.base_url, settings.api_key, settings.model]).encode()
    ).hexdigest()
    assert identity == freeze["provider_configuration_sha256"], "configuration_changed"
    gateway = TracedGateway(configured.gateway, base, events)
    state["status"] = "IN_PROGRESS"
    save(base / "results.json", state)
    if not resume:
        save(
            base / "run-manifest.json",
            dict(
                started_utc=datetime.now(UTC).isoformat(),
                freeze_sha256=digest(base / "freeze.json"),
            ),
        )
    active = None
    try:
        response = gateway.generate(
            LLMRequest(
                contract_version="llm_gateway_v1",
                request_id="e2e-gen-01-preflight",
                model=configured.model,
                messages=[dict(role="user", content="Reply OK.")],
                generation=dict(temperature=0.0, max_output_tokens=8),
                constraints=dict(timeout_seconds=30.0),
            )
        )
        if response.status not in {"success", "partial"} or response.error:
            raise ProviderStopped("preflight_inference_failed")
        services, catalogs = {}, bbs_catalog(root)
        for q, row in zip(references, state["cases"], strict=True):
            if row["status"] == "COMPLETED":
                continue
            assert all(digest(root / p) == sha for p, sha in freeze["runtime_hashes"].items())
            if q["label"] not in services:
                services[q["label"]], _ = pipeline(root, q["label"], base / "inputs", catalogs)
            service = services[q["label"]]
            service.gateway = gateway
            service.repository = VerifiedClaimRepository(base / "execution" / q["id"] / "ledger")
            request = request_for(q, service, configured.model, read("evaluation-config.json"))
            gateway.case, active = q["id"], row
            row["status"] = "STARTED"
            save(base / "results.json", state)
            started = perf_counter()
            try:
                response = service.run(request)
                payload = dict(response=response.model_dump(mode="json"))
                row.update(status="COMPLETED", answer_status=response.status)
            except ProviderStopped:
                row["status"] = "INTERRUPTED"
                raise
            except Exception as exc:
                # A schema/output/local error consumes this attempt, never retries.
                payload = dict(exception_type=type(exc).__name__)
                row.update(status="COMPLETED", answer_status="LOCAL_ERROR")
            finally:
                save(
                    base / "execution" / (q["id"] + ".json"),
                    dict(
                        request=request.model_dump(mode="json"),
                        elapsed_seconds=perf_counter() - started,
                        status=row["status"],
                        ledger=[e.model_dump(mode="json") for e in service.repository.list_all()],
                        **(payload if row["status"] == "COMPLETED" else {}),
                    ),
                )
                save(base / "results.json", state)
            print(q["id"], row["answer_status"], flush=True)
            active = None
        state["status"] = "COMPLETED_PENDING_AUDIT"
    except ProviderStopped as exc:
        if active is not None:
            active["status"] = "INTERRUPTED"
        state.update(
            status="PAUSED — WAITING FOR OWNER", stopped_at=gateway.case, error=exc.args[0]
        )
        print("PAUSED", gateway.case, flush=True)
    finally:
        configured.close()
        state.update(
            finished_utc=datetime.now(UTC).isoformat(), provider_attempts=len(gateway.events)
        )
        save(base / "results.json", state)
        save(
            base / "integrity.json",
            dict(
                protected_unchanged=all(
                    digest(root / p) == sha for p, sha in freeze["protected"].items()
                ),
                references_unchanged=all(
                    digest(base / p) == sha for p, sha in freeze["files"].items()
                ),
            ),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--owner-confirmed-resume", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    base = args.artifacts.resolve()
    if not args.allow_live or not base.is_relative_to(root / "artifacts/evidence/E2E-GEN-01"):
        parser.error("explicit live opt-in and task artifact directory required")
    run(root, base, args.config, resume=args.owner_confirmed_resume)


if __name__ == "__main__":
    main()
