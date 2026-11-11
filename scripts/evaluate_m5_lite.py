"""Bounded BBS M5 Lite evaluation, no OCR, no benchmark, no M6/M7 live calls.

--live is a single reservation, max four network calls, no retries. Case A uses
lexical Supervisor + live Specialist (one call); B uses live Supervisor + two
live Specialists (three calls). No runtime case-name routing.
"""

import argparse
import hashlib
import json
from pathlib import Path

from evaluate_generalization import pipeline
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    SupervisorLite,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    LLMResponse,
    ResponseProvenance,
    Usage,
    parse_json_output,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input

OUTPUT = Path("artifacts/evidence/M5-LITE-01")
CASES = [
    (
        "A",
        "Doanh thu thuần năm 2025 và tăng trưởng doanh thu 2025 so với 2024 của BBS là bao nhiêu?",
    ),
    (
        "B",
        "So sánh doanh thu thuần và lợi nhuận gộp giữa 2024 và 2025, đồng thời phân tích tổng tài sản và tổng nợ phải trả năm 2025 của BBS.",
    ),
]


def save(name, value):
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class EvaluationGateway:
    def __init__(self, gateway):
        self.gateway, self.events = gateway, []

    def generate(self, request):
        size = sum(len(m.content) for m in request.messages)
        if len(self.events) >= 4:
            raise ValueError("evaluation_call_budget_exhausted")
        if size > 8000:
            raise ValueError("evaluation_input_limit")
        # Reserve before transport, including provider/JSON errors; never retry.
        event = dict(
            request_id=request.request_id,
            input_chars=size,
            max_output_tokens=request.generation.max_output_tokens,
        )
        self.events.append(event)
        save("provider-events.json", self.events)
        response = self.gateway.generate(request)
        event.update(
            status=response.status,
            usage=response.usage.model_dump(mode="json"),
            error=response.error.model_dump(mode="json") if response.error else None,
        )
        save("provider-events.json", self.events)
        return response


class RecordedGateway:
    """Offline replay only; provider status and original payloads remain intact."""

    def __init__(self, saved):
        self.saved = saved

    def generate(self, request):
        from vietnamese_financial_multi_agent.core.llm_gateway import _failure

        if request.request_id.startswith("m5-lite-supervisor-"):
            payload = json.loads(self.saved["trace"][0]["reasons"][0])
            metadata = self.saved["usage"]["stages"]["planning"]
        else:
            role = next(
                role
                for role in self.saved["routing_decision"]["selected_roles"]
                if request.request_id.startswith("m5-lite-" + role + "-")
            )
            execution = next(e for e in self.saved["specialist_executions"] if e["role"] == role)
            payload, metadata = execution["result"]["raw_output"], execution["llm"]
        if metadata["status"] != "success":
            return _failure(request, "provider_unavailable")
        return LLMResponse(
            contract_version="llm_gateway_v1",
            request_id=request.request_id,
            status="success",
            finish_reason="stop",
            correlation=request.correlation,
            provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
            usage=Usage.model_validate(metadata["usage"]),
            cost=Cost.model_validate(metadata["cost"]),
            output=parse_json_output(json.dumps(payload)),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.live:
        with (OUTPUT / "live-reserved.json").open("x", encoding="utf-8") as stream:
            json.dump(dict(max_calls=4, retry=False, token_limit=20000), stream)
    service, _ = pipeline(Path.cwd(), "BBS_2025", OUTPUT / "smoke")
    catalog = service.catalog
    before = (
        hashlib.sha256(catalog.model_dump_json().encode()).hexdigest()
        if hasattr(catalog, "model_dump_json")
        else None
    )
    doc = service.documents[0]
    descriptor = next(d for d in catalog.descriptors if d.document_id == doc.document_id)
    context = PlannerContext(
        document_id=doc.document_id,
        company_id=doc.company_id,
        snapshot_id=descriptor.snapshot_id,
        mode="gemini" if args.live or args.replay else "deterministic",
    )
    gateway = None
    if args.live:
        adapter, _ = create_qa_adapter(Path.cwd())
        gateway = EvaluationGateway(SharedLLMGateway({"gemini": adapter}))
    results = []
    for name, question in CASES:
        if args.replay:
            saved = next(
                r
                for r in json.loads((OUTPUT / "live.json").read_text(encoding="utf-8"))
                if r["case"] == name
            )
            gateway = RecordedGateway(saved["output"])
        supervisor = SupervisorLite() if name == "A" else SupervisorLite(gateway)
        engine = FinancialLiteOrchestrator(catalog, gateway, supervisor=supervisor)
        result = engine.run(question=question, context=context)
        batch = to_verification_input(result)
        row = dict(
            case=name,
            question=question,
            output=result.model_dump(mode="json"),
            m6_adapter=batch.model_dump(mode="json"),
        )
        results.append(row)
        save(
            "replay.json" if args.replay else "live.json" if args.live else "offline.json", results
        )
        print(
            name,
            result.status,
            "agents",
            result.routing_decision.selected_roles,
            "candidates",
            len(batch.claims),
            "adapter issues",
            len(batch.issues),
            flush=True,
        )
        if args.replay:
            assert batch.claims and not batch.issues
        elif gateway:
            tokens = sum(e.get("usage", {}).get("total_tokens") or 0 for e in gateway.events)
            if tokens >= 20000 or any(e.get("error") for e in gateway.events):
                print("Provider error/token limit: stop without retry", flush=True)
                break
        else:
            assert batch.claims and not batch.issues
    if not args.live and not args.replay:
        # One real integration smoke: native M6 is the only path to admission.
        response = service.run(
            FinancialQARequest(
                question=CASES[0][1],
                document_id=doc.document_id,
                company_id=doc.company_id,
                snapshot_id=descriptor.snapshot_id,
                m5_lite=True,
                m7_lite=True,
                execution_mode="deterministic",
                force_refresh=True,
            )
        )
        save("pipeline-smoke.json", response.model_dump(mode="json"))
        assert response.trace.stages["m5"].status in {"completed", "partial"}
        assert response.trace.stages["m6"].status != "NOT_EXECUTED"
        accepted = {
            o.verified_claim_id for o in response.trace.outcomes if o.final_decision == "ACCEPT"
        }
        assert set(response.used_verified_claim_ids) <= accepted
        assert response.trace.provider_calls == 0
        print(
            "Native M6/Ledger/M7 smoke", response.status, "accepted", response.newly_accepted_claims
        )
    if before is not None:
        assert hashlib.sha256(catalog.model_dump_json().encode()).hexdigest() == before


if __name__ == "__main__":
    main()
