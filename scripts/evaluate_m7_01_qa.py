"""Fixed-oracle BBS QA replay; adversarial transports and bounded live are separate."""

import argparse
import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from evaluate_m6_01_conversion import digest, save_new
from vietnamese_financial_multi_agent.api.qa_gateway import QACredentialError, create_qa_adapter
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs import VietnameseQAComposer, VietnameseQARequest
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class SavedVerifiedView:
    """Evaluation-only snapshot after one real repository proof-validation read.

    Reuse the public AND-filter implementation verbatim; expose no admission or
    persistence. Latency here is warm saved replay, not disk proof-validation.
    """

    def __init__(self, entries):
        self.entries = list(entries)

    def list_all(self):
        return list(self.entries)

    def query(self, query):
        return VerifiedClaimRepository.query(self, query)


def fake_response(request, mode):
    if mode == "timeout":
        raise TimeoutError
    ids = [
        e["verified_claim_id"] for e in json.loads(request.messages[0].content)["selected_claims"]
    ]
    wire = dict(claim_order=list(reversed(ids)), introduction="by_requirement")
    if mode == "new_value":
        wire["value"] = "999999"
    elif mode == "new_citation":
        wire["citations"] = [dict(pdf_page=999)]
    elif mode == "new_claim":
        wire["claim_order"] = ["verified:invented"]
    elif mode == "reasoning":
        wire["introduction"] = "Doanh nghiệp tốt do hiệu quả tăng."
    elif mode == "drop_caveats":
        wire["caveats"] = []
    elif mode == "duplicate":
        wire["claim_order"] = [ids[0]] * len(ids)
    result = FakeLLMTransport(json_text="{" if mode == "malformed" else json.dumps(wire))(request)
    if mode == "503":
        result.status, result.finish_reason, result.output = "error", "error", None
        result.error = GatewayError(
            category="provider_unavailable",
            code="provider_unavailable",
            origin="provider",
            retryability="retryable",
            provider_error_code="http_503",
        )
    return result


def assess(case, response, entries):
    """Oracle checks use original accepted payloads, never Composer output as labels."""
    expected_ids = {key for r in case["requirements"] for key in r["required_verified_claim_ids"]}
    actual_ids = set(response.used_verified_claim_ids)
    wrong_selection = actual_ids - expected_ids
    unsupported = fabricated = violations = lost_caveats = 0
    for segment in response.grounded_segments:
        for key in segment.verified_claim_ids:
            original = entries.get(key)
            if original is None:
                unsupported += 1
                continue
            identity, claim = original.identity, original.accepted_claim
            unsupported += segment.content != original.content
            expected_context = (
                identity.company_id,
                identity.document_id,
                identity.snapshot_id,
                identity.period,
            )
            context = segment.context
            violations += (
                context.company_id,
                context.document_id,
                context.snapshot_id,
                context.period,
            ) != expected_context
            violations += any(
                case["request"].get(k) is not None and getattr(identity, k) != case["request"][k]
                for k in ("company_id", "document_id", "snapshot_id", "period")
            )
            required = set(
                original.caveats
                + claim.caveats
                + [v for e in claim.supporting_evidence for v in e.caveats]
                + [v for c in original.citations for v in c.limitations]
            )
            lost_caveats += len(required - set(segment.caveats))
            lost_caveats += len(
                set(
                    original.decision.limitations
                    + original.decision.unresolved_blockers
                    + claim.missing_information
                )
                - set(segment.limitations)
            )
            fabricated += sum(c not in segment.citations for c in original.citations)
        originals = [entries[k] for k in segment.verified_claim_ids if k in entries]
        fabricated += sum(not any(c in e.citations for e in originals) for c in segment.citations)
        if case.get("expected_scope"):
            violations += segment.context.reporting_scope != case["expected_scope"]
    fabricated += sum(
        not any(c in s.citations for s in response.grounded_segments) for c in response.citations
    )
    status_ok = response.status == case["expected_status"]
    coverage_ok = len(response.answered_requirements) == case.get(
        "expected_answered_requirements", len(case["requirements"])
    )
    if "expected_unanswered_requirements" in case:
        coverage_ok &= (
            len(response.unanswered_requirements) == case["expected_unanswered_requirements"]
        )
    gateway_ok = (
        not case.get("expected_gateway") or response.llm_metadata.status == case["expected_gateway"]
    )
    return dict(
        passed=bool(
            status_ok
            and coverage_ok
            and actual_ids == expected_ids
            and gateway_ok
            and not (unsupported or fabricated or violations or lost_caveats)
            and response.validation_result.valid
        ),
        status_agreement=status_ok,
        coverage_agreement=coverage_ok,
        selection_precision=1 - len(wrong_selection) / len(actual_ids) if actual_ids else None,
        selection_recall=len(actual_ids & expected_ids) / len(expected_ids)
        if expected_ids
        else None,
        unsupported_financial_claims=unsupported,
        fabricated_citations=fabricated,
        snapshot_scope_violations=violations,
        lost_caveats=lost_caveats,
        missing_selected_ids=sorted(expected_ids - actual_ids),
        unexpected_selected_ids=sorted(wrong_selection),
        gateway_agreement=gateway_ok,
    )


