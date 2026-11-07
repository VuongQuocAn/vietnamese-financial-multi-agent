"""QA-01b real saved-PDF QA, independent accepted-input oracles; never OCR."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median

from evaluate_composition_graph import bbs_catalog
from evaluate_document_qa import build_pipeline
from pydantic import TypeAdapter
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFinancialFact,
    DerivedMetric,
    EvidenceGraph,
    ReportingScopeReview,
    SnapshotCatalog,
)
from vietnamese_financial_multi_agent.evidence.analytical_readiness import AccountingBasisReview
from vietnamese_financial_multi_agent.evidence.composition_graph import select_financial_catalog
from vietnamese_financial_multi_agent.evidence.document_evidence import DocumentEvidence
from vietnamese_financial_multi_agent.evidence.execution_compatibility import (
    ExecutionCompatibilityApproval,
)
from vietnamese_financial_multi_agent.evidence.preparation_policy import (
    FormulaExecutionApproval,
    PreparationApproval,
    PreparedFormulaPolicy,
)
from vietnamese_financial_multi_agent.evidence.source_reviews import SourceReview
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument

CASES = [
    (
        "A1",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và báo cáo có thuyết minh gì về chính sách ghi nhận doanh thu?",
        "full",
        [12],
        {},
    ),
    (
        "A2",
        "BBS_2025",
        "Nợ phải trả chiếm bao nhiêu phần trăm tổng tài sản BBS 2025? Báo cáo có thuyết minh về các khoản vay không?",
        "full",
        [12],
        {},
    ),
    (
        "A3",
        "BBS_2025",
        "Tăng trưởng doanh thu BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "full",
        [14],
        {},
    ),
    (
        "A4",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và báo cáo thuyết minh gì về hàng tồn kho?",
        "partial",
        [],
        {},
    ),
    (
        "A5",
        "BBS_2025",
        "Doanh thu BBS 2025 tăng hay giảm so với năm trước và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu và nguyên nhân là gì?",
        "partial",
        [12],
        {},
    ),
    (
        "A6",
        "BBS_2025",
        "Doanh thu thuần BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "full",
        [14],
        {},
    ),
    (
        "A7",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và báo cáo ghi “thuế thu nhập lại phải trả” ở đâu?",
        "partial",
        [],
        {},
    ),
    (
        "A8",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và tỷ lệ nợ trên tổng tài sản là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "full",
        [12, 14],
        {},
    ),
    (
        "B1",
        "BCC_2025",
        "Doanh thu thuần BCC 2025 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu?",
        "full",
        [13],
        {},
    ),
    (
        "B2",
        "BCC_2025",
        "Biên lợi nhuận gộp BCC 2025 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu?",
        "full",
        [13],
        {},
    ),
    (
        "B3",
        "BCC_2025",
        "ROE BCC 2025 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu?",
        "partial",
        [13],
        {},
    ),
    (
        "C1",
        "BCC_2024",
        "Biên lợi nhuận gộp BCC 2024 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu?",
        "partial",
        [18],
        {},
    ),
    (
        "C2",
        "BCC_2024",
        "Doanh thu thuần BCC 2024 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu?",
        "full",
        [18],
        {},
    ),
    (
        "C3",
        "BCC_2024",
        "So sánh doanh thu BCC 2024 hợp nhất và BCC 2025 riêng và thuyết minh gì về doanh thu?",
        "abstain",
        [],
        {},
    ),
    (
        "D1",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "abstain",
        [],
        {"company_id": "BCC"},
    ),
    (
        "D2",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "abstain",
        [],
        {"document_id": "wrong-document"},
    ),
    (
        "D3",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "abstain",
        [],
        {"composition_id": "wrong-composition"},
    ),
    (
        "D4",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "abstain",
        [],
        {"snapshot_id": "wrong-financial"},
    ),
    (
        "D5",
        "BBS_2025",
        "Biên lợi nhuận gộp BBS 2025 là bao nhiêu và thuyết minh nói gì về nhân viên quản lý chủ chốt?",
        "abstain",
        [],
        {"document_snapshots": ["wrong-document-snapshot"]},
    ),
    (
        "D6",
        "BCC_2025",
        "Biên lợi nhuận gộp BCC 2025 là bao nhiêu và báo cáo thuyết minh gì về chính sách ghi nhận doanh thu?",
        "abstain",
        [],
        {"reporting_scope": "consolidated"},
    ),
]


def read(path):
    return json.loads(path.read_bytes())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def accepted_bcc(root, label, descriptor):
    # GEN-01 report explicitly identifies release as accepted; final/v2 are diagnostic.
    base = root / "artifacts/evidence/GEN-01"
    normalized, audit = base / "normalized-release" / label, base / "audit-release" / label
    policies = read(root / "configs/m4-execution-policies.json")
    calculations = read(audit / "m4-calculations.json")
    bases = {
        json.dumps(b, sort_keys=True): b
        for c in calculations
        for b in c["evidence"]["accounting_bases"]
    }

    def rows(kind, path):
        return TypeAdapter(list[kind]).validate_json(path.read_bytes())

    return SnapshotCatalog(
        [descriptor],
        facts=rows(CanonicalFinancialFact, normalized / "facts.json"),
        evidence=rows(DocumentEvidence, normalized / "evidence.json"),
        metrics=rows(DerivedMetric, audit / "metrics.json"),
        graph=EvidenceGraph.model_validate(read(audit / "graph.json")),
        source_reviews=rows(SourceReview, audit / "source-reviews.json"),
        accounting_bases=[AccountingBasisReview.model_validate(b) for b in bases.values()],
        reporting_scope_reviews=rows(ReportingScopeReview, audit / "reporting-scope-reviews.json"),
        approval=PreparationApproval(
            **read(root / "configs/d02-analytical-policies.json")["preparation_approval"]
        ),
        formula_policies=[PreparedFormulaPolicy(**p) for p in policies["formula_policies"]],
        formula_approvals=[
            FormulaExecutionApproval(**p) for p in policies["formula_execution_approvals"]
        ],
        execution_approval=ExecutionCompatibilityApproval(**policies["execution_approval"]),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/QA-01b/offline"))
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    args.output.mkdir(parents=True, exist_ok=True)
    chosen = [c for c in CASES if args.cases is None or c[0] in args.cases]
    if any((args.output / f"{c[0]}.json").exists() for c in chosen):
        parser.error("choose a fresh output directory; existing results are immutable")
    source = root / "artifacts/evidence/EXT-01"
    protected = [source / "repository/document-evidence.json"]
    protected += [source / f"{label}/composition.json" for label in {c[1] for c in chosen}]
    protected += [p for p in (root / "artifacts/evidence/GEN-01").glob("*-release/*/*.json")]

    def hashes():
        return {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in protected
        }

    before = hashes()
    bbs = bbs_catalog(root)
    pipelines, catalogs = {}, {}
    live_calls = 0
    gateway = None
    if args.live:
        adapter, _ = create_qa_adapter(root)

        def transport(request):
            nonlocal live_calls
            budget = root / "artifacts/evidence/QA-01b/provider-attempts.jsonl"
            existing = len(budget.read_text().splitlines()) if budget.exists() else 0
            if existing >= 12:
                raise ValueError("QA_01b_live_budget_exhausted")
            with budget.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(dict(request_id=request.request_id, event="started")) + "\n"
                )
            live_calls += 1
            return adapter(request)

        gateway = SharedLLMGateway({"gemini": transport})
    # Freeze source oracles before asking the pipeline. They are selected pinned
    # records/PDF-reviewed pages plus accepted financial calculator/fact artifacts.
    oracle = {}
    saved_records = read(source / "repository/document-evidence.json")["records"]
    for case_id, label, question, expected, pages, patch in chosen:
        if label not in pipelines:
            p = build_pipeline(source, args.output / label / "ledger")
            manifest = next(
                m
                for m in p.compositions
                if m.logical_document_id
                == next(
                    d.document_id
                    for d in p.documents
                    if d.company_id == label.split("_")[0]
                    and d.reporting_year == int(label.split("_")[1])
                )
            )
            catalog = (
                select_financial_catalog(bbs, manifest)
                if label.startswith("BBS")
                else accepted_bcc(root, label, manifest.financial_snapshot)
            )
            p.catalog = catalog
            p.documents = [
                QADocument(
                    document_id=manifest.logical_document_id,
                    company_id=catalog.facts[0].company_id,
                    company_aliases=[label.split("_")[0]],
                    reporting_year=int(label.split("_")[1]),
                )
            ]
            p.gateway = gateway
            pipelines[label], catalogs[label] = p, catalog
        p, catalog = pipelines[label], catalogs[label]
        manifest = next(
            m for m in p.compositions if m.logical_document_id == p.documents[0].document_id
        )
        pins = {
            (pin.identity.document_id, pin.identity.snapshot_id, pin.identity.local_id)
            for s in manifest.sources
            if s.status == "verified"
            for pin in s.evidence
        }
        records = [
            r
            for r in saved_records
            if (r["document_id"], r["snapshot_id"], r["local_evidence_id"]) in pins
        ]
        oracle[case_id] = dict(
            label=label,
            question=question,
            expected=expected,
            document_pages=pages,
            request_overrides=patch,
            source_excerpt_oracles=[
                r
                for r in records
                if r["kind"] == "text"
                and any(
                    s.get("reference") and s["reference"]["anchor"]["page"]["page"] in pages
                    for s in r["sources"]
                )
            ],
            financial_facts=[
                f.model_dump(mode="json")
                for f in catalog.facts
                if f.canonical_item_id
                in {
                    "b02.net_revenue",
                    "b02.gross_profit",
                    "b01.total_assets",
                    "b01.total_liabilities",
                }
            ],
            calculation_reference="GEN-01/audit-release"
            if label.startswith("BCC")
            else "M4-03-final",
            ground_truth_origin="original_pdf_visual_review_and_accepted_inputs_not_pipeline_output",
        )
    save(args.output / "oracles.json", oracle)
    summary, results = Counter(), []
    for case_id, label, question, expected, pages, patch in chosen:
        p = pipelines[label]
        request = FinancialQARequest(
            question=question,
            force_refresh=True,
            allow_gateway=args.live,
            execution_mode="gemini" if args.live else "deterministic",
            **patch,
        )
        result = p.run(request)
        category = (
            "full"
            if result.status in {"completed", "completed_with_caveats"}
            else "partial"
            if result.status == "partial_verified_coverage"
            else "abstain"
        )
        expected_page_set = set(pages)
        actual_document_pages = {
            c.pdf_page for c in result.citations if c.snapshot_id != result.trace.snapshot_id
        }
        passed = category == expected and actual_document_pages <= expected_page_set
        if expected != "abstain" and pages:
            passed = passed and bool(actual_document_pages)
        if result.status == "internal_error":
            passed = False
        row = dict(
            case_id=case_id,
            expected=expected,
            category=category,
            passed=passed,
            actual=result.model_dump(mode="json"),
        )
        save(args.output / f"{case_id}.json", row)
        results.append(row)
        summary[category] += 1
        summary["passed"] += passed
        print(
            case_id,
            result.status,
            result.trace.native_decisions,
            result.trace.errors,
            "PASS" if passed else "FAIL",
            flush=True,
        )
    times = sorted(r["actual"]["trace"]["total_latency_ms"] for r in results)
    save(
        args.output / "summary.json",
        dict(
            counts=dict(summary),
            total=len(results),
            median_ms=median(times),
            p95_ms=times[min(len(times) - 1, int(len(times) * 0.95))],
            mode="live_gemini" if args.live else "deterministic_saved_evidence",
            actual_transport_calls=live_calls,
            known_tokens=sum(r["actual"]["trace"]["known_total_tokens"] for r in results),
            source_hashes_unchanged=before == hashes(),
        ),
    )
    save(
        args.output / "integrity.json",
        dict(before=before, after=hashes(), unchanged=before == hashes()),
    )
    assert before == hashes()
    if summary["passed"] != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
