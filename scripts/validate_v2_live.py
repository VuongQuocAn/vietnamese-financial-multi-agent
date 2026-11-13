"""Owner-budgeted V2 smoke: three saved questions, one attempt, no provider retries."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from evaluate_composition_graph import bbs_catalog
from evaluate_generalization import pipeline
from evaluate_multi_agent_integration import must_stop
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway


class ValidationStopped(BaseException):
    pass


def save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BudgetedGateway:
    def __init__(self, gateway, output):
        self.gateway, self.output = gateway, output
        self.events = []
        self.tokens = 0
        self.case = None

    def generate(self, request):
        # UTF-8 bytes conservatively bound byte-level tokenization; include wire
        # metadata and chat-template allowance before authorizing the next call.
        reserve = len(json.dumps(request.export(), ensure_ascii=False).encode())
        reserve += request.generation.max_output_tokens + 2048
        if len(self.events) >= 18 or self.tokens + reserve > 180000:
            raise ValidationStopped("total_budget_reservation_exhausted")
        event = dict(case=self.case, request=request.export(), status="STARTED")
        self.events.append(event)
        save(self.output / "provider-events.json", self.events)
        response = self.gateway.generate(request)
        event.update(status=response.status, response=response.export())
        save(self.output / "provider-events.json", self.events)
        used = response.usage.total_tokens
        if used is None:
            raise ValidationStopped("unknown_token_usage")
        self.tokens += used
        if self.tokens > 180000:
            raise ValidationStopped("provider_usage_exceeded_reserved_budget")
        if must_stop(response):
            raise ValidationStopped("provider_error_fail_stop")
        return response


def validate(root, config, output):
    if (output / "manifest.json").exists():
        raise ValueError("single_pass_already_started_no_automatic_resume")
    if not (output.parent / "offline/replay.json").is_file():
        raise ValueError("offline_replay_required")
    old = root / "artifacts/evidence/E2E-GEN-01"
    cases = [
        ("C01", "BBS_2025"),
        ("C10", "BCC_2025"),
        ("C07", "BBS_2025"),
    ]
    originals = {
        case: json.loads((old / f"execution/{case}.json").read_text(encoding="utf-8"))["request"]
        for case, _ in cases
    }
    configured = create_text_gateway(root, provider="qwen", config_file=config)
    settings = configured.adapter.settings
    owner = json.loads(config.read_text(encoding="utf-8"))
    if (settings.base_url, settings.api_key, settings.model) != (
        owner["BASE_URL"],
        owner["API_KEY"],
        owner["MODEL_NAME"],
    ):
        configured.close()
        raise ValueError("environment_configuration_differs_from_owner_config")
    save(
        output / "manifest.json",
        dict(
            started_utc=datetime.now(UTC).isoformat(),
            cases=[case for case, _ in cases],
            max_calls=18,
            max_tokens=180000,
            max_calls_per_case=6,
            timeout_per_case_seconds=300,
            retries=0,
            model=configured.model.export(),
            source_runtime={
                str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (root / "src").rglob("*.py")
            },
        ),
    )
    save(output / "questions.json", originals)
    gateway = BudgetedGateway(configured.gateway, output)
    state = dict(status="IN_PROGRESS", cases=[], calls=0, tokens=0)
    catalogs = bbs_catalog(root)
    try:
        for case, label in cases:
            gateway.case = case
            row = dict(case=case, status="STARTED")
            state["cases"].append(row)
            save(output / "results.json", state)
            service, _ = pipeline(root, label, output / "inputs" / case, catalogs)
            service.gateway = gateway
            request = FinancialQARequest.model_validate(originals[case]).model_copy(
                update=dict(
                    integration_v2=True,
                    model=configured.model,
                    force_refresh=True,
                    max_provider_calls=6,
                    request_timeout_seconds=300.0,
                )
            )
            started = perf_counter()
            response = service.run(request)
            save(
                output / f"execution/{case}.json",
                dict(
                    request=request.export()
                    if hasattr(request, "export")
                    else request.model_dump(mode="json"),
                    response=response.model_dump(mode="json"),
                    ledger=[e.model_dump(mode="json") for e in service.repository.list_all()],
                ),
            )
            row.update(
                status="COMPLETED",
                pipeline_status=response.status,
                elapsed_seconds=perf_counter() - started,
                calls=response.trace.provider_calls,
                released_claims=len(response.used_verified_claim_ids),
            )
            print(case, response.status, row["calls"], "calls", flush=True)
        state["status"] = "COMPLETED"
    except ValidationStopped as error:
        state["status"] = "STOPPED"
        state["reason"] = str(error)
        if state["cases"] and state["cases"][-1]["status"] == "STARTED":
            state["cases"][-1]["status"] = "INTERRUPTED"
        print("Validation STOPPED:", state["reason"], flush=True)
    finally:
        state.update(calls=len(gateway.events), tokens=gateway.tokens)
        save(output / "results.json", state)
        configured.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/V2-INT-01/live"))
    args = parser.parse_args()
    validate(Path(__file__).resolve().parents[1], args.config_file, args.output)
