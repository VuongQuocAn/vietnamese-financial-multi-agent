"""QA-Fix-02 offline controls; synthetic fixtures are not financial evaluation."""

import json
from unittest.mock import Mock

import pytest
from google.genai import errors, types
from vietnamese_financial_multi_agent.agents import (
    AdaptiveSpecialistRouter,
    FinancialMultiAgentOrchestrator,
    PlannerContext,
    RiskAwareSupervisor,
)
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

from .test_financial_qa import gateway_for
from .test_gemini_adapter import sdk_response
from .test_query_planner import planner

ROLES = ["profitability", "liquidity_and_leverage", "cash_flow_and_earnings_quality"]


def rejected(**changes):
    return dict(intent="unsupported", unsupported_capabilities=ROLES, **changes)


@pytest.mark.parametrize(
    "question",
    [
        "Phân tích khả năng sinh lời, tình hình nợ và dòng tiền kinh doanh TEST 2030",
        "Đánh giá dòng tiền, đòn bẩy và khả năng sinh lời TEST năm 2030",
        "Cho biết thanh khoản và khả năng sinh lời TEST 2030",
    ],
)
def test_broad_supported_domains_clarify_without_selecting_metrics(question):
    raw = rejected()
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.status == "clarification_required", result.reasons
    assert result.missing_information and not result.plan
    assert result.raw_proposal == raw and result.proposal.intent == "unsupported"
    assert result.effective_proposal.formula_ids == []
    assert any(t.stage == "semantic_policy" for t in result.trace)


@pytest.mark.parametrize(
    "question,items,formulas",
    [
        ("Biên lợi nhuận gộp và tổng tài sản TEST 2030", ["b01.total_assets"], ["gross_margin"]),
        (
            "Dòng tiền thuần từ hoạt động kinh doanh, tổng tài sản và biên lợi nhuận gộp TEST 2030",
            ["b01.total_assets", "b03.operating_cash_flow"],
            ["gross_margin"],
        ),
        ("Doanh thu và lợi nhuận gộp TEST 2030", ["b02.net_revenue", "b02.gross_profit"], []),
    ],
)
def test_explicit_targets_recover_rejected_or_omitted_proposal(question, items, formulas):
    raw = rejected()
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.status in {"planned", "blocked"}, result.reasons
    assert result.plan and result.validation.structurally_valid
    effective = result.effective_proposal
    assert set(effective.formula_ids) == set(formulas)
    assert set(effective.required_indicators) == set(items)
    assert (
        effective.intent == "multi_step_analysis"
        and effective.operations[-1].operation == "prepare_bundle"
    )
    assert not effective.unsupported_capabilities and result.raw_proposal == raw
    assert result.query.reporting_scope is None and not result.financial_fact_verified


def test_partial_support_keeps_unsupported_target_for_router():
    question = "Doanh thu thuần và ROE TEST 2030"
    raw = dict(intent="unsupported", unsupported_capabilities=["ROE"])
    instance = planner(gateway=gateway_for(raw, []))
    result = instance.plan(question)
    assert result.status == "planned", result.reasons
    upstream = RiskAwareSupervisor(instance._catalog).execute(result.plan)
    routing = AdaptiveSpecialistRouter().route(
        question=question, planner_result=result, supervisor_result=upstream
    )
    assert routing.status == "partial" and routing.selected_roles == ["profitability"]
    assert any(
        r.status == "unsupported" and r.target_id.lower() == "roe" for r in routing.requirements
    )
    assert result.effective_proposal.unsupported_capabilities == ["ROE"]
    assert result.query.requested_formula_ids == []


def test_unapproved_substitution_is_never_executed():
    question = "ROE TEST 2030"
    raw = planner()._deterministic("Biên lợi nhuận gộp TEST 2030")
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.status == "unsupported" and not result.plan
    assert result.raw_proposal == raw


