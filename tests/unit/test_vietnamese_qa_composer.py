"""Synthetic engineering controls; BBS replay is reported separately."""

import json

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs import (
    VietnameseQAComposer,
    VietnameseQARequest,
    VietnameseQAResponse,
    validate_qa_response,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import SCOPE_CAVEAT
from vietnamese_financial_multi_agent.verification import (
    BoundedVerificationLoop,
    VerificationHistory,
    VerificationProofContext,
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)

from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_verification_judge import case, passes
from .test_verified_claim_ledger import history_for


def admitted_history(data, *, extra_caveat=None):
    batch = batch_for(data)
    if extra_caveat:
        batch.caveats.append(extra_caveat)
    validation, evidence, logic = passes(data, batch)
    return VerificationHistory(
        contexts=[
            VerificationProofContext(
                batch=batch, validation=validation, evidence=evidence, logic=logic
            )
        ],
        outcome=BoundedVerificationLoop().start(
            batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
        ),
    )


@pytest.fixture
def qa(tmp_path):
    repository = VerifiedClaimRepository(tmp_path)
    data, *_ = case()
    data["facts"].sort(key=lambda f: f.canonical_item_id != "b02.net_revenue")
    history = admitted_history(data)
    histories = [history, history_for(metric=True)]
    assert all(r.status == "stored" for r in repository.admit_many(histories))
    entry = repository.list_all()[0]
    context = dict(
        company_id=entry.identity.company_id,
        document_id=entry.identity.document_id,
        snapshot_id=entry.identity.snapshot_id,
        period=entry.identity.period,
    )
    return repository, VerifiedClaimLedger(repository), context


def test_contract_single_multi_partial_roundtrip_and_read_only_stability(qa):
    repository, ledger, context = qa
    before = (repository.root / "verified-claims.json").read_bytes()
    composer = VietnameseQAComposer(ledger)
    for question, status, count in (
        ("Doanh thu là bao nhiêu?", "answered", 1),
        ("Biên lợi nhuận gộp là bao nhiêu?", "answered", 1),
        ("Doanh thu và biên lợi nhuận gộp?", "answered", 2),
        ("Doanh thu và ROE?", "partial", 1),
        ("Doanh thu và tổng tài sản?", "partial", 1),
        ("Doanh thu và những hạn chế của dữ liệu?", "answered", 2),
    ):
        request = VietnameseQARequest(question=question, **context)
        response = composer.compose(request)
        assert response.status == status, response
        assert len(response.answered_requirements) == count
        assert response.validation_result.valid
        assert response == composer.compose(request)
        assert VietnameseQAResponse.model_validate_json(response.model_dump_json()) == response
        assert SCOPE_CAVEAT in response.caveats
        for segment in response.grounded_segments:
            entry = repository.get(segment.verified_claim_ids[0])
            assert segment.content == entry.content
            assert segment.citations == entry.citations
            assert set(entry.caveats) <= set(segment.caveats)
            assert set(entry.decision.limitations) <= set(segment.limitations)
    assert before == (repository.root / "verified-claims.json").read_bytes()
    with pytest.raises(ValidationError):
        VietnameseQARequest(question="   ")
    with pytest.raises(ValidationError):
        VietnameseQARequest(question="Doanh thu?", raw_facts=[])


@pytest.mark.parametrize(
    "question,patch,status",
    [
        ("Tổng tài sản?", {}, "abstained"),
        ("ROE?", {}, "unsupported"),
        ("Lợi nhuận?", {}, "clarification_required"),
        ("Phân tích khả năng sinh lời và cơ cấu nợ", {}, "clarification_required"),
        ("Doanh thu?", {"snapshot_id": None}, "clarification_required"),
        ("Doanh thu?", {"snapshot_id": "wrong"}, "abstained"),
        ("Doanh thu?", {"document_id": "wrong"}, "abstained"),
        ("Doanh thu?", {"period": "1999"}, "abstained"),
        ("Doanh thu hợp nhất?", {}, "abstained"),
        ("Doanh thu bản recovery?", {}, "clarification_required"),
        ("So sánh doanh thu 2024 và 2025", {}, "unsupported"),
        ("Vì sao doanh thu tăng?", {}, "unsupported"),
        ("Doanh thu tài chính?", {}, "unsupported"),
    ],
)
def test_missing_ambiguous_and_unsupported_requirements(qa, question, patch, status):
    _, ledger, context = qa
    response = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question=question, **(context | patch))
    )
    assert response.status == status, response
    assert not response.grounded_segments and not response.citations
    assert response.validation_result.valid


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "malformed",
        "new_value",
        "new_citation",
        "new_claim",
        "reasoning",
        "drop_caveats",
        "duplicate",
        "timeout",
        "503",
    ],
)
def test_gateway_slots_and_adversarial_fallback_once(qa, mode):
    _, ledger, context = qa
    calls = []

    def transport(request):
        calls.append(request)
        assert request.constraints.timeout_seconds == 45
        assert request.generation.max_output_tokens == 1600
        assert len(request.messages[0].content.encode("utf-8")) <= 24000
        payload = json.loads(request.messages[0].content)
        assert "history" not in request.messages[0].content
        ids = [e["verified_claim_id"] for e in payload["selected_claims"]]
        wire = dict(claim_order=list(reversed(ids)), introduction="by_requirement")
        if mode in ("timeout", "503"):
            if mode == "timeout":
                raise TimeoutError
            raise RuntimeError("provider 503")
        if mode == "new_value":
            wire["financial_value"] = "999"
        if mode == "new_citation":
            wire["citations"] = ["invented"]
        if mode == "new_claim":
            wire["claim_order"] = ["invented"]
        if mode == "reasoning":
            wire["introduction"] = "Doanh nghiệp tốt vì doanh thu tăng"
        if mode == "drop_caveats":
            wire["caveats"] = []
        if mode == "duplicate":
            wire["claim_order"] = [ids[0], ids[0]]
        return FakeLLMTransport(json_text="{" if mode == "malformed" else json.dumps(wire))(request)

    gateway = SharedLLMGateway({"gemini": transport})
    response = VietnameseQAComposer(ledger, gateway).compose(
        VietnameseQARequest(
            question="Doanh thu và biên lợi nhuận gộp?", allow_gateway=True, **context
        )
    )
    assert len(calls) == response.llm_metadata.calls == 1
    assert response.llm_metadata.status == ("accepted" if mode == "valid" else "fallback")
    assert response.status == "answered" and response.validation_result.valid
    assert "999" not in response.answer_vi and "invented" not in response.model_dump_json()
    assert SCOPE_CAVEAT in response.answer_vi


