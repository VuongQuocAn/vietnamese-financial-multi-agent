"""FIX-02 final acceptance: frozen questions, committed runtime, real Gateway.

Detailed source payloads and public reasoning traces stay in ignored artifacts.
This is a bounded task acceptance runner, not an M8 benchmark.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from time import perf_counter

from evaluate_real_pdf import build, digest, protected, runtime, save


def freeze(base):
    source = Path("artifacts/evidence/E2E-02")
    questions = {q["id"]: q for q in json.loads((source / "questions.json").read_bytes())}
    references = {r["id"]: r for r in json.loads((source / "reference.json").read_bytes())}
    definitions = [
        ("L01", "Q03", None, "direct fact"),
        ("L02", "Q14", None, "gross margin; Decimal and both operands"),
        (
            "L03",
            "Q21",
            "Tính chênh lệch giữa dòng tiền thuần từ hoạt động kinh doanh và lợi nhuận sau thuế BBS năm 2025 bằng VND; dẫn nguồn hai số liệu.",
            "ad hoc CFO minus PAT; 7070123808 VND",
        ),
        ("L04", "Q21", None, "CFO versus PAT; bounded earnings-quality interpretation"),
        ("L05", "Q23", None, "revenue versus gross profit across periods; no causality"),
        ("L06", "Q20", None, "PAT comparison, both columns of one filing"),
        (
            "L07",
            "Q21",
            "Cho biết doanh thu thuần, lợi nhuận sau thuế và dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025; dẫn nguồn cho từng chỉ tiêu.",
            "three independent sourced facts; preserve each valid branch",
        ),
        (
            "L08",
            "Q13",
            "Đánh giá mức độ sử dụng nợ của BBS cuối năm 2025 qua tỷ lệ nợ phải trả trên tổng tài sản; nêu số liệu, phép tính và giới hạn kết luận.",
            "debt/assets 59.06%; bounded leverage interpretation, no liquidity certainty",
        ),
        (
            "L09",
            "Q11",
            "Tính chênh lệch doanh thu thuần và lợi nhuận gộp BBS 2025 bằng VND; dẫn nguồn và giải thích đây là phép đối chiếu, không phải chỉ tiêu kế toán chuẩn.",
            "MH03 original; dynamic subtraction 417992011559 VND and ad hoc caveat",
        ),
        ("L10", "Q29", None, "two-turn context: revenue then previous-year comparison"),
    ]
    cases = []
    for case_id, original, question, expected in definitions:
        ref = references[original]
        case = dict(
            id=case_id,
            original_id="MH03" if case_id == "L09" else original if question is None else None,
            turns=[question or questions[original]["question"]],
            source={
                k: ref[k]
                for k in ("pdf", "pdf_sha256", "document_id", "reporting_scope", "reporting_year")
            },
            expected_reasoning=expected,
            source_reference_ids=[original],
            conditions="Audit PDF/pages, period/unit, Decimal replay, M6 admission, final prose and citations; status alone is insufficient.",
        )
        if case_id == "L10":
            case["turns"].append(questions["Q30"]["question"])
            case["source_reference_ids"].append("Q30")
        cases.append(case)
    save(
        base / "manifest.json",
        dict(
            cases=cases,
            reference_sha256=digest(source / "reference.json"),
            baseline_sha=subprocess.check_output(
                ["git", "rev-parse", "af4eae9"], text=True
            ).strip(),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", type=Path, default=Path("artifacts/evidence/FIX-02/final-acceptance")
    )
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--sha", default="af4eae9")
    parser.add_argument("--run", default="baseline")
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    if args.freeze:
        if (args.base / "manifest.json").exists():
            raise ValueError("manifest_already_frozen")
        freeze(args.base)
        return
    manifest = json.loads((args.base / "manifest.json").read_bytes())
    output = args.base / args.run
    if output.exists():
        raise ValueError("fresh_run_directory_required")
    root = Path.cwd()
    sha = subprocess.check_output(["git", "rev-parse", args.sha], text=True).strip()
    runtime(output, sha)
    from vietnamese_financial_multi_agent.api.conversations import ConversationService
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

    before = protected(root)
    # Include every pre-existing local change, including untracked task files.
    names = subprocess.check_output(
        ["git", "ls-files", "-m", "-o", "--exclude-standard"], text=True
    ).splitlines()
    local = {name: digest(root / name) for name in names if (root / name).is_file()}
    save(
        output / "freeze.json",
        dict(
            implementation_sha=sha,
            manifest_sha256=digest(args.base / "manifest.json"),
            protected=before,
            local=local,
        ),
    )
    pipeline = build(root, output)
    save(
        output / "catalog.json",
        dict(
            documents=[d.model_dump(mode="json") for d in pipeline.documents],
            facts=[f.model_dump(mode="json") for f in pipeline.catalog.facts],
        ),
    )
    adapter, credential = create_qa_adapter(root)
    save(
        output / "configuration.json",
        dict(
            credential_source=credential.source,
            rotation=False,
            max_actual_attempts=240,
            transient_retries=1,
            per_turn_calls=20,
            per_turn_timeout_seconds=300,
        ),
    )
    attempts, results, active = [], [], {}

    def transport(request):
        response = None
        for retry in range(2):
            if len(attempts) >= 240:
                raise ValueError("acceptance_provider_budget_exhausted")
            number = len(attempts) + 1
            stem = output / "provider" / f"{number:03}"
            save(stem.with_suffix(".request.json"), request.model_dump(mode="json"))
            row = dict(
                number=number,
                **active,
                request_id=request.request_id,
                retry=retry,
                status="started_usage_unknown",
            )
            attempts.append(row)
            save(output / "provider-attempts.json", attempts)
            started = perf_counter()
            response = adapter(request)
            save(stem.with_suffix(".response.json"), response.model_dump(mode="json"))
            row.update(
                status=response.status,
                tokens=response.usage.total_tokens,
                error=response.error.model_dump(mode="json") if response.error else None,
                latency_ms=(perf_counter() - started) * 1000,
            )
            save(output / "provider-attempts.json", attempts)
            code = str(response.error.provider_error_code) if response.error else ""
            transient = any(c in code for c in ("429", "500", "502", "503", "504"))
            transient = transient or bool(response.error and response.error.code == "timeout")
            if not transient or retry:
                break
            time.sleep(3)
        return response

    pipeline.gateway = SharedLLMGateway({"gemini": transport})
    service = ConversationService(pipeline)
    try:
        for case in manifest["cases"]:
            if args.case and case["id"] not in args.case:
                continue
            session = service.create().conversation_id if len(case["turns"]) > 1 else None
            for turn_number, question in enumerate(case["turns"], 1):
                active.update(case=case["id"], turn=turn_number)
                row = dict(**active, question=question)
                started = perf_counter()
                try:
                    request = FinancialQARequest(
                        question=question,
                        force_refresh=True,
                        execution_mode="auto",
                        allow_gateway=True,
                        max_provider_calls=20,
                        request_timeout_seconds=300,
                    )
                    if session:
                        turn = service.send(session, request)
                        row["conversation"] = turn.model_dump(mode="json")
                        response = turn.response
                    else:
                        response = pipeline.run(request)
                    row["actual"] = response.model_dump(mode="json")
                    (output / f"{case['id']}-turn{turn_number}-answer.txt").write_text(
                        response.answer_vi, encoding="utf-8"
                    )
                except Exception as error:
                    row["runtime_error"] = dict(type=type(error).__name__, message=str(error))
                row["elapsed_ms"] = (perf_counter() - started) * 1000
                results.append(row)
                save(output / "results.json", results)
                print(
                    case["id"],
                    turn_number,
                    row.get("actual", {}).get("status", "RUNTIME_FAILURE"),
                    round(row["elapsed_ms"]),
                    "ms",
                    flush=True,
                )
    finally:
        adapter.close()
        frozen_root = (output / "runtime/src").resolve()
        save(
            output / "integrity.json",
            dict(
                implementation_sha=sha,
                protected_count=len(before),
                protected_unchanged=before == protected(root),
                local_unchanged=all(digest(root / n) == h for n, h in local.items()),
                manifest_unchanged=digest(args.base / "manifest.json")
                == json.loads((output / "freeze.json").read_bytes())["manifest_sha256"],
                imported_runtime_verified=all(
                    Path(module.__file__).resolve().is_relative_to(frozen_root)
                    for name, module in sys.modules.items()
                    if name.startswith("vietnamese_financial_multi_agent")
                    and getattr(module, "__file__", None)
                ),
            ),
        )


if __name__ == "__main__":
    main()
