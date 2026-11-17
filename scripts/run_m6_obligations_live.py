"""Bounded M6 goal-binding probes on existing JSON/EF-EG, no OCR/PDF."""

import argparse
from pathlib import Path

from run_m5_coordinator_live import check_sources, prepare
from run_vfb_qwen_e2e import run

CASES = [
    dict(
        id="M6O-SEL-JOIN-01",
        group="multi_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="BBS trong hai năm 2024 và 2025 trình bày ở báo cáo 2025: chọn năm có doanh thu thuần thấp hơn. Truy xuất lợi nhuận sau thuế của chính năm vừa chọn, rồi tính lợi nhuận sau thuế chia doanh thu thuần cùng năm theo phần trăm. Không suy nguyên nhân.",
    ),
    dict(
        id="M6O-SEL-JOIN-02",
        group="multi_hop",
        difficulty="probe",
        document_alias="ADC_2021",
        question="Trong hai năm 2020 và 2021 của báo cáo ADC 2021, chọn năm có doanh thu thuần cao hơn. Tìm lưu chuyển tiền thuần từ hoạt động kinh doanh cùng năm đã chọn và tính dòng tiền kinh doanh chia doanh thu thuần theo phần trăm. Chỉ tính số học, không nhận xét nguyên nhân.",
    ),
]


def verify_saved_m5(root, output, source):
    """Replay exact serialized M5 output; one live M6 call, normal admission/M7."""
    import json

    from run_vfb_qwen_e2e import digest
    from vietnamese_financial_multi_agent.agents.orchestration_contracts import OrchestrationResult
    from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.api.text_gateway import create_text_gateway
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.core.persistence import atomic_json
    from vietnamese_financial_multi_agent.evidence.json_catalog import load_json_corpus_document
    from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
    from vietnamese_financial_multi_agent.verification.ledger_repository import (
        VerifiedClaimRepository,
    )

    saved = json.loads(source.read_bytes())
    original = OrchestrationResult.model_validate_json(
        json.dumps(saved["response"]["trace"]["financial_execution"])
    )
    case = saved["case"]
    prepare(root, output, None, 1, cases=[case])
    atomic_json(
        output / "saved-m5-input.json",
        dict(source_sha256=digest(source), m5=original.model_dump(mode="json")),
    )

    class SavedM5:
        def run(self, **kwargs):
            assert kwargs["question"] == original.question
            return original.model_copy(deep=True)

    configured = create_text_gateway(root, provider="qwen")
    calls = 0

    def transport(request):
        nonlocal calls
        assert calls < 1 and request.request_id.startswith("m6-")
        calls += 1
        atomic_json(output / "provider/001-request.json", request.model_dump(mode="json"))
        response = configured.adapter(request)
        atomic_json(output / "provider/001.json", response.model_dump(mode="json"))
        return response

    try:
        catalog = load_json_corpus_document(
            root / "ViFinBench/refined",
            root / "artifacts/evidence/VFB-IMPORT-03/full-final",
            case["document_alias"],
        )
        request = FinancialQARequest.model_validate(saved["request"])
        context = original.context
        service = FinancialQAPipeline(
            catalog=catalog,
            gateway=SharedLLMGateway({"qwen": transport}),
            orchestrator=SavedM5(),
            documents=[
                QADocument(
                    document_id=context.document_id,
                    company_id=context.company_id,
                    company_aliases=[case["document_alias"].split("_")[0]],
                    reporting_year=int(case["document_alias"].split("_")[1]),
                )
            ],
            repository=VerifiedClaimRepository(output / "ledger"),
        )
        response = service.run(request)
        atomic_json(
            output / "result.json",
            dict(
                case=case,
                response=response.model_dump(mode="json"),
                actual_live_calls=calls,
                mode="saved_exact_m5_live_m6",
            ),
        )
        print(
            json.dumps(
                dict(
                    mode="saved_exact_m5_live_m6",
                    status=response.status,
                    actual_live_calls=calls,
                    decisions=response.trace.native_decisions,
                    released=response.trace.m7_lite.get("released_claims", []),
                    supported=response.trace.m6_lite.get("supported_requirements", {}),
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
    parser.add_argument("mode", choices=["prepare", "run", "verify-saved"])
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M6-OBL-01/live-v1"))
    parser.add_argument("--ids", nargs="+", choices=[c["id"] for c in CASES])
    parser.add_argument("--saved-result", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/M6-OBL-01"):
        parser.error("output outside M6-OBL-01")
    if args.mode == "prepare":
        prepare(root, output, None, 16, cases=CASES)
    elif args.mode == "verify-saved":
        if not args.saved_result:
            parser.error("verify-saved requires --saved-result")
        verify_saved_m5(root, output, args.saved_result)
    else:
        try:
            run(root, output, args.ids)
        finally:
            check_sources(root, output)
