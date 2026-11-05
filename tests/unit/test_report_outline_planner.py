"""Synthetic engineering checks; saved BBS oracle evaluation is separate."""

import json

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.outputs import (
    GroundedReportOutline,
    ReportOutlinePlanner,
    ReportOutlineRequest,
    validate_report_outline,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import SCOPE_CAVEAT
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimLedger,
    VerifiedClaimQuery,
    VerifiedClaimRepository,
)

from .test_m4_execution import fixture
from .test_vietnamese_qa_composer import admitted_history
from .test_vietnamese_qa_composer import qa as qa_fixture


@pytest.fixture
def qa(tmp_path):
    return qa_fixture.__wrapped__(tmp_path)


def test_general_focused_partial_and_contract_immutability(qa):
    repository, ledger, context = qa
    planner = ReportOutlinePlanner(ledger)
    before = (repository.root / "verified-claims.json").read_bytes()
    for report_type, sections, status in (
        ("general_financial_analysis", [], "partial"),
        ("profitability", [], "ready"),
        ("focused_analysis", ["overview"], "ready"),
        ("focused_analysis", ["profitability", "cash_flow"], "partial"),
        ("liquidity_and_leverage", [], "abstained"),
    ):
        request = ReportOutlineRequest(
            report_type=report_type, requested_sections=sections, **context
        )
        request_before = request.model_dump_json()
        response = planner.plan(request)
        assert response.status == status, response
        assert response.validation_result.valid
        assert response == planner.plan(request)
        assert request.model_dump_json() == request_before
        assert GroundedReportOutline.model_validate_json(response.model_dump_json()) == response
        if status != "abstained":
            assert SCOPE_CAVEAT in response.caveats
            assert response.scope.reporting_scope is None
            assert response.used_verified_claim_ids
    assert before == (repository.root / "verified-claims.json").read_bytes()
    for patch in ({"requested_sections": ["invented"]}, {"raw_facts": []}, {"period": " "}):
        with pytest.raises(ValidationError):
            ReportOutlineRequest.model_validate(context | patch)


