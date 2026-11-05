"""Synthetic engineering controls; financial research evidence is evaluated separately."""

import json

import pytest
from jsonschema import validate as validate_schema
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs import (
    GroundedFinancialReport,
    GroundedReportRequest,
    GroundedReportWriter,
    ReportOutlinePlanner,
    ReportOutlineRequest,
    validate_grounded_report,
)
from vietnamese_financial_multi_agent.outputs.grounded_report_writer import _retrieve
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)

from .test_vietnamese_qa_composer import qa as qa_fixture


@pytest.fixture
def qa(tmp_path):
    return qa_fixture.__wrapped__(tmp_path)


def request_for(ledger, context, **kwargs):
    original = ReportOutlineRequest(**(context | kwargs))
    return GroundedReportRequest(
        outline=ReportOutlinePlanner(ledger).plan(original), outline_request=original
    )


def test_typed_general_focused_partial_empty_and_immutability(qa, tmp_path):
    repository, ledger, context = qa
    before = (repository.root / "verified-claims.json").read_bytes()
    for options, expected in (
        ({}, "partial"),
        ({"report_type": "profitability"}, "generated"),
        ({"report_type": "liquidity_and_leverage"}, "abstained"),
        ({"report_type": "cash_flow_and_earnings_quality"}, "abstained"),
        (
            {
                "report_type": "focused_analysis",
                "requested_sections": ["profitability", "cash_flow"],
            },
            "partial",
        ),
        ({"period": None}, "clarification_required"),
        ({"title": "So sánh 2024 và 2025"}, "unsupported"),
        ({"snapshot_id": "recovery"}, "abstained"),
    ):
        request = request_for(ledger, context, **options)
        original = request.model_dump_json()
        report = GroundedReportWriter(ledger).write(request)
        assert report.status == expected
        assert report.validation_result.valid, report.validation_result
        assert report == GroundedFinancialReport.model_validate_json(report.model_dump_json())
        assert report == GroundedReportWriter(ledger).write(request)
        assert original == request.model_dump_json()
        if report.sections:
            assert report.sections[0].section_id == "scope"
            assert report.sections[-1].section_id == "limitations"
            assert "chưa được xác nhận" in report.body_vi
            financial = [p for s in report.sections for p in s.paragraphs if p.source_slot_ids]
            assert all(p.citations and p.context and p.verified_claim_ids for p in financial)
            assert not any(p.paragraph_type == "verified_interpretation" for p in financial)
    assert before == (repository.root / "verified-claims.json").read_bytes()
    with pytest.raises(ValidationError):
        GroundedReportRequest.model_validate({**request.model_dump(), "raw_facts": []})
    request.outline.sections = ["invalid"]
    with pytest.warns(UserWarning), pytest.raises(ValidationError):
        GroundedReportWriter(ledger).write(request)
    empty = VerifiedClaimLedger(VerifiedClaimRepository(tmp_path / "empty"))
    report = GroundedReportWriter(empty).write(request_for(empty, context))
    assert report.status == "abstained" and not report.citations


