"""BBS E2E evaluation; real inputs, mock/replay/live and injected controls are explicit."""

import argparse
import json
from collections import Counter
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from statistics import median
from unittest.mock import patch

from evaluate_d04_closure import save
from evaluate_m4_05_qa import setup
from evaluate_m5_02_planner import protected as previous_protected
from evaluate_m5_04_profitability import regressions
from evaluate_m5_06_cash_flow import compatibility, response_for, stable
from evaluate_m5_07_routing import ReferencePlanner, inject
from run_d01_coverage import digest, load
from vietnamese_financial_multi_agent.agents import (
    AdaptiveSpecialistRouter,
    CashFlowEarningsQualitySpecialist,
    EvidenceAwareQueryPlanner,
    FinancialMultiAgentOrchestrator,
    LiquidityLeverageSpecialist,
    OrchestrationResult,
    PlannerContext,
    PlannerResult,
    ProfitabilitySpecialist,
    RiskAwareSupervisor,
    build_specialist_context,
)
from vietnamese_financial_multi_agent.agents.cash_flow_earnings_quality_specialist import (
    FLOW_ACTIVITIES,
    SIGN_TEMPLATE,
    ZERO_TEMPLATE,
)
from vietnamese_financial_multi_agent.api.qa_gateway import create_qa_adapter
from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.persistence import atomic_json
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceRetrieval
from vietnamese_financial_multi_agent.tools import FinancialCalculationResponse

CLASSES = {
    "profitability": ProfitabilitySpecialist,
    "liquidity_and_leverage": LiquidityLeverageSpecialist,
    "cash_flow_and_earnings_quality": CashFlowEarningsQualitySpecialist,
}


def protected(root):
    hashes = previous_protected(root)
    for folder in (root / "artifacts/evidence").iterdir():
        if folder.is_dir() and not folder.name.startswith("M5-08"):
            hashes.update(
                (p.relative_to(root).as_posix(), digest(p))
                for p in folder.rglob("*")
                if p.is_file() and p.suffix != ".log"
            )
    hashes["web/next-env.d.ts"] = digest(root / "web/next-env.d.ts")
    return dict(sorted(hashes.items()))


def mock_specialist(request, case):
    prompt = json.loads(request.messages[0].content)
    claims = []
    for evidence in prompt["evidence"]:
        metric = evidence["kind"] == "metric"
        claim = dict(
            evidence_id=evidence["evidence_id"],
            kind="approved_metric" if metric else "fact",
            meaning="metric_value" if metric else "fact_value",
            period=evidence["period"],
            statement=None,
        )
        if "sign_template" in prompt:
            claim["sign"] = None
        claims.append(claim)
        if case.get("sign") and evidence.get("canonical_item_id") in FLOW_ACTIVITIES:
            value = Decimal(evidence["value"])
            claims.append(
                dict(
                    claim,
                    kind="supported_interpretation",
                    meaning="cash_flow_sign",
                    sign="positive" if value > 0 else "negative" if value < 0 else "zero",
                    statement=SIGN_TEMPLATE if value else ZERO_TEMPLATE,
                )
            )
    return response_for(request, dict(claims=claims, missing_information=[]))


def inject_upstream(upstream, mode):
    if mode == "conflict_liabilities":
        fact = next(
            f
            for f in upstream.evidence_bundle.facts
            if f.record.canonical_item_id == "b01.total_liabilities"
        )
        other = fact.model_copy(deep=True)
        other.record.value.normalized_value += 1
        upstream.evidence_bundle.facts.append(other)
        upstream.status = "partial"
    else:
        inject(None, upstream, mode)


def reference_proposal(case, source):
    if "custom_year" in case:
        return dict(source.raw_proposal, reporting_years=[case["custom_year"]])
    if "custom_items" not in case:
        return source.raw_proposal
    # Human-declared targets into existing M5-07 reference proposal builder.
    # This is a mock proposal, never financial reference data or Gemini quality.
    builder = object.__new__(ReferencePlanner)
    builder.case = dict(year=2025, reference_items=case["custom_items"], reference_formulas=[])
    proposal = builder._deterministic(case["question"])
    proposal["evidence_needs"] = ["fact", "citations", "analysis_bundle"]
    return proposal


