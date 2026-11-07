"""Replay QA-01a against pinned INT-01a evidence. Artifacts stay local."""

import argparse
import json
from pathlib import Path

from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence.composition import EvidenceComposition
from vietnamese_financial_multi_agent.evidence.document_repository import DocumentEvidenceRepository
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

CASES = [
    ("Ai là người ký báo cáo tài chính BBS năm 2025?", "verification_blocked", None),
    (
        "Thuyết minh BBS năm 2025 nói gì về nhân viên quản lý chủ chốt?",
        "completed_with_caveats",
        14,
    ),
    (
        "Báo cáo BBS 2025 trình bày những khoản mục tiền nào trong bảng tiền?",
        "completed_with_caveats",
        14,
    ),
    ("Ý kiến kiểm toán của BBS năm 2025 là gì?", "verification_blocked", None),
    ("Ai là kế toán trưởng của BBS?", "clarification_required", None),
    ("Ai là người lập và lợi nhuận sau thuế BBS 2025 là bao nhiêu?", "unsupported", None),
    ("BBS 2025 ghi “Nợ xấu và dự phòng phải thu khó đòi” ở đâu?", "completed_with_caveats", 15),
    ("BCC 2025 ghi “BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH” ở đâu?", "completed_with_caveats", 7),
    ("BCC 2025 có ghi “CÔNG TY CỔ PHẦN VICEM BAO BÌ BÚT SƠN” không?", "verification_blocked", None),
    (
        "Ai là người lập biểu, kế toán trưởng và giám đốc của BBS 2025?",
        "verification_blocked",
        None,
    ),
]


def build_pipeline(input_path, ledger_path):
    manifests, documents = [], []
    for path in sorted(input_path.glob("*/composition.json")):
        company, year = path.parent.name.split("_")
        manifest = EvidenceComposition.model_validate_json(path.read_bytes())
        manifests.append(manifest)
        documents.append(
            QADocument(
                document_id=manifest.logical_document_id,
                company_id=company,
                company_aliases=[company],
                reporting_year=int(year),
            )
        )
    return FinancialQAPipeline(
        catalog=SnapshotCatalog([]),
        documents=documents,
        repository=VerifiedClaimRepository(ledger_path),
        compositions=manifests,
        document_repository=DocumentEvidenceRepository(input_path / "repository"),
    )


def expected_sources(pages):
    """Read the original Gemini save, independent of retrieval and QA output."""
    page14 = json.loads((pages / "page-14.json").read_bytes())["output"]
    page15 = json.loads((pages / "page-15.json").read_bytes())["output"]
    text = page14["text_elements"]
    cells = page14["tables"][0]["cells"]
    return {
        1: (
            " ".join(text[i]["text"] for i in (4, 5, 6)),
            {f"/text_elements/{i}" for i in (4, 5, 6)},
        ),
        2: (
            ", ".join(cells[i]["text"] for i in (6, 9)),
            {"/tables/0", "/tables/0/cells/6", "/tables/0/cells/9"},
        ),
        6: (page15["text_elements"][4]["text"], {"/text_elements/4"}),
        7: ("BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", {"/context/1"}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("artifacts/evidence/INT-01a/final"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/QA-01a/final-run"))
    parser.add_argument(
        "--gemini-pages", type=Path, default=Path("artifacts/gemini-ingestion/M1-15/pdf")
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pipeline = build_pipeline(args.input, args.output / "ledger")
    results = []
    oracle = expected_sources(args.gemini_pages)
    for index, (question, status, page) in enumerate(CASES):
        result = pipeline.run(FinancialQARequest(question=question, force_refresh=True))
        passed = result.status == status and {c.pdf_page for c in result.citations} == (
            {page} if page else set()
        )
        expected_text, expected_pointers = oracle.get(index, (None, set()))
        if expected_text:
            passed = (
                passed
                and expected_text in result.answer_vi
                and expected_pointers == {c.source_locator.source_pointer for c in result.citations}
            )
        results.append(
            dict(
                question=question,
                expected=dict(
                    status=status,
                    page=page,
                    text=expected_text,
                    source_pointers=sorted(expected_pointers),
                ),
                actual=result.model_dump(mode="json"),
                passed=passed,
            )
        )
        print(result.status, result.trace.native_decisions, result.trace.errors, question)
    (args.output / "quick-qa.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not all(result["passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
