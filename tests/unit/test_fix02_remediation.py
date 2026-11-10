"""Focused correctness/performance controls; saved-PDF/live evidence is separate."""

import json
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.contracts import _schema_path_exists
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerOperation
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError, parse_json_output
from vietnamese_financial_multi_agent.core.request_gateway import RequestGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.financial_retrieval import FinancialToolResponse
from vietnamese_financial_multi_agent.verification.validators import DeterministicFinancialValidator

from .test_financial_qa_pipeline import setup
from .test_financial_validators import batch_for
from .test_llm_gateway import request
from .test_m4_execution import fixture


def test_reasoning_dependencies_can_reference_validated_execution_operations():
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerProposal

    wire = dict(
        intent="direct_fact",
        operations=[
            dict(
                operation_id="retrieve",
                operation="find_financial_facts",
                canonical_item_id="b02.net_revenue",
            )
        ],
        reasoning_steps=[
            dict(
                step_id="explain",
                operation="interpret",
                inputs=["retrieve"],
                dependencies=["retrieve"],
                goal="Diễn giải",
                expected_output="Nhận xét có nguồn",
            )
        ],
    )
    assert PlannerProposal.model_validate(wire)
    wire["reasoning_steps"][0]["dependencies"] = ["unknown"]
    with pytest.raises(ValueError, match="reasoning_plan_dependency_invalid"):
        PlannerProposal.model_validate(wire)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_missing_critic_ids_restore_unique_premises_or_request_reassessment(ambiguous):
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
    from vietnamese_financial_multi_agent.verification import EvidenceCritic, FinancialLogicCritic

    from .test_evidence_critic import response
    from .test_financial_logic_critic import gateway as logic_gateway
    from .test_multihop_reasoning import reasoning_case

    data, batch = reasoning_case()
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.content = "Các chỉ tiêu trong kỳ được đối chiếu trong phạm vi số liệu đã cung cấp."
    if ambiguous:
        claim.reasoning = None
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    calls = []

    def transport(req):
        calls.append(req)
        payload = json.loads(req.messages[1].content)
        return response(
            req,
            dict(
                candidate_id=payload["candidate_id"],
                assertions=[
                    dict(
                        assertion_id=a["assertion_id"],
                        status="supported",
                        evidence_ids=[]
                        if len(calls) == 1
                        else [e["evidence_id"] for e in payload["evidence"]],
                        reason="direct_support",
                        missing=[],
                    )
                    for a in payload["assertions"]
                ],
            ),
        )

    evidence = EvidenceCritic(catalog, SharedLLMGateway({"gemini": transport})).assess(
        batch, validation
    )
    result = evidence.claims[0]
    assert len(calls) == (2 if ambiguous else 1)
    assert bool(result.trace.binding_recoveries) != ambiguous
    assert bool(result.trace.reassessment_llm) == ambiguous
    assert result.assertions[0].status == "supported" and result.assertions[0].evidence_ids
    assert not result.errors

    def omit_redundant_check_ids(wire):
        for assertion in wire["assertions"]:
            assertion["premise_ids"] = [
                key for key in assertion["premise_ids"] if key.startswith("support:")
            ]

    logic = FinancialLogicCritic(
        logic_gateway(omit_redundant_check_ids, status="consistent")
    ).assess(batch, validation, evidence)
    assert logic.claims[0].trace.llm.calls == 1
    assert logic.claims[0].trace.binding_recoveries
    assert not logic.claims[0].errors


def test_binding_recovery_never_creates_a_supported_verdict():
    from vietnamese_financial_multi_agent.verification import EvidenceCritic

    from .test_evidence_critic import semantic_gateway

    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind = "supported_interpretation"
    claim.analysis_premises = [claim.content]
    claim.content = "Doanh thu trong kỳ được ghi nhận trong báo cáo."
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    result = EvidenceCritic(catalog, semantic_gateway()).assess(batch, validation).claims[0]
    assert not result.trace.binding_recoveries
    assert result.assertions[0].status == "insufficient_evidence"