def score(case, output, data, accepted, counts, invocations, actual_requests):
    facts = {f.observation_identity(): f for f in data["facts"]}
    api = EvidenceRetrieval(data["facts"], graph=data["graph"])
    expected_roles = case["expected_roles"]
    routes = output.routing_decision
    actual_roles = routes.selected_roles if routes else []
    expected_invocations = [] if case.get("projection_fault") else expected_roles
    checks = dict(
        status=output.status == case["expected_status"],
        routing=actual_roles == expected_roles,
        activation=invocations == expected_invocations,
        budget=(
            counts["planner"] == 1
            and counts["supervisor"] <= 1
            and counts["router"] <= 1
            and len(invocations) <= 3
            and len(actual_requests) <= 1 + len(invocations)
        ),
        isolation=True,
        grounding=True,
        citations=True,
        formula_lineage=True,
        unverified=not output.financial_fact_verified,
        failure_isolation=True,
        conflict_handling=True,
    )
    coverage_items, coverage_formulas = set(), set()
    for execution in output.specialist_executions:
        projection = execution.projection
        if projection is None:
            continue
        route = next(r for r in routes.routes if r.role == execution.role)
        bundle = projection.supervisor_result.evidence_bundle
        operands = {o.observation for c in bundle.calculations for o in c.trace.operands}
        checks["isolation"] &= (
            all(
                f.reference in route.supporting_references or f.reference.observation in operands
                for f in bundle.facts
            )
            and bundle.claim_fact_references == projection.claim_fact_references
        )
        checks["isolation"] &= (
            projection.supervisor_result.final_plan_state.query.required_indicators
            == route.assigned_items
            and projection.supervisor_result.final_plan_state.query.original_question
            == output.question
        )
        original = output.supervisor_result.evidence_bundle
        checks["formula_lineage"] &= all(c in original.calculations for c in bundle.calculations)
        checks["formula_lineage"] &= all(
            any(f.reference.observation == o.observation for f in bundle.facts)
            for c in bundle.calculations
            for o in c.trace.operands
        )
        checks["formula_lineage"] &= all(c in original.citations for c in bundle.citations)
        if execution.result:
            checks["isolation"] &= all(
                e.reference in route.supporting_references
                for e in execution.result.supporting_evidence
            )
    for candidate in output.candidates:
        checks["unverified"] &= not candidate.financial_fact_verified
        for evidence in candidate.supporting_evidence:
            if evidence.kind == "fact":
                fact = facts.get(evidence.reference.observation)
                valid = bool(fact) and (
                    evidence.value == str(fact.value.normalized_value)
                    and evidence.unit == fact.value.unit
                    and evidence.scale == str(fact.context.scale)
                    and evidence.period == fact.context.period
                    and evidence.company_id == fact.company_id
                    and evidence.document_id == fact.document_id
                    and evidence.snapshot_id == fact.snapshot_id
                )
                checks["grounding"] &= valid
                reference = api.get_fact(evidence.reference.observation)
                checks["citations"] &= bool(reference.matches) and all(
                    c in reference.matches[0].citations for c in evidence.citations
                )
                coverage_items.add(evidence.canonical_item_id)
            else:
                calc = evidence.calculation
                old = next((c for c in accepted if c.metric_id == calc.metric_id), None)
                checks["grounding"] &= bool(old) and (
                    calc.result == old.result
                    and calc.formula_digest == old.formula_digest
                    and calc.trace.operands == old.trace.operands
                )
                checks["citations"] &= bool(old) and candidate.citations == old.evidence.citations
                coverage_formulas.add(calc.formula_id)
            checks["citations"] &= bool(candidate.citations) and all(
                c in candidate.citations for c in evidence.citations
            )
    checks["coverage"] = coverage_items == set(case["expected_items"]) and coverage_formulas == set(
        case["expected_formulas"]
    )
    if case.get("sign"):
        checks["coverage"] &= any(c.kind == "supported_interpretation" for c in output.candidates)
    if case.get("specialist_failure"):
        checks["failure_isolation"] = (
            output.status == "partial"
            and bool(output.candidates)
            and any(
                e.status == "failed" and e.role == case["specialist_failure"]
                for e in output.specialist_executions
            )
        )
    if case.get("aggregation_control") == "duplicate":
        checks["conflict_handling"] = (
            len(output.candidates) == 1 and len(output.candidates[0].origins) == 2
        )
    if case.get("aggregation_control") == "conflict":
        # The deliberately corrupted value is a negative control, not BBS truth.
        checks["grounding"] = len(output.candidates) == 2 and len(output.conflicts) == 1
        checks["conflict_handling"] = all(c.conflict_ids for c in output.candidates)
    return dict(
        id=case["id"],
        pass_all=all(checks.values()),
        checks=checks,
        status=output.status,
        roles=actual_roles,
        invocations=invocations,
        candidates=len(output.candidates),
        calls=output.usage.calls,
        usage=output.usage.model_dump(mode="json"),
        latency_ms=output.latency_ms,
        stage_latency_ms=output.stage_latency_ms,
        input_mode="real_persisted_BBS_with_synthetic_control"
        if any(
            case.get(k)
            for k in ("injection", "specialist_failure", "projection_fault", "aggregation_control")
        )
        else "real_persisted_BBS",
    )