@pytest.mark.parametrize(
    "mutation",
    [
        "id",
        "content",
        "citation",
        "caveat",
        "limitation",
        "source",
        "snapshot",
        "period",
        "role",
        "kind",
        "title",
        "extra_section",
        "status",
    ],
)
def test_tampered_outline_fails_closed_even_with_forged_validation(qa, mutation):
    _, ledger, context = qa
    request = request_for(ledger, context)
    outline = request.outline
    section = next(s for s in outline.sections if s.claim_slots)
    slot = section.claim_slots[0]
    if mutation == "id":
        slot.verified_claim_ids = ["fabricated"]
    elif mutation == "content":
        slot.accepted_content += " Doanh nghiệp tăng trưởng tốt."
    elif mutation == "citation":
        slot.citations[0].document_id = "other"
    elif mutation == "caveat":
        slot.caveats = []
    elif mutation == "limitation":
        outline.limitations = []
    elif mutation == "source":
        slot.claim_context.document_id = "other"
    elif mutation == "snapshot":
        slot.claim_context.snapshot_id = "recovery"
    elif mutation == "period":
        slot.claim_context.period = "2025-12-31"
    elif mutation == "role":
        slot.period_role = "closing_balance"
    elif mutation == "kind":
        slot.claim_kind = "supported_interpretation"
    elif mutation == "title":
        section.title_vi = "Doanh nghiệp có tài chính an toàn"
    elif mutation == "extra_section":
        outline.sections.insert(1, section.model_copy(deep=True))
    elif mutation == "status":
        outline.status = "ready"
    outline.validation_result.valid = True
    request.allow_gateway = True

    def forbidden(_):
        pytest.fail("gateway_before_outline_validation")

    report = GroundedReportWriter(ledger, SharedLLMGateway({"gemini": forbidden})).write(request)
    assert report.status == "abstained" and not report.validation_result.valid
    assert not report.sections and not report.used_verified_claim_ids and not report.citations


def fake(request, mode):
    if mode == "timeout":
        raise TimeoutError
    payload = json.loads(request.messages[0].content)
    validate_schema(payload["example"], payload["schema"])
    proposal = payload["example"]
    populated = next(s for s in proposal["sections"] if s["paragraphs"])
    group = populated["paragraphs"][0]
    if mode == "valid":
        group["slot_indexes"].reverse()
    elif mode == "section":
        populated["section_index"] = 999
    elif mode == "slot":
        group["slot_indexes"] = [999]
    elif mode == "duplicate":
        group["slot_indexes"] *= 2
    elif mode == "missing":
        populated["paragraphs"] = []
    elif mode == "transition":
        group["transition"] = "excellent_company"
    elif mode == "interpretation":
        group["transition"] = "interpretation"
    elif mode == "move":
        proposal["sections"][0]["paragraphs"] = populated["paragraphs"]
        populated["paragraphs"] = []
    elif mode == "order":
        proposal["sections"].reverse()
    elif mode in ("prose", "calculation", "citation", "caveats", "context"):
        proposal[mode] = "Lợi nhuận tăng 999%; doanh nghiệp an toàn [trang 999]"
    response = FakeLLMTransport(json_text="{" if mode == "malformed" else json.dumps(proposal))(
        request
    )
    if mode == "503":
        response.status, response.finish_reason, response.output = "error", "error", None
        response.error = GatewayError(
            category="provider_unavailable",
            code="provider_unavailable",
            origin="provider",
            provider_error_code="http_503",
            retryability="retryable",
        )
    return response


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "section",
        "slot",
        "duplicate",
        "missing",
        "transition",
        "interpretation",
        "move",
        "order",
        "prose",
        "calculation",
        "citation",
        "caveats",
        "context",
        "malformed",
        "timeout",
        "503",
    ],
)
def test_bounded_gateway_grouping_and_deterministic_fallback(qa, mode):
    _, ledger, context = qa
    request = request_for(ledger, context, report_type="profitability")
    baseline = GroundedReportWriter(ledger).write(request)
    calls = []

    def transport(bound):
        calls.append(bound)
        assert bound.generation.max_output_tokens == 2048
        assert bound.generation.temperature == 0
        assert bound.constraints.timeout_seconds == 45
        assert len(bound.messages[0].content.encode()) <= 32000
        assert '"history"' not in bound.messages[0].content
        return fake(bound, mode)

    request.allow_gateway = True
    report = GroundedReportWriter(ledger, SharedLLMGateway({"gemini": transport})).write(request)
    assert len(calls) == report.llm_metadata.calls == 1
    assert report.validation_result.valid
    assert report.used_verified_claim_ids == baseline.used_verified_claim_ids
    assert report.citations == baseline.citations and report.caveats == baseline.caveats
    assert report.llm_metadata.status == ("accepted" if mode == "valid" else "fallback")
    if mode != "valid":
        assert report.body_vi == baseline.body_vi
        assert report.sections == baseline.sections
    if mode == "503":
        assert report.llm_metadata.error.provider_error_code == "http_503"


