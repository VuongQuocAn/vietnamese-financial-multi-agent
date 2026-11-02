"""Persisted BBS Supervisor evaluation; saved Gemini plans, zero new Gateway calls."""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_d04_closure import save
from evaluate_m4_03_calculator import independent_check
from evaluate_m4_05_qa import bounded_regressions, setup
from evaluate_m5_01_contracts import fact_plan
from evaluate_m5_02_planner import protected as planner_protected
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    EvidenceAwareQueryPlanner,
    EvidencePlan,
    PlannerContext,
    PlannerResult,
    RiskAwareSupervisor,
    SupervisorResult,
    validate_plan,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    EvidenceToolResponse,
    FinancialCalculationResponse,
    FinancialQABaseline,
    QAResponse,
)


def protected(root):
    hashes = planner_protected(root)
    # Pin ALL previous evidence, including original PDFs/cache through prior manifest.
    for folder in (root / "artifacts/evidence").iterdir():
        if folder.is_dir() and not folder.name.startswith("M5-03"):
            hashes.update(
                (p.relative_to(root).as_posix(), digest(p))
                for p in folder.rglob("*")
                if p.is_file() and p.suffix != ".log"
            )
    return dict(sorted(hashes.items()))


def saved_plan(root, folder, case):
    path = root / "artifacts/evidence" / folder / f"response-{case}.json"
    response = PlannerResult.model_validate_json(path.read_text(encoding="utf-8"))
    assert response.plan is not None
    return response.plan, dict(
        path=path.relative_to(root).as_posix(), sha256=digest(path), case=case
    )


def check_evidence(result, data, accepted, catalog, accepted_lineages):
    """Ground truth: persisted facts + accepted M4 artifacts, never Supervisor output."""
    details = []
    for fact in result.evidence_bundle.facts:
        reference = next(
            f for f in data["facts"] if f.observation_identity() == fact.reference.observation
        )
        assert fact.record == reference
        assert [c.source for c in fact.citations] == reference.sources
        assert fact.source_review == catalog.api.get_source_review(reference.observation_identity())
        assert fact.reporting_scope == catalog.get_reporting_scope(
            reference.document_id, reference.snapshot_id
        )
        assert fact.citations and all(c in result.evidence_bundle.citations for c in fact.citations)
        details.append(
            dict(kind="fact", reference=fact.reference.model_dump(mode="json"), exact=True)
        )
    for calculation in result.evidence_bundle.calculations:
        reference = next(a for a in accepted if a.metric_id == calculation.metric_id)
        assert (
            calculation == reference
        )  # Includes trace, formula, approvals, operands, caveats, reviews.
        metric = next(m for m in data["metrics"] if m.metric_id == calculation.metric_id)
        assert calculation.result == independent_check(metric, data["facts"])
        assert all(c in result.evidence_bundle.citations for c in reference.evidence.citations)
        details.append(
            dict(
                kind="metric",
                metric_id=calculation.metric_id,
                result=calculation.result,
                exact=True,
            )
        )
    for source in result.evidence_bundle.sources_and_lineage:
        if source.request.tool == "get_metric_evidence_lineage":
            reference = next(
                r for r in accepted_lineages if r.request.metric_id == source.request.metric_id
            )
            assert source == reference
            accepted_metric = next(a for a in accepted if a.metric_id == source.request.metric_id)
            assert source.metric_matches == [accepted_metric.evidence]
        else:
            reference = catalog.api.get_sources(source.request.reference)
            assert source.matches == reference.matches
    assert not result.financial_fact_verified
    for step in result.step_results:
        original = next(s for s in result.final_plan_state.steps if s.step_id == step.step_id)
        if step.final_state == "completed":
            assert all(
                next(r for r in result.resolved_requirements if r.requirement_id == key)
                for key in original.output_evidence_ids
            )
            positions = {t.step_id: i for i, t in enumerate(result.step_results)}
            assert all(
                result.step_results[positions[k]].final_state == "completed"
                and positions[k] < positions[step.step_id]
                for k in original.prerequisite_step_ids
            )
    return details