def evaluate(
    root,
    output,
    *,
    live=False,
    replay_from=None,
    case_ids=None,
    phase="initial",
    run_regressions=False,
    run_compatibility=False,
    replay_planner_from=None,
):
    if not output.is_relative_to(root / "artifacts/evidence") or not output.name.startswith(
        "M5-08"
    ):
        raise ValueError("new_M5-08_evidence_directory_required")
    if live and replay_from:
        raise ValueError("live_replay_mutually_exclusive")
    cases = load(root / "evaluation/m5-08-scenarios.json")
    if live or replay_from:
        cases = [c for c in cases if c.get("live")]
    else:
        cases = [c for c in cases if not c.get("live_only")]
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]
    if not cases:
        raise ValueError("no_selected_cases")
    output.mkdir(parents=True, exist_ok=False)
    before = protected(root)
    save(output / "hashes-before.json", before)
    save(output / "reference-manifest.json", cases)
    save(
        output / "implementation.json",
        {
            p: digest(root / p)
            for p in (
                "src/agents/orchestrator.py",
                "src/agents/orchestration_contracts.py",
                "src/agents/orchestration_projection.py",
                "src/agents/specialist_common.py",
                "src/agents/supervisor.py",
                "scripts/evaluate_m5_08_orchestration.py",
                "evaluation/m5-08-scenarios.json",
            )
        },
    )
    # Each persisted attempt is counted BEFORE transport, including failures.
    limit = 12 if phase == "initial" else 4
    previous_calls = sum(
        load(p).get("actual_calls", 0)
        for p in (root / "artifacts/evidence").glob("M5-08*/live-ledger.json")
        if load(p).get("phase") == phase
    )
    if live and previous_calls >= limit:
        raise ValueError("live_budget_exhausted")
    ledger = dict(phase=phase, previous_calls=previous_calls, actual_calls=0, limit=limit)
    if live:
        save(output / "live-ledger.json", ledger)
    print(
        f"Pinned {len(before)} protected files; hydrating BBS, {len(cases)} scenarios", flush=True
    )
    data, scopes, recovery, documents = setup(root)
    catalog = SnapshotCatalog(**data)
    accepted = [
        FinancialCalculationResponse.model_validate_json(json.dumps(v))
        for v in load(root / "artifacts/evidence/M4-03-final/executions.json")
    ]
    real_supervisor = RiskAwareSupervisor(catalog)
    active_transport = None

    def dispatch(request):
        return active_transport(request)

    gateway = SharedLLMGateway({"gemini": dispatch})
    real_planner = EvidenceAwareQueryPlanner(catalog, documents, gateway)
    real_router = AdaptiveSpecialistRouter()
    adapter = None
    if live:
        adapter, credential = create_qa_adapter(root)
        save(
            output / "credential-metadata.json",
            dict(source=credential.source, key_index=credential.key_index),
        )
    attempts, rows = [], []
    try:
        for case in cases:
            source_path = root / f"artifacts/evidence/M5-07-final-v2/planner-{case['source']}.json"
            source = PlannerResult.model_validate_json(source_path.read_text(encoding="utf-8"))
            proposal = reference_proposal(case, source)
            selector = next(iter(source.query.selectors), None)
            context = PlannerContext(
                snapshot_id=selector.snapshot_id if selector else None,
                mode="gemini",
            )
            counts = Counter()
            invocations, case_requests = [], []

            def transport(request, case=case, case_requests=case_requests, proposal=proposal):
                stage = "planning" if request.request_id.startswith("planner-") else "specialist"
                index = len(case_requests)
                stem = f"{case['id']}-{index:02d}-{stage}"
                save(output / f"request-{stem}.json", request.model_dump(mode="json"))
                attempt = dict(
                    case=case["id"],
                    stage=stage,
                    request_id=request.request_id,
                    phase=phase,
                    mode="saved_Planner_Gateway_replay"
                    if replay_planner_from and stage == "planning"
                    else "actual_Gemini"
                    if live
                    else "saved_response_replay"
                    if replay_from
                    else "mock_Gateway",
                    outcome="started",
                )
                case_requests.append(attempt)
                attempts.append(attempt)
                save(output / f"attempt-started-{stem}.json", dict(attempt))
                if live and stage == "planning" and replay_planner_from:
                    raw = load(replay_planner_from / f"gateway-{stem}.json")["response"]
                    response = LLMResponse.model_validate(
                        dict(raw, request_id=request.request_id, correlation=None)
                    )
                    attempt["mode"] = "saved_Planner_Gateway_replay"
                elif live:
                    if previous_calls + ledger["actual_calls"] >= limit:
                        raise ValueError("live_budget_exhausted")
                    ledger["actual_calls"] += 1
                    atomic_json(output / "live-ledger.json", ledger)
                    response = adapter(request)
                elif replay_from:
                    raw = load(replay_from / f"gateway-{stem}.json")["response"]
                    response = LLMResponse.model_validate(
                        dict(raw, request_id=request.request_id, correlation=None)
                    )
                else:
                    response = (
                        response_for(request, proposal)
                        if stage == "planning"
                        else mock_specialist(request, case)
                    )
                attempt.update(outcome="returned", response=response.export())
                save(output / f"gateway-{stem}.json", attempt)

                return response

            active_transport = transport

            class CountedPlanner:
                def plan(self, question, context, counts=counts, real_planner=real_planner):
                    counts["planner"] += 1
                    return real_planner.plan(question, context)

            class CountedSupervisor:
                def execute(self, plan, counts=counts, real_supervisor=real_supervisor, case=case):
                    counts["supervisor"] += 1
                    result = real_supervisor.execute(plan)
                    if case.get("injection"):
                        inject_upstream(result, case["injection"])
                    return result

            class CountedRouter:
                def route(self, counts=counts, real_router=real_router, **kwargs):
                    counts["router"] += 1
                    return real_router.route(**kwargs)

            class CountedSpecialist:
                def __init__(self, role, gateway=gateway):
                    self.role, self.agent = role, CLASSES[role](gateway)

                def analyze(self, invocations=invocations, case=case, **kwargs):
                    invocations.append(self.role)
                    if case.get("specialist_failure") == self.role:
                        raise RuntimeError("injected_transport_failure")
                    result = self.agent.analyze(**kwargs)
                    control = case.get("aggregation_control")
                    if control and result.candidates:
                        other = result.candidates[0].model_copy(deep=True)
                        other.candidate_id = "injected-random-candidate-id"
                        if control == "conflict":
                            evidence = result.supporting_evidence[0].model_copy(deep=True)
                            evidence.evidence_id = "injected-conflicting-evidence"
                            evidence.value = str(Decimal(evidence.value) + 1)
                            other.content += " [synthetic conflicting value]"
                            other.supporting_evidence_ids = [evidence.evidence_id]
                            result.supporting_evidence.append(evidence)
                        result.candidates.append(other)
                    return result

            def faulty_projection(upstream, route, case=case):
                upstream = upstream.model_copy(deep=True)
                if case["projection_fault"] == "operand":
                    upstream.evidence_bundle.facts.pop()
                else:
                    upstream.evidence_bundle.citations.clear()
                return build_specialist_context(upstream, route)

            guard = (
                patch(
                    "vietnamese_financial_multi_agent.agents.orchestrator.build_specialist_context",
                    faulty_projection,
                )
                if case.get("projection_fault")
                else nullcontext()
            )
            with guard:
                result = FinancialMultiAgentOrchestrator(
                    planner=CountedPlanner(),
                    supervisor=CountedSupervisor(),
                    router=CountedRouter(),
                    specialists={role: CountedSpecialist(role) for role in CLASSES},
                ).run(question=case["question"], context=context)
            save(output / f"result-{case['id']}.json", result.model_dump(mode="json"))
            assert OrchestrationResult.model_validate_json(result.model_dump_json()) == result
            for execution in result.specialist_executions:
                if execution.projection:
                    save(
                        output / f"projection-{case['id']}-{execution.role}.json",
                        execution.projection.model_dump(mode="json"),
                    )
            row = score(case, result, data, accepted, counts, invocations, case_requests)
            row["planner_proposal_mode"] = (
                "saved_Planner_Gateway_replay"
                if replay_planner_from
                else "fresh_Gemini"
                if live
                else "saved_Gemini_replay"
                if replay_from
                else "saved_reference_proposal_mock_Gateway"
            )
            row["source_planner_sha256"] = digest(source_path)
            rows.append(row)
            save(output / f"score-{case['id']}.json", row)
            print(
                f"{case['id']}: {'PASS' if row['pass_all'] else 'FAIL'} {result.status} roles={len(invocations)} candidates={len(result.candidates)}",
                flush=True,
            )
        if run_regressions:
            regressions(root, data, scopes, recovery, accepted, output, catalog, documents)
        if run_regressions or run_compatibility:
            checks = [dict(check, exact=True) for check in compatibility(root, output)]
            for key in ("C01", "C09", "C11"):
                folder = root / "artifacts/evidence/M5-06-offline-v2"
                old = load(folder / f"result-{key}.json")
                from vietnamese_financial_multi_agent.agents import SupervisorResult

                upstream = SupervisorResult.model_validate_json(
                    (folder / f"upstream-{key}.json").read_text(encoding="utf-8")
                )
                agent = CashFlowEarningsQualitySpecialist(
                    SharedLLMGateway(
                        {
                            "gemini": lambda req, payload=old["raw_output"]: response_for(
                                req, payload
                            )
                        }
                    )
                )
                actual = agent.analyze(question=old["question"], supervisor_result=upstream)
                assert stable(actual.model_dump(mode="json")) == stable(old)
                checks.append(dict(case=key, exact=True))
            save(output / "specialist-compatibility.json", checks)
            routing_checks = []
            for old_path in sorted(
                (root / "artifacts/evidence/M5-07-final-v2").glob("routing-*.json")
            ):
                key = old_path.stem.removeprefix("routing-")
                p = PlannerResult.model_validate_json(
                    (old_path.parent / f"planner-{key}.json").read_text(encoding="utf-8")
                )
                s_path = old_path.parent / f"supervisor-{key}.json"
                s = (
                    SupervisorResult.model_validate_json(s_path.read_text(encoding="utf-8"))
                    if s_path.exists()
                    else None
                )
                actual = AdaptiveSpecialistRouter().route(
                    question=p.question, planner_result=p, supervisor_result=s
                )
                assert actual.model_dump(mode="json") == load(old_path), key
                routing_checks.append(key)
            assert len(routing_checks) == 42
            save(output / "routing-compatibility.json", routing_checks)
    finally:
        save(output / "gateway-attempts.json", attempts)
        save(output / "rows.json", rows)
        after = protected(root)
        save(output / "hashes-after.json", after)
        assert before == after, "protected_artifact_changed"
        metrics = (
            {
                key: dict(passed=sum(r["checks"][key] for r in rows), total=len(rows))
                for key in rows[0]["checks"]
            }
            if rows
            else {}
        )
        summary = dict(
            mode=(
                "partial_live_saved_Planner"
                if replay_planner_from
                else "actual_Gemini_full_pipeline"
            )
            if live
            else "saved_response_replay"
            if replay_from
            else "real_BBS_mock_Gateway",
            phase=phase,
            scenarios=len(rows),
            passed=sum(r["pass_all"] for r in rows),
            planned_scenarios=len(cases),
            actual_calls=ledger["actual_calls"] if live else 0,
            gateway_calls=len(attempts),
            metrics=metrics,
            protected_hashes=len(before),
            protected_unchanged=before == after,
            tokens={
                k: sum(
                    (a.get("response", {}).get("usage", {}).get(k) or 0)
                    for a in attempts
                    if a["mode"] == "actual_Gemini"
                )
                for k in ("input_tokens", "output_tokens", "total_tokens")
            },
            latency_ms=dict(
                median=median(r["latency_ms"] for r in rows) if rows else None,
                max=max((r["latency_ms"] for r in rows), default=None),
            ),
            stage_latency_ms={
                stage: dict(
                    median=median(r["stage_latency_ms"].get(stage, 0) for r in rows),
                    total=sum(r["stage_latency_ms"].get(stage, 0) for r in rows),
                )
                for stage in (rows[0]["stage_latency_ms"] if rows else [])
            },
            financial_fact_verified=False,
        )
        save(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--replay-from", type=Path)
    parser.add_argument("--case-ids", nargs="+")
    parser.add_argument("--phase", choices=("initial", "targeted"), default="initial")
    parser.add_argument("--regressions", action="store_true")
    parser.add_argument("--compatibility", action="store_true")
    parser.add_argument("--replay-planner-from", type=Path)
    args = parser.parse_args()
    summary = evaluate(
        Path.cwd().resolve(),
        args.output.resolve(),
        live=args.allow_live,
        replay_from=args.replay_from.resolve() if args.replay_from else None,
        case_ids=args.case_ids,
        phase=args.phase,
        run_regressions=args.regressions,
        run_compatibility=args.compatibility,
        replay_planner_from=args.replay_planner_from.resolve()
        if args.replay_planner_from
        else None,
    )
    if summary["passed"] != summary["planned_scenarios"]:
        raise SystemExit(1)