@pytest.mark.parametrize(
    "patch,status",
    [
        ({"period": None}, "clarification_required"),
        ({"company_id": None}, "clarification_required"),
        ({"snapshot_id": None}, "clarification_required"),
        ({"document_id": None}, "clarification_required"),
        ({"snapshot_id": "recovery"}, "abstained"),
        ({"document_id": "wrong"}, "abstained"),
        ({"period": "1999"}, "abstained"),
        ({"period": "2024,2025"}, "unsupported"),
        ({"title": "So sánh BBS 2024 và 2025"}, "unsupported"),
        ({"title": "Chứng minh tài chính an toàn"}, "unsupported"),
        ({"title": "ROE"}, "unsupported"),
        ({"title": "Báo cáo hợp nhất"}, "clarification_required"),
        ({"reporting_scope": "consolidated"}, "clarification_required"),
        ({"language": "en"}, "unsupported"),
        ({"report_type": "focused_analysis"}, "clarification_required"),
    ],
)
def test_scope_missing_and_unsupported(qa, patch, status):
    _, ledger, context = qa
    result = ReportOutlinePlanner(ledger).plan(ReportOutlineRequest(**(context | patch)))
    assert result.status == status, result
    assert not result.used_verified_claim_ids and not result.citations
    assert result.validation_result.valid


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "section",
        "slot",
        "duplicate",
        "missing",
        "move_slot",
        "title",
        "prose",
        "citation",
        "caveats",
        "scope",
        "malformed",
        "timeout",
        "503",
        "position",
    ],
)
def test_gateway_permutations_and_fallback(qa, mode):
    _, ledger, context = qa
    calls = []

    def transport(request):
        calls.append(request)
        assert request.generation.temperature == 0
        assert request.generation.max_output_tokens == 1600
        assert request.constraints.timeout_seconds == 45
        assert len(request.messages[0].content.encode()) <= 24000
        assert '"history"' not in request.messages[0].content
        payload = json.loads(request.messages[0].content)
        wire = {
            "sections": [
                dict(
                    section_id=s["section_id"],
                    slot_order=[slot["slot_id"] for slot in reversed(s["slots"])],
                )
                for s in payload["sections"]
            ]
        }
        sections = wire["sections"]
        populated = next(s for s in sections if s["slot_order"])
        if mode == "section":
            sections[1]["section_id"] = "invented"
        elif mode == "slot":
            populated["slot_order"] = ["invented"]
        elif mode == "duplicate":
            populated["slot_order"] *= 2
        elif mode == "missing":
            populated["slot_order"] = []
        elif mode == "move_slot":
            sections[0]["slot_order"] = populated["slot_order"]
            populated["slot_order"] = []
        elif mode == "position":
            sections.reverse()
        elif mode in ("title", "prose", "citation", "caveats", "scope"):
            wire[mode] = "Doanh nghiệp tăng trưởng mạnh 999"
        elif mode == "timeout":
            raise TimeoutError
        elif mode == "503":
            raise RuntimeError("http503")
        return FakeLLMTransport(json_text="{" if mode == "malformed" else json.dumps(wire))(request)

    request = ReportOutlineRequest(report_type="profitability", allow_gateway=True, **context)
    baseline = ReportOutlinePlanner(ledger).plan(request)
    result = ReportOutlinePlanner(ledger, SharedLLMGateway({"gemini": transport})).plan(request)
    assert len(calls) == result.llm_metadata.calls == 1
    assert result.llm_metadata.status == ("accepted" if mode == "valid" else "fallback")
    assert result.validation_result.valid
    assert result.used_verified_claim_ids == baseline.used_verified_claim_ids
    assert result.citations == baseline.citations and result.caveats == baseline.caveats
    if mode != "valid":
        assert result.sections == baseline.sections


@pytest.mark.parametrize(
    "mutation",
    [
        "id",
        "content",
        "citation",
        "caveat",
        "limit",
        "context",
        "kind",
        "role",
        "title",
        "objective",
        "status",
        "section_id",
        "slot_id",
        "omitted",
        "report_scope",
    ],
)
def test_validator_rejects_full_protected_field_tampering(qa, mutation):
    _, ledger, context = qa
    request = ReportOutlineRequest(report_type="profitability", **context)
    result = ReportOutlinePlanner(ledger).plan(request)
    section = next(s for s in result.sections if s.claim_slots)
    slot = section.claim_slots[0]
    if mutation == "id":
        slot.verified_claim_ids = ["invented"]
    elif mutation == "content":
        slot.accepted_content += " 999"
    elif mutation == "citation":
        slot.citations[0].pdf_page = 999
    elif mutation == "caveat":
        slot.caveats = []
    elif mutation == "limit":
        result.limitations = []
    elif mutation == "context":
        slot.claim_context.snapshot_id = "wrong"
    elif mutation == "kind":
        slot.claim_kind = "supported_interpretation"
    elif mutation == "role":
        slot.suggested_role = "supporting_context"
    elif mutation == "title":
        section.title_vi = "Khả năng sinh lời tăng mạnh"
    elif mutation == "objective":
        section.purpose = "Tính ROE để chứng minh tăng trưởng"
    elif mutation == "status":
        result.status = "abstained"
    elif mutation == "section_id":
        section.section_id = "cash_flow"
    elif mutation == "slot_id":
        slot.slot_id = "invented"
    elif mutation == "omitted":
        result.omitted_sections = []
    elif mutation == "report_scope":
        result.scope.reporting_scope = "consolidated"
    assert not validate_report_outline(
        result, ledger.find_claims(VerifiedClaimQuery(**context)).claims, request
    ).valid


