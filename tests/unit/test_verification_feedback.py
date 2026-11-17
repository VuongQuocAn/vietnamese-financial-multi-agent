"""Three bounded controls; synthetic fixtures are not research accuracy evidence."""

import json
from copy import deepcopy
from types import SimpleNamespace

from vietnamese_financial_multi_agent.agents.lite_orchestrator import LiteTask
from vietnamese_financial_multi_agent.agents.specialist_common import SpecialistResult
from vietnamese_financial_multi_agent.agents.verification_feedback import (
    repair_frontier,
    repair_once,
)
from vietnamese_financial_multi_agent.verification.adapter import to_verification_input
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_evidence_obligations import gateway_with_goals
from .test_v2_integration import setup_engine


def owned_goal_gateway():
    from vietnamese_financial_multi_agent.core.llm_contracts import parse_json_output

    gateway = gateway_with_goals([])
    generate = gateway.generate.side_effect

    def assess(request):
        response = generate(request)
        rows = {r["claim_id"]: r for r in json.loads(request.messages[-1].content)}
        payload = response.output.payload
        for verdict in payload["verdicts"]:
            verdict["supported_requirement_ids"] = [
                r["requirement_id"] for r in rows[verdict["claim_id"]]["local_requirements"]
            ]
        return response.model_copy(update=dict(output=parse_json_output(json.dumps(payload))))

    gateway.generate.side_effect = assess
    return gateway


def test_feedback_routes_source_selection_join_formula_and_binding_to_branch():
    context = dict(
        tasks={
            "T1": dict(depends_on=[]),
            "T2": dict(depends_on=["T1"]),
            "T3": dict(depends_on=[]),
        }
    )
    for check, action in [
        ("source", "retrieve_evidence"),
        ("selection", "revise_selection"),
        ("entity_join", "resolve_entity"),
        ("numeric", "revise_formula"),
        ("goal_support", "revise_binding"),
    ]:
        proof = SimpleNamespace(
            validation=SimpleNamespace(
                claims=[
                    SimpleNamespace(
                        checks=[
                            SimpleNamespace(
                                check_id=check, status="fail", expected=dict(task_id="T1")
                            )
                        ]
                    )
                ]
            )
        )
        history = SimpleNamespace(
            outcome=SimpleNamespace(final=SimpleNamespace(candidate_id="C")), proof=proof
        )
        issue = dict(
            check=check, action=action, repairable=True, input_refs=["E"], requirement_ids=["G"]
        )
        feedback = [
            dict(
                candidate_id="C",
                task_ids=["T2"],
                issues=[issue],
                decision="INVESTIGATE",
                supported_requirement_ids=[],
            )
        ]
        roots, affected, routed = repair_frontier(context, feedback, [history])
        assert roots == {"T1"} and affected == {"T1", "T2"}
        assert routed[0]["input_refs"] == ["E"] and routed[0]["action"] == action
        issue["repairable"] = False
        assert not repair_frontier(context, feedback, [history])[1]
        issue["repairable"] = True
        feedback.append(
            dict(
                candidate_id="valid",
                task_ids=["T2"],
                decision="ACCEPT",
                supported_requirement_ids=["G"],
                issues=[],
            )
        )
        assert not repair_frontier(context, feedback, [history])[1]

    context["tasks"]["T1"]["requirement_ids"] = ["G1"]
    context["tasks"]["T2"]["requirement_ids"] = ["G2"]
    binding_feedback = [
        dict(
            candidate_id="scalar",
            task_ids=["T1", "T2"],
            decision="ACCEPT",
            supported_requirement_ids=["G1"],
            issues=[
                dict(
                    check="goal_support",
                    action="revise_binding",
                    repairable=True,
                    requirement_ids=["G2"],
                    input_refs=["E"],
                )
            ],
        )
    ]
    assert repair_frontier(context, binding_feedback, [])[1] == {"T2"}


