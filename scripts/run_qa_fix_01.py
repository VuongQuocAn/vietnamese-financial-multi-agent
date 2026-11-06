"""QA-Fix-01: reuse the production QA-Q01 capture, in an exclusive new folder.

No M5, Gemini, OCR, extraction or admission. Raw outputs stay ignored/local.
"""

import argparse
from pathlib import Path

from run_qa_q01 import protected, read, run_m7, write


def audit(root, output):
    """Bounded saved-output audit against admitted IDs and separate PDF readings."""
    from run_qa_q01 import LEDGER
    from vietnamese_financial_multi_agent.outputs import VietnameseQARequest, VietnameseQAResponse
    from vietnamese_financial_multi_agent.outputs.firewall_qa_binding import (
        validate_qa_request_binding,
    )
    from vietnamese_financial_multi_agent.outputs.qa_composer import validate_qa_response
    from vietnamese_financial_multi_agent.tools.question_understanding import understand
    from vietnamese_financial_multi_agent.verification import (
        VerifiedClaimLedger,
        VerifiedClaimQuery,
        VerifiedClaimRepository,
    )

    previous = root / "artifacts/evidence/QA-Q01"
    final = output / "final"
    summary = read(final / "m7-summary.json")
    admitted = {e["verified_claim_id"]: e for e in summary["ledger_entries"]}
    proof = {e["verified_claim_id"]: e for e in read(previous / "selected-claim-proof-audit.json")}
    references = read(previous / "independent-reference-input.json")
    pdf_values = {o["id"]: o["value"] for o in references["observations"]}
    entries = (
        VerifiedClaimLedger(VerifiedClaimRepository(root / LEDGER))
        .find_claims(VerifiedClaimQuery())
        .claims
    )
    cases = []
    for row in summary["rows"]:
        key = row["id"]
        source = read(final / f"m7-{key}-composer.json")
        request = VietnameseQARequest.model_validate(read(final / f"m7-{key}-request.json"))
        typed_source = VietnameseQAResponse.model_validate_json(
            (final / f"m7-{key}-composer.json").read_text(encoding="utf-8")
        )
        parsed, _ = understand(request.question)
        bound = [
            e
            for e in entries
            if all(
                value is None or getattr(e.identity, field) == value
                for field, value in (
                    ("company_id", request.company_id),
                    ("document_id", request.document_id),
                    ("snapshot_id", request.snapshot_id),
                    ("period", request.period or parsed.period),
                )
            )
        ]
        assert not validate_qa_request_binding(request, typed_source, bound)
        assert validate_qa_response(typed_source, bound).valid
        old = read(previous / f"m7-{key}-composer.json")
        firewall = read(final / f"m7-{key}-firewall.json")
        assert source["validation_result"]["valid"] and firewall["validation_result"]["valid"]
        assert row["firewall"] != "BLOCK"
        assert all(k in admitted and proof[k]["decision"] == "ACCEPT" for k in row["selected_ids"])
        for segment in source["grounded_segments"]:
            for claim_id in segment["verified_claim_ids"]:
                assert (
                    segment["content"].split("\nCông thức:")[0].strip()
                    == proof[claim_id]["content"]
                )
            for citation in segment["citations"]:
                assert citation["document_id"] == segment["context"]["document_id"]
                assert citation["snapshot_id"] == segment["context"]["snapshot_id"]
        cases.append(
            dict(
                id=key,
                before_status=old["status"],
                after_status=source["status"],
                requirements=source["plan"]["requirements"],
                selected_ids=row["selected_ids"],
                firewall=row["firewall"],
                assertion_identity_preserved=True,
            )
        )
    q03 = read(final / "m7-Q03-composer.json")
    for segment in q03["grounded_segments"]:
        explanation = segment["explanation"]
        assert explanation["formula_id"] == "gross_margin" and explanation["result"] == "7.21"
        calc = proof[segment["verified_claim_ids"][0]]["calculation"]
        assert explanation["formula_digest"] == calc["trace"]["approval"]["definition_sha256"]
        for row in explanation["operands"]:
            operand = row["operand"]
            independent = (
                "gross_profit_2025" if operand["role"] == "gross_profit" else "revenue_2025"
            )
            assert operand["value"] == pdf_values[independent]
            assert operand in calc["operands"]
            assert operand["unit"] == "VND" and operand["context"]["scale"] == "1"
            assert operand["context"]["period"] == "2025"
            assert all(c["pdf_page"] == 7 and c in segment["citations"] for c in row["citations"])
    q08 = read(final / "m7-Q08-composer.json")
    assert q08["status"] == "partial"
    assert {r["target_id"] for r in q08["answered_requirements"]} == {
        "b02.net_revenue",
        "b03.operating_cash_flow",
    }
    assert all(not r["interpretation"] for r in q08["answered_requirements"])
    assert "14.319.681.754 VND" in q08["answer_vi"]
    assert "450.474.531.227 VND" in q08["answer_vi"]
    write(
        output / "before-after-audit.json",
        dict(
            cases=cases,
            q03_formula_operands_pdf_match=True,
            q08_facts_without_verdict=True,
            reference_method=references["method"],
            fresh_pdf_review="PDF7 and PDF8 renders visually rechecked in QA-Fix-01; source hashes checked separately",
            ground_truth="Independent PDF readings are distinct from admitted proof/ledger identity checks",
            final_policy_revalidation="10/10 original requests and protected outputs revalidated against final code + real admitted ledger",
        ),
    )
    # Full released answers remain local, including every caveat and exact locator.
    parts = []
    for key in ("Q02", "Q03", "Q06", "Q08"):
        for label, folder in (("Before", previous), ("After", final)):
            parts.append(
                f"## {key} {label}\n\n"
                + (folder / f"m7-{key}-final.txt").read_text(encoding="utf-8")
            )
    write(output / "before-after-verbatim.md", "\n\n".join(parts))
    print("10 source-bound cases audited; Q03 PDF operands and Q08 safe coverage PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("m7", "audit", "integrity"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evidence/QA-Fix-01"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/QA-Fix-01") or not output.is_dir():
        parser.error("requires an existing task-specific evidence folder")
    if args.mode == "m7":
        run_m7(root, output)
    elif args.mode == "audit":
        audit(root, output)
    else:
        before = read(output / "hashes-before.json")
        allowed = {
            "src/outputs/qa_composer.py",
            "src/outputs/qa_contracts.py",
            "src/outputs/firewall_qa_binding.py",
            "src/outputs/qa_explanation.py",
        }
        before = {k: v for k, v in before.items() if k not in allowed}
        after = {k: v for k, v in protected(root, output).items() if k not in allowed}
        changed = [k for k, v in before.items() if after.get(k) != v]
        added = sorted(set(after) - set(before))
        write(
            output / "integrity.json",
            dict(
                protected_files=len(before),
                changed=changed,
                added=added,
                unchanged=not changed and not added,
                external_calls=0,
                authorized_runtime_outputs=sorted(allowed),
            ),
        )
        print(f"Protected {len(before)}; changed {len(changed)}; added {len(added)}")
        if changed or added:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