def test_equivalent_caveat_union_and_conflict_exclusion(qa):
    repository, ledger, context = qa
    data = fixture()
    data["facts"].sort(key=lambda f: f.canonical_item_id != "b02.net_revenue")
    assert (
        repository.admit(admitted_history(data, extra_caveat="additional_source_limitation")).status
        == "stored"
    )
    result = ReportOutlinePlanner(ledger).plan(
        ReportOutlineRequest(report_type="profitability", **context)
    )
    assert len(result.used_verified_claim_ids) == 3
    assert "additional_source_limitation" in result.caveats
    slots = [slot for s in result.sections for slot in s.claim_slots]
    assert len(slots) == 2 and any(len(s.verified_claim_ids) == 2 for s in slots)
    # Detached facade attack: same accepted value with a different source selector.
    # This injection is not admitted and is not counted as real-source coverage.
    entries = ledger.find_claims(VerifiedClaimQuery(**context)).claims
    injected = next(e for e in entries if e.identity.kind == "fact").model_copy(deep=True)
    injected.identity.verified_claim_id = "injected:conflict"
    reference = injected.accepted_claim.supporting_evidence[0].reference
    reference.observation = reference.observation.model_copy(update={"local_id": "other-source"})

    class ConflictLedger:
        def find_claims(self, query):
            return type("Matches", (), {"claims": [*entries, injected]})()

    conflict = ReportOutlinePlanner(ConflictLedger()).plan(
        ReportOutlineRequest(report_type="profitability", **context)
    )
    assert conflict.status == "partial"
    assert "conflicting_verified_claims" in conflict.reasons
    assert all(
        s.claim_kind == "approved_metric"
        for section in conflict.sections
        for s in section.claim_slots
    )


def test_bad_retrieval_empty_ledger_and_budget(qa, tmp_path, monkeypatch):
    _, ledger, context = qa

    def forbidden(*args, **kwargs):
        pytest.fail("unverified_tool_used")

    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.tools.financial_calculator.FinancialCalculator.calculate_financial_metric",
        forbidden,
    )
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.tools.financial_retrieval.FinancialRetrievalTools.find_financial_facts",
        forbidden,
    )
    request = ReportOutlineRequest(**context)
    empty = ReportOutlinePlanner(
        VerifiedClaimLedger(VerifiedClaimRepository(tmp_path / "empty"))
    ).plan(request)
    assert empty.status == "abstained" and not empty.citations

    class WrongLedger:
        def find_claims(self, query):
            return ledger.find_claims(VerifiedClaimQuery())

    bad = ReportOutlinePlanner(WrongLedger()).plan(
        ReportOutlineRequest(**(context | {"snapshot_id": "recovery"}))
    )
    assert bad.status == "abstained" and not bad.citations
    # A real projection budget overflow must avoid the transport entirely.
    entries = ledger.find_claims(VerifiedClaimQuery(**context)).claims
    for e in entries:
        e.accepted_claim.content += "x" * 25000

    class LargeLedger:
        def find_claims(self, query):
            return type("Matches", (), {"claims": entries})()

    large = ReportOutlinePlanner(LargeLedger(), SharedLLMGateway({"gemini": forbidden})).plan(
        ReportOutlineRequest(allow_gateway=True, **context)
    )
    assert large.llm_metadata.status == "fallback" and large.llm_metadata.calls == 0
    assert large.llm_metadata.reason == "projection_budget_exceeded"


def test_distinct_confirmed_scopes_across_targets_require_clarification(qa, monkeypatch):
    _, ledger, context = qa
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.outputs.report_outline_planner.claim_scope",
        lambda entry: "separate" if entry.identity.kind == "fact" else "consolidated",
    )
    result = ReportOutlinePlanner(ledger).plan(
        ReportOutlineRequest(report_type="profitability", **context)
    )
    assert result.status == "clarification_required" and not result.used_verified_claim_ids
    assert result.reasons == ["conflicting_verified_reporting_scopes"]
    assert result.validation_result.valid
