"""Synthetic contract controls; real-PDF evaluation is recorded separately."""

from copy import deepcopy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.agents.specialist_common import ReasoningProof
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.financial_calculator import (
    DynamicOperation,
    FinancialCalculator,
    execute_dynamic,
    render_dynamic,
)
from vietnamese_financial_multi_agent.verification import (
    BoundedVerificationLoop,
    DeterministicFinancialValidator,
    EvidenceCritic,
    FinancialLogicCritic,
    VerificationHistory,
    VerificationProofContext,
    VerifiedClaimRepository,
)
from vietnamese_financial_multi_agent.verification.judge import VerificationJudge

from .test_financial_validators import batch_for
from .test_m4_execution import fixture


def reasoning_case(*, formula="gross_margin", operator="greater"):
    data = fixture(formula)
    batch = batch_for(data)
    claim = batch.claims[0]
    sources, premises = [], []
    for index, fact in enumerate(data["facts"][:2]):
        local = dict(data, facts=[fact, *[f for f in data["facts"] if f != fact]])
        candidate = batch_for(local).claims[0]
        source = candidate.supporting_evidence[0].model_copy(deep=True)
        source.evidence_id = f"E{index + 1}"
        sources.append(source)
        premises.append(candidate.content)
    operations = [
        DynamicOperation(
            operation_id="compare",
            operator=operator,
            inputs=[s.evidence_id for s in sources],
            period_relation="across_periods" if formula == "revenue_yoy" else "same",
        )
    ]
    computation = FinancialCalculator(SnapshotCatalog(**data)).calculate_dynamic(
        {s.evidence_id: s.reference for s in sources},
        operations,
    )
    claim.kind = "supported_interpretation"
    claim.supporting_evidence = sources
    claim.supporting_evidence_ids = [s.evidence_id for s in sources]
    claim.fact_references = [s.reference for s in sources]
    claim.provenance.supporting_references = claim.fact_references
    claim.citations = list({c.model_dump_json(): c for s in sources for c in s.citations}.values())
    claim.analysis_premises = premises
    claim.reasoning = ReasoningProof(
        claim_type="derived_fact", goal="Compare grounded facts", calculation=computation
    )
    claim.content = render_dynamic(computation, {s.evidence_id: s.label for s in sources})
    return data, batch


def verify(data, batch):
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    evidence = EvidenceCritic(catalog).assess(batch, validation)
    logic = FinancialLogicCritic().assess(batch, validation, evidence)
    decision = VerificationJudge().decide(batch, validation, evidence, logic)
    return validation, evidence, logic, decision


@pytest.mark.parametrize(
    "operator",
    [
        "greater",
        "less",
        "equal",
        "subtract",
        "add",
        "sum",
        "mean",
        "ratio",
        "relative_difference",
        "percentage_change",
    ],
)
def test_dynamic_arithmetic_is_independently_verified_and_replayable(tmp_path, operator):
    data, batch = reasoning_case(operator=operator)
    validation, evidence, logic, decision = verify(data, batch)
    assert decision.claims[0].decision == "ACCEPT", decision.model_dump()
    assert evidence.claims[0].trace.llm.calls == logic.claims[0].trace.llm.calls == 0
    history = VerificationHistory(
        contexts=[
            VerificationProofContext(
                batch=batch, validation=validation, evidence=evidence, logic=logic
            )
        ],
        outcome=BoundedVerificationLoop().start(
            batch, validation, evidence, logic, candidate_id="C1"
        ),
    )
    repository = VerifiedClaimRepository(tmp_path)
    admitted = repository.admit(history)
    assert admitted.status == "stored"
    assert VerifiedClaimRepository(tmp_path).get(admitted.verified_claim_id).history == history


@pytest.mark.parametrize(
    "mutation",
    [
        "result",
        "value",
        "period",
        "snapshot",
        "source",
        "unit",
        "citation",
        "content",
        "assumption",
        "conditional",
    ],
)
def test_invalid_reasoning_cannot_promote_even_when_judge_says_pass(mutation):
    data, batch = reasoning_case()
    claim = batch.claims[0]
    if mutation == "result":
        claim.reasoning.calculation.steps[0].result = "999"
    elif mutation == "value":
        claim.reasoning.calculation.operands["E1"].value = "999"
    elif mutation == "period":
        claim.reasoning.calculation.operands["E1"].period = "1999"
    elif mutation == "snapshot":
        claim.snapshot_id = "wrong"
    elif mutation == "source":
        claim.fact_references[0].observation = claim.fact_references[0].observation.model_copy(
            update={"local_id": "invented"}
        )
    elif mutation == "unit":
        claim.reasoning.calculation.operands["E1"].unit = "USD"
    elif mutation == "citation":
        claim.citations[0].pdf_page += 99
    elif mutation == "content":
        claim.content += " Nguyên nhân do doanh nghiệp bán tài sản."
    elif mutation == "assumption":
        claim.reasoning.assumptions = ["Unproven event"]
    else:
        claim.reasoning.claim_type = "conditional_inference"
    assert verify(data, batch)[-1].claims[0].decision != "ACCEPT"


