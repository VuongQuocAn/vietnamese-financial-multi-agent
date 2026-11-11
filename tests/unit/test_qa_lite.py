"""Offline engineering controls; synthetic data is not financial acceptance."""

import json
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import JSONOutput
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway, _failure
from vietnamese_financial_multi_agent.outputs.qa_lite import (
    _numbers_supported,
    compose_lite,
    select_claims,
)
from vietnamese_financial_multi_agent.verification.ledger import build_verified_claim

from .test_financial_qa_pipeline import setup
from .test_verified_claim_ledger import history_for


@pytest.fixture
def admitted():
    entry = build_verified_claim(history_for())
    i = entry.identity
    request = FinancialQARequest(
        question=entry.content,
        company_id=i.company_id,
        document_id=i.document_id,
        snapshot_id=i.snapshot_id,
        period=i.period,
        m7_lite=True,
    )
    return request, entry


def gateway_for(body=None, error=None, malformed=False):
    calls = []

    def transport(request):
        calls.append(request)
        response = _failure(request, error or "timeout")
        if error == "provider_unavailable":
            response.error.origin = "provider"
            response.error.provider_error_code = "http_503"
        if malformed:
            response = _failure(request, "structured_output_invalid")
            response.status = "malformed"
            response.output = JSONOutput(
                format="json", raw_text="{", payload=None, validation_status="invalid_json"
            )
            return response
        if error is None:
            response.status = "success"
            response.error = None
            response.finish_reason = "stop"
            response.output = JSONOutput(
                format="json",
                raw_text=json.dumps(body),
                payload=body,
                validation_status="json_valid",
            )
        return response

    return SharedLLMGateway({"gemini": transport}), calls


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("decision", "not_m6_accept"),
        ("abstain", "not_m6_accept"),
        ("company_id", "scope_identity_mismatch"),
        ("snapshot_id", "scope_identity_mismatch"),
        ("period", "period_out_of_scope"),
        ("citation", "citation_source_mismatch"),
    ],
)
def test_selection_negative_controls_preserve_independent_claim(admitted, mutation, reason):
    request, entry = admitted
    bad = entry.model_copy(deep=True)
    bad.identity.verified_claim_id = "bad"
    if mutation in {"decision", "abstain"}:
        bad.decision.decision = "INVESTIGATE" if mutation == "decision" else "ABSTAIN"
    elif mutation == "citation":
        bad.citations[0].source.document_id = "foreign"
    else:
        setattr(bad.identity, mutation, "1999" if mutation == "period" else "foreign")
    selected, excluded = select_claims(request, [bad, entry])
    assert selected == [entry]
    contradictory = request.model_copy(update={"period": "1999"})
    assert not select_claims(contradictory, [entry])[0]
    assert excluded == [dict(claim_id="bad", reason=reason)]


def test_relevance_and_multi_period_not_coverage(admitted):
    request, entry = admitted
    selected, _ = select_claims(request, [entry])
    assert selected == [entry]
    request.answer_requirements = []  # Legacy coverage is not a release authority.
    comparative = entry.model_copy(deep=True)
    comparative.accepted_claim.supporting_evidence[0].operand_periods = {"prior": "1999"}
    assert (
        select_claims(request, [comparative])[1][0]["reason"] == "comparative_period_out_of_scope"
    )
    irrelevant = request.model_copy(update={"question": "Nợ phải trả và tổng tài sản năm 2030?"})
    assert not select_claims(irrelevant, [entry])[0]
    comparison = request.model_copy(
        update={
            "question": entry.content + " So sánh năm 2029 và 2030?",
            "period": None,
        }
    )
    previous = entry.model_copy(deep=True)
    previous.identity.period = "2029"
    assert len(select_claims(comparison, [entry, previous])[0]) == 2


@pytest.mark.parametrize(
    "variant", ["unknown_id", "fabricated_number", "paraphrase", "invalid_json"]
)
def test_known_errors_fallback_and_natural_paraphrase_releases(admitted, variant):
    request, entry = admitted
    key = entry.identity.verified_claim_id
    segment = dict(text=entry.content, claim_ids=[key])
    if variant == "unknown_id":
        segment["claim_ids"] = ["absent"]
    elif variant == "fabricated_number":
        segment["text"] = entry.content + " Số tiền 999999999 VND."
    elif variant == "paraphrase":
        segment["text"] = "Theo số liệu được xác minh, " + entry.content.replace(" là ", " đạt ")
    body = dict(segments=[segment], gaps=[]) if variant != "invalid_json" else {"wrong": True}
    gateway, calls = gateway_for(body, malformed=variant == "invalid_json")
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert len(calls) == 1 and calls[0].output_spec.schema_ref is None
    assert fields["used_verified_claim_ids"] == [key]
    if variant == "paraphrase":
        assert segment["text"] in fields["answer_vi"]
        assert trace["llm_segments_released"] == 1 and not trace["fallback"]
        return
    assert entry.content in fields["answer_vi"]
    assert "999999999" not in fields["answer_vi"]
    assert "Do đó chất lượng" not in fields["answer_vi"]
    assert trace["fallback"] and fields["status"] == "partial_verified_coverage"
    assert fields["citations"][0].source_citations[0] in entry.citations


@pytest.mark.parametrize("error", ["timeout", "provider_unavailable"])
def test_provider_failure_has_c_gap_and_no_retry(admitted, error):
    request, entry = admitted
    gateway, calls = gateway_for(error=error)
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert len(calls) == 1 and trace["calls"] == 1
    assert {g["type"] for g in trace["gaps"]} == {"C"}
    assert fields["used_verified_claim_ids"] and fields["citations"]


