"""Run QA on the existing persisted research catalog; never extract or replay M6 proofs."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

from evaluate_m4_05_qa import setup
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

QUESTIONS = {
    "E01": "Biên lợi nhuận gộp của BBS năm 2025 là bao nhiêu? Hãy nêu công thức và các số liệu sử dụng.",
    "E02": "Doanh thu thuần và lợi nhuận sau thuế của BBS năm 2025 là bao nhiêu?",
    "E03": "Tổng tài sản và tỷ lệ nợ phải trả trên tổng tài sản của BBS năm 2025 là bao nhiêu?",
    "E04": "Biên lợi nhuận gộp, tỷ lệ nợ phải trả trên tổng tài sản và dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025 là bao nhiêu?",
    "E05": "Doanh thu và dòng tiền từ hoạt động kinh doanh của BBS năm 2025 có cho thấy chất lượng lợi nhuận tốt không?",
}


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question")
    parser.add_argument("--document")
    parser.add_argument("--snapshot")
    parser.add_argument("--company")
    parser.add_argument("--period")
    parser.add_argument("--reporting-scope", choices=["separate", "consolidated"])
    parser.add_argument("--allow-gateway", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--case", choices=list(QUESTIONS), nargs="+")
    parser.add_argument("--label", default="custom")
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/E2E-01"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/E2E-01"):
        parser.error("output must stay within artifacts/evidence/E2E-01")
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must contain only letters, digits, dash or underscore")
    cases = (
        {args.label: args.question}
        if args.question
        else {key: QUESTIONS[key] for key in (args.case or QUESTIONS)}
    )
    output.mkdir(parents=True, exist_ok=True)
    for label in cases:
        if (output / f"{label}.json").exists():
            parser.error("case already exists; choose a new label/output")
    # Single task-wide durable budget, including interrupted calls across resumes
    # and across output subdirectories. No key/model rotation.
    budget_path = root / "artifacts/evidence/E2E-01/provider-attempts.jsonl"
    budget_path.parent.mkdir(parents=True, exist_ok=True)
    calls = (
        [json.loads(line) for line in budget_path.read_text(encoding="utf-8").splitlines()]
        if budget_path.exists()
        else []
    )
    attempts = sum(row["event"] == "started" for row in calls)
    adapter = None
    current = None

    def record(row):
        with budget_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()

    def transport(request):
        nonlocal attempts
        if attempts >= 25:
            raise ValueError("E2E_01_provider_attempt_budget_exhausted")
        attempts += 1
        number = attempts
        row = dict(number=number, case=current, request_id=request.request_id)
        record(dict(row, event="started", usage="unknown"))
        start = perf_counter()
        response = adapter(request)
        record(
            dict(
                row,
                event="finished",
                status=response.status,
                usage=response.usage.model_dump(mode="json"),
                error=response.error.code if response.error else None,
                latency_ms=(perf_counter() - start) * 1000,
            )
        )
        return response

    data, _, _, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    before = {"web/next-env.d.ts": digest(root / "web/next-env.d.ts")}
    before.update(
        {
            p.relative_to(root).as_posix(): digest(p)
            for p in (root / "artifacts/evidence/QA-Fix-02").glob("*-actual-result.json")
        }
    )
    hydrated = json.dumps(
        {
            k: [x.model_dump(mode="json") for x in data[k]]
            for k in ("facts", "metrics", "source_reviews")
        },
        sort_keys=True,
    )
    gateway = None
    if args.allow_gateway:
        adapter, _ = create_qa_adapter(root)
        gateway = SharedLLMGateway({"gemini": transport})
    repository = VerifiedClaimRepository(output / "ledger")
    service = FinancialQAPipeline(
        catalog=catalog, documents=documents, repository=repository, gateway=gateway
    )
    try:
        for label, question in cases.items():
            current = label
            request = FinancialQARequest(
                question=question,
                document_id=args.document,
                snapshot_id=args.snapshot,
                company_id=args.company,
                period=args.period,
                reporting_scope=args.reporting_scope,
                allow_gateway=args.allow_gateway,
                force_refresh=args.force_refresh,
            )
            response = service.run(request)
            write(
                output / f"{label}.json",
                dict(
                    request=request.model_dump(mode="json"),
                    response=response.model_dump(mode="json"),
                ),
            )
            print(
                json.dumps(
                    dict(
                        case=label,
                        status=response.status,
                        mode=response.mode,
                        accepted=response.newly_accepted_claims,
                        native_decisions=response.trace.native_decisions,
                        agents=response.trace.executed_agents,
                        firewall=response.trace.firewall_decision,
                        latency_ms=response.trace.total_latency_ms,
                        provider_attempts_total=attempts,
                    ),
                    ensure_ascii=False,
                ),
                flush=True,
            )
            print(response.answer_vi, flush=True)
            if response.used_verified_claim_ids and not args.force_refresh:
                current = label + "-rerun"
                cached = service.run(request.model_copy(update={"allow_gateway": False}))
                write(output / f"{label}-rerun.json", dict(response=cached.model_dump(mode="json")))
                print(
                    json.dumps(
                        dict(
                            case=current,
                            mode=cached.mode,
                            status=cached.status,
                            provider_calls=cached.trace.provider_calls,
                            latency_ms=cached.trace.total_latency_ms,
                        ),
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    finally:
        if adapter:
            adapter.close()
        hydrated_after = json.dumps(
            {
                k: [x.model_dump(mode="json") for x in data[k]]
                for k in ("facts", "metrics", "source_reviews")
            },
            sort_keys=True,
        )
        write(
            output / ("integrity-" + "-".join(cases) + ".json"),
            dict(
                selected_input_files=len(before),
                selected_files_unchanged=all(
                    digest(root / name) == value for name, value in before.items()
                ),
                hydrated_facts_metrics_reviews_unchanged=hydrated == hydrated_after,
                provider_attempts_total=attempts,
            ),
        )


if __name__ == "__main__":
    main()
