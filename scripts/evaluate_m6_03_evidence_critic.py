"""Bounded BBS evidence assessment; offline mocks, saved inputs and fresh live stay separate."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_m4_02_retrieval import hydrate
from evaluate_m6_01_conversion import digest, save_new
from evaluate_m6_02_validators import batch_for, protected
from vietnamese_financial_multi_agent.agents.cash_flow_earnings_quality_specialist import (
    ITEM_LABELS as FLOW_LABELS,
)
from vietnamese_financial_multi_agent.agents.liquidity_leverage_specialist import (
    ITEM_LABELS as BALANCE_LABELS,
)
from vietnamese_financial_multi_agent.agents.profitability_specialist import (
    ITEM_LABELS,
    METRIC_LABELS,
)
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
from vietnamese_financial_multi_agent.evidence.retrieval import RetrievalReference
from vietnamese_financial_multi_agent.tools import (
    FinancialCalculationResponse,
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)
from vietnamese_financial_multi_agent.verification import (
    DeterministicFinancialValidator,
    EvidenceCritic,
    EvidenceCriticResult,
    ValidationResult,
    VerificationInput,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def persisted_cases(root, data, scopes, recovery):
    """Reconstruct the exact deterministic renderings used by accepted M6-02.

    No M4 arithmetic or M6-02 validation rerun: pair each with its saved result.
    """
    for i, wire in enumerate(load(root / "artifacts/evidence/M4-03-final/executions.json"), 1):
        calc = FinancialCalculationResponse.model_validate_json(json.dumps(wire))
        role = {
            "gross_margin": "revenue",
            "debt_to_assets": "assets",
            "revenue_yoy": "current_revenue",
        }[calc.formula_id]
        op = next(o for o in calc.trace.operands if o.role == role)
        evidence = SpecialistEvidence(
            evidence_id="persisted-metric",
            kind="metric",
            reference=RetrievalReference(kind="metric", record_id=calc.metric_id),
            company_id=op.company_id,
            document_id=calc.document_id,
            snapshot_id=calc.snapshot_id,
            period=op.context.period,
            operand_periods=calc.evidence.record.request.operand_periods,
            label=METRIC_LABELS.get(calc.formula_id, "Tỷ lệ nợ phải trả trên tổng tài sản"),
            value=calc.result,
            unit="percent",
            citations=calc.evidence.citations,
            caveats=calc.caveats,
            calculation=calc,
        )
        yield f"metric-{i:02}", batch_for(evidence, calculation=calc)
    retrieval = FinancialRetrievalTools(SnapshotCatalog(**data))
    labels = {**ITEM_LABELS, **FLOW_LABELS, **BALANCE_LABELS}
    selections = [(s["document_id"], s["snapshot_id"], year) for year, s in scopes.items()]
    selections.append((recovery.document_id, recovery.snapshot_id, 2022))
    for i, (document, snapshot, year) in enumerate(selections, 1):
        for item in ("b02.net_revenue", "b03.operating_cash_flow"):
            fact = next(
                f
                for f in data["facts"]
                if (f.document_id, f.snapshot_id, f.canonical_item_id, f.context.period)
                == (document, snapshot, item, str(year))
            )
            match = retrieval.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=document,
                    snapshot_id=snapshot,
                    local_observation_id=fact.local_observation_id,
                )
            ).matches[0]
            evidence = SpecialistEvidence(
                evidence_id="persisted-fact",
                kind="fact",
                reference=match.reference,
                company_id=fact.company_id,
                document_id=document,
                snapshot_id=snapshot,
                period=str(year),
                label=labels[item],
                canonical_item_id=item,
                value=str(fact.value.normalized_value),
                unit=fact.value.unit,
                scale=str(fact.context.scale),
                citations=match.citations,
                caveats=[],
            )
            yield f"fact-{i:02}-{item.split('.')[0]}", batch_for(evidence)


def mock_response(request, annotation):
    payload = json.loads(request.messages[-1].content)
    wire = dict(
        candidate_id=payload["candidate_id"],
        assertions=[
            dict(
                assertion_id=a["assertion_id"],
                evidence_ids=[e["evidence_id"] for e in payload["evidence"]]
                if annotation["status"] != "insufficient_evidence"
                else [],
                **annotation,
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


def evaluate(root, output, *, live=False, offline_evidence=None):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("output_must_stay_in_artifacts_evidence")
    annotations = load(root / "evaluation/m6-03-scenarios.json")
    output.mkdir(parents=True, exist_ok=False)
    before = protected(root, output)
    save_new(output / "hashes-before.json", before)
    save_new(output / "expected-annotations.json", annotations)
    print(
        f"Pinned {len(before)} protected hashes; mode={'live' if live else 'offline'}", flush=True
    )
    data, scopes, recovery = hydrate(root)
    catalog = SnapshotCatalog(**data)
    rows, attempts = [], []
    adapter = None
    legacy = root / "artifacts/evidence/M6-02-validation-final"
    conversions = root / "artifacts/evidence/M6-01-conversion"
    source_summary = load(conversions / "summary.json")
    fixed = dict(persisted_cases(root, data, scopes, recovery)) if not live else {}
    transport_for_case = [None]
    deterministic_critic = EvidenceCritic(catalog)
    semantic_critic = EvidenceCritic(
        catalog, SharedLLMGateway({"gemini": lambda request: transport_for_case[0](request)})
    )

    def run(case_id, group, batch, validation, expected, annotation=None, legacy_pair=False):
        snapshot = batch.model_dump_json()

        def transport(request):
            # Disk reservation survives interruption; at most six actual calls across
            # all runs of this evaluator, including targeted retests and failures.
            if live:
                budget = root / "artifacts/evidence/M6-03-call-budget"
                budget.mkdir(exist_ok=True)
                slot = next(
                    (i for i in range(1, 7) if not (budget / f"call-{i}.json").exists()), None
                )
                if slot is None:
                    raise ValueError("task_live_call_budget_exhausted")
                save_new(
                    budget / f"call-{slot}.json",
                    dict(
                        case_id=case_id,
                        request_id=request.request_id,
                        output=output.relative_to(root).as_posix(),
                    ),
                )
            index = len(attempts) + 1
            attempt = dict(
                case_id=case_id,
                phase="fresh_live" if live else "mock_semantic",
                request_id=request.request_id,
            )
            attempts.append(attempt)
            save_new(output / f"request-{index}.json", request.model_dump(mode="json"))
            response = adapter(request) if live else mock_response(request, annotation)
            attempt["response"] = response.export()
            save_new(output / f"response-{index}.json", attempt)
            return response

        transport_for_case[0] = transport
        critic = semantic_critic if live or annotation else deterministic_critic
        result = critic.assess(batch, validation, validated_batch=batch if legacy_pair else None)
        assert EvidenceCriticResult.model_validate_json(result.model_dump_json()) == result
        assert batch.model_dump_json() == snapshot and not result.financial_fact_verified
        assert result.conflicts == batch.conflicts
        save_new(output / f"batch-{case_id}.json", batch.model_dump(mode="json"))
        save_new(output / f"validation-{case_id}.json", validation.model_dump(mode="json"))
        save_new(output / f"result-{case_id}.json", result.model_dump(mode="json"))
        actual = [c.status for c in result.claims]
        passed = actual == expected
        row = dict(
            case_id=case_id,
            group=group,
            expected=expected,
            actual=actual,
            passed=passed,
            methods=dict(Counter(c.method for c in result.claims)),
            semantic_assertions=sum(
                len(c.trace.semantic_response.assertions)
                for c in result.claims
                if c.trace.semantic_response
            ),
            semantic_needed=sum(
                a.reasons == ["semantic_assessment_required"] or c.method in {"gemini", "combined"}
                for c in result.claims
                for a in c.assertions
                if a.check_references == []
            ),
            calls=sum(c.trace.llm.calls for c in result.claims),
            errors=[e.model_dump() for c in result.claims for e in c.errors],
        )
        rows.append(row)
        print(f"{case_id}: {actual} expected={expected} {'PASS' if passed else 'FAIL'}", flush=True)
        return result

    try:
        if live:
            # Live pilot can only follow a successful offline evaluation.
            offline = load(
                offline_evidence or root / "artifacts/evidence/M6-03-offline/summary.json"
            )
            if not offline["all_passed"]:
                raise ValueError("offline_evaluation_must_pass_before_live")
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
            for case_id, batch in fixed.items():
                expected = annotations["persisted_source"].get(
                    case_id, annotations["persisted_source"]["default"]
                )
                validation = ValidationResult.model_validate_json(
                    (legacy / f"result-{case_id}.json").read_text(encoding="utf-8")
                )
                run(
                    case_id,
                    "persisted_source_rendering",
                    batch,
                    validation,
                    [expected],
                    legacy_pair=True,
                )
        for row in source_summary["rows"]:
            case_id = row["id"]
            if live and case_id not in annotations["live_cases"]:
                continue
            batch = VerificationInput.model_validate_json(
                (conversions / f"batch-{case_id}.json").read_text(encoding="utf-8")
            )
            validation = ValidationResult.model_validate_json(
                (legacy / f"result-saved-{case_id}.json").read_text(encoding="utf-8")
            )
            expected = ["supported" for i, _ in enumerate(batch.claims)]
            expected = annotations.get("saved_expected", {}).get(case_id, expected)
            annotation = annotations["saved_semantic"].get(case_id)
            run(
                "saved-" + case_id,
                "fresh_Gemini_critic_on_" + row["group"] if live else row["group"],
                batch,
                validation,
                expected,
                annotation,
                legacy_pair=True,
            )
        if not live:
            fact = fixed["fact-05-b02"]
            metric = fixed["metric-01"]
            # Find year2025 independent of source ordering.
            fact = next(
                b
                for k, b in fixed.items()
                if k.startswith("fact-")
                and b.claims[0].period == "2025"
                and b.claims[0].supporting_evidence[0].canonical_item_id == "b02.net_revenue"
            )
            scope = next(
                b
                for k, b in fixed.items()
                if k.startswith("fact-")
                and b.claims[0].period == "2024"
                and b.claims[0].supporting_evidence[0].canonical_item_id == "b02.net_revenue"
            )
            for control, expected in annotations["controls"].items():
                batch = (
                    metric
                    if control in {"formula", "interpretation"}
                    else scope
                    if control == "scope"
                    else fact
                ).model_copy(deep=True)
                claim = batch.claims[0]
                if control == "value":
                    claim.content = claim.content.replace(
                        _number(claim.supporting_evidence[0].value), "999"
                    )
                elif control == "document":
                    claim.document_id = "wrong-document"
                elif control == "snapshot":
                    claim.snapshot_id = "wrong-snapshot"
                elif control == "period":
                    claim.content = claim.content.replace(claim.period, "2020")
                elif control == "currency":
                    claim.content = claim.content.replace("VND", "USD")
                elif control == "scope":
                    batch.context.reporting_scope = "consolidated"
                elif control == "formula":
                    claim.calculation.formula_digest = "tampered"
                elif control == "citation":
                    claim.citations[0].pdf_page += 1
                elif control == "missing_source":
                    identity = claim.fact_references[0].observation
                    claim.fact_references[0] = RetrievalReference(
                        kind="fact",
                        observation=identity.model_copy(update={"local_id": "missing-source"}),
                    )
                    claim.supporting_evidence = []
                    claim.provenance.supporting_references = list(claim.fact_references)
                elif control == "cross_document":
                    other = scope.claims[0].fact_references[0]
                    claim.fact_references.append(other)
                    claim.provenance.supporting_references.append(other)
                elif control == "interpretation":
                    claim.kind = "supported_interpretation"
                    claim.content += " Chứng tỏ doanh nghiệp hoạt động hiệu quả hơn."
                original = batch.model_copy(deep=True)
                validation = DeterministicFinancialValidator(catalog).validate(batch)
                if control == "stale_validation":
                    claim.content += " Đã cải thiện."
                run(
                    "control-" + control,
                    "synthetic_control_on_persisted_BBS",
                    batch,
                    validation,
                    [expected],
                    annotations["interpretation_control"] if control == "interpretation" else None,
                )
                assert original.claims[0].verification_status == "pending"
    finally:
        if adapter:
            adapter.close()
        after = {p: digest(root / p) for p in before}
        save_new(output / "hashes-after.json", after)
        assert before == after, "protected_inputs_changed"
        summary = dict(
            all_passed=bool(rows) and all(r["passed"] for r in rows),
            cases=len(rows),
            claim_rows=sum(len(r["actual"]) for r in rows),
            statuses=dict(Counter(s for r in rows for s in r["actual"])),
            groups=dict(Counter(r["group"] for r in rows)),
            methods=dict(sum((Counter(r["methods"]) for r in rows), Counter())),
            semantic_assertions=sum(r["semantic_assertions"] for r in rows),
            actual_gemini_calls=len(attempts) if live else 0,
            mock_semantic_calls=0 if live else len(attempts),
            tokens=sum(
                a.get("response", {}).get("usage", {}).get("total_tokens") or 0 for a in attempts
            )
            if live
            else 0,
            protected_hashes=len(before),
            protected_unchanged=before == after,
            financial_fact_verified=False,
            limitations="Source agreement, not independent PDF gold or full claim verification accuracy.",
            rows=rows,
        )
        save_new(output / "summary.json", summary)
        print(
            json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False),
            flush=True,
        )
    return summary


def rescore(root, source, output):
    """Correct an annotation from independent saved M6-02 evidence; no execution."""
    if not source.is_relative_to(root / "artifacts/evidence") or not output.is_relative_to(
        root / "artifacts/evidence"
    ):
        raise ValueError("evaluation_paths_must_stay_in_artifacts_evidence")
    output.mkdir(exist_ok=False)
    summary = load(source / "summary.json")
    annotations = load(root / "evaluation/m6-03-scenarios.json")
    save_new(output / "expected-annotations.json", annotations)
    correction_source = root / "artifacts/evidence/M6-02-validation-final/result-saved-E35.json"
    validation = ValidationResult.model_validate_json(correction_source.read_text(encoding="utf-8"))
    assert len(validation.claims) == 2
    assert any(
        c.check_id == "supporting_fact"
        and c.status == "fail"
        and c.expected["value"] != c.observed["value"]
        for c in validation.claims[1].checks
    )
    bindings = {}
    for row in summary["rows"]:
        result_file = source / f"result-{row['case_id']}.json"
        result = EvidenceCriticResult.model_validate_json(result_file.read_text(encoding="utf-8"))
        bindings[result_file.relative_to(root).as_posix()] = digest(result_file)
        assert row["actual"] == [c.status for c in result.claims]
        case_id = row["case_id"].removeprefix("saved-")
        if case_id in annotations.get("saved_expected", {}):
            row["original_expected"] = row["expected"]
            row["expected"] = annotations["saved_expected"][case_id]
            row["annotation_correction"] = annotations["annotation_corrections"][case_id]
        row["passed"] = row["actual"] == row["expected"]
    summary["all_passed"] = bool(summary["rows"]) and all(r["passed"] for r in summary["rows"])
    summary["runtime_source"] = dict(
        path=source.relative_to(root).as_posix(), sha256=digest(source / "summary.json")
    )
    summary["rescore_only"] = True
    summary["annotation_source"] = dict(
        path=correction_source.relative_to(root).as_posix(), sha256=digest(correction_source)
    )
    save_new(output / "result-bindings.json", bindings)
    save_new(output / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--rescore-from", type=Path)
    parser.add_argument("--offline-evidence", type=Path)
    args = parser.parse_args()
    if args.rescore_from:
        summary = rescore(Path.cwd().resolve(), args.rescore_from.resolve(), args.output.resolve())
    else:
        summary = evaluate(
            Path.cwd().resolve(),
            args.output.resolve(),
            live=args.live,
            offline_evidence=args.offline_evidence,
        )
    raise SystemExit(0 if summary["all_passed"] else 1)
