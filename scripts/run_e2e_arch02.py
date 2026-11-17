"""Bounded full-pipeline probes on imported JSON; never opens benchmark questions."""

import argparse
import hashlib
import json
import subprocess
import traceback
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.tools.python_execution import PythonExecutor
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

CASES = [
    dict(
        id="ARCH02-SH01",
        group="single_hop",
        document_alias="BBS_2025",
        question="Theo báo cáo BBS 2025, lợi nhuận gộp năm 2024 là bao nhiêu VND?",
    ),
    dict(
        id="ARCH02-SH02",
        group="single_hop",
        document_alias="ADC_2021",
        question="Tổng lợi nhuận kế toán trước thuế của ADC năm 2021 là bao nhiêu?",
    ),
    dict(
        id="ARCH02-NU03",
        group="numerical",
        document_alias="BBS_2025",
        question="Theo báo cáo BBS 2025, doanh thu thuần năm 2025 trừ doanh thu thuần năm 2024 bằng bao nhiêu VND? Chỉ tính chênh lệch tuyệt đối, không suy nguyên nhân.",
    ),
    dict(
        id="ARCH02-MH04",
        group="multi_hop",
        document_alias="BBS_2025",
        question="Trong hai năm 2024 và 2025 của báo cáo BBS 2025, chọn năm có doanh thu thuần thấp hơn. Từ năm đã chọn, tra lợi nhuận gộp cùng năm rồi tính lợi nhuận gộp chia doanh thu thuần theo phần trăm. Không suy nguyên nhân.",
    ),
    dict(
        id="ARCH02-PY05",
        group="python",
        document_alias="BBS_2025",
        question="Từ báo cáo BBS 2025, tính độ lệch chuẩn tổng thể của tổng tài sản hai năm 2024 và 2025, bằng căn bậc hai của trung bình bình phương độ lệch so với trung bình. Dùng các số VND có nguồn; không thay bằng phương sai, không suy nguyên nhân.",
    ),
    dict(
        id="ARCH02-GAP06",
        group="data_gap",
        document_alias="ADC_2021",
        question="Theo báo cáo ADC 2021 đã nhập, doanh thu thuần năm 2021 là bao nhiêu VND? Nếu chưa đủ bằng chứng thì nêu rõ phần thiếu.",
    ),
    dict(
        id="ARCH02-PY07",
        group="python",
        document_alias="BBS_2025",
        question="Theo báo cáo BBS 2025, tính căn bậc hai của trung bình bình phương lợi nhuận gộp hai năm 2024 và 2025 (RMS), bằng VND. Dùng hai số lợi nhuận gộp có nguồn, không thay bằng trung bình cộng và không suy nguyên nhân.",
    ),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", choices=[c["id"] for c in CASES])
    parser.add_argument("--call-cap", type=int, choices=range(1, 41), default=40)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence/E2E-ARCH-02"):
        parser.error("output must remain in E2E-ARCH-02 artifacts")
    output.mkdir(parents=True, exist_ok=False)
    (output / "provider").mkdir()
    (output / "results").mkdir()
    cases = [c for c in CASES if not args.ids or c["id"] in args.ids]
    atomic_json(output / "questions-only.json", cases)
    sources = {
        str(p.relative_to(args.storage_root)): sha(p)
        for alias in {c["document_alias"] for c in cases}
        for p in (args.storage_root / "ViFinBench/refined" / Path(*alias.split("_"))).rglob(
            "*.json"
        )
    }
    runtime = {str(p.relative_to(root)): sha(p) for p in (root / "src").rglob("*.py")}
    receipt = dict(
        baseline_sha=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        runtime_hashes=runtime,
        source_hashes=sources,
        runner_sha256=sha(Path(__file__)),
        question_manifest_sha256=sha(output / "questions-only.json"),
        prepared_at_utc=datetime.now(UTC).isoformat(),
        settings=dict(
            total_call_cap=args.call_cap,
            per_question_cap=10,
            timeout_seconds=300,
            retries=0,
            adaptive_coordinator=True,
            graph=True,
        ),
        worker=PythonExecutor().preflight(),
    )
    atomic_json(output / "receipt.json", receipt)
    configured = create_text_gateway(root, provider="qwen")
    used, current = 0, None
    events, summaries = [], []

    def transport(request):
        nonlocal used
        if used >= args.call_cap:
            return _failure(request, "quota_exceeded")
        used += 1
        event = dict(
            case_id=current,
            attempt=used,
            started_at_utc=datetime.now(UTC).isoformat(),
            request=request.model_dump(mode="json"),
        )
        path = output / "provider" / f"{used:03}.json"
        atomic_json(path, event)
        started = perf_counter()
        response = configured.adapter(request)
        event.update(
            response=response.model_dump(mode="json"),
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )
        atomic_json(path, event)
        events.append(event)
        print(
            json.dumps(
                dict(
                    case=current,
                    call=used,
                    stage=request.request_id.rsplit("-", 1)[0],
                    status=response.status,
                )
            ),
            flush=True,
        )
        return response

    gateway = SharedLLMGateway({"qwen": transport})
    try:
        for case in cases:
            current = case["id"]
            load_start = perf_counter()
            catalog = load_json_corpus_document(
                args.storage_root / "ViFinBench/refined",
                args.storage_root / "artifacts/evidence/VFB-IMPORT-03/full-final",
                case["document_alias"],
            )
            descriptor = catalog.descriptors[0]
            companies = {f.company_id for f in catalog.facts if f.company_id}
            assert len(companies) == 1, "unresolved_company"
            company = next(iter(companies))
            service = FinancialQAPipeline(
                catalog=catalog,
                gateway=gateway,
                documents=[
                    QADocument(
                        document_id=descriptor.document_id,
                        company_id=company,
                        company_aliases=[case["document_alias"].split("_")[0]],
                        reporting_year=int(case["document_alias"].split("_")[1]),
                    )
                ],
                repository=VerifiedClaimRepository(output / "ledgers" / current),
            )
            request = FinancialQARequest(
                request_id=current,
                question=case["question"],
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
                company_id=company,
                model=configured.model,
                allow_gateway=True,
                execution_mode="auto",
                integration_v2=True,
                adaptive_coordinator=True,
                m5_lite=True,
                m6_lite=True,
                m7_lite=True,
                m5_graph=True,
                force_refresh=True,
                max_provider_calls=10,
                request_timeout_seconds=300,
            )
            payload = dict(
                case=case,
                request=request.model_dump(mode="json"),
                load_seconds=round(perf_counter() - load_start, 3),
            )
            first, started = used, perf_counter()
            try:
                response = service.run(request)
                payload["response"] = response.model_dump(mode="json")
                summary = dict(
                    id=current,
                    status=response.status,
                    agents=response.trace.executed_agents,
                    decisions=response.trace.native_decisions,
                    errors=response.trace.errors,
                    citations=len(response.citations),
                )
            except Exception:
                payload["exception"] = traceback.format_exc()
                summary = dict(id=current, status="runner_exception")
            payload.update(
                wall_seconds=round(perf_counter() - started, 3), transport_attempts=used - first
            )
            summary.update(calls=used - first, seconds=payload["wall_seconds"])
            atomic_json(output / "results" / f"{current}.json", payload)
            summaries.append(summary)
            atomic_json(output / "summary.json", summaries)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        configured.close()
        receipt.update(
            calls=used,
            completed_responses=len(events),
            summaries=summaries,
            known_tokens=sum(e["response"]["usage"].get("total_tokens") or 0 for e in events),
            unknown_usage=sum(e["response"]["usage"].get("total_tokens") is None for e in events),
            sources_unchanged=all(sha(args.storage_root / p) == h for p, h in sources.items()),
            runtime_unchanged=all(sha(root / p) == h for p, h in runtime.items()),
        )
        atomic_json(output / "receipt.json", receipt)
        assert receipt["sources_unchanged"] and receipt["runtime_unchanged"]


if __name__ == "__main__":
    main()
