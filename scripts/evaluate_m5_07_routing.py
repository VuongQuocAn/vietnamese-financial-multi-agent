"""Đánh giá routing BBS offline; reference roles/reasons nằm trong manifest trước run."""

import argparse
import json
from contextlib import ExitStack
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from evaluate_d04_closure import save
from evaluate_m4_05_qa import setup
from evaluate_m5_02_planner import protected as previous_protected
from evaluate_m5_04_profitability import regressions
from evaluate_m5_06_cash_flow import compatibility, response_for, stable
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    AdaptiveSpecialistRouter,
    CashFlowEarningsQualitySpecialist,
    EvidenceAwareQueryPlanner,
    LiquidityLeverageSpecialist,
    PlannerContext,
    PlannerOperation,
    PlannerProposal,
    PlannerResult,
    ProfitabilitySpecialist,
    RiskAwareSupervisor,
    RiskSignal,
    RoutingDecision,
    SupervisorResult,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import (
    EvidenceRetrievalTools,
    FinancialCalculationResponse,
    FinancialCalculator,
    FinancialRetrievalTools,
)


def protected(root):
    hashes = previous_protected(root)
    for folder in (root / "artifacts/evidence").iterdir():
        if folder.is_dir() and not folder.name.startswith("M5-07"):
            hashes.update(
                (p.relative_to(root).as_posix(), digest(p))
                for p in folder.rglob("*")
                if p.is_file() and p.suffix != ".log"
            )
    hashes["web/next-env.d.ts"] = digest(root / "web/next-env.d.ts")
    return dict(sorted(hashes.items()))


class ReferencePlanner(EvidenceAwareQueryPlanner):
    """Bounded mixed fact+metric input to the existing deterministic materializer.

    M5-02 alias baseline omits independently asked facts when a formula is present.
    Reference operations are declared in the scenario, never inferred from Router.
    No Gateway, mock LLM or financial evidence fabrication.
    """

    case = None

    def _deterministic(self, question):
        if not self.case or "reference_items" not in self.case:
            return super()._deterministic(question)
        case = self.case
        proposal = PlannerProposal(
            intent="multi_step_analysis",
            company_alias="BBS",
            reporting_years=[case["year"]],
            required_indicators=case["reference_items"],
            formula_ids=case["reference_formulas"],
            evidence_needs=["fact", "metric", "lineage", "citations"],
        )
        for index, item in enumerate(case["reference_items"]):
            key = f"fact_{index}"
            proposal.operations.extend(
                [
                    PlannerOperation(
                        operation_id=key, operation="find_financial_facts", canonical_item_id=item
                    ),
                    PlannerOperation(
                        operation_id=key + "_source",
                        operation="get_evidence_sources",
                        dependencies=[key],
                    ),
                ]
            )
        for index, formula in enumerate(case["reference_formulas"]):
            key = f"metric_{index}"
            proposal.operations.extend(
                [
                    PlannerOperation(
                        operation_id=key, operation="calculate_financial_metric", formula_id=formula
                    ),
                    PlannerOperation(
                        operation_id=key + "_lineage",
                        operation="get_metric_evidence_lineage",
                        dependencies=[key],
                    ),
                ]
            )
        proposal.operations.append(
            PlannerOperation(
                operation_id="bundle",
                operation="prepare_bundle",
                dependencies=[
                    o.operation_id
                    for o in proposal.operations
                    if o.operation in {"get_evidence_sources", "get_metric_evidence_lineage"}
                ],
            )
        )
        return proposal.model_dump(mode="json")


