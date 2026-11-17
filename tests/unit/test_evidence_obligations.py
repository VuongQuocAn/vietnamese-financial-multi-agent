"""Targeted synthetic controls; these do not certify financial accuracy."""

import json
from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.agents.evidence_coordination import (
    SelectionDemand,
    content_digest,
    join_observations,
    observation,
    select_observations,
)
from vietnamese_financial_multi_agent.agents.lite_orchestrator import inventory
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
from vietnamese_financial_multi_agent.core.llm_contracts import parse_json_output
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.evidence_obligations import current_goal_support
from vietnamese_financial_multi_agent.verification.ledger import (
    LedgerAdmissionError,
    build_verified_claim,
)
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_m6_lite import semantic_gateway


def selection_case():
    data = fixture("revenue_yoy")
    catalog = SnapshotCatalog(**data)
    batch = batch_for(data)
    claim = batch.claims[0]
    from vietnamese_financial_multi_agent.agents.orchestration_contracts import CandidateOrigin

    tid = "T1"
    claim.provenance.origins = [
        CandidateOrigin(
            role="profitability",
            execution_id=tid,
            candidate_id=claim.candidate_id,
            original_content=claim.content,
            supporting_evidence=claim.supporting_evidence,
        )
    ]
    tools = LiteVerificationRuntime(catalog).validator._retrieval
    from vietnamese_financial_multi_agent.tools.financial_retrieval import GetFinancialFactRequest

    rows = [
        observation(
            tools.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=f.document_id,
                    snapshot_id=f.snapshot_id,
                    local_observation_id=f.local_observation_id,
                )
            ).matches[0]
        )
        for f in data["facts"]
    ]
    sources = inventory(
        catalog,
        PlannerContext(
            company_id=claim.company_id,
            document_id=claim.document_id,
            snapshot_id=claim.snapshot_id,
        ),
    )
    selected, selection = select_observations(
        SelectionDemand(
            item=rows[0]["item"], periods=[r["context"]["period"] for r in rows], comparator="max"
        ),
        rows,
        sources,
    )
    assert selected[0]["reference"] == claim.supporting_evidence[0].reference.model_dump(
        mode="json"
    )
    record = dict(
        handle=f"result:{tid}:v1",
        task_id=tid,
        revision=1,
        input_results=[],
        selected_observations=selected,
        coordination=dict(selection=selection, joins=[]),
    )
    record["digest"] = content_digest(record)
    context = dict(
        adaptive_coordinator=True,
        tasks={tid: dict(depends_on=[])},
        task_results={tid: record},
        requirements=[dict(requirement_id="G1", text="Chọn năm doanh thu cao hơn")],
        candidate_requirements={claim.candidate_id: ["G1"]},
    )
    return catalog, batch, context


def gateway_with_goals(goals):
    gateway = semantic_gateway()
    generate = gateway.generate.side_effect

    def assess(request):
        response = generate(request)
        payload = response.output.payload
        for verdict in payload["verdicts"]:
            verdict.update(supported_requirement_ids=goals, issues=[])
        return response.model_copy(update=dict(output=parse_json_output(json.dumps(payload))))

    gateway.generate.side_effect = assess
    return gateway


def test_selection_binding_roundtrip_and_stale_goal_rejected(tmp_path):
    catalog, batch, context = selection_case()
    runtime = LiteVerificationRuntime(catalog, gateway_with_goals(["G1"]), integration_v2=True)
    history = runtime.verify(batch, integration_context=context)[0]
    assert history.outcome.final.decision == "ACCEPT"
    assert runtime.summary["supported_requirements"] == {batch.claims[0].candidate_id: ["G1"]}
    repository = VerifiedClaimRepository(tmp_path)
    assert repository.admit(history).status == "stored"
    entry = VerifiedClaimRepository(tmp_path).list_all()[0]
    assert entry.version == "verified_claim_v2" and entry.history == history
    assert current_goal_support(entry, batch.question, context["requirements"]) == ["G1"]
    assert current_goal_support(entry, "changed", context["requirements"]) == []
    changed_goals = deepcopy(context["requirements"])
    changed_goals[0]["text"] = "different goal"
    assert current_goal_support(entry, batch.question, changed_goals) == []
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite

    key = entry.identity.verified_claim_id
    fields, trace = compose_lite(
        FinancialQARequest(question=batch.question, allow_gateway=False),
        [entry],
        coverage_context=dict(
            requirements=context["requirements"]
            + [dict(requirement_id="G2", text="Missing evidence")],
            verified_requirements={key: ["G1"]},
        ),
    )
    assert trace["released_claims"] == [key] and fields["citations"]
    assert (
        not trace["coverage"]["complete"]
        and not trace["coverage"]["requirements"][1]["verified_claim_ids"]
    )
    for field in ("text", "period", "requested_unit"):
        changed = history.model_copy(deep=True)
        changed.proof.goal_context["local_requirements"][0][field] = "changed"
        with pytest.raises(LedgerAdmissionError):
            build_verified_claim(changed)


