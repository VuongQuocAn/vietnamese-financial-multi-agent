"""Three bounded real-JSON probes. Writes only a new ignored task evidence directory."""

import argparse
import json
import subprocess
from pathlib import Path

from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.agents.python_agent import PythonAgent
from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
from vietnamese_financial_multi_agent.tools.python_execution import PythonExecutor, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--call-cap", type=int, choices=range(1, 13), default=7)
    parser.add_argument("--resume-calculator-from", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=False)
    events, calls = [], 0
    configured = create_text_gateway(root, provider="qwen")

    def save(name, payload):
        (args.output / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def transport(request):
        nonlocal calls
        if calls >= args.call_cap:
            return _failure(request, "quota_exceeded")
        calls += 1
        response = configured.adapter(request)
        events.append(
            dict(request=request.model_dump(mode="json"), response=response.model_dump(mode="json"))
        )
        save("provider-events.json", events)
        print(json.dumps(dict(call=calls, status=response.status)), flush=True)
        return response

    gateway = SharedLLMGateway({"qwen": transport})
    source_dir = args.storage_root / "ViFinBench/refined/BBS/2025"
    before = {p.name: digest(p.read_text(encoding="utf-8-sig")) for p in source_dir.glob("*.json")}
    runtime = {
        p.relative_to(root).as_posix(): digest(p.read_text(encoding="utf-8"))
        for p in (root / "src").rglob("*.py")
    }
    catalog = load_json_corpus_document(
        args.storage_root / "ViFinBench/refined",
        args.storage_root / "artifacts/evidence/VFB-IMPORT-03/full-final",
        "BBS_2025",
    )
    descriptor = catalog.descriptors[0]
    context = PlannerContext(
        company_id=next(f.company_id for f in catalog.facts if f.company_id),
        document_id=descriptor.document_id,
        snapshot_id=descriptor.snapshot_id,
        model=configured.model,
        mode="gemini",
        provider_timeout_seconds=60,
    )
    engine = FinancialLiteOrchestrator(
        catalog, gateway, integration_v2=True, adaptive_coordinator=True
    )
    if args.resume_calculator_from:
        saved = json.loads(args.resume_calculator_from.read_text(encoding="utf-8"))
        saved_plan = LitePlan.model_validate_json(saved["trace"][0]["reasons"][0])

        class SavedSupervisor:
            def plan(self, question, context, sources):
                return saved_plan.model_copy(deep=True), PlannerLLMMetadata(), []

        engine.supervisor = SavedSupervisor()
    cases = [
        (
            "rms",
            "BBS báo cáo 2025: tính căn bậc hai của trung bình bình phương doanh thu thuần hai năm 2024 và 2025 (RMS), dùng số VND có nguồn. Không thay bằng trung bình cộng; không suy nguyên nhân.",
        ),
        (
            "calculator",
            "BBS năm 2025: tính giá vốn hàng bán chia doanh thu thuần, biểu diễn theo phần trăm; chỉ phép tính số học, không suy nguyên nhân.",
        ),
    ]
    outputs = {}
    try:
        for name, question in cases:
            if args.resume_calculator_from and name != "calculator":
                continue
            result = engine.run(question=question, context=context)
            outputs[name] = result
            save(name + ".json", result.model_dump(mode="json"))
            print(
                json.dumps(
                    dict(case=name, status=result.status, candidates=len(result.candidates))
                ),
                flush=True,
            )
        if args.resume_calculator_from:
            return
        # Same real retrieved operands; diagnostic explicitly asks first code to fail.
        matches = outputs["rms"].supervisor_result.evidence_bundle.facts
        question = (
            "Tính độ lệch chuẩn tổng thể doanh thu thuần BBS hai năm 2024 và 2025 bằng "
            "căn bậc hai trung bình bình phương độ lệch so với trung bình. Đơn vị VND. "
            "Đây là kiểm thử sửa lỗi có chủ đích: CHỈ LẦN SINH ĐẦU, thêm dòng `diagnostic_missing` "
            "trong solve trước return để tạo NameError. Khi nhận traceback thì bỏ dòng đó "
            "và trả code tính đúng. Không đổi operands hoặc công thức."
        )
        record, _ = PythonAgent(gateway).run(
            objective=question,
            requirement="dispersion",
            matches=matches,
            context=context,
        )
        save("repair.json", record)
        print(
            json.dumps(
                dict(case="repair", status=record["execution_status"], calls=record["calls"])
            ),
            flush=True,
        )
    finally:
        configured.close()
        after = {
            p.name: digest(p.read_text(encoding="utf-8-sig")) for p in source_dir.glob("*.json")
        }
        assert before == after
        save(
            "receipt.json",
            dict(
                baseline_sha=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                runtime_hashes=runtime,
                source_hashes=before,
                source_unchanged=before == after,
                calls=calls,
                known_tokens=sum(e["response"]["usage"].get("total_tokens") or 0 for e in events),
                worker=PythonExecutor().preflight(),
                call_cap=args.call_cap,
                saved_plan_sha256=digest(args.resume_calculator_from.read_text(encoding="utf-8"))
                if args.resume_calculator_from
                else None,
            ),
        )


if __name__ == "__main__":
    main()