def inject(planner, upstream, mode):
    """Controls change copies only; never alter accepted persisted evidence."""
    if not mode:
        return
    if mode == "approval_payload":
        upstream.evidence_bundle.calculations[0].evidence.closure.readiness["formula_policy"][
            "execution_approved"
        ] = False
        return
    if mode == "unsupported_with_fact":
        question = planner.question.rstrip("?") + " và Current Ratio?"
        planner.question = planner.query.original_question = question
        planner.plan.query.original_question = question
        upstream.final_plan_state.query.original_question = question
        planner.proposal.unsupported_capabilities.append("current_ratio")
        return
    if mode in {"blocked_supervisor", "partial_supervisor"}:
        upstream.status = "blocked" if mode == "blocked_supervisor" else "partial"
        return
    if mode == "global_compatibility":
        upstream.risk_signals.append(
            RiskSignal(code="cross_document_compatibility_unresolved", reason="injected_D03-B10")
        )
        return
    if mode in {"formula_risk", "missing_lineage"}:
        metric = next(
            r for r in upstream.final_plan_state.requirements if r.evidence_type == "metric"
        )
        upstream.status = "partial"
        if mode == "formula_risk":
            upstream.risk_signals.append(
                RiskSignal(
                    code="formula_not_approved",
                    reason="injected_formula",
                    requirement_ids=[metric.requirement_id],
                )
            )
        else:
            upstream.evidence_bundle.calculations[0].evidence.reviewed_lineage.lineage = None
        return
    bundle = upstream.evidence_bundle
    fact = next(f for f in bundle.facts if f.record.canonical_item_id == "b03.operating_cash_flow")
    target = next(
        r
        for r in upstream.final_plan_state.requirements
        if r.canonical_item_id == "b03.operating_cash_flow"
    )
    if mode == "optional_cash":
        for plan in (planner.plan, upstream.final_plan_state):
            for requirement in plan.requirements:
                if (
                    requirement.requirement_id == target.requirement_id
                    or target.requirement_id in requirement.dependencies
                ):
                    requirement.importance = "optional"
        bundle.facts.remove(fact)
        return
    upstream.status = "partial"
    if mode in {"missing_cash", "branch_scope"}:
        code = "missing_evidence" if mode == "missing_cash" else "reporting_scope_unresolved"
        upstream.risk_signals.append(
            RiskSignal(
                code=code, reason="injected_" + mode, requirement_ids=[target.requirement_id]
            )
        )
        if mode == "missing_cash":
            bundle.facts.remove(fact)
    elif mode == "conflict_cash":
        other = fact.model_copy(deep=True)
        other.record.value.normalized_value += 1
        bundle.facts.append(other)
    elif mode == "citation_cash":
        fact.citations[0].pdf_page = 999
    elif mode == "period_cash":
        fact.record.context.period = "2024"
    else:
        raise ValueError("unknown_injection:" + mode)


def guarded_route(router, planner, upstream):
    """Only routing latency; real Supervisor preparation runs outside this guard."""

    def forbidden(*args, **kwargs):
        raise AssertionError("router_tool_or_Gemini_or_specialist_execution")

    with ExitStack() as stack:
        for cls, method in (
            (SharedLLMGateway, "generate"),
            (RiskAwareSupervisor, "_dispatch"),
            (FinancialRetrievalTools, "find_financial_facts"),
            (FinancialCalculator, "calculate_financial_metric"),
            (EvidenceRetrievalTools, "get_evidence_sources"),
            (EvidenceRetrievalTools, "get_metric_evidence_lineage"),
            (ProfitabilitySpecialist, "analyze"),
            (LiquidityLeverageSpecialist, "analyze"),
            (CashFlowEarningsQualitySpecialist, "analyze"),
        ):
            stack.enter_context(patch.object(cls, method, forbidden))
        start = perf_counter()
        decision = router.route(
            question=planner.question, planner_result=planner, supervisor_result=upstream
        )
        elapsed = (perf_counter() - start) * 1000
    return decision, elapsed