@pytest.mark.parametrize("second_response", ["valid", "malformed", "changed_company"])
def test_planner_json_reemission_is_bounded_and_preserves_request(second_response):
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

    from .test_evidence_critic import response
    from .test_query_planner import planner

    instance = planner()
    question = "Doanh thu TEST 2030"
    payload = instance._deterministic(question)
    calls = []

    def transport(req):
        calls.append(req)
        if len(calls) == 1 or second_response == "malformed":
            result = response(req, {})
            result.status = "malformed"
            result.output = parse_json_output(
                '{"company_alias":"TEST","reasoning_steps":[- inputs"}'
            )
            result.error = GatewayError(
                category="structured_output_invalid",
                code="structured_output_invalid",
                origin="adapter",
                retryability="unknown",
            )
            return result
        if second_response == "changed_company":
            payload["company_alias"] = "OTHER"
        return response(req, payload)

    instance._gateway = SharedLLMGateway({"gemini": transport})
    context = PlannerContext(
        mode="auto",
        provider_attempt_limit=1,
        conversation_context=[dict(original_question="So với năm trước thì sao?", period="2030")],
    )
    result = instance.plan(question, context)
    assert len(calls) == result.llm.calls == 2
    assert calls[0].messages[:2] == calls[1].messages[:2]
    assert calls[1].output_spec.format == "json" and calls[1].output_spec.schema_ref is None
    assert len(result.llm.attempts) == 2
    if second_response == "valid":
        assert result.status == "planned", result.reasons
        assert result.plan.query.company_alias == "TEST"
        assert any(t.outcome == "planner_json_reemitted" for t in result.trace)
    else:
        assert result.status == "failed"
        assert result.plan is None


def test_planner_requests_missing_assignments_once_instead_of_inventing_roles():
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

    from .test_evidence_critic import response
    from .test_query_planner import planner

    instance = planner()
    question = "Phân tích doanh thu TEST 2030"
    payload = instance._deterministic(question)
    payload.update(reasoning_required=True, assignments=[])
    calls = []

    def transport(req):
        calls.append(req)
        if len(calls) == 2:
            payload["assignments"] = [
                dict(
                    role="profitability",
                    task="Phân tích số liệu doanh thu được giao",
                    indicators=["b02.net_revenue"],
                )
            ]
        return response(req, payload)

    instance._gateway = SharedLLMGateway({"gemini": transport})
    result = instance.plan(question, PlannerContext(mode="auto", provider_attempt_limit=1))
    assert result.status == "planned", result.reasons
    assert len(calls) == 2 and len(result.effective_proposal.assignments) == 1
    assert "thiếu assignments" in calls[1].messages[-1].content


def test_metric_interpretation_coverage_uses_calculation_operands():
    from vietnamese_financial_multi_agent.outputs.qa_composer import matches_financial_target
    from vietnamese_financial_multi_agent.outputs.qa_contracts import QARequirement

    from .test_verified_claim_ledger import history_for

    claim = history_for(metric=True).outcome.final.original_claim.model_copy(deep=True)
    claim.kind = "supported_interpretation"
    indicators = [
        m.record.canonical_item_id
        for o in claim.calculation.evidence.operands
        for m in o.facts.matches
    ]
    goal = QARequirement(
        requirement_id="analysis",
        text="Diễn giải tỷ lệ",
        kind="metric",
        target_id=claim.calculation.formula_id,
        interpretation=True,
        required_indicators=indicators,
    )
    assert matches_financial_target(claim, goal)
    goal.required_indicators.append("b03.operating_cash_flow")
    assert not matches_financial_target(claim, goal)


def test_optional_explanation_does_not_reduce_completeness(tmp_path):
    from vietnamese_financial_multi_agent.outputs import VietnameseQAComposer, VietnameseQARequest
    from vietnamese_financial_multi_agent.outputs.qa_contracts import QARequirement

    from .test_vietnamese_qa_composer import qa

    _, ledger, context = qa.__wrapped__(tmp_path)
    goals = [
        QARequirement(
            requirement_id="value", text="Doanh thu", kind="fact", target_id="b02.net_revenue"
        ),
        QARequirement(
            requirement_id="extra",
            text="Nhận xét hỗ trợ",
            kind="fact",
            target_id="b02.net_revenue",
            interpretation=True,
            required=False,
        ),
    ]
    result = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question="Doanh thu?", answer_requirements=goals, **context)
    )
    assert result.status == "answered" and not result.unanswered_requirements
    goals[1].required = True
    result = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question="Doanh thu?", answer_requirements=goals, **context)
    )
    assert result.status == "partial"


