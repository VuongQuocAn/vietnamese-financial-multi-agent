"""One live C01/C07/C10 pass; QA gaps continue, infrastructure errors stop."""

import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter


class ValidationStopped(BaseException):
    """Bypass pipeline fallbacks so a provider failure cannot trigger another call."""


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BudgetedGateway:
    def __init__(self, gateway, output, events, case):
        self.gateway, self.output, self.events, self.case = gateway, output, events, case

    def generate(self, request):
        if len(self.events) >= 18 or sum(e["case"] == self.case for e in self.events) >= 6:
            raise ValidationStopped("call_budget_exhausted")
        event = dict(case=self.case, request=request.export(), status="STARTED")
        self.events.append(event)
        save(self.output / "provider-events.json", self.events)
        started = perf_counter()
        response = self.gateway.generate(request)
        event.update(
            status=response.status,
            response=response.export(),
            elapsed_seconds=perf_counter() - started,
        )
        save(self.output / "provider-events.json", self.events)
        print(self.case, "call", len(self.events), response.status, flush=True)
        if response.error and response.error.category not in {
            "structured_output_invalid",
            "schema_mismatch",
            "safety",
        }:
            raise ValidationStopped("provider_non_success_fail_stop")
        return response


def validate(root, output, case, owner, implementation):
    implementation = subprocess.check_output(
        ["git", "rev-parse", implementation], cwd=root, text=True
    ).strip()
    fingerprint = hashlib.sha256(
        json.dumps(
            [owner[k] for k in ("BASE_URL", "API_KEY", "MODEL_NAME")], separators=(",", ":")
        ).encode()
    ).hexdigest()
    previous = read(root / "artifacts/evidence/V2-INT-01/live-confirmation-20261113/manifest.json")
    assert fingerprint == previous["provider_configuration_sha256"], "owner_configuration_changed"
    manifest_path, state_path = output / "manifest.json", output / "results.json"
    if not manifest_path.exists():
        assert case == "C01" and not output.exists(), "fresh_output_required"
        output.mkdir(parents=True)
        archive = subprocess.check_output(
            ["git", "archive", "--format=zip", implementation, "src"], cwd=root
        )
        zipfile.ZipFile(io.BytesIO(archive)).extractall(output / "frozen")
        references = read(root / "artifacts/evidence/E2E-GEN-01/references.json")
        save(
            output / "gold-references.json",
            [r for r in references if r["id"] in {"C01", "C07", "C10"}],
        )
        save(
            manifest_path,
            dict(
                started_utc=datetime.now(UTC).isoformat(),
                implementation_commit=implementation,
                cases=["C01", "C07", "C10"],
                max_calls=18,
                max_calls_per_case=6,
                token_precount=False,
                max_total_tokens=None,
                token_usage_source="provider_reported_when_available",
                timeout_per_case_seconds=300,
                retries=0,
                provider_configuration_sha256=fingerprint,
                model=owner["MODEL_NAME"],
            ),
        )
        save(state_path, dict(status="PREPARED", cases=[]))
        save(output / "provider-events.json", [])
    state, manifest = read(state_path), read(manifest_path)
    assert manifest["implementation_commit"] == implementation
    assert manifest["provider_configuration_sha256"] == fingerprint
    assert not any(row["case"] == case for row in state["cases"]), "case_already_attempted_no_retry"
    if case != "C01":
        assert state["status"] == "AWAITING_QA_REVIEW"
        expected = ["C01"] if case == "C07" else ["C01", "C07"]
        assert [row["case"] for row in state["cases"]] == expected
    else:
        assert state["status"] == "PREPARED"

    # Import the approved implementation, never the unrelated local runtime edits.
    import vietnamese_financial_multi_agent as package

    package.__path__ = [str(output / "frozen/src")]
    from evaluate_composition_graph import bbs_catalog
    from evaluate_generalization import pipeline
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.core.qwen_adapter import QwenAdapter, QwenSettings

    events = read(output / "provider-events.json")
    adapter = QwenAdapter(QwenSettings(owner["BASE_URL"], owner["API_KEY"], owner["MODEL_NAME"]))
    gateway = BudgetedGateway(SharedLLMGateway({"qwen": adapter}), output, events, case)
    # Only the original request is reused. Every provider response comes from live Qwen.
    original = read(root / f"artifacts/evidence/E2E-GEN-01/execution/{case}.json")["request"]
    catalog = bbs_catalog(root)
    service, _ = pipeline(
        root, "BCC_2025" if case == "C10" else "BBS_2025", output / "inputs" / case, catalog
    )
    service.gateway = gateway
    request = FinancialQARequest.model_validate(original).model_copy(
        update=dict(
            integration_v2=True,
            model=ModelIdentity(provider="qwen", model=owner["MODEL_NAME"]),
            force_refresh=True,
            max_provider_calls=6,
            request_timeout_seconds=300.0,
        )
    )
    row = dict(case=case, status="STARTED")
    state["cases"].append(row)
    state["status"] = "IN_PROGRESS"
    save(state_path, state)
    save(output / f"request-{case}.json", request.model_dump(mode="json"))
    started = perf_counter()
    try:
        response = service.run(request)
        save(
            output / f"execution/{case}.json",
            dict(
                request=request.model_dump(mode="json"),
                response=response.model_dump(mode="json"),
                ledger=[e.model_dump(mode="json") for e in service.repository.list_all()],
            ),
        )
        row.update(status="COMPLETED", pipeline_status=response.status)
        state["status"] = "AWAITING_QA_REVIEW"
        print(case, "FINAL", response.status, flush=True)
    except ValidationStopped as error:
        row["status"] = "INTERRUPTED"
        state.update(status="STOPPED", reason=str(error))
        print("STOPPED", str(error), flush=True)
    except Exception as error:
        row["status"] = "INTERRUPTED"
        state.update(status="STOPPED", reason="local_exception", error_type=type(error).__name__)
        print("STOPPED local_exception", type(error).__name__, flush=True)
    finally:
        row["elapsed_seconds"] = perf_counter() - started
        row["calls"] = sum(e["case"] == case for e in events)
        state.update(
            calls=len(events),
            known_tokens=sum(
                e.get("response", {}).get("usage", {}).get("total_tokens") or 0 for e in events
            ),
            unknown_usage_calls=sum(
                e.get("response", {}).get("usage", {}).get("total_tokens") is None for e in events
            ),
        )
        save(state_path, state)
        adapter.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["C01", "C07", "C10"], required=True)
    parser.add_argument("--implementation", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config-file", type=Path)
    args = parser.parse_args()
    owner = (
        read(args.config_file)
        if args.config_file
        else json.loads(sys.stdin.readline().lstrip("\ufeff"))
    )
    validate(
        Path(__file__).resolve().parents[1],
        args.output.resolve(),
        args.case,
        owner,
        args.implementation,
    )