def test_multi_period_explicit_dependency_and_failed_branch_isolation():
    data, batch = reasoning_case(formula="revenue_yoy", operator="percentage_change")
    good = batch.claims[0].model_copy(deep=True)
    bad = good.model_copy(deep=True)
    bad.candidate_id = bad.provenance.m5_candidate_id = "bad"
    bad.reasoning.calculation.steps[0].result = "999"
    batch.claims = [good, bad]
    decisions = verify(data, batch)[-1].claims
    assert decisions[0].decision == "ACCEPT", decisions[0].model_dump()
    assert decisions[1].decision != "ACCEPT"


def test_dynamic_graph_zero_units_invalid_dependency_and_multihop():
    _, batch = reasoning_case(operator="ratio")
    operands = batch.claims[0].reasoning.calculation.operands
    operations = [
        DynamicOperation(operation_id="ratio", operator="ratio", inputs=["E1", "E2"]),
        DynamicOperation(operation_id="scaled", operator="multiply", inputs=["ratio", "E2"]),
    ]
    output = execute_dynamic(operands, operations)
    assert Decimal(output.steps[-1].result).quantize(Decimal("0.0001")) == Decimal(
        operands["E1"].value
    )
    for mutation, reason in [
        ("zero", "zero_denominator"),
        ("unit", "unit_mismatch"),
        ("dependency", "dependency_invalid"),
        ("period", "period_mismatch"),
    ]:
        local, ops = deepcopy(operands), deepcopy(operations)
        if mutation == "zero":
            local["E2"].value = "0"
        elif mutation == "unit":
            local["E2"].unit = "USD"
        elif mutation == "dependency":
            ops[0].inputs[0] = "__import__('os')"
        else:
            local["E2"].period = "1999"
        with pytest.raises(ValueError, match=reason):
            execute_dynamic(local, ops)


def test_unbound_number_and_unsupported_cause_remain_unverified():
    data, batch = reasoning_case()
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.content = "Doanh thu tăng 999% vì bán tài sản."
    validation, _, _, decision = verify(data, batch)
    assert any(c.reason_code == "reasoning_unbound_number" for c in validation.claims[0].checks)
    assert decision.claims[0].decision != "ACCEPT"


@pytest.mark.parametrize("formula", ["gross_margin", "revenue_yoy"])
def test_composer_renderer_firewall_preserve_calculation_and_hide_internal_metadata(
    tmp_path, formula
):
    from vietnamese_financial_multi_agent.outputs import CitationRenderer, VietnameseQAComposer
    from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
    from vietnamese_financial_multi_agent.outputs.qa_contracts import (
        QARequirement,
        VietnameseQARequest,
    )
    from vietnamese_financial_multi_agent.verification import VerifiedClaimLedger

    data, batch = reasoning_case(formula=formula, operator="subtract")
    claim = batch.claims[0]
    batch.caveats.extend(
        ["PLANNER_TASK: private task", "candidate_pending_M6", "INTERNAL_OPERATION_7"]
    )
    validation, evidence, logic, _ = verify(data, batch)
    history = VerificationHistory(
        contexts=[
            VerificationProofContext(
                batch=batch, validation=validation, evidence=evidence, logic=logic
            )
        ],
        outcome=BoundedVerificationLoop().start(
            batch, validation, evidence, logic, candidate_id="C1"
        ),
    )
    repository = VerifiedClaimRepository(tmp_path)
    assert repository.admit(history).status == "stored"
    ledger = VerifiedClaimLedger(repository)
    request = VietnameseQARequest(
        question="Đối chiếu các dữ kiện được giao.",
        company_id=claim.company_id,
        document_id=claim.document_id,
        snapshot_id=claim.snapshot_id,
        period=claim.period,
        answer_requirements=[
            QARequirement(
                requirement_id="calculation",
                text="Đối chiếu",
                kind="fact",
                interpretation=True,
                interpretation_topic="dynamic_calculation",
                target_id=claim.supporting_evidence[0].canonical_item_id,
                required_indicators=[s.canonical_item_id for s in claim.supporting_evidence],
            )
        ],
    )
    response = VietnameseQAComposer(ledger).compose(request)
    assert response.status == "answered", response.model_dump()
    rendered = CitationRenderer().render_qa(response)
    result = InformationFirewall(ledger).evaluate_qa(
        request=request, response=response, rendered=rendered
    )
    assert result.decision in {"ALLOW", "ALLOW_WITH_CAVEAT"}, result.model_dump()
    assert claim.content in rendered.rendered_text
    assert rendered.references
    assert all(
        token not in rendered.rendered_text
        for token in ["PLANNER_TASK", "candidate_pending_M6", "INTERNAL_OPERATION_7"]
    )
    assert "PLANNER_TASK: private task" in rendered.caveats