def test_explicit_comparative_periods_in_same_filing_survive_inventory(tmp_path):
    from types import SimpleNamespace

    from vietnamese_financial_multi_agent.outputs import VietnameseQARequest
    from vietnamese_financial_multi_agent.outputs.firewall_qa_binding import request_inventory
    from vietnamese_financial_multi_agent.outputs.qa_contracts import QARequirement

    from .test_vietnamese_qa_composer import qa

    repository, _, context = qa.__wrapped__(tmp_path)
    entry = next(e for e in repository.list_all() if e.identity.kind == "fact")
    entries, goals = [], []
    for year in ("2029", "2030"):
        claim = entry.accepted_claim.model_copy(deep=True)
        claim.period = year
        identity = entry.identity.model_copy(update={"period": year, "verified_claim_id": year})
        entries.append(
            SimpleNamespace(
                identity=identity,
                accepted_claim=claim,
                decision=entry.decision,
                verification_status="verified",
                content=entry.content,
            )
        )
        goals.append(
            QARequirement(
                requirement_id=year,
                text="So sánh doanh thu",
                kind="fact",
                target_id="b02.net_revenue",
                period=year,
            )
        )
    context.pop("period")
    request = VietnameseQARequest(
        question="So sánh doanh thu hai kỳ", answer_requirements=goals, **context
    )
    plan, status = request_inventory(request, entries)
    assert status == "answered" and set(plan.selected_verified_claim_ids) == {"2029", "2030"}
    entries[1].identity = entries[1].identity.model_copy(update={"document_id": "other"})
    assert request_inventory(request, entries)[1] == "clarification_required"


@pytest.mark.parametrize("explicit_operand", [False, True])
def test_internal_operations_do_not_create_answer_targets(tmp_path, explicit_operand):
    service, req, _, _, output = setup(tmp_path)
    service.gateway = Mock()
    proposal = output.planner_result.effective_proposal
    proposal.operations.extend(
        PlannerOperation(
            operation_id=f"operand-{i}", operation="find_financial_facts", canonical_item_id=item
        )
        for i, item in enumerate(["b02.gross_profit", "b02.net_revenue"])
    )
    if explicit_operand:
        req.question += " Và cho biết doanh thu thuần."
    response = service.run(req)
    assert response.trace.native_decisions.get("ACCEPT") == 1
    assert bool(response.trace.unanswered_requirements) == explicit_operand
    assert response.status == (
        "partial_verified_coverage" if explicit_operand else "completed_with_caveats"
    )
    assert (
        response.trace.adaptive_rounds[0]["judge"]["assessment"] != "PASS"
        if explicit_operand
        else response.trace.adaptive_rounds[0]["judge"]["assessment"] == "PASS"
    )


def test_metric_goal_binds_operands_inside_verified_calculation(tmp_path):
    from vietnamese_financial_multi_agent.agents.planner_contracts import UserRequestedTarget

    service, req, _, _, output = setup(tmp_path)
    service.gateway = Mock()
    output.planner_result.effective_proposal.user_requested_targets = [
        UserRequestedTarget(
            kind="metric",
            target_id="gross_margin",
            period="2030",
            required_indicators=["b02.gross_profit", "b02.net_revenue"],
        )
    ]
    result = service.run(req)
    assert result.status == "completed_with_caveats", result.trace.unanswered_requirements
    assert result.trace.native_decisions == {"ACCEPT": 1}
    assert result.citations and "Công thức:" in result.answer_vi


def test_invalid_goal_contract_is_typed_block_not_internal_error(tmp_path):
    service, req, repo, _, output = setup(tmp_path)
    service.gateway = Mock()
    output.status, output.candidates = "failed", []
    output.planner_result.status = "failed"
    output.planner_result.reasons = ["answer_target_outside_plan_indicators"]
    result = service.run(req)
    assert result.status == "verification_blocked"
    assert not result.used_verified_claim_ids and not repo.list_all()


