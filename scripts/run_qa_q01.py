"""QA-only capture through public M5/M7 APIs; no mocks, admission or runtime edits.

prepare creates an exclusive output and hashes all protected inputs. m7 uses the
real persisted repository (including its proof validation), without a warm view.
m5 permits at most 16 real provider calls, one orchestration per selected question.
All financial outputs, prompts and source images remain in ignored artifacts.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

QUESTIONS = [
    "Tổng tài sản của BBS năm 2025 là bao nhiêu?",
    "Doanh thu thuần và lợi nhuận sau thuế của BBS năm 2025 là bao nhiêu?",
    "Biên lợi nhuận gộp của BBS năm 2025 là bao nhiêu? Hãy nêu công thức và các số liệu sử dụng.",
    "Tỷ lệ nợ phải trả trên tổng tài sản của BBS năm 2025 là bao nhiêu?",
    "Dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025 là bao nhiêu?",
    "Biên lợi nhuận gộp và tỷ lệ nợ trên tổng tài sản nói lên điều gì về khả năng sinh lời và mức độ sử dụng nợ của BBS năm 2025?",
    "Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh của BBS năm 2025.",
    "Doanh thu thuần và dòng tiền kinh doanh của BBS năm 2025 có cho thấy chất lượng lợi nhuận tốt không? Giải thích dựa trên số liệu.",
    "Hệ số thanh toán nhanh của BBS năm 2025 là bao nhiêu?",
    "So sánh biên lợi nhuận gộp của BBS năm 2024 và 2025. Mức thay đổi này phản ánh điều gì?",
]
LEDGER = "artifacts/evidence/M6-06-ledger-final-v2/ledger"


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, ensure_ascii=False, indent=2)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def protected(root, output):
    paths = [root / "web/next-env.d.ts"]
    for name in ("data", "artifacts/evidence", "src", "configs", "prompts", "evaluation"):
        paths.extend(
            p
            for p in (root / name).rglob("*")
            if p.is_file() and not p.is_relative_to(output) and "__pycache__" not in p.parts
        )
    return {p.relative_to(root).as_posix(): checksum(p) for p in sorted(set(paths))}


def prepare(root, output):
    import importlib.metadata

    import pypdfium2 as pdfium
    from vietnamese_financial_multi_agent.api.qa_gateway import (
        QACredentialError,
        resolve_qa_credential,
    )
    from vietnamese_financial_multi_agent.core.gemini_adapter import DEFAULT_GEMINI_MODEL

    output.mkdir(parents=True, exist_ok=False)
    write(output / "hashes-before.json", protected(root, output))
    write(output / "questions.json", {f"Q{i:02}": q for i, q in enumerate(QUESTIONS, 1)})
    pdfs = []
    for year in range(2021, 2026):
        path = root / f"data/raw/Financial_Report_pdf/BBS/{year}/BBS_{year}.pdf"
        doc = pdfium.PdfDocument(path)
        pdfs.append(
            dict(
                path=path.relative_to(root).as_posix(),
                pages=len(doc),
                sha256=checksum(path),
                text_chars=[len(page.get_textpage().get_text_range()) for page in doc],
            )
        )
        if year in (2024, 2025):
            for page in range(min(10, len(doc))):
                doc[page].render(scale=1.5).to_pil().save(output / f"BBS_{year}-p{page + 1}.png")
        doc.close()
    try:
        cred = resolve_qa_credential(root)
        credential = dict(available=True, source=cred.source, key_index=cred.key_index)
    except QACredentialError as error:
        credential = dict(available=False, reason=str(error))
    metadata = dict(
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        origin_main=subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip(),
        python=sys.version,
        packages={
            p: importlib.metadata.version(p)
            for p in ("pypdfium2", "pydantic", "google-genai", "pytest")
        },
        pdfs=pdfs,
        credential=credential,
        model=DEFAULT_GEMINI_MODEL,
        maximum_provider_calls=16,
        retries=0,
        quota="No remaining-quota/billing API instrumented; provider may reject. No model switch.",
    )
    write(output / "preflight.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False), flush=True)


def run_m7(root, output):
    from vietnamese_financial_multi_agent.outputs import (
        CitationRenderer,
        InformationFirewall,
        VietnameseQAComposer,
        VietnameseQARequest,
    )
    from vietnamese_financial_multi_agent.verification import (
        VerifiedClaimLedger,
        VerifiedClaimQuery,
        VerifiedClaimRepository,
    )

    start = perf_counter()
    ledger = VerifiedClaimLedger(VerifiedClaimRepository(root / LEDGER))
    matches = ledger.find_claims(VerifiedClaimQuery())
    cold_ms = (perf_counter() - start) * 1000
    entries = matches.claims
    identities = [e.identity.model_dump(mode="json") for e in entries]
    # Exact source context from existing accepted records, never injected claims.
    doc = json.loads((root / "evaluation/m7-01-scenarios.json").read_text(encoding="utf-8"))
    request = next(c["request"] for c in doc["scenarios"] if c["id"] == "revenue-2025")
    fields = {k: request[k] for k in ("document_id", "snapshot_id")}
    company = next(
        e.identity.company_id for e in entries if e.identity.document_id == fields["document_id"]
    )
    rows = []
    for i, question in enumerate(QUESTIONS, 1):
        case = f"Q{i:02}"
        tick = perf_counter()
        req = VietnameseQARequest(question=question, company_id=company, **fields)
        write(output / f"m7-{case}-request.json", req.model_dump(mode="json"))
        response = VietnameseQAComposer(ledger).compose(req)
        composed = perf_counter()
        write(output / f"m7-{case}-composer.json", response.model_dump(mode="json"))
        rendered = CitationRenderer().render_qa(response)
        projected = perf_counter()
        write(output / f"m7-{case}-rendered.json", rendered.model_dump(mode="json"))
        decision = InformationFirewall(ledger).evaluate_qa(
            request=req, response=response, rendered=rendered
        )
        ended = perf_counter()
        write(output / f"m7-{case}-firewall.json", decision.model_dump(mode="json"))
        final = decision.validated_output.rendered_text or decision.validated_output.message_vi
        write(output / f"m7-{case}-final.txt", final)
        row = dict(
            id=case,
            execution="ACTUAL_EXECUTION",
            status=response.status,
            firewall=decision.decision,
            release_status=decision.release_status,
            selected_ids=response.used_verified_claim_ids,
            latency_ms=dict(
                compose=(composed - tick) * 1000,
                render=(projected - composed) * 1000,
                firewall=(ended - projected) * 1000,
                total=(ended - tick) * 1000,
            ),
        )
        rows.append(row)
        print(json.dumps(row), flush=True)
    write(
        output / "m7-summary.json",
        dict(
            cold_ledger_load_ms=cold_ms,
            ledger_entries=identities,
            repository="production_no_warm_view",
            rows=rows,
            external_calls=0,
            fresh_m6_verification=False,
        ),
    )


def run_m5(root, output):
    from evaluate_m4_05_qa import setup
    from vietnamese_financial_multi_agent.agents import (
        AdaptiveSpecialistRouter,
        CashFlowEarningsQualitySpecialist,
        EvidenceAwareQueryPlanner,
        FinancialMultiAgentOrchestrator,
        LiquidityLeverageSpecialist,
        PlannerContext,
        ProfitabilitySpecialist,
        RiskAwareSupervisor,
    )
    from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

    data, scopes, _, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    write(
        output / "m5-inventory.json",
        dict(
            scopes=scopes,
            facts=len(data["facts"]),
            metrics=len(data["metrics"]),
            documents=[d.model_dump(mode="json") for d in documents],
        ),
    )
    adapter, _ = create_qa_adapter(root)
    calls, rows = [], []
    current_case = None

    def transport(request):
        if len(calls) >= 16:
            raise ValueError("QA_Q01_call_budget_exhausted")
        stem = f"m5-{current_case}-call{len(calls) + 1:02}"
        write(output / f"{stem}-request.json", request.model_dump(mode="json"))
        calls.append(dict(case=current_case, request_id=request.request_id))
        response = adapter(request)
        write(output / f"{stem}-response.json", response.export())
        calls[-1].update(response=response.export())
        return response

    gateway = SharedLLMGateway({"gemini": transport})
    orchestrator = FinancialMultiAgentOrchestrator(
        planner=EvidenceAwareQueryPlanner(catalog, documents, gateway),
        supervisor=RiskAwareSupervisor(catalog),
        router=AdaptiveSpecialistRouter(),
        specialists={
            "profitability": ProfitabilitySpecialist(gateway),
            "liquidity_and_leverage": LiquidityLeverageSpecialist(gateway),
            "cash_flow_and_earnings_quality": CashFlowEarningsQualitySpecialist(gateway),
        },
    )
    try:
        for i in (3, 6, 7, 8):
            current_case = f"Q{i:02}"
            context = PlannerContext(
                document_id=scopes[2025]["document_id"],
                snapshot_id=scopes[2025]["snapshot_id"],
                reporting_year=2025,
                mode="gemini",
            )
            result = orchestrator.run(question=QUESTIONS[i - 1], context=context)
            write(output / f"m5-{current_case}-result.json", result.model_dump(mode="json"))
            row = dict(
                id=current_case,
                execution="ACTUAL_EXECUTION",
                status=result.status,
                roles=[e.role for e in result.specialist_executions],
                candidates=len(result.candidates),
                usage=result.usage.model_dump(mode="json"),
                latency_ms=result.latency_ms,
            )
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "usage"}), flush=True)
    finally:
        write(
            output / "m5-summary.json",
            dict(rows=rows, actual_provider_calls=len(calls), calls=calls),
        )
        adapter.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "m7", "m5", "integrity"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "QA-Q01"
    ):
        raise ValueError("QA_Q01_output_required")
    if args.mode == "prepare":
        prepare(root, output)
    elif args.mode == "m7":
        run_m7(root, output)
    elif args.mode == "m5":
        run_m5(root, output)
    else:
        before, after = read(output / "hashes-before.json"), protected(root, output)
        changed = [p for p, value in before.items() if after.get(p) != value]
        write(
            output / "integrity.json",
            dict(
                protected_files=len(before), changed=changed, added=sorted(set(after) - set(before))
            ),
        )
        print(json.dumps(dict(protected_files=len(before), changed=changed)), flush=True)
        if changed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