def test_truth_is_independent_of_goal_support_and_feedback_is_scoped():
    catalog, batch, context = selection_case()
    runtime = LiteVerificationRuntime(catalog, gateway_with_goals([]), integration_v2=True)
    history = runtime.verify(batch, integration_context=context)[0]
    assert history.outcome.final.decision == "ACCEPT"
    feedback = runtime.summary["feedback"][0]
    assert feedback["supported_requirement_ids"] == []
    assert feedback["task_ids"] and feedback["issues"][0]["check"] == "goal_support"
    assert (
        feedback["issues"][0]["input_refs"] and feedback["issues"][0]["action"] == "revise_binding"
    )

    from .test_multihop_reasoning import reasoning_case

    data, calculation_batch = reasoning_case()
    candidate = calculation_batch.claims[0]
    context = dict(
        adaptive_coordinator=True,
        requirements=[dict(requirement_id="G", text="Another formula")],
        candidate_requirements={candidate.candidate_id: ["G"]},
    )
    arithmetic = LiteVerificationRuntime(
        SnapshotCatalog(**data), gateway_with_goals([]), integration_v2=True
    )
    assert (
        arithmetic.verify(calculation_batch, integration_context=context)[0].outcome.final.decision
        == "ACCEPT"
    )
    assert arithmetic.summary["supported_requirements"][candidate.candidate_id] == []
    bad_formula_gateway = gateway_with_goals([])
    generate = bad_formula_gateway.generate.side_effect

    def reject(request):
        response = generate(request)
        payload = response.output.payload
        payload["verdicts"][0].update(
            verdict="UNSUPPORTED",
            reason="Wrong financial formula",
            issues=[dict(check="formula", reason_code="formula_goal_mismatch", input_refs=[])],
        )
        return response.model_copy(update=dict(output=parse_json_output(json.dumps(payload))))

    bad_formula_gateway.generate.side_effect = reject
    wrong = LiteVerificationRuntime(
        SnapshotCatalog(**data), bad_formula_gateway, integration_v2=True
    )
    assert (
        wrong.verify(calculation_batch, integration_context=context)[0].outcome.final.decision
        == "ABSTAIN"
    )
    assert any(i["check"] == "formula" for i in wrong.summary["feedback"][0]["issues"])


def test_selection_and_join_replay_block_tampered_sources_domain_and_pairs():
    catalog, batch, original = selection_case()
    tid = next(iter(original["task_results"]))
    parent = original["task_results"][tid]
    parent["coordination"]["joins"] = [join_observations(parent, parent["selected_observations"])]
    # Join points to a different input task, as in a real consumer closure.
    previous = deepcopy(parent)
    previous["handle"] = "result:parent:v1"
    previous["task_id"] = "parent"
    previous["coordination"]["joins"] = []
    previous["digest"] = content_digest({k: v for k, v in previous.items() if k != "digest"})
    parent["coordination"]["joins"] = [join_observations(previous, parent["selected_observations"])]
    parent["input_results"] = [
        {k: previous[k] for k in ("handle", "task_id", "revision", "digest")}
    ]
    parent["digest"] = content_digest({k: v for k, v in parent.items() if k != "digest"})
    original["tasks"][tid]["depends_on"] = ["parent"]
    original["tasks"]["parent"] = dict(depends_on=[])
    original["task_results"]["parent"] = previous
    positive = LiteVerificationRuntime(catalog, gateway_with_goals(["G1"]), integration_v2=True)
    assert (
        positive.verify(batch, integration_context=original)[0].outcome.final.decision == "ACCEPT"
    )
    for failure in ("domain", "source", "pairs"):
        context = deepcopy(original)
        record = context["task_results"][tid]
        if failure == "domain":
            record["coordination"]["selection"]["domain"].pop()
        elif failure == "source":
            record["selected_observations"][0]["value"] = "999"
        else:
            record["coordination"]["joins"][0]["pairs"] = []
        record["digest"] = content_digest({k: v for k, v in record.items() if k != "digest"})
        runtime = LiteVerificationRuntime(catalog, gateway_with_goals(["G1"]), integration_v2=True)
        assert (
            runtime.verify(batch, integration_context=context)[0].outcome.final.decision != "ACCEPT"
        )
        assert runtime.provider_metadata == []
        assert runtime.summary["feedback"][0]["issues"]