def test_specialist_creates_public_reasoning_and_separate_calculation_candidates():
    from vietnamese_financial_multi_agent.agents.profitability_specialist import (
        ProfitabilityProposal,
    )
    from vietnamese_financial_multi_agent.agents.specialist_common import (
        SpecialistResult,
        generate_candidates,
    )
    from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity

    from .test_financial_qa import gateway_for

    _, batch = reasoning_case()
    result = SpecialistResult(
        question="Đối chiếu các chỉ tiêu",
        upstream_status="completed",
        supporting_evidence=batch.claims[0].supporting_evidence,
    )
    payload = dict(
        claims=[],
        missing_information=[],
        analyses=[
            dict(
                statement="Quan hệ đối chiếu là một dấu hiệu cần xem xét trong phạm vi kỳ báo cáo.",
                evidence_ids=["E1", "E2"],
                goal="Đối chiếu",
                operations=[
                    dict(operation_id="comparison", operator="greater", inputs=["E1", "E2"])
                ],
                limitations=["Một quan hệ không đủ đánh giá toàn diện."],
            )
        ],
    )
    generate_candidates(
        gateway=gateway_for(payload, []),
        model=ModelIdentity(provider="gemini", model="test"),
        result=result,
        prompt={},
        proposal_type=ProfitabilityProposal,
        render=lambda proposal, evidence: "unused",
        prefix="test",
    )
    assert {c.reasoning.claim_type for c in result.candidates if c.reasoning} == {
        "derived_fact",
        "reasoned_conclusion",
    }
    assert all(not c.financial_fact_verified for c in result.candidates)


@pytest.mark.parametrize("causal", [False, True])
def test_reasoned_interpretation_requires_both_critics_and_causal_evidence(causal):
    from .test_evidence_critic import semantic_gateway
    from .test_financial_logic_critic import gateway

    data, batch = reasoning_case()
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.content = (
        "Đây là nguyên nhân dẫn đến lợi nhuận cải thiện."
        if causal
        else "Quan hệ đối chiếu cho phép xem xét mức độ chênh lệch trong kỳ, với giới hạn của hai chỉ tiêu."
    )
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)

    def supported(payload):
        for assertion in payload["assertions"]:
            assertion.update(
                status="supported", reason="direct_support", missing=[], evidence_ids=["E1", "E2"]
            )

    evidence = EvidenceCritic(catalog, semantic_gateway(supported)).assess(batch, validation)
    logic = FinancialLogicCritic(gateway(status="consistent")).assess(batch, validation, evidence)
    decision = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert (decision.decision == "ACCEPT") is not causal, decision.model_dump()


def test_source_conflict_is_not_calculable():
    data, batch = reasoning_case()
    fact = data["facts"][0].model_copy(deep=True)
    fact.local_observation_id += "-conflict"
    fact.value.normalized_value += Decimal(1)
    data["facts"].append(fact)
    with pytest.raises(ValueError, match="conflicting_source_values"):
        FinancialCalculator(SnapshotCatalog(**data)).calculate_dynamic(
            {s.evidence_id: s.reference for s in batch.claims[0].supporting_evidence},
            [DynamicOperation(operation_id="r", operator="ratio", inputs=["E1", "E2"])],
        )


def test_reasoning_plan_is_bounded_topological_and_legacy_wire_is_preserved():
    from pydantic import ValidationError
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerProposal

    legacy = PlannerProposal(intent="direct_fact")
    assert "reasoning_steps" not in legacy.model_dump()
    step = dict(
        step_id="compare",
        operation="compare",
        inputs=["revenue", "profit"],
        dependencies=[],
        goal="Compare",
        expected_output="Grounded comparison",
    )
    assert PlannerProposal(intent="multi_step_analysis", reasoning_steps=[step]).reasoning_steps
    with pytest.raises(ValidationError, match="reasoning_plan_dependency_invalid"):
        PlannerProposal(
            intent="multi_step_analysis", reasoning_steps=[dict(step, dependencies=["compare"])]
        )


