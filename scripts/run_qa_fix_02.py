"""QA-Fix-02: saved diagnostic or bounded fresh BBS orchestration; no extraction."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

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
from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

QUESTIONS = {
    "Q03": "Biên lợi nhuận gộp của BBS năm 2025 là bao nhiêu? Hãy nêu công thức và các số liệu sử dụng.",
    "Q06": "Biên lợi nhuận gộp và tỷ lệ nợ trên tổng tài sản nói lên điều gì về khả năng sinh lời và mức độ sử dụng nợ của BBS năm 2025?",
    "N02": "Cho biết dòng tiền thuần từ hoạt động kinh doanh và doanh thu thuần của BBS năm 2025, kèm nguồn cho mỗi chỉ tiêu.",
    "N03": "Hãy cho biết biên lợi nhuận gộp, tỷ lệ nợ trên tổng tài sản và dòng tiền thuần từ hoạt động kinh doanh của BBS năm 2025.",
    "Q07": "Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh của BBS năm 2025.",
    "Q08": "Doanh thu thuần và dòng tiền kinh doanh của BBS năm 2025 có cho thấy chất lượng lợi nhuận tốt không? Giải thích dựa trên số liệu.",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    # Exclusive files: no accidental overwrite of accepted or earlier traces.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, output, cases, live, *, correction=False):
    output.mkdir(parents=True, exist_ok=True)
    calls = []
    # Append a numbered ledger after every attempt; inspect these on resume even
    # if a prior process died before the final summary was written.
    ledgers = sorted(output.glob("provider-ledger-*.json"))
    if ledgers:
        calls = read(ledgers[-1])
    before = {"web/next-env.d.ts": digest(root / "web/next-env.d.ts")}
    for path in (root / "artifacts/evidence/QA-Q01").glob("m5-*.json"):
        before[path.relative_to(root).as_posix()] = digest(path)
    data, scopes, _, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    # Logical equality of the hydrated data is checked below, no full dataset hashing.
    input_before = json.dumps(
        {
            k: [x.model_dump(mode="json") for x in data[k]]
            for k in ("facts", "metrics", "source_reviews")
        },
        sort_keys=True,
    )
    adapter = None
    if live:
        adapter, credential = create_qa_adapter(root)
        if not (output / "configuration.json").exists():
            write(
                output / "configuration.json",
                dict(
                    model=PlannerContext().model.model,
                    key_source=credential.source,
                    key_index=credential.key_index,
                    rotation=False,
                    maximum_provider_attempts=20,
                ),
            )
    current = None

    def transport(request):
        if len(calls) >= 20:
            raise ValueError("QA_Fix_02_provider_budget_exhausted")
        number = len(calls) + 1
        stem = f"{current}-call{number:02}"
        write(output / f"{stem}-request.json", request.model_dump(mode="json"))
        row = dict(
            number=number,
            case=current,
            request_id=request.request_id,
            status="started_usage_unknown",
        )
        calls.append(row)
        # A started call consumes budget even after interruption.
        write(output / f"provider-ledger-{number:02}-a.json", calls)
        started = perf_counter()
        response = adapter(request)
        row.update(
            response=response.export(),
            latency_ms=(perf_counter() - started) * 1000,
            status=response.status,
        )
        write(output / f"{stem}-response.json", response.export())
        write(output / f"provider-ledger-{number:02}-b.json", calls)
        return response

    try:
        for case in cases:
            current = case + ("-correction" if correction else "")
            target = output / f"{current}-{'actual' if live else 'saved'}-result.json"
            if target.exists():
                raise ValueError("case_already_executed")
            if live and len(calls) >= 20:
                print(
                    json.dumps(
                        dict(
                            case=case,
                            mode="NOT_EXECUTED",
                            reason="provider_attempt_budget_exhausted",
                        )
                    ),
                    flush=True,
                )
                break
            if live:
                gateway = SharedLLMGateway({"gemini": transport})
            else:
                saved = read(root / "artifacts/evidence/QA-Q01/m5-Q07-call03-response.json")

                def replay(request, saved=saved):
                    payload = dict(
                        saved, request_id=request.request_id, correlation=request.correlation
                    )
                    return LLMResponse.model_validate(payload)

                gateway = SharedLLMGateway({"gemini": replay})
            instance = FinancialMultiAgentOrchestrator(
                planner=EvidenceAwareQueryPlanner(catalog, documents, gateway),
                supervisor=RiskAwareSupervisor(catalog),
                router=AdaptiveSpecialistRouter(),
                specialists={
                    "profitability": ProfitabilitySpecialist(gateway),
                    "liquidity_and_leverage": LiquidityLeverageSpecialist(gateway),
                    "cash_flow_and_earnings_quality": CashFlowEarningsQualitySpecialist(gateway),
                },
            )
            context = PlannerContext(
                document_id=scopes[2025]["document_id"],
                snapshot_id=scopes[2025]["snapshot_id"],
                reporting_year=2025,
                provider_attempt_limit=min(2, max(1, 20 - len(calls))),
            )
            result = instance.run(question=QUESTIONS[case], context=context)
            write(
                target,
                dict(
                    mode="ACTUAL_EXECUTION" if live else "SAVED_TRACE",
                    result=result.model_dump(mode="json"),
                ),
            )
            print(
                json.dumps(
                    dict(
                        case=case,
                        status=result.status,
                        planner=result.planner_result.status if result.planner_result else None,
                        roles=[e.role for e in result.specialist_executions],
                        candidates=len(result.candidates),
                        actual_attempts_total=len(calls),
                        stop=result.stop_conditions,
                    ),
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        if adapter:
            adapter.close()
        after = {name: digest(root / name) for name in before}
        input_after = json.dumps(
            {
                k: [x.model_dump(mode="json") for x in data[k]]
                for k in ("facts", "metrics", "source_reviews")
            },
            sort_keys=True,
        )
        write(
            output
            / f"integrity-{'-'.join(cases)}-{'live' if live else 'saved'}{'-correction' if correction else ''}.json",
            dict(
                selected_input_files=len(before),
                hashes_unchanged=before == after,
                hydrated_facts_metrics_reviews_unchanged=input_before == input_after,
            ),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--case", choices=list(QUESTIONS), nargs="+")
    parser.add_argument(
        "--correction",
        action="store_true",
        help="Preserve initial traces and use the same total provider budget",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts/evidence/QA-Fix-02"
    run(
        root,
        output,
        args.case or (list(QUESTIONS) if args.allow_live else ["Q07"]),
        args.allow_live,
        correction=args.correction,
    )


if __name__ == "__main__":
    main()
