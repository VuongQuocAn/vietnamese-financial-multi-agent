"""Post-runtime BBS comparison; independent references never enter the QA pipeline."""

import json
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from run_e2e_financial_qa import write
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts/evidence/E2E-01"
    reference = json.loads(
        (root / "artifacts/evidence/QA-Q01/independent-reference-input.json").read_text(
            encoding="utf-8"
        )
    )
    observations = {o["id"]: o for o in reference["observations"]}
    items = {
        "b01.total_assets": "assets_2025",
        "b01.total_liabilities": "liabilities_2025",
        "b02.net_revenue": "revenue_2025",
        "b02.gross_profit": "gross_profit_2025",
        "b02.profit_after_tax": "net_profit_2025",
        "b03.operating_cash_flow": "cfo_2025",
    }
    formulas = {
        "gross_margin": {"gross_profit": "gross_profit_2025", "revenue": "revenue_2025"},
        "debt_to_assets": {"liabilities": "liabilities_2025", "assets": "assets_2025"},
    }
    entries = {
        e.identity.verified_claim_id: e
        for e in VerifiedClaimRepository(output / "ledger").list_all()
    }
    comparisons, cases = [], []
    for label in ("E01", "E02", "E03", "E04", "E05"):
        payload = json.loads((output / f"{label}.json").read_text(encoding="utf-8"))
        response = payload["response"]
        trace = response["trace"]
        expected_identity = (trace["company_id"], trace["document_id"], trace["snapshot_id"])
        for key in response["used_verified_claim_ids"]:
            entry = entries[key]
            assert entry.verification_status == "verified" and entry.decision.decision == "ACCEPT"
            assert (
                entry.identity.company_id,
                entry.identity.document_id,
                entry.identity.snapshot_id,
            ) == expected_identity
            assert entry.identity.period[:4] == "2025"
            assert all(
                (c.document_id, c.snapshot_id) == expected_identity[1:] for c in entry.citations
            )
            pages = {c.pdf_page for c in entry.citations}
            claim = entry.accepted_claim
            if claim.calculation:
                calc = claim.calculation
                expected_operands = formulas[calc.formula_id]
                operands = {o.role: o for o in calc.trace.operands}
                numbers = []
                for role, reference_id in expected_operands.items():
                    independent = observations[reference_id]
                    operand = operands[role]
                    assert Decimal(operand.value) == Decimal(independent["value"])
                    assert operand.unit == "VND" and operand.context.scale == Decimal(1)
                    assert independent["page"] in pages
                    numbers.append(Decimal(independent["value"]))
                expected = (numbers[0] / numbers[1] * 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                assert Decimal(calc.result) == expected
                value, target = calc.result, calc.formula_id
            else:
                evidence = [e for e in claim.supporting_evidence if e.kind == "fact"]
                assert len(evidence) == 1
                item = evidence[0]
                independent = observations[items[item.canonical_item_id]]
                assert Decimal(item.value) == Decimal(independent["value"])
                assert item.unit == "VND" and Decimal(item.scale) == Decimal(1)
                assert independent["page"] in pages
                value, target = item.value, item.canonical_item_id
            comparisons.append(
                dict(
                    case=label,
                    verified_claim_id=key,
                    target=target,
                    value=value,
                    pdf_pages=sorted(pages),
                    independent_match=True,
                )
            )
        if response["used_verified_claim_ids"]:
            assert trace["firewall_decision"] in ("ALLOW", "ALLOW_WITH_CAVEAT")
            assert response["citations"]
        rerun = output / f"{label}-rerun.json"
        cached = (
            json.loads(rerun.read_text(encoding="utf-8"))["response"] if rerun.exists() else None
        )
        if cached:
            assert cached["trace"]["provider_calls"] == 0
            assert cached["trace"]["stages"]["m5"]["status"] == "NOT_EXECUTED"
            assert cached["trace"]["stages"]["m6"]["status"] == "NOT_EXECUTED"
            assert cached["used_verified_claim_ids"] == response["used_verified_claim_ids"]
            assert cached["answer_vi"] == response["answer_vi"]
        cases.append(
            dict(
                case=label,
                status=response["status"],
                mode=response["mode"],
                answer_excerpt=response["answer_vi"].split("\nLưu ý:")[0],
                native_decisions=trace["native_decisions"],
                newly_accepted=response["newly_accepted_claims"],
                reused=response["reused_claims"],
                agents=trace["executed_agents"],
                tool_calls=len(trace["tool_calls"]),
                citations=len(response["citations"]),
                firewall=trace["firewall_decision"],
                stages=trace["stages"],
                latency_ms=trace["total_latency_ms"],
                rerun_mode=cached["mode"] if cached else None,
                rerun_latency_ms=cached["trace"]["total_latency_ms"] if cached else None,
            )
        )
    calls = [
        json.loads(line)
        for line in (output / "provider-attempts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    starts = [c for c in calls if c["event"] == "started"]
    finishes = [c for c in calls if c["event"] == "finished"]
    assert len(starts) <= 25
    summary = dict(
        reference_method=reference["method"],
        reference_reused_from="QA-Q01 independent PDF readings",
        new_visual_pdf_audit=False,
        cases=cases,
        comparisons=comparisons,
        admitted_entries=len(entries),
        provider_attempts=len(starts),
        known_total_tokens=sum(c["usage"].get("total_tokens") or 0 for c in finishes),
        provider_errors=sum(c["status"] != "success" for c in finishes),
        unknown_usage_attempts=len(starts)
        - sum(c["usage"].get("total_tokens") is not None for c in finishes),
        native_totals=dict(sum((Counter(c["native_decisions"]) for c in cases), Counter())),
    )
    write(output / "financial-audit.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