@pytest.mark.parametrize("binding", ["operation", "relation", "unknown"])
def test_explicit_goal_binding_preserves_raw_proposal_and_rejects_unknown(binding):
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext

    from .test_financial_qa import gateway_for
    from .test_query_planner import planner

    instance = planner()
    question = "Doanh thu TEST 2030"
    proposal = instance._deterministic(question)
    proposal["user_requested_targets"] = [dict(kind="fact", target_id="fact_0")]
    if binding == "relation":
        proposal["user_requested_targets"] = [
            dict(
                kind="explanation",
                target_id=None,
                interpretation=True,
                interpretation_topic="metric_meaning",
                required_indicators=["b02.net_revenue"],
            )
        ]
    elif binding == "unknown":
        proposal["user_requested_targets"][0]["target_id"] = "unregistered-operation"
    instance._gateway = gateway_for(proposal, [])
    result = instance.plan(question, PlannerContext(mode="auto"))
    assert result.status == ("failed" if binding == "unknown" else "planned"), result.reasons
    assert result.raw_proposal == proposal
    if binding != "unknown":
        goal = result.effective_proposal.user_requested_targets[0]
        assert goal.kind == "fact" and goal.target_id == "b02.net_revenue"


@pytest.mark.parametrize(
    "text,blocked",
    [
        ("Chưa đủ cơ sở để kết luận tỷ lệ này cải thiện.", False),
        (
            "Báo cáo ghi nhận dữ liệu nhưng chưa đủ cơ sở tính toán tỷ lệ chuyển đổi hoặc kết luận chất lượng lợi nhuận.",
            False,
        ),
        ("Không thể kết luận tỷ lệ cải thiện, nhưng tỷ lệ tăng mạnh.", True),
        ("Không thiếu bằng chứng tỷ lệ tăng.", True),
        ("Chưa đủ cơ sở kết luận, tỷ lệ tăng 15%.", True),
    ],
)
def test_limitation_scope_does_not_hide_quantitative_assertions(text, blocked):
    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind = "supported_interpretation"
    claim.analysis_premises = [claim.content]
    claim.content = text
    result = DeterministicFinancialValidator(SnapshotCatalog(**data)).validate(batch)
    failures = [c for c in result.claims[0].checks if c.status == "fail"]
    assert bool(failures) == blocked


def test_malformed_critic_does_not_poison_unrelated_calls():
    from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport

    gateway = Mock()
    transport = FakeLLMTransport()

    def generate(req):
        result = transport(req)
        if req.request_id == "bad":
            result.output = parse_json_output('{"missing": [}')
            result.status = "malformed"
            result.error = GatewayError(
                category="structured_output_invalid",
                code="structured_output_invalid",
                origin="adapter",
                retryability="unknown",
            )
        return result

    gateway.generate.side_effect = generate
    budget = RequestGateway(gateway, max_calls=2, timeout_seconds=10)
    assert budget.generate(request("bad")).status == "malformed"
    assert budget.generate(request("good")).status == "success"
    assert len(budget.events) == 2
    assert budget.generate(request("over-budget")).status == "error"
    assert gateway.generate.call_count == 2