def test_repair_reuses_independent_accept_reverifies_new_version_and_releases(tmp_path):
    catalog, context, engine, _ = setup_engine()
    engine.adaptive_coordinator = True
    plan = engine.supervisor.plan.return_value[0]
    plan.tasks.append(
        LiteTask(
            task_id="T3",
            specialist="profitability",
            objective="dependent",
            requirement_ids=["R1"],
            depends_on=["T1"],
        )
    )
    original = engine._specialist
    calls = []

    def specialize(task, *args):
        calls.append(task.task_id)
        if task.task_id == "T3":
            return SpecialistResult(
                question="dependent", upstream_status="partial", status="partial"
            )
        result = original(task, *args)
        if task.task_id == "T1" and not engine.workspace.repair_used:
            result.candidates[0].content = "Unsupported scalar 999999999."
        return result

    engine._specialist = specialize
    output = engine.run(question="probe", context=context)
    runtime = LiteVerificationRuntime(catalog, owned_goal_gateway(), integration_v2=True)
    histories = runtime.verify(
        to_verification_input(output), integration_context=output.integration_context
    )
    independent = next(h for h in histories if h.proof.goal_context["owner_task_ids"] == ["T2"])
    assert independent.outcome.final.decision == "ACCEPT"
    before = deepcopy(output.integration_context)
    calls.clear()
    repaired, current, trace = repair_once(engine, output, runtime, histories)
    assert calls == ["T1", "T3"] and engine.supervisor.plan.call_count == 1
    assert repaired.integration_context["task_results"]["T2"] == before["task_results"]["T2"]
    assert repaired.integration_context["task_results"]["T1"]["revision"] == 2
    assert repaired.integration_context["tasks"]["T3"]["revision"] == 2
    assert (
        next(
            h
            for h in current
            if h.outcome.final.candidate_id == independent.outcome.final.candidate_id
        )
        is independent
    )
    assert trace["reused_candidate_ids"] == [independent.outcome.final.candidate_id]
    assert trace["reverified_candidate_ids"] and all(
        cid.endswith(":r2") for cid in trace["reverified_candidate_ids"]
    )
    assert all(h.outcome.final.decision == "ACCEPT" for h in current)
    assert trace["candidate_lineage"] and trace["before"] == before
    repository = VerifiedClaimRepository(tmp_path)
    assert all(r.status == "stored" for r in repository.admit_many(current))
    entries = VerifiedClaimRepository(tmp_path).list_all()
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
    from vietnamese_financial_multi_agent.verification.evidence_obligations import (
        current_goal_support,
    )

    fields, m7 = compose_lite(
        FinancialQARequest(question="probe", allow_gateway=False),
        entries,
        coverage_context=dict(
            requirements=repaired.integration_context["requirements"],
            verified_requirements={
                e.identity.verified_claim_id: current_goal_support(
                    e, "probe", repaired.integration_context["requirements"]
                )
                for e in entries
            },
        ),
    )
    assert fields["citations"] and m7["coverage"]["complete"]
    assert (
        repair_once(engine, repaired, runtime, current)[2]["stop_reason"] == "repair_limit_reached"
    )
    assert calls == ["T1", "T3"]


def test_identical_repair_stops_without_second_m6_and_budget_preserves_partial():
    catalog, context, engine, _ = setup_engine()
    engine.adaptive_coordinator = True
    output = engine.run(question="probe", context=context)
    runtime = LiteVerificationRuntime(catalog, gateway_with_goals([]), integration_v2=True)
    histories = runtime.verify(
        to_verification_input(output), integration_context=output.integration_context
    )
    engine.gateway = SimpleNamespace(events=[], max_calls=0, deadline=10**12, failure_category=None)
    assert (
        repair_once(engine, output, runtime, histories)[2]["stop_reason"]
        == "repair_budget_unavailable"
    )
    assert not engine.workspace.repair_used
    engine.gateway = None
    old_calls = len(runtime.provider_metadata)
    current, kept, trace = repair_once(engine, output, runtime, histories)
    assert current is output and kept is histories
    assert trace["stop_reason"] == "no_proposal_progress" and trace["rounds"] == 1
    assert len(runtime.provider_metadata) == old_calls
    assert repair_once(engine, current, runtime, kept)[2]["stop_reason"] == "repair_limit_reached"
    # A changed but still invalid proposal retains the original partial frontier.
    _, _, other, _ = setup_engine()
    other.adaptive_coordinator = True
    original = other._specialist

    def worsen(task, *args):
        result = original(task, *args)
        if other.workspace.repair_used:
            for claim in result.candidates:
                claim.content = "Unsupported scalar 999999999."
        return result

    other._specialist = worsen
    first = other.run(question="probe", context=context)
    verifier = LiteVerificationRuntime(catalog, gateway_with_goals([]), integration_v2=True)
    first_histories = verifier.verify(
        to_verification_input(first), integration_context=first.integration_context
    )
    returned, decisions, attempted = repair_once(other, first, verifier, first_histories)
    assert returned is first and decisions is first_histories
    assert attempted["stop_reason"] == "no_verified_progress"
    assert attempted["retained_original_frontier"] and attempted["m6_after"]
