"""Bounded BBS reasoning evaluation; frozen upstream replay, synthetic controls and live separate."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from evaluate_m4_02_retrieval import hydrate
from evaluate_m6_01_conversion import digest, save_new
from evaluate_m6_02_validators import batch_for, protected
from evaluate_m6_03_evidence_critic import load
from vietnamese_financial_multi_agent.agents.specialist_common import SpecialistEvidence, _number
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    JSONOutput,
    LLMResponse,
    ResponseProvenance,
    Usage,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import FinancialRetrievalTools, GetFinancialFactRequest
from vietnamese_financial_multi_agent.verification import (
    DeterministicFinancialValidator,
    EvidenceCritic,
    EvidenceCriticResult,
    FinancialLogicCritic,
    FinancialLogicCriticResult,
    ValidationResult,
    VerificationInput,
)


def mock_logic(request, scenario):
    payload = json.loads(request.messages[-1].content)
    status = scenario["expected"][-1]
    wire = dict(
        candidate_id=payload["candidate_id"],
        assertions=[
            dict(
                assertion_id=a["assertion_id"],
                status=status,
                reason={
                    "consistent": "bounded_interpretation",
                    "inconsistent": "contradiction",
                    "insufficient_context": "missing_premises",
                }[status],
                required_premises=scenario["required"],
                missing_evidence=scenario["required"] if status == "insufficient_context" else [],
                premise_ids=payload["allowed_premise_ids"],
                evidence_ids=[e["evidence_id"] for e in payload["evidence"]],
                limitations=["bounded_to_supplied_evidence"],
            )
            for a in payload["assertions"]
        ],
    )
    return LLMResponse(
        contract_version="llm_gateway_v1",
        request_id=request.request_id,
        status="success",
        finish_reason="stop",
        correlation=request.correlation,
        provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
        usage=Usage(status="unknown", source="unknown"),
        cost=Cost(status="unknown", source="unknown"),
        output=JSONOutput(
            format="json", raw_text=json.dumps(wire), payload=wire, validation_status="json_valid"
        ),
    )


def canonical_fact_batch(data, fact):
    match = (
        FinancialRetrievalTools(SnapshotCatalog(**data))
        .get_financial_fact(
            GetFinancialFactRequest(
                document_id=fact.document_id,
                snapshot_id=fact.snapshot_id,
                local_observation_id=fact.local_observation_id,
            )
        )
        .matches[0]
    )
    evidence = SpecialistEvidence(
        evidence_id="persisted-fact",
        kind="fact",
        reference=match.reference,
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period=fact.context.period,
        label="Lưu chuyển tiền thuần từ hoạt động đầu tư",
        canonical_item_id=fact.canonical_item_id,
        value=str(fact.value.normalized_value),
        unit=fact.value.unit,
        scale=str(fact.context.scale),
        citations=match.citations,
        caveats=[],
    )
    return batch_for(evidence)


def evaluate(root, output, *, live=False, offline_evidence=None, case_ids=None):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("output_must_stay_in_artifacts_evidence")
    oracle_path = root / "evaluation/m6-04-scenarios.json"
    oracle = load(oracle_path)
    if live:
        if offline_evidence is None or not offline_evidence.resolve().is_relative_to(
            root / "artifacts/evidence"
        ):
            raise ValueError("live_requires_offline_evidence")
        offline = load(offline_evidence / "summary.json")
        if not offline["all_passed"] or offline["oracle_sha256"] != digest(oracle_path):
            raise ValueError("offline_evaluation_must_pass_with_current_oracle")
    output.mkdir(parents=True, exist_ok=False)
    before = protected(root, output)
    save_new(output / "hashes-before.json", before)
    save_new(output / "expected-oracle.json", oracle)
    print(f"Pinned {len(before)} hashes; mode={'live' if live else 'offline'}", flush=True)
    data, scopes, recovery = hydrate(root)
    catalog = SnapshotCatalog(**data)
    validator, evidence_critic = DeterministicFinancialValidator(catalog), EvidenceCritic(catalog)
    source = root / "artifacts/evidence/M6-03-offline"
    summary = load(source / "summary.json")
    batches = {
        r["case_id"]: VerificationInput.model_validate_json(
            (source / f"batch-{r['case_id']}.json").read_text(encoding="utf-8")
        )
        for r in summary["rows"]
    }
    margin = batches["saved-E02"]
    cfo = next(
        b
        for k, b in batches.items()
        if k.startswith("fact-")
        and b.claims[0].period == "2025"
        and b.claims[0].supporting_evidence[0].canonical_item_id == "b03.operating_cash_flow"
    )
    separate = next(
        b
        for k, b in batches.items()
        if k.startswith("fact-")
        and b.claims[0].period == "2024"
        and b.claims[0].supporting_evidence[0].canonical_item_id == "b02.net_revenue"
    )
    investing_fact = next(
        f
        for f in data["facts"]
        if f.canonical_item_id == "b03.investing_cash_flow"
        and f.context.period == "2025"
        and f.value.normalized_value < 0
    )
    bases = dict(
        margin=margin,
        debt=batches["saved-E36"],
        negative_yoy=batches["saved-E25"],
        cfo=cfo,
        separate_2024=separate,
        negative_investing=canonical_fact_batch(data, investing_fact),
    )
    # Oracle premises checked independently of the critic outputs.
    assert Decimal(margin.claims[0].calculation.result) > 0
    assert Decimal(bases["negative_yoy"].claims[0].calculation.result) < 0
    assert Decimal(cfo.claims[0].supporting_evidence[0].value) > 0
    assert not any(
        f.canonical_item_id == "b03.operating_cash_flow"
        and f.value.normalized_value is not None
        and f.value.normalized_value < 0
        for f in data["facts"]
    )
    rows, attempts = [], []
    adapter = None
    current_scenario = [None]

    def transport(request):
        scenario = current_scenario[0]
        if live:
            budget = root / "artifacts/evidence/M6-04-call-budget"
            budget.mkdir(exist_ok=True)
            slot = next((i for i in range(1, 7) if not (budget / f"call-{i}.json").exists()), None)
            if slot is None:
                raise ValueError("task_live_call_budget_exhausted")
            save_new(
                budget / f"call-{slot}.json",
                dict(
                    case_id=scenario["id"],
                    request_id=request.request_id,
                    output=output.relative_to(root).as_posix(),
                ),
            )
        attempt = dict(case_id=scenario["id"], phase="fresh_live" if live else "mock_generation")
        attempts.append(attempt)
        index = len(attempts)
        save_new(output / f"request-{index}.json", request.model_dump(mode="json"))
        try:
            response = adapter(request) if live else mock_logic(request, scenario)
            attempt["response"] = response.export()
            return response
        except Exception as error:
            attempt["error_type"] = type(error).__name__
            raise
        finally:
            save_new(output / f"response-{index}.json", attempt)

    deterministic = FinancialLogicCritic()
    semantic = FinancialLogicCritic(SharedLLMGateway({"gemini": transport}))

    def run(case_id, group, batch, validation, evidence, expected, *, legacy=False, scenario=None):
        current_scenario[0] = scenario
        snapshots = [x.model_dump_json() for x in (batch, validation, evidence)]
        result = (
            semantic if live or scenario and scenario.get("semantic") else deterministic
        ).assess(
            batch,
            validation,
            evidence,
            validated_batch=batch if legacy else None,
            evidence_batch=batch if legacy else None,
            evidence_validation=validation if legacy else None,
        )
        assert [x.model_dump_json() for x in (batch, validation, evidence)] == snapshots
        assert FinancialLogicCriticResult.model_validate_json(result.model_dump_json()) == result
        assert result.conflicts == batch.conflicts and not result.financial_fact_verified
        for name, obj in (
            ("batch", batch),
            ("validation", validation),
            ("evidence", evidence),
            ("result", result),
        ):
            save_new(output / f"{name}-{case_id}.json", obj.model_dump(mode="json"))
        findings = [a for c in result.claims for a in c.assertions]
        actual = [a.status for a in findings]
        errors = [*result.errors, *[e for c in result.claims for e in c.errors]]
        expect_consistency = scenario and scenario.get("mutation", "").startswith("stale_")
        passed = actual == expected
        if expect_consistency:
            passed &= any(e.stage == "consistency" for e in errors)
        if scenario and scenario.get("semantic"):
            passed &= sum(c.trace.llm.calls for c in result.claims) == 1
            passed &= any(c.trace.semantic_response for c in result.claims)
        rows.append(
            dict(
                case_id=case_id,
                group=group,
                expected=expected,
                actual=actual,
                passed=bool(passed),
                methods=dict(Counter(a.method for a in findings)),
                reasons=[a.reason_codes for a in findings],
                errors=[e.model_dump(mode="json") for e in errors],
                calls=sum(c.trace.llm.calls for c in result.claims),
                rationale=scenario["rationale"]
                if scenario
                else "Frozen source assertion only, except separately annotated saved sign interpretations.",
            )
        )
        print(f"{case_id}: {'PASS' if passed else 'FAIL'} {actual}", flush=True)

    try:
        if live:
            adapter, credential = create_qa_adapter(root)
            save_new(
                output / "credential-metadata.json",
                dict(
                    source=credential.source,
                    key_count=credential.key_count,
                    key_index=credential.key_index,
                ),
            )
        else:
            for row in summary["rows"]:
                case_id = row["case_id"]
                if case_ids and case_id not in case_ids:
                    continue
                if not (case_id.startswith(("metric-", "fact-", "saved-"))):
                    continue
                batch = batches[case_id]
                validation = ValidationResult.model_validate_json(
                    (source / f"validation-{case_id}.json").read_text(encoding="utf-8")
                )
                evidence = EvidenceCriticResult.model_validate_json(
                    (source / f"result-{case_id}.json").read_text(encoding="utf-8")
                )
                expected = oracle["saved_overrides"].get(
                    case_id, [oracle["persisted_default"] for _ in batch.claims]
                )
                run(case_id, row["group"], batch, validation, evidence, expected, legacy=True)
        for scenario in oracle["scenarios"]:
            if case_ids and scenario["id"] not in case_ids:
                continue
            if live and (not scenario.get("live") or case_ids and scenario["id"] not in case_ids):
                continue
            batch = bases[scenario["base"]].model_copy(deep=True)
            claim = batch.claims[0]
            claim.kind = "supported_interpretation"
            claim.content += " " + scenario["tail"]
            mutation = scenario.get("mutation")
            if mutation == "scope":
                batch.context.reporting_scope = "consolidated"
            elif mutation == "snapshots":
                original = next(
                    b
                    for k, b in batches.items()
                    if k.startswith("fact-")
                    and b.claims[0].period == "2022"
                    and b.claims[0].snapshot_id != recovery.snapshot_id
                )
                ref = original.claims[0].fact_references[0]
                claim.fact_references.append(ref)
                claim.provenance.supporting_references.append(ref)
            elif mutation == "numeric":
                claim.content = claim.content.replace(_number(claim.calculation.result), "999,00")
            validation = validator.validate(batch)
            if mutation == "stale_validation":
                claim.content += " Nguồn đã đổi."
            evidence = evidence_critic.assess(batch, validation)
            if mutation == "stale_evidence":
                evidence.claims[0].content += " stale"
            group = (
                "synthetic_counterfactual_on_real_BBS"
                if scenario.get("counterfactual")
                else "synthetic_interpretation_on_real_BBS"
            )
            run(
                scenario["id"],
                ("fresh_Gemini_on_" if live else "") + group,
                batch,
                validation,
                evidence,
                scenario["expected"],
                scenario=scenario,
            )
    finally:
        if adapter:
            adapter.close()
        after = {p: digest(root / p) for p in before}
        save_new(output / "hashes-after.json", after)
        result_summary = dict(
            all_passed=bool(rows) and all(r["passed"] for r in rows) and before == after,
            cases=len(rows),
            assertion_statuses=dict(Counter(s for r in rows for s in r["actual"])),
            groups=dict(Counter(r["group"] for r in rows)),
            methods=dict(sum((Counter(r["methods"]) for r in rows), Counter())),
            actual_gemini_calls=len(attempts) if live else 0,
            mock_calls=0 if live else len(attempts),
            tokens=sum(
                a.get("response", {}).get("usage", {}).get("total_tokens") or 0 for a in attempts
            )
            if live
            else 0,
            oracle_sha256=digest(oracle_path),
            protected_hashes=len(before),
            protected_unchanged=before == after,
            limitations="No independent PDF gold or full verification accuracy; synthetic interpretations and mock upstream semantics explicitly separate.",
            rows=rows,
        )
        save_new(output / "summary.json", result_summary)
        print(
            json.dumps(
                {k: v for k, v in result_summary.items() if k != "rows"}, ensure_ascii=False
            ),
            flush=True,
        )
    return result_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--offline-evidence", type=Path)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    result = evaluate(
        Path.cwd().resolve(),
        args.output.resolve(),
        live=args.live,
        offline_evidence=args.offline_evidence,
        case_ids=args.cases,
    )
    raise SystemExit(0 if result["all_passed"] else 1)
