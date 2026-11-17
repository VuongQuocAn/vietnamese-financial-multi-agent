"""Replay saved M5 Python on real JSON; cap at two M6 calls, no M5/M7 calls."""

import argparse
import json
import subprocess
from copy import deepcopy
from pathlib import Path

from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.tools.python_execution import PythonExecutor, digest
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--saved-m5", type=Path, required=True)
    parser.add_argument("--document-alias", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    saved_wire = args.saved_m5.read_text(encoding="utf-8")
    original = OrchestrationResult.model_validate_json(saved_wire)
    company, year = args.document_alias.rsplit("_", 1)
    source_dir = args.storage_root / "ViFinBench/refined" / company / year
    before = {p.name: digest(p.read_text(encoding="utf-8-sig")) for p in source_dir.glob("*.json")}
    catalog = load_json_corpus_document(
        args.storage_root / "ViFinBench/refined",
        args.storage_root / "artifacts/evidence/VFB-IMPORT-03/full-final",
        args.document_alias,
    )
    worker = PythonExecutor()
    assert worker.preflight()["status"] == "ready"
    batch = to_verification_input(original)
    python_claims = [c for c in batch.claims if c.python_execution]
    assert len(python_claims) == 1
    if args.offline:
        runtime = LiteVerificationRuntime(catalog, integration_v2=True)
        histories = runtime.verify(batch, integration_context=original.integration_context)
        atomic_json(args.output / "histories.json", [h.model_dump(mode="json") for h in histories])
        atomic_json(args.output / "summary.json", runtime.summary)
        print(
            json.dumps(
                dict(
                    mode="offline",
                    decisions=runtime.summary["decisions"],
                    python_replay=bool(histories[-1].proof.python_replay),
                )
            )
        )
        return

    configured = create_text_gateway(root, provider="qwen")
    events = []

    def transport(request):
        assert len(events) < 2 and request.request_id.startswith("m6-")
        response = configured.adapter(request)
        events.append(
            dict(request=request.model_dump(mode="json"), response=response.model_dump(mode="json"))
        )
        atomic_json(args.output / "provider-events.json", events)
        print(json.dumps(dict(call=len(events), status=response.status)), flush=True)
        return response

    gateway = SharedLLMGateway({"qwen": transport})

    class SavedM5:
        def run(self, **kwargs):
            assert kwargs["question"] == original.question
            return original.model_copy(deep=True)

    try:
        atomic_json(
            args.output / "saved-m5-input.json",
            dict(source_sha256=digest(saved_wire), m5=original.model_dump(mode="json")),
        )
        request = FinancialQARequest(
            question=original.question,
            company_id=original.context.company_id,
            document_id=original.context.document_id,
            snapshot_id=original.context.snapshot_id,
            integration_v2=True,
            # Reuse the exact saved adaptive Workspace; do not schedule M5 repairs.
            adaptive_coordinator=False,
            m5_lite=True,
            m6_lite=True,
            m7_lite=True,
            execution_mode="gemini",
            model=configured.model,
            allow_gateway=True,
            max_provider_calls=2,
        )
        service = FinancialQAPipeline(
            catalog=catalog,
            gateway=gateway,
            orchestrator=SavedM5(),
            documents=[
                QADocument(
                    document_id=original.context.document_id,
                    company_id=original.context.company_id,
                    company_aliases=[company],
                    reporting_year=int(year),
                )
            ],
            repository=VerifiedClaimRepository(args.output / "ledger"),
        )
        response = service.run(request)
        atomic_json(
            args.output / "correct.json",
            dict(
                request=request.model_dump(mode="json"), response=response.model_dump(mode="json")
            ),
        )
        print(
            json.dumps(
                dict(
                    case="correct",
                    status=response.status,
                    m7=response.trace.m7_status,
                    decisions=response.trace.native_decisions,
                    citations=len(response.citations),
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )

        # Adversarial control: remove the square root, keep original RMS spec/goal.
        # Execute to create a reproducible yet dimensionally/financially wrong candidate.
        wrong = original.model_copy(deep=True)
        context = wrong.integration_context
        tid = next(t for t, r in context["task_results"].items() if r.get("python_candidate"))
        record = deepcopy(context["task_results"][tid]["python_candidate"])
        execution = record["executions"][-1]
        assert ".sqrt()" in execution["code"]
        execution["code"] = execution["code"].replace(".sqrt()", "")
        execution["code_digest"] = digest(execution["code"])
        recomputed = worker.execute(
            execution["code"], record["operands"], execution["outputs"], execution["constants"]
        )
        assert recomputed["status"] == "success"
        execution.update(recomputed)
        record["results"] = recomputed["results"]
        context["tasks"][tid]["python_candidate"] = record
        result = context["task_results"][tid]
        result["python_candidate"] = record
        result["digest"] = digest({k: v for k, v in result.items() if k != "digest"})
        wrong_batch = to_verification_input(wrong)
        wrong_batch.claims = [c for c in wrong_batch.claims if c.python_execution]
        runtime = LiteVerificationRuntime(
            catalog, gateway, model=configured.model, integration_v2=True
        )
        histories = runtime.verify(wrong_batch, integration_context=context)
        admission = VerifiedClaimRepository(args.output / "wrong-ledger").admit(histories[0])
        atomic_json(
            args.output / "wrong-formula.json",
            dict(
                m5=wrong.model_dump(mode="json"),
                histories=[h.model_dump(mode="json") for h in histories],
                summary=runtime.summary,
                admission=admission.model_dump(mode="json"),
            ),
        )
        print(
            json.dumps(
                dict(
                    case="wrong_formula",
                    decision=histories[0].outcome.final.decision,
                    replay=bool(histories[0].proof.python_replay),
                    admission=admission.status,
                )
            ),
            flush=True,
        )
    finally:
        configured.close()
        after = {
            p.name: digest(p.read_text(encoding="utf-8-sig")) for p in source_dir.glob("*.json")
        }
        assert before == after
        atomic_json(
            args.output / "receipt.json",
            dict(
                implementation_sha=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                runtime_hashes={
                    p.relative_to(root).as_posix(): digest(p.read_text(encoding="utf-8"))
                    for p in (root / "src").rglob("*.py")
                },
                saved_m5_sha256=digest(saved_wire),
                source_hashes=before,
                source_unchanged=before == after,
                calls=len(events),
                known_tokens=sum(e["response"]["usage"].get("total_tokens") or 0 for e in events),
                unknown_usage=sum(
                    e["response"]["usage"].get("total_tokens") is None for e in events
                ),
                worker=worker.preflight(),
            ),
        )


if __name__ == "__main__":
    main()
