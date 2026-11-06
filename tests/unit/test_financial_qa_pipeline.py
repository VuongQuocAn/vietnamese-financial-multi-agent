"""Synthetic E2E controls, with real M6 policy/admission and real M7 release."""

from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents import PlannerContext
from vietnamese_financial_multi_agent.agents.orchestration_contracts import CandidateConflict
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.citation_renderer import CitationRenderer
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification import VerifiedClaimRepository

from .test_m4_execution import fixture
from .test_orchestrator import inputs, metric_specialist, pipeline
from .test_verified_claim_ledger import history_for

QUESTION = "Biên lợi nhuận gộp TEST năm 2030?"


def setup(tmp_path):
    data = fixture()
    p, s = inputs()
    m5, *_ = pipeline(p, s, {"profitability": metric_specialist([])})
    result = m5.run(question=QUESTION, context=PlannerContext(mode="deterministic"))
    document = QADocument(
        document_id=data["descriptors"][0].document_id,
        company_id=data["facts"][0].company_id,
        company_aliases=["TEST"],
        reporting_year=2030,
    )
    repository = VerifiedClaimRepository(tmp_path)
    orchestrator = Mock()
    orchestrator.run.return_value = result
    orchestrator.run.side_effect = lambda **kwargs: result.model_copy(
        deep=True,
        update={
            "question": kwargs["question"],
            "context": kwargs["context"],
        },
    )
    service = FinancialQAPipeline(
        catalog=SnapshotCatalog(**data),
        documents=[document],
        repository=repository,
        orchestrator=orchestrator,
    )
    request = FinancialQARequest(
        question=QUESTION,
        document_id=document.document_id,
        snapshot_id=data["descriptors"][0].snapshot_id,
        allow_gateway=True,
    )
    return service, request, repository, orchestrator, result


def test_fresh_verification_release_then_cache_without_provider(tmp_path):
    service, request, repo, m5, result = setup(tmp_path)
    before = result.model_dump_json()
    response = service.run(request)
    assert response.mode == "FRESH_M5_M6_M7", response
    assert response.status == "completed_with_caveats"
    assert response.newly_accepted_claims == 1 and response.used_verified_claim_ids
    assert response.citations and response.trace.firewall_decision == "ALLOW_WITH_CAVEAT"
    assert response.trace.executed_agents == ["profitability"]
    assert len(repo.list_all()) == 1 and result.model_dump_json() == before
    cached = service.run(request.model_copy(update={"allow_gateway": False}))
    assert cached.mode == "CACHE_HIT" and cached.answer_vi == response.answer_vi
    assert cached.reused_claims == 1 and cached.trace.provider_calls == 0
    assert m5.run.call_count == 1
    assert cached.trace.stages["m5"].status == "NOT_EXECUTED"
    assert not cached.trace.executed_agents


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot_id", "wrong-snapshot"),
        ("company_id", "wrong-company"),
        ("period", "2029"),
        ("document_id", "wrong-document"),
    ],
)
def test_no_cross_identity_reuse(tmp_path, field, value):
    service, request, repo, m5, _ = setup(tmp_path)
    assert service.run(request).used_verified_claim_ids
    m5.reset_mock()
    response = service.run(request.model_copy(update={field: value, "allow_gateway": False}))
    assert not response.used_verified_claim_ids and response.reused_claims == 0
    assert response.mode != "CACHE_HIT"
    m5.run.assert_not_called()
    assert len(repo.list_all()) == 1


@pytest.mark.parametrize(
    "question",
    [
        "ROE TEST năm 2030?",
        "So sánh doanh thu TEST năm 2029 và 2030?",
        "Phân tích tài chính TEST?",
    ],
)
def test_known_unsupported_or_ambiguous_does_not_invoke_m5(tmp_path, question):
    service, request, _, m5, _ = setup(tmp_path)
    response = service.run(request.model_copy(update={"question": question}))
    assert response.status in {"unsupported", "clarification_required"}
    m5.run.assert_not_called()


def test_explicit_unconfirmed_scope_is_not_invented(tmp_path):
    service, request, _, m5, _ = setup(tmp_path)
    response = service.run(request.model_copy(update={"reporting_scope": "consolidated"}))
    assert response.status == "clarification_required"
    assert not response.used_verified_claim_ids
    m5.run.assert_not_called()


@pytest.mark.parametrize(
    "status,expected",
    [
        ("clarification_required", "clarification_required"),
        ("failed", "internal_error"),
        ("blocked", "verification_blocked"),
    ],
)
def test_stopped_m5_never_verifies_or_claims_specialists_executed(tmp_path, status, expected):
    service, request, repo, _, source = setup(tmp_path)
    source.status, source.candidates, source.specialist_executions = status, [], []
    source.planner_result.status = status
    response = service.run(request)
    assert response.status == expected
    assert response.trace.stages["m6"].status == "NOT_EXECUTED"
    assert not repo.list_all() and not response.trace.executed_agents


def test_cross_document_candidate_is_blocked_before_admission(tmp_path):
    service, request, repo, _, source = setup(tmp_path)
    source.candidates[0].citations[0].source.document_id = "foreign-document"
    response = service.run(request)
    assert response.status == "verification_blocked"
    assert not repo.list_all() and not response.used_verified_claim_ids


def test_duplicate_candidate_and_force_refresh_do_not_duplicate_admission(tmp_path):
    service, request, repo, _, source = setup(tmp_path)
    source.candidates.append(source.candidates[0].model_copy(deep=True))
    first = service.run(request)
    assert first.newly_accepted_claims == 1, first
    second = service.run(request.model_copy(update={"force_refresh": True}))
    assert second.newly_accepted_claims == 0
    assert len(repo.list_all()) == 1 and second.used_verified_claim_ids