def evaluate(root, output, *, run_regressions=False, reuse_inputs=None):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M5-07"
    ):
        raise ValueError("new_M5-07_evidence_directory_required")
    output.mkdir(parents=True, exist_ok=False)
    cases = load(root / "evaluation/m5-07-scenarios.json")
    assert len(cases) >= 30 and len({c["id"] for c in cases}) == len(cases)
    save(output / "reference-manifest.json", cases)
    hashes = protected(root)
    save(output / "hashes-before.json", hashes)
    save(
        output / "implementation.json",
        {
            path: digest(root / path)
            for path in (
                "src/agents/adaptive_router.py",
                "src/agents/routing_contracts.py",
                "scripts/evaluate_m5_07_routing.py",
                "evaluation/m5-07-scenarios.json",
            )
        },
    )
    print(f"Pinned {len(hashes)} protected files; hydrating persisted BBS", flush=True)
    data, scopes, recovery, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    planner = ReferencePlanner(catalog, documents)
    supervisor = RiskAwareSupervisor(catalog)
    all_cases = {c["id"]: c for c in cases}
    cache, sources = {}, {}

    def prepare(case):
        key = case["id"]
        if key in cache:
            return tuple(v.model_copy(deep=True) if v else None for v in cache[key])
        if case.get("base"):
            p, s = prepare(all_cases[case["base"]])
            sources[key] = {
                "base": case["base"],
                "mode": "injected_negative_control"
                if case.get("injection")
                else "persisted_caveat_control",
            }
        elif case.get("saved_planner"):
            path = root / "artifacts/evidence" / case["saved_planner"]
            p = PlannerResult.model_validate_json(path.read_text(encoding="utf-8"))
            trace = root / f"artifacts/evidence/M5-03-verified/execution-{case['trace']}.json"
            s = SupervisorResult.model_validate_json(trace.read_text(encoding="utf-8"))
            sources[key] = {
                "mode": "persisted_planner_supervisor",
                "planner": case["saved_planner"],
                "planner_sha256": digest(path),
                "trace": case["trace"],
                "trace_sha256": digest(trace),
            }
        elif (
            reuse_inputs
            and (reuse_inputs / f"planner-{key}.json").is_file()
            and (reuse_inputs / f"supervisor-{key}.json").is_file()
            and not case.get("reference_items")
        ):
            p = PlannerResult.model_validate_json(
                (reuse_inputs / f"planner-{key}.json").read_text(encoding="utf-8")
            )
            s = SupervisorResult.model_validate_json(
                (reuse_inputs / f"supervisor-{key}.json").read_text(encoding="utf-8")
            )
            assert p.question == case["question"]
            sources[key] = {
                "mode": "reused_deterministic_BBS_inputs",
                "from": reuse_inputs.relative_to(root).as_posix(),
            }
        else:
            snapshot = (
                None
                if case.get("unbound_snapshot")
                else recovery.snapshot_id
                if case.get("snapshot") == "recovery"
                else scopes[case["year"]]["snapshot_id"]
            )
            planner.case = case
            p = planner.plan(
                case["question"], PlannerContext(mode="deterministic", snapshot_id=snapshot)
            )
            s = supervisor.execute(p.plan) if p.plan else None
            sources[key] = {
                "mode": "deterministic_reference_proposal"
                if case.get("reference_items")
                else "deterministic_BBS_planner_supervisor"
            }
        inject(p, s, case.get("injection"))
        cache[key] = p, s
        return tuple(v.model_copy(deep=True) if v else None for v in (p, s))

    router, rows = AdaptiveSpecialistRouter(), []
    for case in cases:
        p, s = prepare(case)
        before = (p.model_dump_json(), s.model_dump_json() if s else None)
        save(output / f"planner-{case['id']}.json", p.model_dump(mode="json"))
        if s:
            save(output / f"supervisor-{case['id']}.json", s.model_dump(mode="json"))
        decision, latency = guarded_route(router, p, s)
        assert before == (p.model_dump_json(), s.model_dump_json() if s else None), "mutated_input"
        assert RoutingDecision.model_validate_json(decision.model_dump_json()) == decision
        if s:
            s.evidence_bundle.facts.reverse()
            s.evidence_bundle.calculations.reverse()
            s.evidence_bundle.citations.reverse()
        repeat, _ = guarded_route(router, p, s)
        deterministic = repeat == decision
        reasons = sorted(
            set(
                decision.stop_reasons
                + [r.code for r in decision.risk_signals]
                + [r for t in decision.trace for r in t.reasons]
                + [r for q in decision.requirements for r in q.reasons]
            )
        )
        actual, expected = set(decision.selected_roles), set(case["expected_roles"])
        reason_ok = all(any(wanted in r for r in reasons) for wanted in case["expected_reasons"])
        caveats_ok = not case.get("expect_caveats") or bool(decision.caveats)
        row = dict(
            id=case["id"],
            group=case["group"],
            source=sources[case["id"]],
            question=p.question,
            expected_roles=sorted(expected),
            actual_roles=sorted(actual),
            expected_status=case["expected_status"],
            status=decision.status,
            reasons=reasons,
            reasons_correct=reason_ok,
            deterministic=deterministic,
            caveats_correct=caveats_ok,
            correct=actual == expected
            and decision.status == case["expected_status"]
            and reason_ok
            and caveats_ok
            and deterministic,
            latency_ms=latency,
            true_positive=len(actual & expected),
            false_positive=len(actual - expected),
            false_negative=len(expected - actual),
        )
        save(output / f"routing-{case['id']}.json", decision.model_dump(mode="json"))
        rows.append(row)
        print(
            case["id"],
            row["correct"],
            decision.status,
            decision.selected_roles,
            "" if row["correct"] else reasons,
            flush=True,
        )
    save(output / "rows.json", rows)
    if run_regressions:
        accepted = [
            FinancialCalculationResponse.model_validate_json(json.dumps(r))
            for r in load(root / "artifacts/evidence/M4-03-final/executions.json")
        ]
        regressions(root, data, scopes, recovery, accepted, output, catalog, documents)
        checks = compatibility(root, output)
        for case_id in ("C01", "C09", "C11"):
            folder = root / "artifacts/evidence/M5-06-offline-v2"
            old = load(folder / f"result-{case_id}.json")
            upstream = SupervisorResult.model_validate_json(
                (folder / f"upstream-{case_id}.json").read_text(encoding="utf-8")
            )
            gateway = SharedLLMGateway(
                {"gemini": lambda req, payload=old["raw_output"]: response_for(req, payload)}
            )
            actual = CashFlowEarningsQualitySpecialist(gateway).analyze(
                question=old["question"], supervisor_result=upstream
            )
            assert stable(actual.model_dump(mode="json")) == stable(old), case_id
            checks.append(dict(case=case_id, exact=True, status=actual.status))
        save(output / "specialist-compatibility.json", checks)
    after = protected(root)
    assert hashes == after, "protected_artifact_changed"
    save(output / "hashes-after.json", after)

    def fraction(n, d):
        return n / d if d else None

    tp = sum(r["true_positive"] for r in rows)
    fp = sum(r["false_positive"] for r in rows)
    fn = sum(r["false_negative"] for r in rows)
    multi = [r for r in rows if len(r["expected_roles"]) > 1]
    abstain = [r for r in rows if not r["expected_roles"]]
    partial = [r for r in rows if r["expected_status"] == "partial"]
    negative = [r for r in rows if r["group"] == "negative"]
    summary = dict(
        total=len(rows),
        passed=sum(r["correct"] for r in rows),
        routing_accuracy=fraction(sum(r["correct"] for r in rows), len(rows)),
        specialist_selection_precision=fraction(tp, tp + fp),
        specialist_selection_recall=fraction(tp, tp + fn),
        multi_specialist_coverage=fraction(
            sum(set(r["expected_roles"]) <= set(r["actual_roles"]) for r in multi), len(multi)
        ),
        incorrect_specialist_activation=fp,
        unnecessary_specialist_activation=sum(
            max(0, len(r["actual_roles"]) - len(r["expected_roles"])) for r in rows
        ),
        appropriate_abstention_blocking=fraction(sum(r["correct"] for r in abstain), len(abstain)),
        partial_routing_correctness=fraction(sum(r["correct"] for r in partial), len(partial)),
        risk_gate_correctness=fraction(sum(r["correct"] for r in negative), len(negative)),
        determinism=fraction(sum(r["deterministic"] for r in rows), len(rows)),
        routing_latency_ms=dict(
            median=median(r["latency_ms"] for r in rows), maximum=max(r["latency_ms"] for r in rows)
        ),
        protected_hashes_unchanged=len(hashes),
        actual_Gemini_calls=0,
        router_tool_calls=0,
        specialist_executions_during_routing=0,
        compatibility_replay_transport="saved responses in-process; zero Gemini API",
        regressions_run=run_regressions,
    )
    save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regressions", action="store_true")
    parser.add_argument("--reuse-inputs", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = evaluate(
        root,
        args.output.resolve(),
        run_regressions=args.regressions,
        reuse_inputs=args.reuse_inputs.resolve() if args.reuse_inputs else None,
    )
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
