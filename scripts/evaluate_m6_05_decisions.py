"""Frozen BBS decision replay, explicit controls and one-pass revision evaluation; zero live calls."""

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from evaluate_m4_02_retrieval import hydrate
from evaluate_m6_01_conversion import digest, save_new
from evaluate_m6_02_validators import protected
from evaluate_m6_03_evidence_critic import load
from vietnamese_financial_multi_agent.agents.orchestration_contracts import CandidateConflict
from vietnamese_financial_multi_agent.agents.specialist_common import _number
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification import (
    BoundedVerificationLoop,
    DeterministicFinancialValidator,
    EvidenceCritic,
    EvidenceCriticResult,
    FinancialLogicCritic,
    FinancialLogicCriticResult,
    ValidationResult,
    VerificationDecisionResult,
    VerificationInput,
    VerificationJudge,
    VerificationLoopResult,
)
from vietnamese_financial_multi_agent.verification.validation_contracts import (
    validation_result_digest,
    verification_input_digest,
)


def read_inputs(folder, case_id):
    return tuple(
        model.model_validate_json((folder / f"{prefix}-{case_id}.json").read_text(encoding="utf-8"))
        for prefix, model in (
            ("batch", VerificationInput),
            ("validation", ValidationResult),
            ("evidence", EvidenceCriticResult),
            ("result", FinancialLogicCriticResult),
        )
    )


def fresh_pass(data, batch):
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    evidence = EvidenceCritic(catalog, max_semantic_calls=0).assess(batch, validation)
    logic = FinancialLogicCritic(max_semantic_calls=0).assess(batch, validation, evidence)
    return validation, evidence, logic