def test_invalid_evidence_defers_without_release(tmp_path):
    service, request, repo, _, source = setup(tmp_path)
    source.candidates[0].citations = []
    response = service.run(request)
    assert response.deferred_claims + response.rejected_claims == 1
    assert not repo.list_all() and not response.citations
    assert response.status == "verification_blocked"


def test_partial_reuse_preserves_missing_standalone_fact(tmp_path):
    service, request, repo, m5, _ = setup(tmp_path)
    assert service.run(request).newly_accepted_claims == 1
    # A calculation's revenue operand must never cover standalone revenue.
    repo.admit(history_for())
    request.question = "Biên lợi nhuận gộp, doanh thu và lợi nhuận sau thuế TEST năm 2030?"
    response = service.run(request)
    assert response.mode == "PARTIAL_REUSE_AND_REFRESH"
    assert m5.run.call_count == 2
    assert response.status == "partial_verified_coverage"
    assert any(
        r.target_id == "b02.profit_after_tax" for r in response.trace.unanswered_requirements
    )
    assert "full_request_refresh_fallback" in response.trace.limitations


def test_firewall_block_never_releases_composer_body(tmp_path):
    service, request, _, _, _ = setup(tmp_path)
    renderer = CitationRenderer()

    class TamperedRenderer:
        def render_qa(self, source):
            rendered = renderer.render_qa(source)
            rendered.rendered_text += " Lợi nhuận giả 999 tỷ."
            return rendered

    service.renderer = TamperedRenderer()
    response = service.run(request)
    assert response.status == "firewall_blocked"
    assert "999" not in response.answer_vi and not response.citations
    assert not response.used_verified_claim_ids


def test_bounded_revision_reruns_all_checks(tmp_path):
    service, request, repo, _, source = setup(tmp_path)
    source.candidates[0].content = "Biên lợi nhuận gộp kỳ 2030 là 999,00%."
    response = service.run(request)
    assert response.newly_accepted_claims == 1, response
    entry = repo.list_all()[0]
    assert len(entry.history.contexts) == 2
    assert entry.history.outcome.attempts[0].decision == "REVISE"
    assert entry.decision.decision == "ACCEPT" and "999" not in response.answer_vi


def test_provider_failure_does_not_release_unverified_candidates(tmp_path):
    service, request, repo, _, source = setup(tmp_path)
    source.status = source.planner_result.status = "failed"
    metadata = source.usage.stages["planning"]
    metadata.calls = 1
    metadata.error = GatewayError(
        category="provider_unavailable",
        code="provider_unavailable",
        retryability="retryable",
        origin="provider",
        provider_error_code="http_503",
    )
    source.usage.stages = {"planning": metadata}
    response = service.run(request)
    assert response.status == "provider_unavailable" and response.mode == "PROVIDER_FAILURE"
    assert response.trace.provider_calls == 1 and response.trace.provider_errors
    assert not repo.list_all() and not response.used_verified_claim_ids
    assert response.trace.stages["m6"].status == "NOT_EXECUTED"


@pytest.mark.parametrize("mutation", ["no_assertion", "missing_evidence"])
def test_mixed_accept_and_nonaccept_preserves_verified_answer(tmp_path, mutation):
    service, request, repo, _, source = setup(tmp_path)
    bad = source.candidates[0].model_copy(deep=True)
    bad.candidate_id = "bad-candidate"
    if mutation == "no_assertion":
        bad.content = "Không có bằng chứng cho kết luận này."
        bad.kind = "supported_interpretation"
    else:
        bad.citations = []
    source.candidates.append(bad)
    response = service.run(request)
    assert response.newly_accepted_claims == 1, response
    assert response.rejected_claims + response.deferred_claims == 1
    assert len(repo.list_all()) == 1 and response.used_verified_claim_ids
    assert "Không có bằng chứng cho kết luận này" not in response.answer_vi


def test_partial_reuse_without_gateway_still_releases_verified_subset(tmp_path):
    service, request, _, m5, source = setup(tmp_path)
    assert service.run(request).used_verified_claim_ids
    request.question = "Biên lợi nhuận gộp và doanh thu TEST năm 2030?"
    request.allow_gateway = False
    partial = service.run(request)
    assert partial.status == "partial_verified_coverage"
    assert partial.mode == "PARTIAL_REUSE_ONLY" and partial.used_verified_claim_ids
    assert any(r.target_id == "b02.net_revenue" for r in partial.trace.unanswered_requirements)
    assert m5.run.call_count == 1
    request.allow_gateway = True
    source.status, source.candidates = "clarification_required", []
    stopped = service.run(request)
    assert stopped.status == "partial_verified_coverage" and stopped.used_verified_claim_ids
    assert stopped.trace.stages["m6"].status == "NOT_EXECUTED"


@pytest.mark.parametrize("existing", [False, True])
def test_conflicting_candidates_remain_nonadmitted(tmp_path, existing):
    service, request, repo, _, source = setup(tmp_path)
    if existing:
        assert service.run(request).used_verified_claim_ids
        request.force_refresh = True
    conflicting = source.candidates[0].model_copy(deep=True)
    conflicting.candidate_id = "conflicting-candidate"
    conflicting.content = "Biên lợi nhuận gộp kỳ 2030 là 999,00%."
    source.candidates.append(conflicting)
    source.conflicts = [
        CandidateConflict(
            conflict_id="conflict", candidate_ids=[c.candidate_id for c in source.candidates]
        )
    ]
    for candidate in source.candidates:
        candidate.conflict_ids = ["conflict"]
    response = service.run(request)
    assert response.status == "verification_blocked" and not response.used_verified_claim_ids
    assert response.deferred_claims + response.rejected_claims == 2
    assert len(repo.list_all()) == int(existing)