def test_numeric_integrity_supports_paraphrase_rounding_and_units_not_semantics():
    claim = SimpleNamespace(
        content="Năm 2025, tỷ lệ là 59,06%; lợi nhuận là 7.249.557.946 VND.",
        accepted_claim=SimpleNamespace(calculation=None, supporting_evidence=[]),
    )
    assert _numbers_supported("Tỷ lệ nợ đạt khoảng 59,1% vào năm 2025.", [claim])
    assert _numbers_supported("Lợi nhuận đạt khoảng 7,25 tỷ đồng.", [claim])
    assert not _numbers_supported("Tỷ lệ là 59,2%.", [claim])
    assert not _numbers_supported("Tỷ lệ là 59,06 VND.", [claim])
    assert not _numbers_supported("Năm 2026 là 59,1%.", [claim])
    assert not _numbers_supported("Kết quả là 999999999 VND.", [claim])
    # Numeric integrity deliberately cannot certify a financial conclusion.
    assert _numbers_supported("Tỷ lệ 59,06% chứng tỏ an toàn.", [claim])


def test_page_references_keep_exact_per_claim_source_bindings(admitted):
    request, entry = admitted
    other = entry.model_copy(deep=True)
    other.identity.verified_claim_id = "other-accepted"
    for number, e in enumerate([entry, other]):
        citation = e.citations[0].model_copy(deep=True)
        citation.source.reference.source_pointer += f"/variant-{number}"
        e.decision.supporting_citations = [citation]
        e.accepted_claim.citations = [citation]
    fields, trace = compose_lite(request, [entry, other])
    assert len(fields["citations"]) == 1
    reference = fields["citations"][0]
    assert len(reference.source_citations) == 2
    assert reference.source_locator.provenance_level == "page"
    assert reference.source_locator.element_id is None and reference.anchor_id is None
    assert set(reference.bound_verified_claim_ids) == {
        entry.identity.verified_claim_id,
        "other-accepted",
    }
    assert len(trace["citation_bindings"]) == 2
    assert (
        trace["citation_bindings"][0]["source_ids"] != trace["citation_bindings"][1]["source_ids"]
    )


def test_valid_segment_survives_other_bad_segment_and_omission(admitted):
    request, entry = admitted
    other = entry.model_copy(deep=True)
    other.identity.verified_claim_id = "other-accepted"
    key = entry.identity.verified_claim_id
    gateway, _ = gateway_for(
        dict(
            segments=[
                dict(text=entry.content, claim_ids=[key]),
                dict(text="Phân tích không có nguồn.", claim_ids=["absent"]),
            ],
            gaps=[],
        )
    )
    fields, trace = compose_lite(request, [entry, other], gateway=gateway)
    assert len(trace["rejected_segments"]) == 1
    assert trace["segments"][0] == dict(text=entry.content, claim_ids=[key])
    assert fields["used_verified_claim_ids"] == [key, "other-accepted"]


def test_empty_ledger_does_not_invent_sources_or_call_provider(admitted):
    request, _ = admitted
    gateway, calls = gateway_for({})
    fields, trace = compose_lite(request, [], gateway=gateway)
    assert not calls and not fields["citations"] and not fields["used_verified_claim_ids"]
    assert trace["gaps"][0]["type"] == "B"
    _, missing_source = compose_lite(request, [], source_available=False)
    assert missing_source["gaps"][0]["type"] == "A"


def test_lite_fresh_cache_refresh_failure_and_legacy_compatibility(tmp_path):
    service, request, repo, m5, result = setup(tmp_path)
    legacy = service.run(request)
    assert legacy.trace.answer_mode == "legacy" and not request.m7_lite
    lite_request = request.model_copy(update={"m7_lite": True, "allow_gateway": False})
    cached = service.run(lite_request)
    assert cached.used_verified_claim_ids == legacy.used_verified_claim_ids
    assert cached.trace.answer_mode == "lite" and cached.citations
    assert cached.status == "partial_verified_coverage"
    before = repo._path().read_bytes()
    result.status = "failed"
    failed = service.run(
        lite_request.model_copy(update={"force_refresh": True, "execution_mode": "deterministic"})
    )
    assert failed.used_verified_claim_ids == cached.used_verified_claim_ids
    assert repo._path().read_bytes() == before
    assert any(g["type"] == "C" for g in failed.trace.m7_lite["gaps"])
    # API wire round-trip keeps all existing fields and source locators.
    assert type(failed).model_validate_json(failed.model_dump_json()) == failed
    fresh_service, fresh_request, _, _, _ = setup(tmp_path / "fresh")
    fresh = fresh_service.run(fresh_request.model_copy(update={"m7_lite": True}))
    assert fresh.newly_accepted_claims == 1 and fresh.used_verified_claim_ids


def test_current_request_claims_survive_broad_question_but_keep_scope_checks(admitted):
    request, entry = admitted
    request.question = "Nhận xét tình hình tài chính năm " + entry.identity.period[:4]
    identity = entry.identity.verified_claim_id
    assert not select_claims(request, [entry])[0]
    assert select_claims(request, [entry], [identity])[0] == [entry]
    foreign = entry.model_copy(deep=True)
    foreign.identity.company_id = "foreign"
    selected, excluded = select_claims(request, [foreign], [identity])
    assert not selected
    assert excluded[0]["reason"] == "scope_identity_mismatch"
    bad_period = request.model_copy(update={"period": "1999"})
    assert not select_claims(bad_period, [entry], [identity])[0]
