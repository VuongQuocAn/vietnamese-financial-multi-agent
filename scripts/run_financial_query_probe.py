"""PDF-bound finite structured queries; input JSON contains cache paths and query specs."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from vietnamese_financial_multi_agent.accounting import evaluate_automated_relationships
from vietnamese_financial_multi_agent.accounting.financial_runtime import (
    process_financial_pdf,
    recover_financial_target,
)
from vietnamese_financial_multi_agent.tools.financial_query import (
    EvidenceSelector,
    FinancialQuery,
    answer_query,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = (Path(__file__).resolve().parents[1] / "artifacts").resolve()
    if not args.output.resolve().is_relative_to(root):
        parser.error("output must be under ignored artifacts/")
    config = json.loads(args.spec.read_text(encoding="utf-8"))
    cache = {
        int(p): json.loads(Path(f).read_text(encoding="utf-8")) for p, f in config["cache"].items()
    }
    started = perf_counter()
    runtime = process_financial_pdf(
        args.pdf,
        symbol=config["symbol"],
        year=config["year"],
        pages=list(cache),
        cached_records=cache,
    )
    evidence = runtime["evidence"]
    relationships = evaluate_automated_relationships(runtime["records"])
    queries = [
        FinancialQuery(
            q["query_id"],
            tuple(EvidenceSelector(**s) for s in q["operands"]),
            q.get("operation", "retrieve"),
        )
        for q in config["queries"]
    ]
    before = [answer_query(q, evidence, relationship_checks=relationships) for q in queries]
    recoveries = []
    for request in config.get("recoveries", []):
        result = recover_financial_target(
            args.pdf,
            selector=EvidenceSelector(**request["selector"]),
            target=request["target"],
            evidence=evidence,
            symbol=config["symbol"],
            year=config["year"],
            cached_record=json.loads(Path(request["cache"]).read_text(encoding="utf-8")),
        )
        evidence = result["evidence"]
        recoveries.append(dict(target=request["target"], success=result["target_recovered"]))
    after = [answer_query(q, evidence, relationship_checks=relationships) for q in queries]
    report = dict(
        mode="structured_query_probe",
        before=before,
        after=after,
        recoveries=recoveries,
        gemini_calls=0,
        elapsed_seconds=perf_counter() - started,
        quality=runtime["quality"].model_dump(mode="json"),
        trace=[e.model_dump(mode="json") for e in evidence],
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            dict(
                queries=len(queries),
                before_answered=sum(a["status"] == "answered" for a in before),
                after_answered=sum(a["status"] == "answered" for a in after),
                recoveries=recoveries,
                elapsed_seconds=report["elapsed_seconds"],
            )
        )
    )


if __name__ == "__main__":
    main()