def evaluate(root, output, resume_from=None):
    if not output.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Output must stay under artifacts/evidence")
    output.mkdir(parents=True, exist_ok=False)
    if resume_from is not None and not resume_from.is_relative_to(root / "artifacts/evidence"):
        raise ValueError("Resume evidence must stay under artifacts/evidence")
    save(
        output / "implementation.json",
        dict(supervisor_sha256=digest(root / "src/agents/supervisor.py")),
    )
    if resume_from is not None:
        assert load(resume_from / "implementation.json")["supervisor_sha256"] == digest(
            root / "src/agents/supervisor.py"
        ), "Cannot reuse traces from a different Supervisor implementation"
    hashes = protected(root)
    if resume_from is not None:
        assert load(resume_from / "hashes-before.json") == hashes, (
            "Cannot reuse evaluation after protected inputs changed"
        )
    save(output / "hashes-before.json", hashes)
    print(f"Pinned {len(hashes)} protected inputs; hydrating BBS", flush=True)
    data, scopes, recovery, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    original = [r.model_dump_json() for r in [*data["facts"], *data["metrics"], *data["evidence"]]]
    accepted = [
        FinancialCalculationResponse.model_validate_json(json.dumps(r))
        for r in load(root / "artifacts/evidence/M4-03-final/executions.json")
    ]
    accepted_lineages = [
        EvidenceToolResponse.model_validate_json(json.dumps(r))
        for r in load(root / "artifacts/evidence/M4-04/metric-lineages.json")
    ]
    planner = EvidenceAwareQueryPlanner(catalog, documents)
    cases = []

    def add_saved(case_id, folder, name, expected="completed", injection=None):
        plan, provenance = saved_plan(root, folder, name)
        cases.append(
            dict(id=case_id, plan=plan, origin=provenance, expected=expected, injection=injection)
        )

    def add_planned(case_id, question, snapshot_id=None):
        previous = resume_from / f"plan-{case_id}.json" if resume_from else None
        if previous and previous.is_file():
            cases.append(
                dict(
                    id=case_id,
                    plan=EvidencePlan.model_validate_json(previous.read_text(encoding="utf-8")),
                    expected="completed",
                    origin=dict(
                        mode="M5-02 deterministic materializer",
                        question=question,
                        snapshot_id=snapshot_id,
                    ),
                )
            )
            return
        proposed = planner.plan(
            question, PlannerContext(mode="deterministic", snapshot_id=snapshot_id)
        )
        assert proposed.status == "planned", proposed.reasons
        cases.append(
            dict(
                id=case_id,
                plan=proposed.plan,
                expected="completed",
                origin=dict(
                    mode="M5-02 deterministic materializer",
                    question=question,
                    snapshot_id=snapshot_id,
                ),
            )
        )

    add_saved("S01_assets2025", "M5-02-offline-final", "P01")
    add_saved("S02_revenue2024", "M5-02-offline-final", "P02")
    add_saved("S03_gross_margin2025", "M5-02-offline-final", "P05")
    add_planned("S04_debt2025", "Tính tỷ lệ nợ trên tổng tài sản BBS năm 2025.")
    add_planned("S05_yoy2025", "Tăng trưởng doanh thu BBS năm 2025?")
    add_saved("S06_multi2024_Gemini", "M5-02-live-final", "F01")
    add_saved("S07_cash_profit2025", "M5-02-offline-final", "P11")
    add_saved("S08_recovery2022_Gemini", "M5-02-live-final", "F04")
    add_planned(
        "S08b_original2022", "Tính biên lợi nhuận gộp BBS năm 2022.", scopes[2022]["snapshot_id"]
    )
    # Planner deliberately emits no EvidencePlan for ambiguity/cross-document;
    # use M5-01 negative controls to test Supervisor's independent preflight.
    ambiguity = fact_plan(
        "S09",
        "Tổng tài sản BBS 2022 chưa chọn snapshot?",
        dict(document_id=scopes[2022]["document_id"]),
        "b01.total_assets",
        "2022-12-31",
    )
    cases.append(
        dict(
            id="S09_ambiguity",
            plan=ambiguity,
            expected="blocked",
            stop="unresolved_ambiguity",
            origin=dict(mode="M5-01 negative control; M5-02 emits no plan"),
        )
    )
    cross = cases[0]["plan"].model_copy(deep=True)
    cross.query.cross_document_comparison = True
    cross.query.original_question = "So sánh BBS 2021 với 2025."
    cross.query.selectors.append(cross.query.selectors[0].model_copy(update=scopes[2021]))
    cross = EvidencePlan.model_validate_json(cross.model_dump_json())
    cases.append(
        dict(
            id="S10_cross_document",
            plan=cross,
            expected="blocked",
            stop="compatibility_gate_blocked",
            origin=dict(mode="M5-02 P01 + explicit cross-document negative query"),
        )
    )
    add_saved("S11_consolidated_scope", "M5-02-offline-final", "P18", "blocked")
    cases[-1]["stop"] = "compatibility_gate_blocked"
    add_saved("S12_runtime_missing", "M5-02-live-final", "F01", "partial", "unavailable")
    add_saved("S12b_runtime_conflict", "M5-02-live-final", "F01", "partial", "conflicted")
    add_saved("S13_optional_sources", "M5-02-offline-final", "P01", "completed", "optional")
    optional = cases[-1]["plan"]
    for requirement in optional.requirements:
        if requirement.evidence_type == "citations":
            requirement.importance = "optional"
    add_saved("S14_budget", "M5-02-offline-final", "P05", "partial")
    cases[-1].update(budget=3, stop="execution_limit_reached")
    add_saved("S15_Gemini_metric2023", "M5-02-live-final", "F03")
    add_saved("S16_assets2021", "M5-02-offline-final", "P04")
    add_saved("S17_cash2023", "M5-02-offline-final", "P03")
    rows, detailed = [], []
    supervisor = RiskAwareSupervisor(catalog)
    for case in cases:
        previous_execution = resume_from / f"execution-{case['id']}.json" if resume_from else None
        if previous_execution and previous_execution.is_file():
            case["plan"] = EvidencePlan.model_validate_json(
                (resume_from / f"plan-{case['id']}.json").read_text(encoding="utf-8")
            )
        plan = case["plan"]
        original_plan = plan.model_dump_json()
        injection = case.get("injection")
        dispatch = supervisor._dispatch
        target = next(
            (
                s
                for s in plan.steps
                if s.tool
                == ("get_evidence_sources" if injection == "optional" else "find_financial_facts")
            ),
            None,
        )
        if injection:

            def injected(
                operation, request, *, target=target, dispatch=dispatch, injection=injection
            ):
                response = dispatch(operation, request)
                if operation == target.tool and all(
                    request.model_dump(mode="json").get(k) == v for k, v in target.arguments.items()
                ):
                    response.status = "unavailable" if injection == "optional" else injection
                    response.matches = []
                    response.reasons = ["injected_after_preflight_" + injection]
                elif injection == "optional" and operation == target.tool:
                    response.status, response.matches = "unavailable", []
                    response.reasons = ["injected_optional_source_unavailable"]
                return response

            supervisor._dispatch = injected
        try:
            if previous_execution and previous_execution.is_file():
                result = SupervisorResult.model_validate_json(
                    previous_execution.read_text(encoding="utf-8")
                )
            else:
                result = supervisor.execute(plan, max_steps=case.get("budget", 20))
        finally:
            supervisor._dispatch = dispatch
        save(output / f"plan-{case['id']}.json", plan.model_dump(mode="json"))
        save(output / f"execution-{case['id']}.json", result.model_dump(mode="json"))
        assert plan.model_dump_json() == original_plan
        assert SupervisorResult.model_validate_json(result.model_dump_json()) == result
        checks = check_evidence(result, data, accepted, catalog, accepted_lineages)
        correct = result.status == case["expected"]
        if case.get("stop"):
            correct &= case["stop"] in result.triggered_stop_conditions
        if case["expected"] == "blocked":
            correct &= result.executed_steps == 0 and not result.tool_trace
        if injection and injection != "optional":
            correct &= result.initial_validation.execution_eligible and any(
                t.final_state == "blocked" for t in result.step_results
            )
            correct &= result.skipped_steps > 0 and any(
                t.final_state == "completed" and t.operation == "get_evidence_sources"
                for t in result.step_results
            )
        if injection == "optional":
            correct &= result.evidence_bundle.complete and any(
                not r.blocking for r in result.risk_signals if "injected" in r.reason
            )
        complete = result.evidence_bundle.complete
        if case["expected"] == "completed":
            correct &= complete and bool(
                result.evidence_bundle.facts or result.evidence_bundle.calculations
            )
        if case["id"] == "S03_gross_margin2025":
            assert result.evidence_bundle.calculations[0].result == "7.21"
        row = dict(
            id=case["id"],
            origin=case["origin"],
            injected=bool(injection),
            preflight=result.initial_validation.disposition,
            scheduled_steps=len(plan.steps),
            executed_steps=result.executed_steps,
            skipped_steps=result.skipped_steps,
            final_status=result.status,
            correct=bool(correct),
            grounded=bool(checks),
            evidence_complete=complete,
            resolved_required=sum(r.importance == "required" for r in result.resolved_requirements),
            total_required=sum(r.importance == "required" for r in plan.requirements),
            stop_reason=result.triggered_stop_conditions,
            risks=[r.model_dump(mode="json") for r in result.risk_signals],
            latency_ms=result.latency_ms,
        )
        rows.append(row)
        detailed.append(dict(id=case["id"], checks=checks))
        if previous_execution and previous_execution.is_file():
            row["reused_execution"] = dict(
                path=previous_execution.relative_to(root).as_posix(),
                sha256=digest(previous_execution),
            )
        save(output / f"score-{case['id']}.json", row)
        print(
            f"{row['id']}: preflight={row['preflight']} steps={result.executed_steps}/{len(plan.steps)} status={result.status} correct={bool(correct)}",
            flush=True,
        )
        assert correct, row
    save(output / "independent-checks.json", detailed)
    save(output / "scores.json", rows)
    m4_checkpoint = resume_from / "regression-m4.json" if resume_from else None
    regressions = (
        load(m4_checkpoint)
        if m4_checkpoint and m4_checkpoint.is_file()
        else bounded_regressions(root, data, scopes, recovery, accepted, output)
    )
    save(output / "regression-m4.json", regressions)
    print("M4: 18 exact calculations/29 queries/36 pairs/D-06/D-07 PASS", flush=True)
    # Exact accepted deterministic QA 36 responses; no Gateway or Gemini.
    qa = FinancialQABaseline(catalog, documents)
    qa_cases = load(root / "evaluation/m4-05-questions.json")
    from evaluate_m4_05_qa import context_for

    accepted_qa = load(root / "artifacts/evidence/M4-05-final/responses.json")
    qa_checkpoint = resume_from / "regression-qa.json" if resume_from else None
    if qa_checkpoint and qa_checkpoint.is_file():
        assert load(qa_checkpoint)["exact_ids"] == [c["id"] for c in qa_cases]
    else:
        for case, previous in zip(qa_cases, accepted_qa, strict=True):
            assert case["id"] == previous["id"]
            assert qa.answer(
                case["question"], context_for(case, scopes, recovery)
            ) == QAResponse.model_validate_json(json.dumps(previous["response"]))
    save(output / "regression-qa.json", dict(exact_ids=[c["id"] for c in qa_cases]))
    regressions["qa_exact"] = len(qa_cases)
    print(f"M4-05: {len(qa_cases)} exact QA responses PASS", flush=True)
    contract_cases = load(root / "artifacts/evidence/M5-01-scope-final/cases.json")
    contract_checkpoint = resume_from / "regression-contracts.json" if resume_from else None
    passed_contracts = (
        load(contract_checkpoint)["exact_ids"]
        if contract_checkpoint and contract_checkpoint.is_file()
        else []
    )
    for case in contract_cases:
        if case["case_id"] in passed_contracts:
            continue
        filename = (
            "invalid-period-binding"
            if case["case_id"] == "invalid_period_binding"
            else case["case_id"]
        )
        path = root / "artifacts/evidence/M5-01-scope-final" / f"{filename}.json"
        saved = load(path)
        assert (
            validate_plan(saved["plan"], catalog=catalog).model_dump(mode="json")
            == saved["validation"]
        )
        passed_contracts.append(case["case_id"])
    assert set(passed_contracts) == {c["case_id"] for c in contract_cases}
    save(output / "regression-contracts.json", dict(exact_ids=passed_contracts))
    regressions["m5_01_cases"] = len(contract_cases)
    print(f"M5-01: {len(contract_cases)} exact contract cases PASS", flush=True)
    assert original == [
        r.model_dump_json() for r in [*data["facts"], *data["metrics"], *data["evidence"]]
    ]
    after = {p: digest(root / p) for p in hashes}
    save(output / "hashes-after.json", after)
    assert hashes == after
    summary = dict(
        total=len(rows),
        correct=sum(r["correct"] for r in rows),
        statuses=dict(Counter(r["final_status"] for r in rows)),
        calls=0,
        protected_hashes=len(hashes),
        hashes_unchanged=True,
        json_roundtrip_exact=True,
        reused_executions=sum("reused_execution" in r for r in rows),
        regression=regressions,
        financial_fact_verified=False,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--resume-from", type=Path, help="Reuse immutable execution traces; redo independent checks"
    )
    args = parser.parse_args()
    evaluate(
        Path.cwd().resolve(),
        args.output.resolve(),
        args.resume_from.resolve() if args.resume_from else None,
    )