def test_schema_path_generation_reuses_immutable_schema(monkeypatch):
    original = FinancialToolResponse.model_json_schema
    calls = []

    def schema(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(FinancialToolResponse, "model_json_schema", schema)
    assert _schema_path_exists(FinancialToolResponse, "status")
    assert _schema_path_exists(FinancialToolResponse, "matches.0.record.document_id")
    assert len(calls) <= 1


def test_recorded_malformed_shape_remains_invalid():
    from vietnamese_financial_multi_agent.verification.evidence_contracts import (
        SemanticEvidenceAssessment,
    )

    raw = '{"candidate_id":"C1","assertions":[{"assertion_id":"A1","status":"supported","evidence_ids":["E1"],"reason":"direct_support",_missing:[]}]}'
    assert parse_json_output(raw).validation_status == "invalid_json"
    with pytest.raises((ValueError, json.JSONDecodeError)):
        SemanticEvidenceAssessment.model_validate_json(raw)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Biên lợi nhuận gộp TEST 2030?", {("metric", "gross_margin", False)}),
        (
            "Biên lợi nhuận gộp và cho biết doanh thu thuần TEST 2030?",
            {("metric", "gross_margin", False), ("fact", "b02.net_revenue", False)},
        ),
        ("Doanh thu thuần TEST 2030?", {("fact", "b02.net_revenue", False)}),
        (
            "Doanh thu thuần và lợi nhuận sau thuế TEST 2030?",
            {("fact", "b02.net_revenue", False), ("fact", "b02.profit_after_tax", False)},
        ),
        (
            "Biên lợi nhuận gộp TEST 2030? Nêu công thức và số liệu sử dụng.",
            {("metric", "gross_margin", False), ("explanation", "gross_margin", False)},
        ),
    ],
)
def test_question_goals_preserve_explicit_independent_targets(question, expected):
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerProposal
    from vietnamese_financial_multi_agent.outputs.qa_composer import planned_requirements

    proposal = PlannerProposal(intent="multi_step_analysis")
    requirements = planned_requirements(question, proposal)
    assert {
        (r.kind, r.target_id, r.interpretation) for r in requirements if r.kind != "explanation"
    } == {e for e in expected if e[0] != "explanation"}
    if any(e[0] == "metric" for e in expected):
        assert {r.aspect for r in requirements if r.kind == "explanation"} == {
            "formula",
            "operands",
        }


def test_request_snapshot_isolation_and_detached_lineage_results():
    from vietnamese_financial_multi_agent.tools.financial_retrieval import FinancialRetrievalTools

    catalog = SnapshotCatalog(**fixture())
    session = catalog.request_snapshot()
    tools = FinancialRetrievalTools(session)
    assert tools._catalog is session
    original = session.facts[0].value.normalized_value
    catalog.facts[0].value.normalized_value = "123456"
    assert session.facts[0].value.normalized_value == original
    first = session.select(session.descriptors[0].document_id)
    first.candidates[0].known_limitations.append("caller_mutation")
    assert (
        "caller_mutation"
        not in session.select(session.descriptors[0].document_id).candidates[0].known_limitations
    )
    metric_id = session.metrics[0].metric_id
    result = session.api.get_lineage(metric_id)
    result.reasons.append("caller_mutation")
    assert "caller_mutation" not in session.api.get_lineage(metric_id).reasons


def test_prompt_schema_caller_mutation_does_not_poison_cache():
    from vietnamese_financial_multi_agent.core.schema_cache import model_schema

    schema = model_schema(FinancialToolResponse)
    schema["properties"].clear()
    assert model_schema(FinancialToolResponse)["properties"]


@pytest.mark.parametrize(
    "control,expected",
    [
        ("valid", None),
        ("wrapper", None),
        ("multiple_objects", "invalid_schema"),
        ("missing_field", "invalid_schema"),
        ("extra_field", "invalid_schema"),
        ("foreign_evidence", "invalid_semantic_contract"),
        ("malformed", "invalid_json"),
        ("truncated", "truncated"),
        ("503", "provider_failure"),
    ],
)
def test_critic_failure_categories_keep_strict_validation(control, expected):
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
    from vietnamese_financial_multi_agent.verification.evidence_critic import EvidenceCritic

    from .test_evidence_critic import response

    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    claim.kind = "supported_interpretation"
    claim.analysis_premises = [claim.content]
    claim.content = "Doanh thu trong kỳ được ghi nhận trong báo cáo."

    def transport(req):
        if control == "503":
            return _failure(req, "provider_unavailable")
        source = json.loads(req.messages[-1].content)
        payload = dict(
            candidate_id=source["candidate_id"],
            assertions=[
                dict(
                    assertion_id=a["assertion_id"],
                    status="supported",
                    evidence_ids=["E1"],
                    reason="direct_support",
                    missing=[],
                )
                for a in source["assertions"]
            ],
        )
        if control == "missing_field":
            del payload["assertions"][0]["missing"]
        elif control == "extra_field":
            payload["assertions"][0]["extra"] = True
        elif control == "foreign_evidence":
            payload["assertions"][0]["evidence_ids"] = ["FOREIGN"]
        elif control in {"wrapper", "multiple_objects"}:
            payload = [payload] * (1 if control == "wrapper" else 2)
        result = response(req, payload)
        if control == "malformed":
            result.status = "malformed"
            result.output = parse_json_output('{"missing": [}')
            result.error = GatewayError(
                category="structured_output_invalid",
                code="structured_output_invalid",
                origin="adapter",
                retryability="unknown",
            )
        elif control == "truncated":
            result.status, result.finish_reason = "partial", "length"
        return result

    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    assessed = (
        EvidenceCritic(catalog, SharedLLMGateway({"gemini": transport}))
        .assess(batch, validation)
        .claims[0]
    )
    assert assessed.trace.failure_kind == expected
    assert assessed.status == ("supported" if expected is None else "partially_supported") or (
        expected is not None and assessed.status == "insufficient_evidence"
    )


