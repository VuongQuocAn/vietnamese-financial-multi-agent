"""Independent QA-01b release audit against frozen source oracles and accepted M4 saves."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from evaluate_evidence_fusion import read, save
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    oracles = read(args.run / "oracles.json")
    if args.cases:
        oracles = {key: value for key, value in oracles.items() if key in args.cases}
    references = read(Path("artifacts/evidence/M4-03-final/executions.json"))
    for label in {o["label"] for o in oracles.values() if o["label"].startswith("BCC")}:
        references += read(
            Path("artifacts/evidence/GEN-01/audit-release") / label / "m4-calculations.json"
        )
    approved = {r["metric_id"]: r for r in references}
    ledgers = {
        label: {
            e.identity.verified_claim_id: e
            for e in VerifiedClaimRepository(args.run / label / "ledger").list_all()
        }
        for label in {o["label"] for o in oracles.values()}
    }
    totals, tools, selected, executed, decisions, admissions = (Counter() for _ in range(6))
    cases = []
    for case_id, oracle in oracles.items():
        row = read(args.run / f"{case_id}.json")
        result, errors = row["actual"], []
        entries = ledgers[oracle["label"]]
        facts = {
            (f["document_id"], f["snapshot_id"], f["local_observation_id"]): f
            for f in oracle["financial_facts"]
        }
        sources = {
            (r["document_id"], r["snapshot_id"], r["local_evidence_id"]): r
            for r in oracle["source_excerpt_oracles"]
        }
        context = result["trace"].get("fusion_bundle", {}).get("context", {})
        for key in result["used_verified_claim_ids"]:
            entry = entries[key]
            claim, identity = entry.accepted_claim, entry.identity
            if (identity.document_id, identity.company_id) != (
                context["document_id"],
                context["company_id"],
            ):
                errors.append("source_context_leakage")
            if entry.decision.decision != "ACCEPT" or entry.verification_status != "verified":
                errors.append("unverified_claim_released")
            if identity.kind == "document":
                if (identity.composition_id, identity.composition_sha256) != (
                    context["composition_id"],
                    context["composition_sha256"],
                ):
                    errors.append("composition_leakage")
                exact = [
                    sources.get(
                        (r.evidence.document_id, r.evidence.snapshot_id, r.evidence.local_id), {}
                    ).get("raw_text")
                    for r in claim.references
                ]
                if exact != claim.quotations:
                    errors.append("document_quotation_not_in_frozen_oracle")
            else:
                if identity.snapshot_id != context["snapshot_id"] or not identity.period.startswith(
                    oracle["label"].split("_")[1]
                ):
                    errors.append("financial_snapshot_or_year_leakage")
                if claim.calculation:
                    reference = approved.get(claim.calculation.metric_id)
                    if (
                        not reference
                        or reference["status"] != "computed"
                        or Decimal(reference["result"]) != Decimal(claim.calculation.result)
                    ):
                        errors.append("financial_result_not_in_accepted_M4_oracle")
                else:
                    for support in claim.supporting_evidence:
                        ref = support.reference.observation
                        original = facts.get((ref.document_id, ref.snapshot_id, ref.local_id))
                        if not original or Decimal(support.value) != Decimal(
                            original["value"]["normalized_value"]
                        ):
                            errors.append("financial_fact_not_in_frozen_oracle")
        for citation in result["citations"]:
            for claim_id in citation["bound_verified_claim_ids"]:
                if claim_id not in result["used_verified_claim_ids"] or any(
                    c not in [v.model_dump(mode="json") for v in entries[claim_id].citations]
                    for c in citation["source_citations"]
                ):
                    errors.append("citation_claim_binding_mismatch")
            totals["citations_checked"] += 1
        plan = result["trace"].get("document_release", {}).get("requirements", {})
        for requirement in plan.get("requirements", []):
            kind = requirement["kind"]
            lane = (
                "document"
                if kind == "document"
                else "financial"
                if kind in {"fact", "metric", "explanation"}
                else None
            )
            if requirement["reason"] in {"unsupported_formula", "unsupported_question_or_formula"}:
                lane = "financial"
            if lane:
                totals[lane + "_requirements"] += 1
                totals[lane + "_covered"] += bool(requirement["verified_claim_ids"])
            totals["causal_requirements_blocked"] += (
                requirement["reason"] == "unsupported_causal_inference"
            )
        if (
            result["status"] in {"completed", "completed_with_caveats"}
            and result["trace"]["unanswered_requirements"]
        ):
            errors.append("partial_reported_completed")
        tools.update(c["tool"] for c in result["trace"]["tool_calls"])
        selected.update(result["trace"]["selected_agents"])
        executed.update(result["trace"]["executed_agents"])
        decisions.update(result["trace"]["native_decisions"])
        admissions.update(o["admission_status"] for o in result["trace"]["outcomes"])
        totals["graph_cases"] += bool(result["trace"].get("fusion_bundle", {}).get("graph_paths"))
        totals["provider_calls"] += result["trace"]["provider_calls"]
        totals["known_tokens"] += result["trace"]["known_total_tokens"]
        totals["errors"] += len(errors)
        totals["cases_audited"] += 1
        cases.append(
            dict(
                case_id=case_id,
                expected_status_pass=row["passed"],
                errors=errors,
                selected_claims=result["used_verified_claim_ids"],
            )
        )
    save(
        args.run / ("partial-audit.json" if args.cases else "independent-audit.json"),
        dict(
            totals=dict(totals),
            tools=dict(tools),
            selected_agents=dict(selected),
            executed_agents=dict(executed),
            decisions=dict(decisions),
            admissions=dict(admissions),
            cases=cases,
        ),
    )
    print(json.dumps(dict(totals=totals, tools=tools, decisions=decisions), ensure_ascii=False))
    assert not totals["errors"] and all(c["expected_status_pass"] for c in cases)


if __name__ == "__main__":
    main()