def evaluate(root, output, ledger_root, mode):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M7-01-"
    ):
        raise ValueError("new_output_must_be_M7_01_under_artifacts_evidence")
    output.mkdir(parents=True, exist_ok=False)
    if mode == "integrity":
        before = load(root / "artifacts/evidence/M7-01-preflight/hashes-before.json")
        after = {name: digest(root / name) if (root / name).is_file() else None for name in before}
        save_new(output / "hashes-after.json", after)
        summary = dict(
            protected_hashes=len(before),
            unchanged=before == after,
            changed=[name for name in before if before[name] != after[name]],
        )
        save_new(output / "summary.json", summary)
        print(json.dumps(summary), flush=True)
        return summary["unchanged"]
    oracle_path = root / "evaluation/m7-01-scenarios.json"
    oracle = load(oracle_path)
    save_new(output / "expected-oracle.json", oracle)
    ledger_file = ledger_root / "verified-claims.json"
    if not ledger_file.is_file() or digest(ledger_file) != oracle["ledger_sha256"]:
        raise ValueError("ledger_source_missing_or_not_pinned")
    print("Hydrating proof-validated M6 ledger (read only)", flush=True)
    ledger = VerifiedClaimLedger(VerifiedClaimRepository(ledger_root))
    entries = {
        e.identity.verified_claim_id: e for e in ledger.find_claims(VerifiedClaimQuery()).claims
    }
    ledger = VerifiedClaimLedger(SavedVerifiedView(entries.values()))
    print(f"Hydrated {len(entries)} verified claims", flush=True)
    adapter = None
    if mode == "live":
        try:
            adapter, _ = create_qa_adapter(root)
        except QACredentialError:
            save_new(
                output / "summary.json",
                dict(
                    live_status="BLOCKED",
                    reason="credential_unavailable",
                    calls=0,
                    oracle_sha256=digest(oracle_path),
                ),
            )
            print("LIVE BLOCKED: credential unavailable", flush=True)
            return False
    cases = [c for c in oracle["scenarios"] if mode != "live" or c.get("live")]
    rows, calls = [], []
    empty = VerifiedClaimLedger(VerifiedClaimRepository(output / "empty-ledger"))
    sentinels = Counter()

    def forbid(label):
        def blocked(*args, **kwargs):
            sentinels[label] += 1
            raise AssertionError("unverified_source_or_calculator_used")

        return blocked

    guards = ExitStack()
    for target, label in (
        (
            "tools.financial_calculator.FinancialCalculator.calculate_financial_metric",
            "metric_calculations",
        ),
        (
            "tools.financial_retrieval.FinancialRetrievalTools.find_financial_facts",
            "unverified_sources",
        ),
        ("agents.orchestrator.FinancialMultiAgentOrchestrator.run", "unverified_sources"),
    ):
        guards.enter_context(patch("vietnamese_financial_multi_agent." + target, forbid(label)))
    try:
        for case in cases:

            def transport(request, scenario=case):
                if mode == "live":
                    # Persist a task-wide budget *before* sending. Never retry/rotate keys.
                    budget = root / "artifacts/evidence/M7-01-call-budget"
                    budget.mkdir(exist_ok=True)
                    slot = next(
                        (i for i in range(1, 4) if not (budget / f"call-{i}.json").exists()), None
                    )
                    if slot is None:
                        raise ValueError("task_live_budget_exhausted")
                    save_new(
                        budget / f"call-{slot}.json",
                        dict(case_id=scenario["id"], request_id=request.request_id),
                    )
                call = dict(case_id=scenario["id"], mode=mode)
                calls.append(call)
                save_new(output / f"request-{len(calls)}.json", request.model_dump(mode="json"))
                result = (
                    adapter(request)
                    if mode == "live"
                    else fake_response(request, scenario["gateway_mode"])
                )
                call["response"] = result.model_dump(mode="json")
                save_new(output / f"gateway-{len(calls)}.json", call)
                return result

            gateway = (
                SharedLLMGateway({"gemini": transport})
                if (mode == "live" or case.get("gateway_mode"))
                else None
            )
            request = VietnameseQARequest.model_validate(case["request"])
            if mode == "live":
                request.allow_gateway = True
            composer = VietnameseQAComposer(empty if case.get("empty_ledger") else ledger, gateway)
            start = perf_counter()
            response = composer.compose(request)
            row = dict(
                id=case["id"],
                group=case["group"],
                expected_status=case["expected_status"],
                status=response.status,
                latency_ms=(perf_counter() - start) * 1000,
                llm=response.llm_metadata.model_dump(mode="json"),
                answered=len(response.answered_requirements),
                unanswered=len(response.unanswered_requirements),
                **assess(case, response, entries),
            )
            rows.append(row)
            save_new(output / f"response-{case['id']}.json", response.model_dump(mode="json"))
            print(
                f"{case['id']}: {response.status} {'PASS' if row['passed'] else 'FAIL'}", flush=True
            )
    finally:
        guards.close()
        if adapter:
            adapter.close()
    groups = {
        name: dict(
            cases=len(group := [r for r in rows if r["group"] == name]),
            passed=sum(r["passed"] for r in group),
        )
        for name in sorted({r["group"] for r in rows})
    }
    fallbacks = [r for r in rows if r["llm"]["status"] == "fallback"]
    summary = dict(
        mode=mode,
        all_passed=all(r["passed"] for r in rows),
        cases=len(rows),
        groups=groups,
        oracle_sha256=digest(oracle_path),
        ledger_sha256=oracle["ledger_sha256"],
        availability=dict(
            total=len(entries), kinds=dict(Counter(e.identity.kind for e in entries.values()))
        ),
        status_agreement=sum(r["status_agreement"] for r in rows) / len(rows),
        requirement_coverage_agreement=sum(r["coverage_agreement"] for r in rows) / len(rows),
        safety={
            k: sum(r[k] for r in rows)
            for k in (
                "unsupported_financial_claims",
                "fabricated_citations",
                "snapshot_scope_violations",
                "lost_caveats",
            )
        },
        # Composer dependencies contain only ledger/Gateway; source sentinel tests additionally guard tools.
        unverified_candidates_used=sentinels["unverified_sources"],
        unauthorized_metric_calculations=sentinels["metric_calculations"],
        calls=len(calls),
        proposal_statuses=dict(Counter(r["llm"]["status"] for r in rows)),
        fallback_success=sum(r["passed"] for r in fallbacks),
        fallback_cases=len(fallbacks),
        recorded_tokens=sum((r["llm"].get("usage") or {}).get("total_tokens") or 0 for r in rows),
        unknown_usage_calls=sum(
            r["llm"]["calls"]
            and (not r["llm"]["usage"] or r["llm"]["usage"]["total_tokens"] is None)
            for r in rows
        ),
        provider_errors=sum(r["llm"]["error"] is not None for r in rows),
        rows=rows,
        limitations="Source-bound saved-policy QA and separate fake transports; not independent PDF financial accuracy.",
    )
    if mode == "live":
        summary["live_status"] = (
            "SUCCESS"
            if len(calls) == 3
            and all(r["llm"]["status"] == "accepted" and r["passed"] for r in rows)
            else "PARTIAL"
        )
    save_new(output / "summary.json", summary)
    print(
        json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False),
        flush=True,
    )
    return summary["all_passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--ledger-root", type=Path, default=Path("artifacts/evidence/M6-06-ledger-final-v2/ledger")
    )
    parser.add_argument("--mode", choices=("offline", "live", "integrity"), default="offline")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    raise SystemExit(
        0 if evaluate(root, args.output.resolve(), args.ledger_root.resolve(), args.mode) else 1
    )
