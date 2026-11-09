"""FIX-02: eight frozen real-PDF cases, actual Gateway, fresh isolated ledger.

Source/reference payloads and detailed traces remain under ignored artifacts.
Every execution is persisted, including failures; no automatic output retries.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

from evaluate_real_pdf import build, digest, save
from evaluate_real_pdf import protected as protected_inputs
from vietnamese_financial_multi_agent.api.conversations import ConversationService
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/FIX-02/live"))
    parser.add_argument("--mode", choices=["auto", "deterministic"], default="auto")
    parser.add_argument(
        "--case-id",
        action="append",
        choices=["Q01", "Q11", "Q21", "Q08", "Q22", "Q33", "Q34", "F08"],
    )
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh_output_directory_required")
    root = Path.cwd()
    inputs = root / "artifacts/evidence/E2E-02"
    questions = {q["id"]: q for q in json.loads((inputs / "questions.json").read_bytes())}
    cases = [dict(questions[key]) for key in ("Q01", "Q11", "Q21", "Q08", "Q22", "Q33", "Q34")]
    cases.append(dict(id="F08", question="Như thế có đáng lo không?", conversation="analysis"))
    cases[2]["conversation"] = "analysis"
    for case in cases:
        if case["id"] in {"Q33", "Q34"}:
            case["conversation"] = "source"
    if args.case_id:
        cases = [case for case in cases if case["id"] in args.case_id]
    protected = protected_inputs(root)
    protected = {name: value for name, value in protected.items() if not name.startswith("src/")}
    save(
        args.output / "freeze.json",
        dict(
            cases=cases,
            mode=args.mode,
            references_sha256=digest(inputs / "reference.json"),
            protected=protected,
            runtime_files={
                p.relative_to(root).as_posix(): digest(p) for p in (root / "src").rglob("*.py")
            },
        ),
    )
    pipeline = build(root, args.output)
    attempts = []
    if args.mode == "auto":
        adapter, _ = create_qa_adapter(root)

        def transport(request):
            if len(attempts) >= 100:
                raise ValueError("evaluation_provider_budget_exhausted")
            started = perf_counter()
            response = adapter(request)
            save(
                args.output / "provider" / (request.request_id + ".json"),
                dict(
                    request=request.model_dump(mode="json"),
                    response=response.model_dump(mode="json"),
                ),
            )
            attempts.append(
                dict(
                    request_id=request.request_id,
                    status=response.status,
                    tokens=response.usage.total_tokens,
                    error=response.error.code if response.error else None,
                    latency_ms=(perf_counter() - started) * 1000,
                )
            )
            save(args.output / "provider-attempts.json", attempts)
            return response

        pipeline.gateway = SharedLLMGateway({"gemini": transport})
    service, sessions, results = ConversationService(pipeline), {}, []
    for case in cases:
        started = perf_counter()
        request = FinancialQARequest(
            question=case["question"],
            force_refresh=True,
            execution_mode=args.mode,
            allow_gateway=args.mode == "auto",
            max_provider_calls=20,
            request_timeout_seconds=180,
        )
        row = dict(id=case["id"], question=case["question"])
        try:
            if case.get("conversation"):
                key = case["conversation"]
                if key not in sessions:
                    sessions[key] = service.create().conversation_id
                turn = service.send(sessions[key], request)
                row["conversation"] = turn.model_dump(mode="json")
                response = turn.response
            else:
                response = pipeline.run(request)
            row["actual"] = response.model_dump(mode="json")
        except Exception as error:
            row["runtime_error"] = type(error).__name__
        row["elapsed_ms"] = (perf_counter() - started) * 1000
        results.append(row)
        save(args.output / "results.json", results)
        print(
            case["id"],
            row.get("actual", {}).get("status", "RUNTIME_ERROR"),
            round(row["elapsed_ms"]),
            row.get("actual", {}).get("trace", {}).get("provider_calls", 0),
            flush=True,
        )
    save(
        args.output / "integrity.json",
        dict(
            protected_count=len(protected),
            protected_unchanged=all(digest(root / p) == h for p, h in protected.items()),
            references_unchanged=digest(inputs / "reference.json")
            == json.loads((args.output / "freeze.json").read_bytes())["references_sha256"],
        ),
    )


if __name__ == "__main__":
    main()
