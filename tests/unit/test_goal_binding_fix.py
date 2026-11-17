"""Bounded synthetic controls; live saved-trace evidence is recorded separately."""

from copy import deepcopy

from vietnamese_financial_multi_agent.agents.evidence_coordination import (
    SelectionDemand,
    content_digest,
    select_observations,
)
from vietnamese_financial_multi_agent.agents.lite_orchestrator import inventory
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification.evidence_obligations import current_goal_support
from vietnamese_financial_multi_agent.verification.ledger import build_verified_claim
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import (
    LiteVerificationRuntime,
    decide,
)

from .test_evidence_obligations import gateway_with_goals, selection_case
from .test_multihop_reasoning import reasoning_case


def mismatched_period_case():
    catalog, batch, context = selection_case()
    claim = batch.claims[0]
    current = deepcopy(context["task_results"]["T1"])
    selection = current["coordination"]["selection"]
    selected, record = select_observations(
        SelectionDemand.model_validate(
            dict(
                selection["selection"],
                comparator="min",
                periods=[p for p in selection["selection"]["periods"] if p != claim.period],
            )
        ),
        selection["domain"],
        inventory(
            catalog,
            batch.context.model_copy(
                update=dict(
                    company_id=claim.company_id,
                    document_id=claim.document_id,
                    snapshot_id=claim.snapshot_id,
                    period=None,
                )
            ),
        ),
    )
    assert selected[0]["context"]["period"] != claim.period
    root = deepcopy(current)
    root.update(selected_observations=selected, coordination=dict(selection=record, joins=[]))
    root["digest"] = content_digest({k: v for k, v in root.items() if k != "digest"})
    child = dict(
        current,
        handle="result:T2:v1",
        task_id="T2",
        coordination={},
        input_results=[{k: root[k] for k in ("handle", "task_id", "revision", "digest")}],
    )
    child["digest"] = content_digest({k: v for k, v in child.items() if k != "digest"})
    context["task_results"] = dict(T1=root, T2=child)
    context["tasks"]["T2"] = dict(depends_on=["T1"])
    claim.provenance.origins[0].execution_id = "T2"
    context["requirements"] = [
        dict(requirement_id="valid", text=f"Doanh thu thuần năm {claim.period}"),
        dict(requirement_id="selected", text="Doanh thu thuần cùng năm đã chọn"),
        dict(requirement_id="wrong_item", text=f"Lợi nhuận sau thuế năm {claim.period}"),
        dict(requirement_id="wrong_year", text=f"Doanh thu thuần năm {int(claim.period) - 2}"),
    ]
    ids = [r["requirement_id"] for r in context["requirements"]]
    context["candidate_requirements"] = {claim.candidate_id: ids}
    runtime = LiteVerificationRuntime(catalog, gateway_with_goals(ids), integration_v2=True)
    history = runtime.verify(batch, integration_context=context)[0]
    return context, history, runtime


def test_supported_truth_does_not_grant_wrong_indicator_period_or_selection(tmp_path):
    context, history, runtime = mismatched_period_case()
    assert history.outcome.final.decision == "ACCEPT"
    assert history.proof.semantic.verdict == "SUPPORTED"
    assert history.proof.semantic.supported_requirement_ids == ["valid"]
    assert list(runtime.summary["supported_requirements"].values()) == [["valid"]]
    missing = runtime.summary["feedback"][0]["issues"][-1]
    assert set(missing["requirement_ids"]) == {"selected", "wrong_item", "wrong_year"}
    repository = VerifiedClaimRepository(tmp_path)
    assert repository.admit(history).status == "stored"
    entry = VerifiedClaimRepository(tmp_path).list_all()[0]
    assert build_verified_claim(entry.history) == entry
    assert current_goal_support(entry, history.proof.batch.question, context["requirements"]) == [
        "valid"
    ]
    _, m7 = compose_lite(
        FinancialQARequest(question=history.proof.batch.question, allow_gateway=False),
        [entry],
        coverage_context=dict(
            requirements=context["requirements"],
            verified_requirements={entry.identity.verified_claim_id: ["valid"]},
        ),
    )
    assert m7["released_claims"] == [entry.identity.verified_claim_id]
    assert [r["status"] for r in m7["coverage"]["requirements"]] == [
        "satisfied",
        "unverified",
        "unverified",
        "unverified",
    ]


def test_legacy_raw_binding_is_filtered_without_mutating_saved_truth():
    context, history, _ = mismatched_period_case()
    legacy = history.model_copy(deep=True)
    legacy.proof.semantic.supported_requirement_ids = ["selected", "wrong_item"]
    legacy.outcome.attempts = [decide(legacy.proof)]
    entry = build_verified_claim(legacy)
    saved = entry.model_dump_json()
    assert current_goal_support(entry, legacy.proof.batch.question, context["requirements"]) == []
    fields, m7 = compose_lite(
        FinancialQARequest(question=legacy.proof.batch.question, allow_gateway=False),
        [entry],
        coverage_context=dict(
            requirements=context["requirements"],
            verified_requirements={
                entry.identity.verified_claim_id: current_goal_support(
                    entry, legacy.proof.batch.question, context["requirements"]
                )
            },
        ),
    )
    assert not fields["citations"] and not m7["released_claims"]
    assert entry.decision.decision == "ACCEPT" and entry.model_dump_json() == saved


def test_correct_calculation_keeps_only_goal_with_matching_operator_order_and_unit():
    data, batch = reasoning_case(operator="ratio")
    requirements = [
        dict(requirement_id="valid", text="Tính lợi nhuận gộp chia doanh thu thuần"),
        dict(requirement_id="wrong_order", text="Tính doanh thu thuần chia lợi nhuận gộp"),
        dict(requirement_id="wrong_operator", text="Tính lợi nhuận gộp trừ doanh thu thuần"),
        dict(
            requirement_id="wrong_unit",
            text="Tính lợi nhuận gộp chia doanh thu thuần (%)",
        ),
    ]
    ids = [r["requirement_id"] for r in requirements]
    runtime = LiteVerificationRuntime(
        SnapshotCatalog(**data), gateway_with_goals(ids), integration_v2=True
    )
    history = runtime.verify(
        batch,
        integration_context=dict(
            adaptive_coordinator=True,
            requirements=requirements,
            candidate_requirements={batch.claims[0].candidate_id: ids},
        ),
    )[0]
    assert history.outcome.final.decision == "ACCEPT"
    assert history.proof.semantic.supported_requirement_ids == ["valid"]
