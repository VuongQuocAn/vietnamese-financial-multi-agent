"""Bounded M7-only acceptance on saved real Ledger; no OCR or M5/M6 execution.

Preparation is offline. --live is explicitly opt-in, one irreversible reservation
per case and at most four provider attempts, including errors; never resume/retry.
Private payloads stay under ignored artifacts/evidence/M7-LITE-01.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from vietnamese_financial_multi_agent.api.claim_selection import select_claims
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)

BASELINE = "b9d0cdb88417a344f1269dbfb6cf7300b18824bd"
SOURCE = Path("artifacts/evidence/FIX-02/final-acceptance/remediation-native-proof-final")
OUTPUT = Path("artifacts/evidence/M7-LITE-01")
CASES = {"L04": "Q21", "L05": "Q23", "L08": "L08", "L09": "L09"}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    freeze = json.loads((SOURCE / "freeze.json").read_bytes())
    if freeze["implementation_sha"] != BASELINE:
        raise ValueError("wrong_saved_baseline")
    ledger = VerifiedClaimLedger(VerifiedClaimRepository(SOURCE / "ledger"))
    rows = json.loads((SOURCE / "results.json").read_bytes())
    cases = []
    for row in rows:
        if row["case"] not in CASES:
            continue
        trace = row["actual"]["trace"]
        scope = {k: trace[k] for k in ("document_id", "company_id", "snapshot_id")}
        request = FinancialQARequest(
            question=row["question"],
            m7_lite=True,
            max_provider_calls=1,
            execution_mode="gemini",
            **scope,
        )
        entries = ledger.find_claims(VerifiedClaimQuery(**scope)).claims
        current = [o["verified_claim_id"] for o in trace["outcomes"] if o["verified_claim_id"]]
        selected, excluded = select_claims(request, entries, current)
        offline, metadata = compose_lite(request, selected)
        cases.append(
            dict(
                case=CASES[row["case"]],
                saved_case=row["case"],
                question=row["question"],
                request=request.model_dump(mode="json"),
                current_request_claims=current,
                input_claims=[e.identity.verified_claim_id for e in entries],
                selected_claims=[e.identity.verified_claim_id for e in selected],
                claims=[
                    dict(
                        id=e.identity.verified_claim_id,
                        content=e.content,
                        decision=e.decision.decision,
                        kind=e.identity.kind,
                        period=e.identity.period,
                        citation_pages=[c.pdf_page for c in e.citations],
                    )
                    for e in selected
                ],
                excluded=excluded,
                legacy_answer=row["actual"]["answer_vi"],
                legacy_status=row["actual"]["status"],
                legacy_released=row["actual"]["used_verified_claim_ids"],
                offline_answer=offline["answer_vi"],
                offline_trace=metadata,
            )
        )
        print(CASES[row["case"]], "selected", len(selected), "excluded", len(excluded), flush=True)
    if len(cases) != 4:
        raise ValueError("missing_saved_case")
    return ledger, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.live:
        # Reserve the whole run before validation/network. No hidden retries or
        # automatic continuation after credentials/quota/provider recover.
        with (OUTPUT / "live-reserved.json").open("x", encoding="utf-8") as f:
            json.dump(dict(max_calls=4, retry=False), f)
    ledger, cases = prepare()
    before = digest(SOURCE / "ledger/verified-claims.json")
    evidence = dict(
        baseline=BASELINE,
        source_run=SOURCE.as_posix(),
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        ledger_sha256=before,
        results_sha256=digest(SOURCE / "results.json"),
        cases=cases,
    )
    if not args.live:
        from evaluate_generalization import pipeline as load_pipeline

        pipeline, _ = load_pipeline(Path.cwd(), "BBS_2025", OUTPUT / "smoke")
        pipeline.repository = ledger._repository
        case = next(c for c in cases if c["case"] == "Q23")
        smoke = pipeline.run(
            FinancialQARequest.model_validate(case["request"]).model_copy(
                update={"allow_gateway": False}
            )
        )
        evidence["pipeline_smoke"] = smoke.model_dump(mode="json")
        if (
            set(smoke.used_verified_claim_ids) != set(case["selected_claims"])
            or smoke.trace.provider_calls
            or smoke.trace.stages["m5"].status != "NOT_EXECUTED"
            or smoke.trace.stages["m6"].status != "NOT_EXECUTED"
        ):
            save(OUTPUT / "preparation.json", evidence)
            raise ValueError("real_pipeline_smoke_failed")
        print("Real Q23 pipeline smoke: PASS, no M5/M6/provider", flush=True)
        save(OUTPUT / "preparation.json", evidence)
        return
    try:
        adapter, credential = create_qa_adapter(Path.cwd())
    except Exception as error:
        evidence["blocker"] = type(error).__name__
        save(OUTPUT / "live-results.json", evidence)
        return
    evidence["credential_source"] = credential.source
    calls = 0
    for case in cases:
        if not case["selected_claims"]:
            case["live_status"] = "NOT_TESTABLE"
            continue
        selected = ledger.find_claims(
            VerifiedClaimQuery(
                **{k: case["request"][k] for k in ("company_id", "document_id", "snapshot_id")}
            )
        ).claims
        by_id = {e.identity.verified_claim_id: e for e in selected}
        selected = [by_id[k] for k in case["selected_claims"]]

        def transport(request, case_id=case["case"]):
            nonlocal calls
            if calls >= 4:
                raise ValueError("live_budget_exhausted")
            calls += 1
            receipt = OUTPUT / f"{case_id}-provider.json"
            with receipt.open("x", encoding="utf-8") as f:
                json.dump(dict(attempt=calls, status="reserved"), f)
            result = adapter(request)
            save(receipt, result.model_dump(mode="json"))
            return result

        fields, trace = compose_lite(
            FinancialQARequest.model_validate(case["request"]),
            selected,
            gateway=SharedLLMGateway({"gemini": transport}),
        )
        case["live_status"] = "ATTEMPTED"
        case["lite_answer"] = fields["answer_vi"]
        case["final_status"] = fields["status"]
        case["trace"] = trace
        case["citations"] = [r.model_dump(mode="json") for r in fields["citations"]]
        case["retained"] = fields["used_verified_claim_ids"]
        case["lost"] = sorted(set(case["selected_claims"]) - set(case["retained"]))
        # Shared citations can have multiple variants bound to distinct claims.
        # Audit each variant against at least one explicitly bound ACCEPT claim.
        case["citation_binding_errors"] = [
            r.citation_id
            for r in fields["citations"]
            if any(
                not any(c in by_id[k].citations for k in r.bound_verified_claim_ids)
                for c in r.source_citations
            )
        ]
        evidence["actual_calls"] = calls
        save(OUTPUT / "live-results.json", evidence)
        print(
            case["case"],
            fields["status"],
            "retained",
            len(case["retained"]),
            "tokens",
            trace["known_total_tokens"],
            "fallback",
            trace["fallback"],
            flush=True,
        )
    evidence["ledger_unchanged"] = before == digest(SOURCE / "ledger/verified-claims.json")
    save(OUTPUT / "live-results.json", evidence)


if __name__ == "__main__":
    main()
