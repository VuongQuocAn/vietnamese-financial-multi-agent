"""FIX-02: eight frozen real-PDF cases, actual Gateway, fresh isolated ledger.

Source/reference payloads and detailed traces remain under ignored artifacts.
Every execution is persisted, including failures; no automatic output retries.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from evaluate_real_pdf import build, digest, runtime, save
from evaluate_real_pdf import protected as protected_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/FIX-02/live"))
    parser.add_argument("--mode", choices=["auto", "deterministic"], default="auto")
    parser.add_argument(
        "--acceptance", action="store_true", help="One targeted Q21/F08/Q01/Q11/Q08 pass"
    )
    parser.add_argument(
        "--committed-runtime",
        action="store_true",
        help="Import exact committed source, preserving unrelated local work",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        choices=["Q01", "Q11", "Q21", "Q08", "Q22", "Q23", "Q24", "MH03", "Q33", "Q34", "F08"],
    )
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh_output_directory_required")
    root = Path.cwd()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if args.committed_runtime:
        runtime(args.output, head)
    from vietnamese_financial_multi_agent.api.conversations import ConversationService
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

    inputs = root / "artifacts/evidence/E2E-02"
    questions = {q["id"]: q for q in json.loads((inputs / "questions.json").read_bytes())}
    cases = [
        dict(questions[key])
        for key in ("Q01", "Q11", "Q21", "Q08", "Q22", "Q23", "Q24", "Q33", "Q34")
    ]
    cases.append(
        dict(
            id="MH03",
            question="Tính chênh lệch doanh thu thuần và lợi nhuận gộp BBS 2025 bằng VND; dẫn nguồn và giải thích đây là phép đối chiếu, không phải chỉ tiêu kế toán chuẩn.",
        )
    )
    cases.append(dict(id="F08", question="Như thế có đáng lo không?", conversation="analysis"))
    cases[2]["conversation"] = "analysis"
    for case in cases:
        if case["id"] in {"Q33", "Q34"}:
            case["conversation"] = "source"
    if args.case_id:
        cases = [case for case in cases if case["id"] in args.case_id]
    if args.acceptance:
        selected = {case["id"]: case for case in cases}
        cases = [selected[key] for key in ("Q21", "F08", "Q01", "Q11", "Q08")]
    protected = protected_inputs(root)
    protected = {name: value for name, value in protected.items() if not name.startswith("src/")}
    save(
        args.output / "freeze.json",
        dict(
            cases=cases,
            mode=args.mode,
            implementation_sha=head,
            runtime_source="git_archive" if args.committed_runtime else "working_tree",
            references_sha256=digest(inputs / "reference.json"),
            protected=protected,
            runtime_files={
                p.relative_to(source_root.parent).as_posix(): digest(p)
                for source_root in [
                    args.output / "runtime/src" if args.committed_runtime else root / "src"
                ]
                for p in source_root.rglob("*.py")
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
            imported_runtime_verified=all(
                Path(module.__file__)
                .resolve()
                .is_relative_to((args.output / "runtime/src").resolve())
                for name, module in sys.modules.items()
                if args.committed_runtime
                and name.startswith("vietnamese_financial_multi_agent")
                and getattr(module, "__file__", None)
            )
            if args.committed_runtime
            else None,
            protected_count=len(protected),
            protected_unchanged=all(digest(root / p) == h for p, h in protected.items()),
            references_unchanged=digest(inputs / "reference.json")
            == json.loads((args.output / "freeze.json").read_bytes())["references_sha256"],
            implementation_sha=head,
            runtime_unchanged=all(
                digest((args.output / "runtime" if args.committed_runtime else root) / name)
                == value
                for name, value in json.loads((args.output / "freeze.json").read_bytes())[
                    "runtime_files"
                ].items()
            ),
        ),
    )


if __name__ == "__main__":
    main()