def test_specialist_retains_valid_arithmetic_branch_when_another_branch_fails():
    from vietnamese_financial_multi_agent.agents.profitability_specialist import (
        ProfitabilityProposal,
    )
    from vietnamese_financial_multi_agent.agents.specialist_common import (
        SpecialistResult,
        generate_candidates,
    )
    from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity

    from .test_financial_qa import gateway_for

    _, batch = reasoning_case()
    result = SpecialistResult(
        question="Đối chiếu",
        upstream_status="completed",
        supporting_evidence=batch.claims[0].supporting_evidence,
    )
    payload = dict(
        claims=[],
        missing_information=[],
        analyses=[
            dict(
                statement="Unproven conclusion on bad branch",
                evidence_ids=["E1", "E2"],
                operations=[
                    dict(operation_id="bad", operator="ratio", inputs=["missing", "E2"]),
                    dict(operation_id="good", operator="subtract", inputs=["E1", "E2"]),
                ],
            )
        ],
    )
    generate_candidates(
        gateway=gateway_for(payload, []),
        model=ModelIdentity(provider="gemini", model="test"),
        result=result,
        prompt={},
        proposal_type=ProfitabilityProposal,
        render=lambda *args: "unused",
        prefix="test",
    )
    arithmetic = [c for c in result.candidates if c.reasoning]
    assert len(arithmetic) == 1 and arithmetic[0].reasoning.claim_type == "derived_fact"
    assert "Unproven" not in arithmetic[0].content
    assert [s.operation.operation_id for s in arithmetic[0].reasoning.calculation.steps] == ["good"]


def test_missing_graph_edges_do_not_block_grounded_calculation():
    data, batch = reasoning_case(operator="subtract")
    data["graph"] = None
    assert verify(data, batch)[-1].claims[0].decision == "ACCEPT"


def test_approved_metric_can_be_a_reasoning_premise_without_another_calculator():
    from .test_evidence_critic import semantic_gateway
    from .test_financial_logic_critic import gateway

    data = fixture()
    batch = batch_for(data, metric=True)
    claim = batch.claims[0]
    claim.kind = "supported_interpretation"
    claim.analysis_premises = [claim.content]
    claim.reasoning = ReasoningProof(
        claim_type="reasoned_conclusion", goal="Interpret reported margin"
    )
    claim.content = "Chỉ tiêu này phản ánh quan hệ lợi nhuận gộp với doanh thu trong kỳ; chưa chứng minh xu hướng."
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)

    def supported(payload):
        for assertion in payload["assertions"]:
            assertion.update(
                status="supported",
                reason="direct_support",
                missing=[],
                evidence_ids=["E1", "E2", "E3"],
            )

    evidence = EvidenceCritic(catalog, semantic_gateway(supported)).assess(batch, validation)
    logic = FinancialLogicCritic(gateway(status="consistent")).assess(batch, validation, evidence)
    decision = VerificationJudge().decide(batch, validation, evidence, logic).claims[0]
    assert decision.decision == "ACCEPT", decision.model_dump()


def test_statement_identifiers_and_disclosed_methodology_are_not_unverified_numbers():
    data, batch = reasoning_case()
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.reasoning.assumptions = ["Use supplied observations only."]
    claim.content = "B02 và B03 là hai nguồn trong kỳ 2030."
    validation = DeterministicFinancialValidator(SnapshotCatalog(**data)).validate(batch)
    assert not any(
        c.status == "fail" or c.check_id == "conditional_assumptions"
        for c in validation.claims[0].checks
    )
    assert verify(data, batch)[-1].claims[0].decision != "ACCEPT"  # Critics are still required.