@pytest.mark.parametrize(
    "question,changes,context,status",
    [
        ("Doanh thu TEST 2030", {"reporting_scope": "separate"}, {}, "failed"),
        (
            "Doanh thu TEST 2030 riêng",
            {},
            {"reporting_scope": "consolidated"},
            "clarification_required",
        ),
        ("Doanh thu TEST 2030", {}, {"reporting_year": 2029}, "clarification_required"),
        ("Doanh thu TEST 2029 và 2030", {}, {}, "blocked"),
    ],
)
def test_recovery_preserves_scope_year_and_cross_document_gates(question, changes, context, status):
    raw = rejected(**changes)
    result = planner(gateway=gateway_for(raw, [])).plan(question, PlannerContext(**context))
    assert result.status == status and not result.plan


def test_missing_evidence_blocks_recovery_instead_of_computing_zero():
    instance = planner()
    data = instance._catalog
    result = planner(gateway=gateway_for(rejected(), [])).plan("Lợi nhuận trước thuế TEST 2030")
    assert result.status == "blocked" and result.plan
    assert not result.financial_fact_verified
    assert all(s.status == "pending" for s in result.plan.steps)
    assert data.facts  # Original catalog untouched.


def provider_pipeline(outcomes, *, attempts=2, timeout=60):
    client = Mock()
    client.models.generate_content.side_effect = outcomes
    gateway = SharedLLMGateway({"gemini": GeminiAdapter(client)})
    instance = planner(gateway=gateway)
    supervisor, router = Mock(), Mock()
    orchestrator = FinancialMultiAgentOrchestrator(
        planner=instance, supervisor=supervisor, router=router, specialists={}
    )
    context = PlannerContext(provider_attempt_limit=attempts, provider_timeout_seconds=timeout)
    return client, instance, supervisor, router, orchestrator, context


def api_error(code):
    return errors.APIError(code, {"error": {"code": code, "message": "synthetic provider failure"}})


def test_503_then_success_retains_attempt_provenance_usage_and_latency():
    raw = planner()._deterministic("Doanh thu TEST 2030")
    client, instance, _, _, _, context = provider_pipeline(
        [
            api_error(503),
            sdk_response(
                json.dumps(raw),
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=9, candidates_token_count=2, total_token_count=11
                ),
            ),
        ]
    )
    result = instance.plan("Doanh thu TEST 2030", context)
    assert (
        result.status == "planned"
        and client.models.generate_content.call_count == result.llm.calls == 2
    )
    assert len(result.llm.attempts) == 2
    assert result.llm.attempts[0].response.error.provider_error_code == "http_503"
    assert result.llm.attempts[0].response.error.origin == "provider"
    assert result.llm.attempts[1].response.status == "success"
    assert result.llm.latency_ms >= sum(a.latency_ms for a in result.llm.attempts)
    assert result.llm.usage.total_tokens == 11
    configs = [c.kwargs["config"] for c in client.models.generate_content.call_args_list]
    assert configs[1].http_options.timeout < configs[0].http_options.timeout
    # Use the real supervisor/router; absent Specialist only stops its own stage.
    completed_planner = Mock()
    completed_planner.plan.return_value = result
    orchestration = FinancialMultiAgentOrchestrator(
        planner=completed_planner,
        supervisor=RiskAwareSupervisor(instance._catalog),
        router=AdaptiveSpecialistRouter(),
        specialists={},
    )
    output = orchestration.run(question=result.question, context=context)
    assert output.usage.calls == 2 and output.usage.calls_with_unknown_tokens == 1
    assert output.usage.total_tokens == 11


def test_omission_and_approved_metric_substitution_require_clarification():
    raw = planner()._deterministic("Biên lợi nhuận gộp TEST 2030")
    raw["formula_ids"] = ["debt_to_assets"]
    raw["operations"][0]["formula_id"] = "debt_to_assets"
    result = planner(gateway=gateway_for(raw, [])).plan("Biên lợi nhuận gộp TEST 2030")
    assert result.status == "clarification_required" and not result.plan
    assert result.raw_proposal == raw


