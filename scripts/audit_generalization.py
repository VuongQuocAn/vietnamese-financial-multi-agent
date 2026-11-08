"""GEN-02 independent frozen-source/requirement audit, separate from M6 decisions."""

import argparse
import math
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median

from evaluate_evidence_fusion import read, save
from evaluate_generalization import digest
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository


def reference_key(ref):
    return ref.document_id, ref.snapshot_id, ref.local_id


def record_key(record):
    return record["document_id"], record["snapshot_id"], record["local_evidence_id"]


def fact_key(fact):
    return fact["document_id"], fact["snapshot_id"], fact["local_observation_id"]


def audit(base, phase, subset):
    frozen = read(base / "freeze.json")
    assert all(digest(base / name) == value for name, value in frozen["files"].items())
    questions = read(base / f"{subset}-oracles.json")
    sources = read(base / "sources.json")
    discrepancy_path = base / "pdf-review/discrepancies.json"
    discrepancies = read(discrepancy_path) if discrepancy_path.exists() else []
    run = base / phase
    entries = {}
    cases, timings = [], defaultdict(list)
    selected, executed, tools, decisions, admissions = (Counter() for _ in range(5))
    for q in questions:
        result_path = run / f"{q['id']}.json"
        if not result_path.exists():
            continue
        if q["label"] not in entries:
            entries[q["label"]] = {
                e.identity.verified_claim_id: e
                for e in VerifiedClaimRepository(run / q["label"] / "ledger").list_all()
            }
        result = read(result_path)["actual"]
        trace = result["trace"]
        source = sources[q["label"]]
        records = {record_key(r): r for r in source["records"]}
        facts = {fact_key(f): f for f in source["facts"]}
        released, unsupported, errors, released_records = [], [], [], set()
        for claim_id in result["used_verified_claim_ids"]:
            entry = entries[q["label"]].get(claim_id)
            if entry is None:
                errors.append("missing_ledger_entry")
                continue
            claim = entry.accepted_claim
            released.append(entry)
            if entry.identity.document_id != source["manifest"]["logical_document_id"]:
                unsupported.append(claim_id + ":document_leakage")
            if entry.identity.kind == "document":
                originals = [records.get(reference_key(ref.evidence)) for ref in claim.references]
                if (
                    any(r is None for r in originals)
                    or [r["raw_text"] for r in originals if r] != claim.quotations
                ):
                    unsupported.append(claim_id + ":quotation_not_in_frozen_source")
                released_records.update(reference_key(ref.evidence) for ref in claim.references)
                if any(
                    d["label"] == q["label"]
                    and any(
                        ref.evidence.local_id == d["local_evidence_id"] for ref in claim.references
                    )
                    for d in discrepancies
                ):
                    unsupported.append(claim_id + ":original_pdf_negation_mismatch")
            else:
                if (
                    entry.identity.snapshot_id
                    != source["manifest"]["financial_snapshot"]["snapshot_id"]
                ):
                    unsupported.append(claim_id + ":financial_snapshot_leakage")
                if claim.calculation:
                    # Recompute from the accepted raw numerical facts, not the M6 verdict.
                    formula = claim.calculation.formula_id
                    expected = [r for r in q["requirements"] if r.get("metric") == formula]
                    if not expected or abs(
                        Decimal(claim.calculation.result) - Decimal(expected[0]["expected_value"])
                    ) > Decimal("0.005"):
                        unsupported.append(claim_id + ":independent_calculation_mismatch")
                    elif {
                        reference_key(o.observation) for o in claim.calculation.trace.operands
                    } != {fact_key(f) for f in expected[0]["expected_facts"]}:
                        unsupported.append(claim_id + ":independent_operand_identity_mismatch")
                else:
                    for support in claim.supporting_evidence:
                        if support.reference.observation:
                            original = facts.get(reference_key(support.reference.observation))
                            if not original or Decimal(
                                original["value"]["normalized_value"]
                            ) != Decimal(support.value):
                                unsupported.append(claim_id + ":fact_value_not_in_frozen_source")
                            elif (
                                support.canonical_item_id != original["canonical_item_id"]
                                or support.period != original["context"]["period"]
                                or support.unit != original["value"]["unit"]
                                or support.scale != original["context"]["scale"]
                                or support.company_id != original["company_id"]
                            ):
                                unsupported.append(claim_id + ":fact_context_mismatch")
        retrieved = {
            (e["document_id"], e["snapshot_id"], e["local_id"])
            for call in trace["tool_calls"]
            if call["tool"] == "search_document_evidence"
            for match in call.get("matches", [])
            for e in match.get("evidence_ids", [])
        }
        admitted_ids = {
            o["verified_claim_id"]
            for o in trace["outcomes"]
            if o["final_decision"] == "ACCEPT" and o["verified_claim_id"]
        }
        admitted_records = {
            reference_key(r.evidence)
            for key in admitted_ids
            if key in entries[q["label"]]
            for r in getattr(entries[q["label"]][key].accepted_claim, "references", [])
            if r.evidence
        }
        coverage = []
        for i, requirement in enumerate(q["requirements"], 1):
            supported_ids, partial = [], False
            if "expected_records" in requirement:
                expected_keys = {record_key(r) for r in requirement["expected_records"]}
                overlap = released_records & expected_keys
                complete = expected_keys <= released_records
                partial = bool(overlap)
                supported_ids = [str(k) for k in sorted(overlap)]
            elif "fact" in requirement:
                complete = any(
                    e.identity.kind != "document"
                    and any(
                        s.canonical_item_id == requirement["fact"]
                        and s.value is not None
                        and Decimal(s.value) == Decimal(requirement["expected_value"])
                        for s in e.accepted_claim.supporting_evidence
                    )
                    for e in released
                )
                partial = complete
            elif "metric" in requirement:
                complete = any(
                    e.identity.kind != "document"
                    and e.accepted_claim.calculation
                    and e.accepted_claim.calculation.formula_id == requirement["metric"]
                    and abs(
                        Decimal(e.accepted_claim.calculation.result)
                        - Decimal(requirement["expected_value"])
                    )
                    <= Decimal("0.005")
                    for e in released
                )
                if complete and requirement.get("operands"):
                    # Original question requests displayed operands, not merely hidden proof.
                    digits = "".join(
                        c for c in result["answer_vi"].split("Giới hạn")[0] if c.isdigit()
                    )
                    complete = all(
                        f["value"]["normalized_value"].replace("-", "") in digits
                        for f in requirement["expected_facts"]
                    )
                    partial = True
                else:
                    partial = complete
            else:
                complete = False
            coverage.append(
                dict(
                    requirement_id=f"{q['id']}-R{i}",
                    lane="document"
                    if "expected_records" in requirement
                    else "financial"
                    if "fact" in requirement or "metric" in requirement
                    else "blocked",
                    complete=bool(complete),
                    useful_partial=bool(partial),
                    matched_source_keys=supported_ids,
                    capability_blocked=requirement.get("capability_blocked")
                    or requirement.get("blocked"),
                    retrieval_complete=(
                        {record_key(r) for r in requirement["expected_records"]} <= retrieved
                    )
                    if "expected_records" in requirement
                    else None,
                    verified_source_coverage=(
                        {record_key(r) for r in requirement["expected_records"]} <= admitted_records
                    )
                    if "expected_records" in requirement
                    else None,
                )
            )
        citation_audit = []
        for citation in result["citations"]:
            issues = []
            locator = citation["source_locator"]
            if any(
                x.split(":original_pdf_negation_mismatch")[0]
                in citation["bound_verified_claim_ids"]
                for x in unsupported
                if x.endswith(":original_pdf_negation_mismatch")
            ):
                issues.append("original_pdf_support_mismatch")
            if citation["document_id"] != source["manifest"]["logical_document_id"]:
                issues.append("wrong_document")
            for claim_id in citation["bound_verified_claim_ids"]:
                entry = entries[q["label"]].get(claim_id)
                if entry is None or claim_id not in result["used_verified_claim_ids"]:
                    issues.append("unreleased_claim_binding")
                    continue
                originals = [c.model_dump(mode="json") for c in entry.citations]
                if any(c not in originals for c in citation["source_citations"]):
                    issues.append("citation_binding_mismatch")
            # Original selector/page/image must occur in an independently frozen source.
            original_sources = [s for r in source["records"] for s in r["sources"]]
            original_sources += [s for f in source["facts"] for s in f["sources"]]
            if not any(
                s["document_id"] == citation["document_id"]
                and s["snapshot_id"] == citation["snapshot_id"]
                and s.get("reference")
                and s["reference"]["source_pointer"] == locator["source_pointer"]
                and s["reference"]["anchor"]["page"]["page"] == citation["pdf_page"]
                and s["reference"]["anchor"]["page"]["image"] == locator["image_reference"]
                for s in original_sources
            ):
                issues.append("selector_not_in_frozen_source")
            citation_audit.append(dict(citation_id=citation["citation_id"], issues=issues))
        has_answer = bool(result["used_verified_claim_ids"])
        all_covered = all(c["complete"] for c in coverage)
        useful = any(c["complete"] or c["useful_partial"] for c in coverage)
        category = (
            "incorrect"
            if unsupported
            else "full"
            if all_covered and has_answer
            else "partial"
            if useful and has_answer
            else "incorrect"
            if has_answer
            else "abstain"
        )
        false_abstention = (
            category == "abstain"
            and q["source_answerable"]
            and q["answerability"] not in {"POLICY_RESTRICTED"}
        )
        earliest = None
        if not all_covered:
            earliest = (
                "provider_runtime"
                if result["status"] in {"internal_error", "provider_unavailable"}
                else "context_binding"
                if result["status"] == "clarification_required"
                else "unsupported_capability"
                if q["answerability"] == "UNSUPPORTED_CAPABILITY"
                else "valid_policy_restriction"
                if q["answerability"] == "POLICY_RESTRICTED"
                else "planner_or_retrieval_pending_trace_review"
            )
        cases.append(
            dict(
                id=q["id"],
                label=q["label"],
                question=q["question"],
                expected_answerability=q["answerability"],
                source_answerable=q["source_answerable"],
                actual_status=result["status"],
                classification=category,
                false_abstention=false_abstention,
                correct_abstention=category == "abstain"
                and q["answerability"] in {"UNANSWERABLE_SOURCE", "AMBIGUOUS", "POLICY_RESTRICTED"},
                unsupported_claims=unsupported,
                substantive_claims=len(released),
                errors=errors,
                requirements=coverage,
                citations=citation_audit,
                selected_agents=trace["selected_agents"],
                executed_agents=trace["executed_agents"],
                tools=[c["tool"] for c in trace["tool_calls"]],
                m6=trace["native_decisions"],
                m7=trace["m7_status"],
                firewall=trace["firewall_decision"],
                earliest_stage=earliest,
                answer_vi=result["answer_vi"],
                trace=f"{phase}/{q['id']}.json",
                latency_ms=trace["total_latency_ms"],
                provider_calls=trace["provider_calls"],
                provider_errors=trace["provider_errors"],
                accepted_unreleased_claim_ids=sorted(
                    admitted_ids - set(result["used_verified_claim_ids"])
                ),
                mode=result["mode"],
            )
        )
        selected.update(trace["selected_agents"])
        executed.update(trace["executed_agents"])
        tools.update(c["tool"] for c in trace["tool_calls"])
        decisions.update(trace["native_decisions"])
        admissions.update(o["admission_status"] for o in trace["outcomes"])
        timings["total"].append(trace["total_latency_ms"])
        for stage, value in trace["stages"].items():
            if value["status"] != "NOT_EXECUTED":
                timings[stage].append(value["latency_ms"])
        for lane in trace.get("fusion_bundle", {}).get("lane_results", []):
            for name, value in lane["response"]["trace"]["stages"].items():
                if value["status"] != "NOT_EXECUTED":
                    timings[lane["lane"] + "." + name].append(value["latency_ms"])

    def metric(numerator, denominator):
        return dict(
            numerator=len(numerator),
            denominator=len(denominator),
            numerator_ids=numerator,
            denominator_ids=denominator,
        )

    def ids(predicate):
        return [c["id"] for c in cases if predicate(c)]

    fully = ids(lambda c: c["expected_answerability"] == "FULLY_ANSWERABLE")
    answerable = ids(lambda c: c["source_answerable"])
    answering = ids(lambda c: c["substantive_claims"] > 0)
    citations = [f"{c['id']}:{x['citation_id']}" for c in cases for x in c["citations"]]
    claims = [f"{c['id']}:{i}" for c in cases for i in range(c["substantive_claims"])]
    unsupported = [f"{c['id']}:{x}" for c in cases for x in c["unsupported_claims"]]
    metrics = dict(
        full_answer_rate=metric(
            ids(lambda c: c["id"] in fully and c["classification"] == "full"), fully
        ),
        useful_answer_rate=metric(
            ids(lambda c: c["id"] in answerable and c["classification"] in {"full", "partial"}),
            answerable,
        ),
        false_abstention_rate=metric(ids(lambda c: c["false_abstention"]), answerable),
        correct_abstention_rate=metric(
            ids(lambda c: c["correct_abstention"]),
            ids(
                lambda c: (
                    c["expected_answerability"]
                    in {"UNANSWERABLE_SOURCE", "AMBIGUOUS", "POLICY_RESTRICTED"}
                )
            ),
        ),
        incorrect_answer_rate=metric(ids(lambda c: c["classification"] == "incorrect"), answering),
        unsupported_claim_rate=metric(unsupported, claims),
        citation_correctness=metric(
            [
                f"{c['id']}:{x['citation_id']}"
                for c in cases
                for x in c["citations"]
                if not x["issues"]
            ],
            citations,
        ),
    )
    for lane in ("financial", "document"):
        applicable = [r for c in cases for r in c["requirements"] if r["lane"] == lane]
        metrics[lane + "_requirement_coverage"] = metric(
            [r["requirement_id"] for r in applicable if r["complete"]],
            [r["requirement_id"] for r in applicable],
        )
    document_requirements = [r for c in cases for r in c["requirements"] if r["lane"] == "document"]
    metrics["retrieval_coverage"] = metric(
        [r["requirement_id"] for r in document_requirements if r["retrieval_complete"]],
        [r["requirement_id"] for r in document_requirements],
    )
    metrics["verified_document_coverage"] = metric(
        [r["requirement_id"] for r in document_requirements if r["verified_source_coverage"]],
        [r["requirement_id"] for r in document_requirements],
    )
    save(
        run / "independent-audit.json",
        dict(
            cases=cases,
            metrics=metrics,
            classifications=dict(Counter(c["classification"] for c in cases)),
            selected_agents=dict(selected),
            executed_agents=dict(executed),
            tools=dict(tools),
            decisions=dict(decisions),
            admissions=dict(admissions),
            latency={
                k: dict(
                    count=len(v),
                    median_ms=median(v),
                    p95_ms=sorted(v)[math.ceil(len(v) * 0.95) - 1],
                )
                for k, v in timings.items()
            },
            frozen_dataset_unchanged=True,
            completed_cases=len(cases),
            expected_cases=len(questions),
        ),
    )
    print(phase, Counter(c["classification"] for c in cases), flush=True)
    for c in cases:
        print(
            c["id"],
            c["classification"],
            [r["complete"] for r in c["requirements"]],
            c["actual_status"],
            c["unsupported_claims"],
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase")
    parser.add_argument("--subset", choices=["development", "holdout"], default="development")
    parser.add_argument("--base", type=Path, default=Path("artifacts/evidence/GEN-02"))
    args = parser.parse_args()
    audit(args.base, args.phase, args.subset)
