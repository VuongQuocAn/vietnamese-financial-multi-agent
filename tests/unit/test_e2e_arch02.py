"""API-to-M7 regression smoke; synthetic evidence is not financial evaluation."""

import json
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import FinancialLiteOrchestrator
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import parse_json_output
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

from .test_v2_integration import setup_engine


@pytest.mark.parametrize(
    "mode,allow_gateway,answer_calls",
    [("auto", True, 1), ("deterministic", True, 0), ("auto", False, 0)],
)
def test_v2_pipeline_preserves_answer_gateway_and_verified_bindings(
    tmp_path, mode, allow_gateway, answer_calls
):
    catalog, context, _, _ = setup_engine()
    question = "Doanh thu thuần TEST năm 2030 là bao nhiêu?"
    output = FinancialLiteOrchestrator(catalog).run(question=question, context=context)
    calls = []

    def transport(request):
        calls.append(request)
        payload = json.loads(request.messages[1].content)
        if request.request_id.startswith("m7-lite-"):
            body = dict(
                segments=[
                    dict(text=row["content"], claim_ids=[row["claim_id"]])
                    for row in payload["verified_claims"]
                ],
                gaps=[],
            )
        else:
            assert request.request_id.startswith("m6-lite-")
            body = dict(
                verdicts=[
                    dict(
                        claim_id=row["claim_id"],
                        verdict="SUPPORTED",
                        reason="source supports goal",
                        supported_requirement_ids=[
                            r["requirement_id"] for r in row["local_requirements"]
                        ],
                        issues=[],
                    )
                    for row in payload
                ]
            )
        response = _failure(request, "timeout")
        response.status, response.error, response.finish_reason = "success", None, "stop"
        response.output = parse_json_output(json.dumps(body))
        return response

    repository = VerifiedClaimRepository(tmp_path)
    service = FinancialQAPipeline(
        catalog=catalog,
        documents=[
            QADocument(
                document_id=context.document_id,
                company_id=context.company_id,
                reporting_year=2030,
                company_aliases=["TEST"],
            )
        ],
        repository=repository,
        gateway=SharedLLMGateway({"gemini": transport}),
        orchestrator=Mock(run=Mock(return_value=output)),
    )
    response = service.run(
        FinancialQARequest(
            question=question,
            company_id=context.company_id,
            document_id=context.document_id,
            snapshot_id=context.snapshot_id,
            execution_mode=mode,
            allow_gateway=allow_gateway,
            force_refresh=True,
        )
    )
    m7 = [r for r in calls if r.request_id.startswith("m7-lite-")]
    assert len(m7) == answer_calls
    assert response.trace.m7_lite["calls"] == answer_calls
    if m7:
        assert response.used_verified_claim_ids and response.citations, response.trace.errors
        sent = json.loads(m7[0].messages[1].content)
        assert sent["goal_bindings"] == response.trace.integration_context["verified_requirements"]
        assert sent["verified_coverage"] == response.trace.m7_lite["coverage"]
        assert response.trace.m7_lite["rendering_mode"] == "grounded_natural_answer"
    assert {e.identity.verified_claim_id for e in repository.list_all()} >= set(
        response.used_verified_claim_ids
    )