def test_judge_outage_preserves_native_accepted_derived_proof(monkeypatch):
    from types import SimpleNamespace as NS
    from unittest.mock import Mock

    import vietnamese_financial_multi_agent.agents.adaptive_controller as module
    from vietnamese_financial_multi_agent.agents.planner_contracts import (
        PlannerContext,
        PlannerProposal,
    )
    from vietnamese_financial_multi_agent.verification.adaptive_judge import (
        AdaptiveJudge,
        JudgeFeedback,
    )

    data, batch = reasoning_case()
    v, e, logic, _ = verify(data, batch)
    history = VerificationHistory(
        contexts=[VerificationProofContext(batch=batch, validation=v, evidence=e, logic=logic)],
        outcome=BoundedVerificationLoop().start(batch, v, e, logic, candidate_id="C1"),
    )
    output = NS(
        status="completed",
        supervisor_result=None,
        specialist_executions=[],
        planner_result=NS(
            effective_proposal=PlannerProposal(
                intent="multi_step_analysis", reasoning_required=True
            ),
            model_dump=lambda **kwargs: {},
        ),
    )
    monkeypatch.setattr(module, "to_verification_input", lambda _: batch)
    monkeypatch.setattr(
        module,
        "VerificationRuntime",
        lambda *args, **kwargs: NS(
            verify=lambda *a, **kw: [history], provider_metadata=[], stage_latency_ms={}
        ),
    )
    monkeypatch.setattr(
        AdaptiveJudge, "assess", lambda *args: JudgeFeedback(assessment="JUDGE_ERROR")
    )
    controller = module.AdaptiveFinancialController(
        Mock(run=lambda **kwargs: output), None, None, None
    )
    _, actual = controller.run("Compare", PlannerContext(mode="auto"))
    assert actual == [history] and history.outcome.final.decision == "ACCEPT"


def test_automatic_context_uses_unique_company_filing_anchor(tmp_path):
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest

    from .test_financial_qa_pipeline import setup

    service, _, _, _, _ = setup(tmp_path)
    document = service.documents[0]
    service.documents.append(
        document.model_copy(update=dict(document_id="prior-document", reporting_year=2029))
    )
    bound, blocked, reasons = service._context(
        FinancialQARequest(question="Doanh thu TEST 2030 tăng so với 2029?", execution_mode="auto")
    )
    assert blocked is None, reasons
    assert bound.document_id == document.document_id
    _, blocked, _ = service._context(
        FinancialQARequest(question="So sánh TEST 2030 và TEST 2029", execution_mode="auto")
    )
    assert blocked == "clarification_required"


def test_single_filing_comparison_needs_semantic_planning_not_cross_document_approval():
    from vietnamese_financial_multi_agent.tools.question_understanding import understand

    assert understand("Tính chênh lệch doanh thu và lợi nhuận TEST 2030")[1] == [
        "semantic_intent_requires_gateway"
    ]
    assert (
        "cross_document_comparison_blocked_D03_B10"
        in understand("So sánh TEST 2030 và OTHER 2029")[1]
    )


def test_partial_answer_keeps_independent_derived_branch_without_claiming_analysis_complete(
    tmp_path,
):
    from vietnamese_financial_multi_agent.outputs import CitationRenderer, VietnameseQAComposer
    from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
    from vietnamese_financial_multi_agent.outputs.qa_contracts import (
        QARequirement,
        VietnameseQARequest,
    )
    from vietnamese_financial_multi_agent.verification import VerifiedClaimLedger

    data, batch = reasoning_case()
    v, e, logic, _ = verify(data, batch)
    history = VerificationHistory(
        contexts=[VerificationProofContext(batch=batch, validation=v, evidence=e, logic=logic)],
        outcome=BoundedVerificationLoop().start(batch, v, e, logic, candidate_id="C1"),
    )
    repo = VerifiedClaimRepository(tmp_path)
    repo.admit(history)
    ledger = VerifiedClaimLedger(repo)
    c = batch.claims[0]
    request = VietnameseQARequest(
        question="Giải thích quan hệ được giao",
        company_id=c.company_id,
        document_id=c.document_id,
        snapshot_id=c.snapshot_id,
        period=c.period,
        answer_requirements=[
            QARequirement(
                requirement_id="analysis",
                text="Giải thích",
                kind="fact",
                target_id=c.supporting_evidence[0].canonical_item_id,
                interpretation=True,
                interpretation_topic="metric_meaning",
                required_indicators=[s.canonical_item_id for s in c.supporting_evidence],
            )
        ],
    )
    answer = VietnameseQAComposer(ledger).compose(request)
    assert answer.status == "partial" and [
        r.requirement_id for r in answer.unanswered_requirements
    ] == ["analysis"]
    assert c.content in answer.answer_vi
    rendered = CitationRenderer().render_qa(answer)
    assert (
        InformationFirewall(ledger)
        .evaluate_qa(request=request, response=answer, rendered=rendered)
        .decision
        == "ALLOW_WITH_CAVEAT"
    )