@pytest.mark.parametrize(
    "mutation",
    [
        "content",
        "body",
        "citation",
        "caveat",
        "limitation",
        "context",
        "ids",
        "missing",
        "status",
        "scope",
        "paragraph",
        "title",
        "kind",
        "section_caveat",
    ],
)
def test_local_validator_rejects_text_and_every_protected_binding(qa, mutation):
    _, ledger, context = qa
    request = request_for(ledger, context)
    report = GroundedReportWriter(ledger).write(request)
    paragraph = next(p for s in report.sections for p in s.paragraphs if p.source_slot_ids)
    if mutation == "content":
        paragraph.text_vi += " Điều này chứng tỏ tăng trưởng mạnh."
    elif mutation == "body":
        report.body_vi += " Khuyến nghị đầu tư."
    elif mutation == "citation":
        paragraph.citations[0].document_id = "fabricated"
    elif mutation == "caveat":
        paragraph.caveats = []
    elif mutation == "limitation":
        report.limitations = []
    elif mutation == "context":
        paragraph.context[0].claim_context.period = "2024"
    elif mutation == "ids":
        paragraph.verified_claim_ids = ["fabricated"]
    elif mutation == "missing":
        paragraph.source_slot_ids = []
    elif mutation == "status":
        report.status = "generated"
    elif mutation == "scope":
        report.scope.snapshot_id = "recovery"
    elif mutation == "paragraph":
        report.sections[1].paragraphs.append(paragraph.model_copy(deep=True))
    elif mutation == "title":
        report.report_title = "Tài chính vững mạnh"
    elif mutation == "kind":
        paragraph.paragraph_type = "verified_interpretation"
    elif mutation == "section_caveat":
        report.sections[-1].caveats = []
    report.validation_result.valid = True
    assert not validate_grounded_report(
        report, _retrieve(ledger, request.outline_request), request
    ).valid


def test_writer_preserves_explicit_closing_date_and_duplicate_caveats(qa):
    from vietnamese_financial_multi_agent.verification import (
        BoundedVerificationLoop,
        VerificationHistory,
        VerificationProofContext,
    )

    from .test_financial_validators import batch_for
    from .test_m4_execution import fixture
    from .test_verification_judge import passes
    from .test_vietnamese_qa_composer import admitted_history

    repository, ledger, context = qa
    data = fixture("debt_to_assets")
    batch = batch_for(data, metric=True)
    validation, evidence, logic = passes(data, batch)
    repository.admit(
        VerificationHistory(
            contexts=[
                VerificationProofContext(
                    batch=batch, validation=validation, evidence=evidence, logic=logic
                )
            ],
            outcome=BoundedVerificationLoop().start(
                batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
            ),
        )
    )
    data = fixture()
    data["facts"].sort(key=lambda f: f.canonical_item_id != "b02.net_revenue")
    repository.admit(admitted_history(data, extra_caveat="additional_source_limitation"))
    request = request_for(ledger, context, period_context={"period_end": "2030-12-31"})
    report = GroundedReportWriter(ledger).write(request)
    assert report.validation_result.valid and "Tại ngày 2030-12-31" in report.body_vi
    assert report.scope.period == "2030" and report.scope.included_periods == ["2030", "2030-12-31"]
    paragraphs = [p for s in report.sections for p in s.paragraphs if p.source_slot_ids]
    assert any(len(p.verified_claim_ids) > len(p.source_slot_ids) for p in paragraphs)
    assert "additional_source_limitation" in report.caveats
    for section in request.outline.sections:
        for slot in section.claim_slots:
            assert sum(p.text_vi.count(slot.accepted_content) for p in paragraphs) == 1


