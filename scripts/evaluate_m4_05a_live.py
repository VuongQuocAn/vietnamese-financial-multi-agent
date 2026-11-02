"""Bounded live intent QA BBS: tối đa 5 requests, không retry/rotation tự động."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from evaluate_d04_closure import save
from evaluate_m4_04_evidence import manifest
from evaluate_m4_05_qa import assess, reference_for, setup
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.api.qa_gateway import QACredentialError, create_qa_adapter
from vietnamese_financial_multi_agent.core.gemini_adapter import DEFAULT_GEMINI_MODEL
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    FinancialCalculationResponse,
    FinancialQABaseline,
    QAContext,
)
from vietnamese_financial_multi_agent.tools.question_understanding import understand


def json_records(value):
    return json.loads(json.dumps(value, default=lambda item: item.model_dump(mode="json")))


def evaluate(root, output, *, key_file=None, key_index=0, case_ids=None):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    hashes = manifest(root)
    for path in (root / "artifacts/evidence/M4-05-final").glob("*.json"):
        hashes[path.relative_to(root).as_posix()] = digest(path)
    save(output / "hashes-before.json", hashes)
    data, scopes, recovery, documents = setup(root)
    cases = load(root / "evaluation/m4-05a-live-questions.json")
    if case_ids:
        if not set(case_ids) <= {c["id"] for c in cases}:
            raise ValueError("Unknown live case ID")
        cases = [c for c in cases if c["id"] in case_ids]
    assert 1 <= len(cases) <= 5
    benchmark = {c["question"] for c in load(root / "evaluation/m4-05-questions.json")}
    assert all(c["question"] not in benchmark for c in cases)
    accepted = [
        FinancialCalculationResponse.model_validate_json(json.dumps(row))
        for row in load(root / "artifacts/evidence/M4-03-final/executions.json")
    ]
    references = {c["id"]: reference_for(c, data, scopes, recovery, accepted) for c in cases}
    save(output / "references.json", json_records(references))
    api = FinancialQABaseline(SnapshotCatalog(**data), documents)
    preflights = []
    for case in cases:
        parsed, errors = understand(case["question"])
        offline = api.answer(case["question"], QAContext())
        assert offline.llm.calls == 0 and offline.status == "unsupported", case["id"]
        preflights.append(
            dict(
                id=case["id"],
                parsed=parsed.model_dump(mode="json"),
                errors=errors,
                qa_status=offline.status,
            )
        )
    save(output / "deterministic-preflight.json", preflights)
    adapter, credential = create_qa_adapter(root, key_file=key_file, key_index=key_index)
    save(
        output / "credential-metadata.json",
        dict(
            source=credential.source,
            key_count=credential.key_count,
            key_index=credential.key_index,
        ),
    )
    calls, rows, responses = [], [], []

    def transport(request):
        if len(calls) >= 5:
            raise RuntimeError("live_request_budget_exhausted")
        result = adapter(request)
        calls.append(dict(request_id=request.request_id, response=result.export()))
        save(output / f"gateway-{len(calls):02d}.json", calls[-1])
        return result

    api = FinancialQABaseline(
        SnapshotCatalog(**data), documents, gateway=SharedLLMGateway({"gemini": transport})
    )
    try:
        for case in cases:
            # Không truyền document/year/target; Gemini phải hiểu chính câu hỏi.
            context = QAContext(allow_gateway=True)
            assert context.canonical_item_id is None and context.formula_id is None
            previous = len(calls)
            start = perf_counter()
            response = api.answer(case["question"], context)
            elapsed = (perf_counter() - start) * 1000
            checks = assess(response, references[case["id"]])
            gateway_used = (
                response.llm.calls == len(calls) - previous == 1
                and response.llm.parsing_method == "gateway"
            )
            rows.append(
                dict(
                    id=case["id"],
                    question=case["question"],
                    parsed_by=response.llm.parsing_method,
                    intent=response.parsed.intent,
                    status=response.status,
                    **checks,
                    gateway_used=gateway_used,
                    calls=response.llm.calls,
                    latency_ms=elapsed,
                    llm=response.llm.model_dump(mode="json"),
                )
            )
            responses.append(
                dict(
                    id=case["id"],
                    context=context.model_dump(mode="json"),
                    response=response.model_dump(mode="json"),
                )
            )
            save(output / f"response-{case['id']}.json", responses[-1])
            save(output / f"score-{case['id']}.json", rows[-1])
            print(
                json.dumps(
                    dict(
                        id=case["id"],
                        status=response.status,
                        correct=checks["correct"],
                        gateway_used=gateway_used,
                        calls=response.llm.calls,
                        llm_status=response.llm.status,
                        error=response.llm.error.category if response.llm.error else None,
                    )
                ),
                flush=True,
            )
            if response.llm.error:
                # Không lặp lỗi quota/network hoặc chuyển key không có bằng chứng.
                break
    finally:
        adapter.close()
    save(output / "responses.json", responses)
    save(output / "scores.json", rows)
    save(output / "gateway-responses.json", calls)
    after = {p: digest(root / p) for p in hashes}
    assert after == hashes
    save(output / "hashes-after.json", after)
    known_tokens = all(
        r["llm"]["usage"] and r["llm"]["usage"]["source"] == "provider_reported" for r in rows
    )
    summary = dict(
        mode="live_Gemini_real_BBS",
        requested_model=DEFAULT_GEMINI_MODEL,
        provider_reported_models=sorted(
            {
                r["llm"]["provenance"]["provider_reported_model"]
                for r in rows
                if r["llm"]["provenance"] and r["llm"]["provenance"]["provider_reported_model"]
            }
        ),
        questions_attempted=len(rows),
        questions_not_run=[c["id"] for c in cases[len(rows) :]],
        calls=len(calls),
        gateway_parsed=sum(r["gateway_used"] for r in rows),
        successful_gateway_responses=sum(r["llm"]["status"] == "success" for r in rows),
        correct=sum(r["correct"] and r["gateway_used"] for r in rows),
        answered=sum(r["status"] == "answered" for r in rows),
        grounded=sum(r["grounded_citations"] for r in rows),
        tokens={
            name: sum(r["llm"]["usage"][name] for r in rows)
            if known_tokens and all(r["llm"]["usage"][name] is not None for r in rows)
            else None
            for name in ("input_tokens", "output_tokens", "total_tokens")
        },
        protected_input_hashes=len(hashes),
        hashes_unchanged=True,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/M4-05a-live"))
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--key-index", type=int, default=0)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    if not args.allow_live:
        parser.error("Live requests require --allow-live")
    try:
        evaluate(
            Path.cwd().resolve(),
            args.output.resolve(),
            key_file=args.key_file,
            key_index=args.key_index,
            case_ids=args.cases,
        )
    except QACredentialError as error:
        print(json.dumps(dict(live_status="configuration_error", error_code=str(error))))
        raise SystemExit(1) from None
