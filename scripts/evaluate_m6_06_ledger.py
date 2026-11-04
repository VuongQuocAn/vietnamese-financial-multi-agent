"""Bounded saved BBS proof replay and fixed ledger controls; no Gemini/OCR calls."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_m6_01_conversion import digest, save_new
from evaluate_m6_03_evidence_critic import load
from vietnamese_financial_multi_agent.verification import (
    EvidenceCriticResult,
    FinancialLogicCriticResult,
    LedgerConflict,
    ValidationResult,
    VerificationDecisionResult,
    VerificationHistory,
    VerificationInput,
    VerificationLoopResult,
    VerificationProofContext,
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)
from vietnamese_financial_multi_agent.verification.validation_contracts import (
    verification_input_digest,
)


def context_for(folder, case_id, *, loop=None):
    if loop is None:
        batch = VerificationInput.model_validate_json(
            (folder / f"batch-{case_id}.json").read_text(encoding="utf-8")
        )
    else:
        batch = loop.revision_input.batch
    payload = dict(batch=batch)
    for field, model in (
        ("validation", ValidationResult),
        ("evidence", EvidenceCriticResult),
        ("logic", FinancialLogicCriticResult),
    ):
        name = f"{field}-{case_id}" if loop is None else f"{case_id}-{field}"
        payload[field] = model.model_validate_json(
            (folder / f"{name}.json").read_text(encoding="utf-8")
        )
    context = VerificationProofContext(**payload)
    if loop is None:
        result = VerificationDecisionResult.model_validate_json(
            (folder / f"decision-{case_id}.json").read_text(encoding="utf-8")
        )
        if result.trace.legacy_pairing:
            context.validated_batch = context.evidence_batch = batch
            context.evidence_validation = context.validation
    return context


def direct_history(context, record):
    return VerificationHistory(
        contexts=[context],
        outcome=VerificationLoopResult(
            parent_candidate_id=record.candidate_id,
            initial_input=context.batch,
            attempts=[record],
            stopped=record.decision != "REVISE",
            stop_reason=None if record.decision == "REVISE" else "initial_decision_terminal",
        ),
    )


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M6-06-"
    ):
        raise ValueError("new_output_must_be_M6_06_under_artifacts_evidence")
    oracle_path = root / "evaluation/m6-06-scenarios.json"
    oracle = load(oracle_path)
    upstream_path = root / oracle["upstream_oracle"]
    assert digest(upstream_path) == oracle["upstream_oracle_sha256"]
    upstream = load(upstream_path)
    # Preflight manifest includes all accepted artifacts/raw/processed and Web local.
    before = load(root / "artifacts/evidence/M6-06-preflight/hashes-before.json")
    output.mkdir(parents=True, exist_ok=False)
    save_new(output / "expected-oracle.json", oracle)
    source = root / "artifacts/evidence/M6-05-decisions-initial"
    prior = load(source / "summary.json")
    repository = VerifiedClaimRepository(output / "ledger")
    histories, rows, controls = {}, [], []
    pending = []

    def run(case_id, history, expected, group):
        pending.append((case_id, history, expected, group))

    def flush():
        results = repository.admit_many([h for _, h, _, _ in pending])
        for (case_id, history, expected, group), result in zip(pending, results, strict=True):
            rows.append(
                dict(
                    case_id=case_id,
                    expected=expected,
                    actual=result.status,
                    passed=expected == result.status,
                    group=group,
                    reason=result.reason,
                )
            )
            save_new(output / f"proof-{case_id}.json", history.model_dump(mode="json"))
            print(f"{case_id}: {result.status} expected={expected}", flush=True)
        pending.clear()

    def check(case_id, actual):
        expected = oracle["controls"][case_id]
        controls.append(
            dict(case_id=case_id, expected=expected, actual=actual, passed=actual == expected)
        )
        print(f"control {case_id}: {actual} expected={expected}", flush=True)

    for row in prior["rows"]:
        cid = row["case_id"]
        context = context_for(source, cid)
        decisions = VerificationDecisionResult.model_validate_json(
            (source / f"decision-{cid}.json").read_text(encoding="utf-8")
        )
        if cid.startswith("control-"):
            expected = next(
                c["expected"] for c in upstream["controls"] if cid == "control-" + c["id"]
            )
        elif cid.startswith("M6-04-live"):
            expected = upstream["saved_live_expected"]
        else:
            expected = upstream["replay_overrides"].get(
                cid, [upstream["replay_default"] for _ in context.batch.claims]
            )
        assert len(decisions.claims) == len(expected)
        for index, (record, decision) in enumerate(zip(decisions.claims, expected, strict=True)):
            key = cid if len(decisions.claims) == 1 else f"{cid}-{index}"
            history = direct_history(context, record)
            histories[key] = history
            run(key, history, "stored" if decision == "ACCEPT" else "rejected", row["group"])

    for scenario in upstream["loops"]:
        cid = "loop-" + scenario["id"]
        outcome = VerificationLoopResult.model_validate_json(
            (source / f"{cid}.json").read_text(encoding="utf-8")
        )
        initial = histories["control-" + scenario["initial"]].contexts[0]
        history = VerificationHistory(
            contexts=[initial, context_for(source, cid, loop=outcome)], outcome=outcome
        )
        histories[cid] = history
        run(
            cid,
            history,
            "stored" if scenario["expected"] == "ACCEPT" else "rejected",
            "saved_revised_candidate",
        )

    print(f"Replaying {len(pending)} saved proof histories in one atomic batch", flush=True)
    flush()
    base = histories["metric-13"]
    revision = histories["loop-numeric_fresh"]

    # Fresh repositories make each fixed control independent of earlier imports.
    def admission_control(cid, history):
        result = VerifiedClaimRepository(output / "controls" / cid).admit(history)
        check(cid, result.status)
        save_new(output / f"control-proof-{cid}.json", history.model_dump(mode="json"))

    for cid, history in (
        ("direct_accept", base),
        ("caveated_accept", histories["control-source_caveats"]),
        ("revised_numeric", revision),
        ("revised_prefix", histories["loop-prefix_fresh"]),
        ("original_revise", histories["control-numeric_correction"]),
        ("investigate", histories["control-formula_failure"]),
        ("abstain", histories["control-no_financial_evidence"]),
        ("unresolved_conflict", histories["control-unresolved_conflict-0"]),
        ("original_recovery_mix", histories["original_recovery_mix"]),
        ("revision_stale_results", histories["loop-stale_pass"]),
    ):
        admission_control(cid, history)

    for cid in (
        "forged_accept",
        "changed_content",
        "changed_source",
        "changed_snapshot",
        "stale_proof",
        "missing_final_verification",
        "changed_parent",
        "changed_parent_decision",
        "changed_caveats",
        "changed_calculation",
        "revision_changed_source",
    ):
        h = (
            revision
            if cid
            in {
                "missing_final_verification",
                "changed_parent",
                "changed_parent_decision",
                "revision_changed_source",
            }
            else base
        ).model_copy(deep=True)
        final = h.outcome.final
        if cid == "forged_accept":
            h = histories["control-no_financial_evidence"].model_copy(deep=True)
            # Exercise a JSON round trip after editing only decision=ACCEPT.
            wire = h.model_dump(mode="json")
            wire["outcome"]["attempts"][0]["decision"] = "ACCEPT"
            h = VerificationHistory.model_validate_json(json.dumps(wire))
        elif cid == "changed_content":
            final.original_claim.content += " changed"
        elif cid == "changed_source":
            ref = final.original_claim.fact_references[0]
            ref.observation = ref.observation.model_copy(update={"local_id": "synthetic-other"})
        elif cid == "changed_snapshot":
            final.original_claim.snapshot_id = "synthetic-other"
        elif cid == "stale_proof":
            h.contexts[0].logic.evidence_result_sha256 = "0" * 64
        elif cid == "missing_final_verification":
            h.contexts.pop()
        elif cid == "changed_parent":
            h.outcome.revision_input.parent_candidate_id = "synthetic-other"
        elif cid == "changed_parent_decision":
            h.outcome.attempts[0].reason_codes.append("synthetic-other")
        elif cid == "changed_caveats":
            final.caveats = []
        elif cid == "changed_calculation":
            final.original_claim.calculation.result = "999.00"
        elif cid == "revision_changed_source":
            h.contexts[1].batch.claims[0].snapshot_id = "synthetic-other"
        admission_control(cid, h)

    check("duplicate_import", repository.admit(base).status)
    changed = histories["control-source_caveats"].model_copy(deep=True)
    changed.contexts[0].validated_batch = changed.contexts[0].batch.model_copy(deep=True)
    # Modern results ignore this redundant legacy pairing; identity stays exact.
    try:
        repository.admit(changed)
    except LedgerConflict:
        check("different_payload", "conflict")
    else:
        check("different_payload", "no_conflict")

    entries = repository.list_all()
    restarted = VerifiedClaimRepository(output / "ledger")
    restored = restarted.list_all()
    check("restart", "preserved" if restored == entries else "lost")
    ledger = VerifiedClaimLedger(restarted)
    check(
        "empty_query",
        ledger.find_claims(VerifiedClaimQuery(snapshot_id="synthetic-missing")).status,
    )
    pair = ledger.find_claims(VerifiedClaimQuery(period="2022", kind="fact")).claims
    snapshots = {e.identity.snapshot_id for e in pair}
    check(
        "snapshot_separation",
        "separate" if {"D-01/normalized-v2", "D-02/recovery-2022-v1"} <= snapshots else "merged",
    )
    metrics = ledger.find_claims(VerifiedClaimQuery(period="2025", kind="approved_metric")).claims
    check(
        "metric_separation",
        "separate"
        if len({m for e in metrics for m in e.accepted_claim.metric_ids}) >= 2
        else "merged",
    )

    query_checks = []
    # Cover each filter with representative fact/metric entries, while checking
    # exact preservation for every restored entry without repeated full scans.
    representatives = [
        next(e for e in restored if not e.accepted_claim.metric_ids),
        next(e for e in restored if e.accepted_claim.metric_ids),
    ]
    for entry in representatives:
        claim = entry.accepted_claim
        queries = [
            VerifiedClaimQuery(
                company_id=claim.company_id,
                document_id=claim.document_id,
                snapshot_id=claim.snapshot_id,
                period=claim.period,
                kind=claim.kind,
            ),
            VerifiedClaimQuery(reference=claim.fact_references[0]),
        ]
        if claim.metric_ids:
            queries.append(VerifiedClaimQuery(metric_id=claim.metric_ids[0]))
        else:
            queries.append(
                VerifiedClaimQuery(canonical_item_id=claim.supporting_evidence[0].canonical_item_id)
            )
        query_checks.append(all(entry in ledger.find_claims(q).claims for q in queries))
    expected_histories = {
        verification_input_digest(h.outcome.final): h
        for h in histories.values()
        if h.outcome.final.decision == "ACCEPT"
    }
    for entry in restored:
        expected_history = expected_histories[entry.identity.final_decision_sha256]
        expected_claim = next(
            c
            for c in expected_history.contexts[-1].batch.claims
            if c.candidate_id == entry.identity.accepted_candidate_id
        )
        assert entry.history == expected_history
        assert entry.accepted_claim == expected_claim
        assert entry.citations == expected_history.outcome.final.supporting_citations
        assert entry.caveats == expected_history.outcome.final.caveats
        assert entry.accepted_claim.calculation == expected_claim.calculation

    # Mixed valid/REVISE candidates share a real-source input and fresh deterministic results.
    from evaluate_m4_02_retrieval import hydrate
    from evaluate_m6_05_decisions import fresh_pass
    from vietnamese_financial_multi_agent.agents.specialist_common import _number
    from vietnamese_financial_multi_agent.verification import VerificationJudge

    batch = base.contexts[0].batch.model_copy(deep=True)
    second = batch.claims[0].model_copy(deep=True)
    second.candidate_id = second.provenance.m5_candidate_id = "synthetic-mixed-revise"
    second.content = second.content.replace(_number(second.calculation.result), "999,00")
    batch.claims.append(second)
    data, _, _ = hydrate(root)
    validation, evidence, logic = fresh_pass(data, batch)
    context = VerificationProofContext(
        batch=batch, validation=validation, evidence=evidence, logic=logic
    )
    decisions = VerificationJudge().decide(batch, validation, evidence, logic)
    for index, expected in enumerate(("stored", "rejected")):
        run(
            f"mixed-{index}",
            direct_history(context, decisions.claims[index]),
            expected,
            "synthetic_mixed_batch_real_BBS",
        )
    flush()

    after = {p: digest(root / p) for p in before}
    save_new(output / "hashes-after.json", after)
    rejected_expected = [r for r in rows + controls if r["expected"] == "rejected"]
    positive = [r for r in rows + controls if r["expected"] == "stored"]
    unsafe = sum(r["actual"] in {"stored", "idempotent"} for r in rejected_expected)
    false_rejections = sum(r["actual"] != "stored" for r in positive)
    summary = dict(
        all_passed=all(r["passed"] for r in rows + controls)
        and all(query_checks)
        and before == after,
        replay_claims=len(rows),
        replay_statuses=dict(Counter(r["actual"] for r in rows)),
        control_cases=len(controls),
        stored_entries=len(restarted.list_all()),
        representative_BBS_stored=sum(
            r["actual"] == "stored" and r["group"] == "persisted_source_rendering" for r in rows
        ),
        unsafe_verified_entries=unsafe,
        false_rejections=false_rejections,
        admission_precision=(len(positive) - false_rejections)
        / (len(positive) - false_rejections + unsafe),
        revision_entries=sum(len(e.history.contexts) == 2 for e in restored),
        citation_integrity=len(restored),
        lineage_integrity=sum(e.accepted_claim.calculation is not None for e in restored),
        query_checks_passed=sum(query_checks),
        query_checks_total=len(query_checks),
        protected_hashes=len(before),
        protected_unchanged=before == after,
        gemini_calls=0,
        ocr_calls=0,
        oracle_sha256=digest(oracle_path),
        rows=rows,
        controls=controls,
        limitations="Saved-source renderings/mock/live upstream replay and synthetic controls; not independent PDF financial accuracy.",
    )
    save_new(output / "summary.json", summary)
    print(
        json.dumps({k: v for k, v in summary.items() if k not in {"rows", "controls"}}), flush=True
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(Path.cwd().resolve(), args.output.resolve())
    raise SystemExit(0 if result["all_passed"] else 1)