def test_budget_language_and_read_failure_do_not_call_gateway(qa):
    _, ledger, context = qa
    request = request_for(ledger, context)
    request.language = "en"
    assert GroundedReportWriter(ledger).write(request).status == "unsupported"

    class FailedLedger:
        def find_claims(self, query):
            raise OSError("read failure")

    assert GroundedReportWriter(FailedLedger()).write(request).reasons == ["ledger_read_failed"]
    # A detached engineering projection with long accepted content, never real evidence.
    entries = ledger.find_claims(VerifiedClaimQuery(**context)).claims
    for entry in entries:
        entry.accepted_claim.content += "x" * 33000

    class LargeLedger:
        def find_claims(self, query):
            return type("Matches", (), {"claims": entries})()

    large = LargeLedger()
    request = request_for(large, context)
    request.allow_gateway = True

    def forbidden(_):
        pytest.fail("projection_budget_not_enforced")

    result = GroundedReportWriter(large, SharedLLMGateway({"gemini": forbidden})).write(request)
    assert result.validation_result.valid
    assert result.llm_metadata.reason == "projection_budget_exceeded"
    assert result.llm_metadata.calls == 0


def test_equivalent_wordings_render_once_keep_all_bindings_and_cannot_be_split(qa):
    from vietnamese_financial_multi_agent.verification import (
        BoundedVerificationLoop,
        VerificationHistory,
        VerificationProofContext,
    )

    from .test_financial_validators import batch_for
    from .test_m4_execution import fixture
    from .test_verification_judge import passes

    repository, ledger, context = qa
    data = fixture()
    data["facts"].sort(key=lambda f: f.canonical_item_id != "b02.net_revenue")
    batch = batch_for(data)
    batch.claims[0].content = batch.claims[0].content.replace(" là ", " đạt ")
    batch.caveats.append("variant_mandatory_caveat")
    validation, evidence, logic = passes(data, batch)
    admission = repository.admit(
        VerificationHistory(
            contexts=[
                VerificationProofContext(
                    batch=batch, validation=validation, evidence=evidence, logic=logic
                )
            ],
            outcome=BoundedVerificationLoop().start(
                batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
            ),
        )
    )
    assert admission.status == "stored"
    request = request_for(ledger, context, report_type="profitability")
    report = GroundedReportWriter(ledger).write(request)
    slots = next(s.claim_slots for s in request.outline.sections if s.claim_slots)
    facts = [s for s in slots if s.claim_kind == "fact"]
    assert len(facts) == 2
    assert sum(s.accepted_content in report.body_vi for s in facts) == 1
    paragraph = next(
        p
        for s in report.sections
        for p in s.paragraphs
        if admission.verified_claim_id in p.verified_claim_ids
    )
    assert {s.slot_id for s in facts} <= set(paragraph.source_slot_ids)
    assert "variant_mandatory_caveat" in paragraph.caveats
    assert report.validation_result.valid
    request.allow_gateway = True

    def split(bound):
        proposal = json.loads(bound.messages[0].content)["example"]
        section = next(s for s in proposal["sections"] if s["paragraphs"])
        indexes = [i for g in section["paragraphs"] for i in g["slot_indexes"]]
        section["paragraphs"] = [dict(slot_indexes=[i], transition="evidence") for i in indexes]
        return FakeLLMTransport(json_text=json.dumps(proposal))(bound)

    fallback = GroundedReportWriter(ledger, SharedLLMGateway({"gemini": split})).write(request)
    assert fallback.llm_metadata.status == "fallback" and fallback.body_vi == report.body_vi
    # Same wording/typed premises but a different citation identity is NOT merged.
    from vietnamese_financial_multi_agent.outputs.grounded_report_writer import _equivalences

    facts[0].citations = [
        c.model_copy(update={"anchor_id": "different-source"}) for c in facts[0].citations
    ]
    keys = _equivalences(request.outline, _retrieve(ledger, request.outline_request))
    assert keys[facts[0].slot_id] != keys[facts[1].slot_id]
