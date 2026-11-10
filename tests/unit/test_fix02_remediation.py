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


def test_substantive_revision_reaches_native_complete_without_mutating_proof(monkeypatch):
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
    m5.run.side_effect = outputs
    monkeypatch.setattr(module, "to_verification_input", lambda _: None)
    runtime = Mock(provider_metadata=[], stage_latency_ms={})
    runtime.verify.side_effect = [[], [history]]
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
    assert len(controller.rounds) == 2 and controller.rounds[-1]["judge"]["coverage"]["complete"]
    assert controller.rounds[-1]["stop_reason"] == "PASS"
    assert m5.run.call_args_list[1].kwargs["context"].feedback["issues"]
    assert all(call.kwargs == {"allow_revision": False} for call in runtime.verify.call_args_list)
    assert histories == [history] and history.model_dump_json() == original
