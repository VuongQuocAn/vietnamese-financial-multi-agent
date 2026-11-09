"""Focused conversation controls; synthetic fixtures are engineering evidence only."""

from fastapi.testclient import TestClient
from vietnamese_financial_multi_agent.api.conversations import ConversationService
from vietnamese_financial_multi_agent.api.main import create_app
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.tools import QADocument

from .test_financial_qa_pipeline import setup


def ask(service, session, question, **kwargs):
    return service.send(session.conversation_id, FinancialQARequest(question=question, **kwargs))


def test_real_pipeline_followup_and_http_history(tmp_path):
    pipeline, _, _, _, _ = setup(tmp_path / "ledger")
    service = ConversationService(pipeline)
    app = create_app(storage_root=tmp_path / "web", conversation_service=service)
    with TestClient(app) as client:
        session = client.post("/api/conversations").json()
        url = f"/api/conversations/{session['conversation_id']}"
        first = client.post(
            url + "/messages",
            json={"question": "Biên lợi nhuận gộp TEST năm 2030?"},
        ).json()
        assert first["response"]["used_verified_claim_ids"], first
        second = client.post(
            url + "/messages", json={"question": "Công thức tính chỉ số này là gì?"}
        ).json()
        assert second["response"]["status"] == "completed_with_caveats", second
        assert second["response"]["citations"]
        assert second["response"]["trace"]["firewall_decision"] == "ALLOW_WITH_CAVEAT"
        assert second["response"]["trace"]["provider_calls"] == 0
        assert "topic" in second["inherited"]
        assert len(client.get(url).json()["turns"]) == 2
        assert client.get("/api/conversations/missing").status_code == 404
        assert client.post("/api/conversations").json()["turn_id"] == 0
        assert client.post(url + "/messages", json={"question": " "}).status_code == 422
    state = service.history(session["conversation_id"])
    state.topics.clear()
    assert service.history(session["conversation_id"]).topics


def test_resolution_switches_relative_year_scope_and_isolation(tmp_path):
    pipeline, request, _, _, _ = setup(tmp_path)
    pipeline.documents.append(
        QADocument(
            document_id="other",
            company_id="OTHER",
            company_aliases=["OTHER"],
            reporting_year=2029,
        )
    )
    service = ConversationService(pipeline)
    session = service.create()
    ask(service, session, request.question, execution_mode="deterministic")
    state = service.history(session.conversation_id)
    state.selected_context.composition_id = "document-composition"
    state.selected_context.composition_sha256 = "document-digest"
    state.selected_context.document_snapshots = ["document-source"]
    state.topics = ["doanh thu thuần"]
    bound, ctx, *_ = service._resolve(
        state, FinancialQARequest(question="So với năm trước thì sao?")
    )
    assert "Tăng trưởng doanh thu" in bound.question and "2030" in bound.question
    assert ctx.period == "2030"
    assert bound.composition_id is None and not bound.document_snapshots
    state.topics = ["Nhân viên quản lý chủ chốt"]
    state.reference_question = "Thuyết minh TEST 2030 nói gì về nhân viên quản lý chủ chốt?"
    bound, *_ = service._resolve(state, FinancialQARequest(question="Nội dung đó ở trang nào?"))
    from vietnamese_financial_multi_agent.tools.question_understanding import understand

    assert bound.period is None and understand(bound.question)[0].period is None
    state.topics = ["doanh thu thuần"]
    bound, *_ = service._resolve(state, FinancialQARequest(question="Còn UNKNOWN năm 2029?"))
    assert bound is None
    bound, ctx, *_ = service._resolve(state, FinancialQARequest(question="Còn OTHER năm 2029?"))
    assert ctx.company_id == "OTHER" and ctx.period == "2029"
    assert ctx.snapshot_id is None and ctx.document_id is None
    assert "TEST" not in bound.question
    bound, ctx, *_ = service._resolve(state, FinancialQARequest(question="Còn năm trước?"))
    assert ctx.period == "2029" and "2030" not in bound.question
    ask(service, session, "ROE OTHER 2029?", execution_mode="deterministic")
    assert not service.history(session.conversation_id).verified_claim_ids
    assert not service.history(session.conversation_id).topics
    other = service.create()
    result = ask(service, other, "Công thức chỉ số này?")
    assert result.response.status == "clarification_required"
    assert not result.context.company_id
    assert not ConversationService(pipeline)._sessions


def test_ambiguity_failure_and_unverified_targets_do_not_become_context(tmp_path):
    pipeline, _, _, _, _ = setup(tmp_path)
    service = ConversationService(pipeline, history_limit=2)
    session = service.create()
    for question in ("Doanh thu?", "ROE TEST 2030?", "Công thức chỉ số này?"):
        turn = ask(service, session, question, execution_mode="deterministic")
        assert not turn.response.used_verified_claim_ids
    state = service.history(session.conversation_id)
    assert not state.topics and not state.resolved_context
    assert state.turn_id == 3 and len(state.turns) == 2
    state.topics = ["doanh thu", "lợi nhuận gộp"]
    bound, *_, clarification = service._resolve(state, FinancialQARequest(question="Nó là gì?"))
    assert bound is None and clarification
    state.selected_context.reporting_scope = "separate"
    bound, ctx, *_ = service._resolve(state, FinancialQARequest(question="Doanh thu TEST 2030?"))
    assert ctx.reporting_scope == "separate" and "riêng" in bound.question