def test_registered_capability_contradiction_without_exact_question_alias_clarifies():
    result = planner(gateway=gateway_for(rejected(), [])).plan("Đánh giá doanh nghiệp TEST 2030")
    assert result.status == "clarification_required" and not result.plan


@pytest.mark.parametrize("cash_label", ["dòng tiền kinh doanh", "CFO"])
def test_cash_flow_paraphrases_preserve_explicit_targets_without_quality_verdict(cash_label):
    question = (
        f"Doanh thu thuần và {cash_label} TEST 2030 có cho thấy chất lượng lợi nhuận tốt không?"
    )
    raw = dict(intent="unsupported", unsupported_capabilities=["earnings_quality_evidence"])
    result = planner(gateway=gateway_for(raw, [])).plan(question)
    assert result.effective_proposal.required_indicators == [
        "b02.net_revenue",
        "b03.operating_cash_flow",
    ]
    assert result.status == "blocked" and result.plan  # CFO absent in fixture.
    assert not result.effective_proposal.unsupported_capabilities
    assert result.effective_proposal.formula_ids == [] and not result.financial_fact_verified


def test_valid_clarification_reason_is_preserved_when_operations_are_deliberately_empty():
    raw = dict(
        intent="ambiguous",
        required_indicators=["b02.net_revenue", "b03.operating_cash_flow"],
        missing_information=["earnings_quality_criteria_required"],
    )
    result = planner(gateway=gateway_for(raw, [])).plan(
        "Doanh thu và CFO TEST 2030 có cho thấy chất lượng lợi nhuận tốt không?"
    )
    assert result.status == "clarification_required" and not result.plan
    assert result.effective_proposal.missing_information == raw["missing_information"]
    assert result.query.missing_information == raw["missing_information"]


@pytest.mark.parametrize(
    "outcomes,attempts,category,count",
    [
        ([api_error(503), api_error(503)], 2, "provider_unavailable", 2),
        ([api_error(503)], 1, "provider_unavailable", 1),
        ([api_error(429)], 2, "rate_limit", 1),
        ([api_error(401)], 2, "authentication", 1),
        ([api_error(403)], 2, "authorization", 1),
        ([sdk_response("bad json")], 2, "structured_output_invalid", 1),
        ([TimeoutError()], 2, "timeout", 1),
    ],
)
def test_provider_failure_does_not_fake_downstream(outcomes, attempts, category, count):
    client, _, supervisor, router, orchestrator, context = provider_pipeline(
        outcomes, attempts=attempts
    )
    output = orchestrator.run(question="Doanh thu TEST 2030", context=context)
    assert (
        output.status == "failed"
        and client.models.generate_content.call_count == output.usage.calls == count
    )
    assert output.planner_result.llm.error.category == category
    assert category in output.stop_conditions
    assert output.usage.calls_with_unknown_tokens == count and output.usage.total_tokens is None
    supervisor.execute.assert_not_called()
    router.route.assert_not_called()
    assert not output.candidates and not output.specialist_executions
    assert all(
        t.outcome == "skipped"
        for t in output.trace
        if t.stage in {"supervisor", "routing", "specialist_execution", "candidate_aggregation"}
    )


def test_503_retry_obeys_total_timeout(monkeypatch):
    from vietnamese_financial_multi_agent.core import llm_gateway

    elapsed = [0.0]
    monkeypatch.setattr(llm_gateway, "perf_counter", lambda: elapsed[0])
    client, instance, _, _, _, context = provider_pipeline([], timeout=1)

    def expired(**kwargs):
        elapsed[0] = 2.0
        raise api_error(503)

    client.models.generate_content.side_effect = expired
    result = instance.plan("Doanh thu TEST 2030", context)
    assert result.status == "failed" and result.llm.calls == 1
    assert client.models.generate_content.call_count == 1
