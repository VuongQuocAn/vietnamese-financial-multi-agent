"""Controlled scalar fault on saved real M5 output; never mutate source evidence."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from run_m5_coordinator_live import check_sources, prepare
from run_vfb_qwen_e2e import digest
from vietnamese_financial_multi_agent.agents.integration_workspace import (
    IntegrationRequirement,
    IntegrationWorkspace,
)
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
)
from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
from vietnamese_financial_multi_agent.agents.orchestrator import aggregate_candidates
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository


def replay(root, output, source):
    saved = json.loads(source.read_bytes())
    trace = saved["response"]["trace"]
    original = OrchestrationResult.model_validate_json(json.dumps(trace["financial_execution"]))
    context = deepcopy(original.integration_context)
    plan = LitePlan.model_validate_json(original.trace[0].reasons[0])
    supported = trace["m6_lite"]["supported_requirements"]
    parents = {tid for task in context["tasks"].values() for tid in task["depends_on"]}
    eligible = [
        c
        for c in original.candidates
        if c.kind == "fact"
        and not c.reasoning
        and len(c.origins) == 1
        and c.origins[0].execution_id not in parents
        and set(supported.get(c.candidate_id, [])).intersection(
            context["tasks"][c.origins[0].execution_id]["requirement_ids"]
        )
    ]
    selected = eligible[-1]
    tid = selected.origins[0].execution_id
    execution = next(e for e in original.specialist_executions if e.execution_id == tid)
    candidate = next(
        c for c in execution.result.candidates if c.candidate_id == selected.origins[0].candidate_id
    )
    before_content = candidate.content
    candidate.content = candidate.content.split(" là ")[0] + " là 999999999 VND."
    original.candidates, original.conflicts = aggregate_candidates(original.specialist_executions)
    prepare(root, output, None, 8, cases=[saved["case"]])
    atomic_json(
        output / "controlled-input.json",
        dict(
            mode="controlled_invalid_scalar_saved_m5",
            source_sha256=digest(source),
            task_id=tid,
            before_content=before_content,
            injected_content=candidate.content,
            source_evidence_unchanged=True,
            m5=original.model_dump(mode="json"),
        ),
    )
    configured = create_text_gateway(root, provider="qwen")
    calls = 0

    def transport(request):
        nonlocal calls
        assert calls < 8 and not request.request_id.startswith("m5-coordinator-plan-")
        calls += 1
        atomic_json(
            output / "provider" / f"{calls:03}-request.json", request.model_dump(mode="json")
        )
        response = configured.adapter(request)
        atomic_json(output / "provider" / f"{calls:03}.json", response.model_dump(mode="json"))
        return response

    class ReplayPipeline(FinancialQAPipeline):
        def _m5(self, request, *, catalog=None, **_):
            engine = FinancialLiteOrchestrator(catalog, self.gateway)
            workspace = engine.workspace = IntegrationWorkspace(
                [IntegrationRequirement.model_validate(r) for r in context["requirements"]],
                question=original.question,
                evidence=original.supervisor_result.evidence_bundle.model_copy(deep=True),
                tasks=deepcopy(context["tasks"]),
                task_results=deepcopy(context["task_results"]),
                observations=deepcopy(context["observations"]),
                expansion_used=True,
            )
            workspace.record_result(
                next(t for t in plan.tasks if t.task_id == tid), execution.result
            )
            original.integration_context = workspace.export(original.candidates)
            engine._active_plan = plan
            engine.run = lambda **_: original.model_copy(deep=True)
            return engine

    try:
        case = saved["case"]
        catalog = load_json_corpus_document(
            root / "ViFinBench/refined",
            root / "artifacts/evidence/VFB-IMPORT-03/full-final",
            case["document_alias"],
        )
        trusted = original.context
        service = ReplayPipeline(
            catalog=catalog,
            gateway=SharedLLMGateway({"qwen": transport}),
            documents=[
                QADocument(
                    document_id=trusted.document_id,
                    company_id=trusted.company_id,
                    company_aliases=[case["document_alias"].split("_")[0]],
                    reporting_year=int(case["document_alias"].split("_")[1]),
                )
            ],
            repository=VerifiedClaimRepository(output / "ledger"),
        )
        request = FinancialQARequest.model_validate(saved["request"]).model_copy(
            update=dict(
                request_id="controlled-feedback-replay",
                max_provider_calls=8,
                request_timeout_seconds=240,
            )
        )
        response = service.run(request)
        atomic_json(
            output / "result.json",
            dict(
                case=case,
                mode="controlled_invalid_scalar_saved_m5",
                actual_live_calls=calls,
                response=response.model_dump(mode="json"),
            ),
        )
        print(
            json.dumps(
                dict(
                    status=response.status,
                    actual_live_calls=calls,
                    decisions=response.trace.native_decisions,
                    repair=[
                        {
                            k: r.get(k)
                            for k in (
                                "rounds",
                                "repaired_task_ids",
                                "reused_task_ids",
                                "stop_reason",
                            )
                        }
                        for r in response.trace.adaptive_rounds
                    ],
                    released=len(response.used_verified_claim_ids),
                    citations=len(response.citations),
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        configured.close()
        check_sources(root, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saved-result", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/M5-COORD-03/controlled-replay")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = (root / args.output).resolve()
    source = (root / args.saved_result).resolve()
    allowed = root / "artifacts/evidence/M5-COORD-03"
    if not destination.is_relative_to(allowed) or not source.is_relative_to(allowed):
        parser.error("paths outside M5-COORD-03")
    replay(root, destination, source)