@pytest.mark.parametrize(
    "mutation", ["text", "value", "citation", "caveat", "context", "id", "status"]
)
def test_local_gate_rejects_tampered_protected_output(qa, mutation):
    _, ledger, context = qa
    response = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question="Doanh thu?", **context)
    )
    segment = response.grounded_segments[0]
    if mutation == "text":
        response.answer_vi += " Doanh nghiệp có tài chính tốt."
    elif mutation == "value":
        segment.content += " 999"
    elif mutation == "citation":
        segment.citations[0].pdf_page = 999
    elif mutation == "caveat":
        response.caveats = []
    elif mutation == "context":
        segment.context.snapshot_id = "recovery"
    elif mutation == "id":
        response.used_verified_claim_ids = ["unknown"]
    elif mutation == "status":
        response.status = "abstained"
    assert not validate_qa_response(response, ledger.find_claims(VerifiedClaimQuery()).claims).valid


def test_empty_ledger_never_falls_back_to_m4_or_m5(tmp_path, monkeypatch):
    from vietnamese_financial_multi_agent.tools.financial_calculator import FinancialCalculator
    from vietnamese_financial_multi_agent.tools.financial_retrieval import FinancialRetrievalTools

    def forbidden(*args, **kwargs):
        pytest.fail("unverified_tool_used")

    monkeypatch.setattr(FinancialCalculator, "calculate_financial_metric", forbidden)
    monkeypatch.setattr(FinancialRetrievalTools, "find_financial_facts", forbidden)
    composer = VietnameseQAComposer(VerifiedClaimLedger(VerifiedClaimRepository(tmp_path)))
    response = composer.compose(
        VietnameseQARequest(
            question="Doanh thu?", document_id="doc", snapshot_id="snapshot", allow_gateway=True
        )
    )
    assert response.status == "abstained" and response.llm_metadata.calls == 0


def test_wrong_context_returned_by_facade_fails_closed(qa):
    _, ledger, context = qa

    class WrongLedger:
        def find_claims(self, query):
            return ledger.find_claims(VerifiedClaimQuery())

    response = VietnameseQAComposer(WrongLedger()).compose(
        VietnameseQARequest(question="Doanh thu?", **(context | {"snapshot_id": "recovery"}))
    )
    assert response.status == "abstained" and not response.grounded_segments
    assert "retrieval_context_mismatch" in response.reasons


def test_duplicate_verified_assertions_preserve_all_caveats_and_identity(qa):
    repository, ledger, context = qa
    data = fixture()
    data["facts"].sort(key=lambda f: f.canonical_item_id != "b02.net_revenue")
    extra = "additional_source_limitation"
    assert repository.admit(admitted_history(data, extra_caveat=extra)).status == "stored"
    response = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question="Doanh thu?", **context)
    )
    assert response.status == "answered" and response.validation_result.valid
    assert len(response.used_verified_claim_ids) == 2
    assert len(response.grounded_segments) == 1
    assert extra in response.grounded_segments[0].caveats and extra in response.answer_vi


def test_multi_intent_different_periods_requires_clarification(qa):
    original, _, context = qa
    repository = VerifiedClaimRepository(original.root / "different-periods")
    # Prior-year source is independently admitted through M6; never invent a ledger entry.
    data = fixture("revenue_yoy")
    data["facts"].sort(key=lambda f: f.context.period)
    assert repository.admit(admitted_history(data)).status == "stored"
    assert repository.admit(history_for(metric=True)).status == "stored"
    ledger = VerifiedClaimLedger(repository)
    context.pop("period")
    response = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question="Doanh thu và biên lợi nhuận gộp?", **context)
    )
    assert response.status == "clarification_required" and not response.grounded_segments
    assert response.validation_result.valid