def evaluate(root, output):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("output_must_stay_under_artifacts_evidence")
    oracle_path = root / "evaluation/m6-05-scenarios.json"
    oracle = load(oracle_path)
    output.mkdir(parents=True, exist_ok=False)
    before = protected(root, output)
    preflight = root / "artifacts/evidence/M6-05-preflight/hashes-before.json"
    baseline = load(preflight) if preflight.exists() else before
    assert all(before[p] == h for p, h in baseline.items())
    save_new(output / "hashes-before.json", before)
    save_new(output / "expected-oracle.json", oracle)
    print(f"Pinned {len(before)} hashes; fixed oracle {digest(oracle_path)}", flush=True)
    rows, loop_rows = [], []
    judge = VerificationJudge()

    def run(case_id, group, inputs, expected, *, legacy=False):
        batch, validation, evidence, logic = inputs
        originals = [x.model_dump_json() for x in inputs]
        pairing = (
            dict(validated_batch=batch, evidence_batch=batch, evidence_validation=validation)
            if legacy
            else {}
        )
        result = judge.decide(*inputs, **pairing)
        assert [x.model_dump_json() for x in inputs] == originals
        assert result == judge.decide(*inputs, **pairing)
        assert VerificationDecisionResult.model_validate_json(result.model_dump_json()) == result
        assert result.trace.verification_input_sha256 == verification_input_digest(batch)
        assert result.trace.validation_result_sha256 == validation_result_digest(validation)
        assert result.trace.evidence_result_sha256 == verification_input_digest(evidence)
        assert result.trace.logic_result_sha256 == verification_input_digest(logic)
        assert result.conflicts == batch.conflicts
        for record, claim in zip(result.claims, batch.claims, strict=True):
            assert record.original_claim == claim
            assert all(c in record.caveats for c in claim.caveats)
            assert record.validation in validation.claims
            assert record.evidence in evidence.claims
            assert record.logic in logic.claims
        actual = [c.decision for c in result.claims]
        for prefix, obj in zip(("batch", "validation", "evidence", "logic"), inputs, strict=True):
            save_new(output / f"{prefix}-{case_id}.json", obj.model_dump(mode="json"))
        save_new(output / f"decision-{case_id}.json", result.model_dump(mode="json"))
        row = dict(
            case_id=case_id,
            group=group,
            orchestration_status=batch.orchestration_status,
            candidate_ids=[c.candidate_id for c in batch.claims],
            expected=expected,
            actual=actual,
            passed=expected == actual,
            reasons=[c.reason_codes for c in result.claims],
            caveats=[c.caveats for c in result.claims],
            errors=[e.code for c in result.claims for e in c.errors],
        )
        rows.append(row)
        print(
            f"{case_id}: {'PASS' if row['passed'] else 'FAIL'} expected={expected} actual={actual}",
            flush=True,
        )
        return result

    source = root / "artifacts/evidence/M6-04-offline-final-v2"
    saved = {}
    for row in load(source / "summary.json")["rows"]:
        cid = row["case_id"]
        inputs = read_inputs(source, cid)
        saved[cid] = inputs
        expected = oracle["replay_overrides"].get(
            cid, [oracle["replay_default"] for _ in inputs[0].claims]
        )
        run(cid, row["group"], inputs, expected, legacy=True)
    # Saved provider failures and successful Gemini logic remain separate from
    # offline synthetic semantics; do not retry any provider here.
    for folder in ("M6-04-live", "M6-04-live-targeted"):
        live_source = root / "artifacts/evidence" / folder
        for row in load(live_source / "summary.json")["rows"]:
            cid = row["case_id"]
            run(
                folder + "-" + cid,
                "saved_Gemini_logic_with_frozen_upstream_support",
                read_inputs(live_source, cid),
                oracle["saved_live_expected"],
            )

    data, _, _ = hydrate(root)
    controls = {}
    for scenario in oracle["controls"]:
        mutation = scenario["mutation"]
        batch = saved["saved-E02"][0].model_copy(deep=True)
        if mutation == "snapshots":
            # Keep the actual 2022 original + recovery pair; a 2025 base plus
            # an original-2022 reference would only exercise a generic mix.
            batch = saved["original_recovery_mix"][0].model_copy(deep=True)
        if mutation in {"missing_source", "no_source"}:
            batch = next(
                inputs[0].model_copy(deep=True)
                for cid, inputs in saved.items()
                if cid.startswith("fact-") and inputs[0].claims[0].period == "2025"
            )
        claim = batch.claims[0]
        if mutation in {"numeric", "conflict_numeric"}:
            claim.content = claim.content.replace(_number(claim.calculation.result), "999,00")
        if mutation == "formula":
            claim.calculation.formula_digest = "synthetic-invalid-formula"
        elif mutation in {"tail", "multi_tail"}:
            claim.kind = "supported_interpretation"
            claim.content += " Hiệu quả kinh doanh cải thiện rõ rệt."
            if mutation == "multi_tail":
                claim.content += " Do chi phí giảm nên lợi nhuận tăng."
        elif mutation == "scope":
            batch.context.reporting_scope = "consolidated"
        elif mutation == "snapshots":
            assert (
                len(
                    {
                        (r.observation.document_id, r.observation.snapshot_id)
                        for r in claim.fact_references
                        if r.observation
                    }
                )
                > 1
            )
            assert claim.period == "2022"
        elif mutation == "missing_source":
            ref = claim.fact_references[0]
            ref.observation = ref.observation.model_copy(
                update={"local_id": "synthetic-missing-source"}
            )
            claim.provenance.supporting_references = [ref]
            claim.supporting_evidence[0].reference = ref
        elif mutation == "no_source":
            claim.kind = "supported_interpretation"
            claim.content = "Doanh nghiệp chắc chắn thịnh vượng."
            claim.fact_references = claim.provenance.supporting_references = []
            claim.supporting_evidence = []
            claim.supporting_evidence_ids = []
            claim.citations = []
        elif mutation == "partial":
            batch.orchestration_status = "partial"
            batch.stop_conditions = ["unrelated_specialist_failed"]
        elif mutation == "caveats":
            claim.caveats.extend(
                [
                    "usable_with_caveat",
                    "source_review_unverified",
                    "page_level_only",
                    "reporting_scope_unresolved",
                ]
            )
        elif mutation == "identity":
            batch.source_result_sha256 = "malformed-synthetic-identity"
        if mutation in {"conflict", "conflict_numeric"}:
            second = claim.model_copy(deep=True)
            second.candidate_id = second.provenance.m5_candidate_id = (
                "control-conflicting-candidate"
            )
            batch.claims.append(second)
            batch.orchestration_status = "partial"
            batch.conflicts = [
                CandidateConflict(
                    conflict_id="control-conflict",
                    candidate_ids=[c.candidate_id for c in batch.claims],
                )
            ]
            for c in batch.claims:
                c.provenance.conflict_ids = ["control-conflict"]
        validation, evidence, logic = fresh_pass(data, batch)
        if mutation == "stale_validation":
            claim.content += " Đã thay đổi."
        elif mutation == "stale_evidence":
            evidence.claims[0].content += " stale"
        elif mutation == "stale_logic":
            logic.evidence_result_sha256 = "stale"
        elif mutation == "missing_check":
            validation.claims[0].checks = [
                c for c in validation.claims[0].checks if c.check_id != "numeric"
            ]
            # This is a controlled incomplete result, fully bound to that result,
            # rather than a stale digest control (tested separately).
            evidence.validation_result_sha256 = validation_result_digest(validation)
            evidence.claims[0].deterministic_findings = validation.claims[0].checks
            logic = FinancialLogicCritic(max_semantic_calls=0).assess(batch, validation, evidence)
        inputs = (batch, validation, evidence, logic)
        run(
            "control-" + scenario["id"],
            "synthetic_decision_control_on_persisted_BBS",
            inputs,
            scenario["expected"],
        )
        controls[scenario["id"]] = inputs

    for scenario in oracle["loops"]:
        inputs = controls[scenario["initial"]]
        loop = BoundedVerificationLoop()
        history = loop.start(*inputs, candidate_id=inputs[0].claims[0].candidate_id)
        revision = loop.propose(history)
        mutation = scenario["mutation"]
        if mutation == "snapshot":
            revision.batch.claims[0].snapshot_id = "synthetic-other-snapshot"
        elif mutation == "parent":
            revision.parent_candidate_id = "synthetic-other-parent"
        revised_data = deepcopy(data)
        if mutation == "missing_facts":
            revised_data["facts"] = []
        fresh = fresh_pass(revised_data, revision.batch) if mutation != "stale" else inputs[1:]
        outcome = loop.submit(history, revision, *fresh)
        assert VerificationLoopResult.model_validate_json(outcome.model_dump_json()) == outcome
        assert len(outcome.attempts) == 2 and outcome.stopped
        assert outcome.attempts[0] == history.attempts[0]
        try:
            loop.submit(outcome, revision, *fresh)
        except ValueError as error:
            assert str(error) == "revision_budget_exhausted"
        else:
            raise AssertionError("third_attempt_was_allowed")
        cid = "loop-" + scenario["id"]
        save_new(output / f"{cid}.json", outcome.model_dump(mode="json"))
        for name, obj in zip(("validation", "evidence", "logic"), fresh, strict=True):
            save_new(output / f"{cid}-{name}.json", obj.model_dump(mode="json"))
        actual = outcome.final.decision
        loop_rows.append(
            dict(
                case_id=cid,
                group="revised_candidate",
                expected=scenario["expected"],
                actual=actual,
                passed=actual == scenario["expected"],
                attempts=len(outcome.attempts),
                stop_reason=outcome.stop_reason,
            )
        )
        print(f"{cid}: {actual}", flush=True)

    pairs = [(e, a) for row in rows for e, a in zip(row["expected"], row["actual"], strict=True)]
    pairs.extend((r["expected"], r["actual"]) for r in loop_rows)
    confusion = {
        expected: dict(Counter(a for e, a in pairs if e == expected))
        for expected in ("ACCEPT", "REVISE", "INVESTIGATE", "ABSTAIN")
    }
    after = {p: digest(root / p) for p in before}
    save_new(output / "hashes-after.json", after)
    positives = sum(e == "ACCEPT" for e, _ in pairs)
    false_abstentions = sum(e == "ACCEPT" and a == "ABSTAIN" for e, a in pairs)
    unnecessary_investigations = sum(e == "ACCEPT" and a == "INVESTIGATE" for e, a in pairs)
    summary = dict(
        all_passed=all(r["passed"] for r in rows + loop_rows) and before == after,
        cases=len(rows),
        candidate_decisions=len(pairs),
        loop_scenarios=len(loop_rows),
        groups=dict(Counter(r["group"] for r in rows)),
        orchestration_statuses=dict(Counter(r["orchestration_status"] for r in rows)),
        decisions=dict(Counter(a for _, a in pairs)),
        confusion_matrix=confusion,
        unsafe_accept_count=sum(e != "ACCEPT" and a == "ACCEPT" for e, a in pairs),
        expected_accept_count=positives,
        false_abstention_count=false_abstentions,
        false_abstention_rate=false_abstentions / positives if positives else None,
        unnecessary_investigation_count=unnecessary_investigations,
        protected_hashes=len(before),
        original_protected_hashes=len(baseline),
        protected_unchanged=before == after,
        actual_gemini_calls=0,
        ocr_calls=0,
        oracle_sha256=digest(oracle_path),
        rows=rows,
        loops=loop_rows,
        limitations="Source-bound replay and synthetic policy controls, not independent PDF gold or end-to-end financial accuracy. Saved upstream mocks/live/provider failures remain labeled.",
    )
    save_new(output / "summary.json", summary)
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in {"rows", "loops"}}, ensure_ascii=False
        ),
        flush=True,
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(Path.cwd().resolve(), args.output.resolve())
    raise SystemExit(0 if result["all_passed"] else 1)