@pytest.mark.parametrize("failed_revision", [False, True])
def test_substantive_revision_reaches_native_complete_without_mutating_proof(
    monkeypatch, failed_revision
):
    from types import SimpleNamespace as NS

    import vietnamese_financial_multi_agent.agents.adaptive_controller as module
    from vietnamese_financial_multi_agent.agents.planner_contracts import (
        PlannerContext,
        PlannerProposal,
        SpecialistAssignment,
        UserRequestedTarget,
    )
    from vietnamese_financial_multi_agent.verification.adaptive_judge import (
        JudgeFeedback,
        JudgeIssue,
    )

    from .test_adaptive_router import inputs
    from .test_verified_claim_ledger import history_for

    history = history_for()
    original = history.model_dump_json()
    claim = history.outcome.final.original_claim
    target = claim.supporting_evidence[0].canonical_item_id
    _, supervisor = inputs("Doanh thu TEST 2030")
    context = PlannerContext(
        **{k: getattr(claim, k) for k in ("company_id", "document_id", "snapshot_id", "period")}
    )
    outputs = []
    for task in ("Retrieve the requested fact", "Render the retrieved requested fact"):
        proposal = PlannerProposal(
            intent="direct_fact",
            reasoning_required=True,
            user_requested_targets=[UserRequestedTarget(kind="fact", target_id=target)],
            assignments=[SpecialistAssignment(role="profitability", task=task)],
        )
        outputs.append(
            NS(
                status="completed",
                context=context,
                supervisor_result=supervisor,
                specialist_executions=[],
                planner_result=NS(effective_proposal=proposal, model_dump=lambda **_: {}),
            )
        )
    m5 = Mock()
    if failed_revision:
        outputs[1].status = "failed"
    m5.run.side_effect = outputs
    monkeypatch.setattr(module, "to_verification_input", lambda _: None)
    runtime = Mock(provider_metadata=[], stage_latency_ms={})
    runtime.verify.side_effect = [[history] if failed_revision else [], [history]]
    monkeypatch.setattr(module, "VerificationRuntime", lambda *a, **kw: runtime)
    judge = Mock(latency_ms=0)
    judge.assess.side_effect = [
        JudgeFeedback(
            assessment="REVISION_NEEDED",
            revision_required=True,
            issues=[
                JudgeIssue(
                    issue_type="INCOMPLETE_COVERAGE",
                    explanation="Requested fact not rendered",
                    required_evidence=[target],
                    suggested_action="REVISE_ANALYSIS",
                )
            ],
        ),
        JudgeFeedback(assessment="PASS"),
    ]
    monkeypatch.setattr(module, "AdaptiveJudge", lambda *a: judge)
    controller = module.AdaptiveFinancialController(m5, None, NS(exhausted=False), None)
    _, histories = controller.run("Chỉ tiêu đã yêu cầu TEST 2030?", context)
    assert len(controller.rounds) == 2
    if failed_revision:
        assert controller.rounds[-1]["judge"] is None
        assert controller.rounds[-1]["stop_reason"] == "execution_unavailable"
        assert runtime.verify.call_count == 1
    else:
        assert controller.rounds[-1]["judge"]["coverage"]["complete"]
        assert controller.rounds[-1]["stop_reason"] == "PASS"
    assert m5.run.call_args_list[1].kwargs["context"].feedback["issues"]
    assert all(call.kwargs == {"allow_revision": False} for call in runtime.verify.call_args_list)
    assert histories == [history] and history.model_dump_json() == original
