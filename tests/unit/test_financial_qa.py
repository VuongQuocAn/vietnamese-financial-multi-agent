"""Synthetic controls cho baseline; real BBS evaluation chạy riêng, không gọi mạng."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    LLMResponse,
    ResponseProvenance,
    Usage,
    parse_json_output,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog, SnapshotDescriptor
from vietnamese_financial_multi_agent.tools import (
    FinancialQABaseline,
    QAContext,
    QADocument,
    QAResponse,
)
from vietnamese_financial_multi_agent.tools.question_understanding import understand

from .test_m4_execution import fixture


def baseline(data=None, gateway=None):
    data = data or fixture()
    descriptor = data["descriptors"][0]
    document = QADocument(
        document_id=descriptor.document_id,
        company_id=data["facts"][0].company_id,
        company_aliases=["TEST"],
        reporting_year=2030,
    )
    return FinancialQABaseline(SnapshotCatalog(**data), [document], gateway=gateway)


def test_direct_grounded_format_scale_and_response_round_trip():
    data = fixture()
    fact = next(f for f in data["facts"] if f.canonical_item_id == "b02.net_revenue")
    fact.value.normalized_value = Decimal("12345678901234567890.00100")
    fact.value.unit, fact.context.scale = "triệu đồng", Decimal("1000000")
    data["source_reviews"] = []
    before = deepcopy(data)
    result = baseline(data).answer("Doanh thu thuần TEST năm 2030 là bao nhiêu?")
    assert result.status == "answered"
    assert result.numerical_result == "12345678901234567890.00100"
    assert "12.345.678.901.234.567.890,00100 triệu đồng" in result.answer_vi
    assert "1000000" in result.answer_vi and result.facts[0].record == fact
    assert result.citations == result.evidence[0].matches[0].citations
    assert result.tool_trace[0].tool == "find_financial_facts"
    assert not result.financial_fact_verified and result.llm.calls == 0
    assert QAResponse.model_validate_json(result.model_dump_json()) == result
    assert data == before


@pytest.mark.parametrize(
    "formula,question",
    [
        ("gross_margin", "Biên lợi nhuận gộp TEST năm 2030?"),
        ("debt_to_assets", "Tỷ lệ nợ trên tổng tài sản TEST năm 2030?"),
        ("revenue_yoy", "Tăng trưởng doanh thu TEST năm 2030?"),
    ],
)
def test_analytical_uses_calculator_and_exact_lineage(formula, question):
    result = baseline(fixture(formula=formula)).answer(question)
    assert result.status == "answered", result.reasons
    assert result.numerical_result == result.calculation.result
    assert result.calculation.trace.formula.formula_id == formula
    assert result.citations == result.calculation.evidence.citations
    assert [s.tool for s in result.tool_trace] == [
        "list_financial_metrics",
        "calculate_financial_metric",
        "get_metric_evidence_lineage",
    ]
    assert len(result.facts) == 2 and "Số liệu gốc" in result.answer_vi
    assert QAResponse.model_validate_json(result.model_dump_json()) == result


def test_evidence_followup_needs_explicit_target_and_keeps_source_vs_financial_distinction():
    api = baseline()
    result = api.answer(
        "Công thức là gì, lấy số nào và trang nào?",
        QAContext(
            document_id=fixture()["descriptors"][0].document_id,
            reporting_year=2030,
            formula_id="gross_margin",
        ),
    )
    assert result.parsed.intent == "evidence_explanation" and result.status == "answered"
    assert "đã đối chiếu giá trị/dòng với PDF" in result.answer_vi
    assert "chưa phải xác minh độc lập" in result.answer_vi
    assert not result.financial_fact_verified
    missing = api.answer("Nguồn ở đâu?", QAContext(reporting_year=2030))
    assert missing.status == "clarification_required" and not missing.tool_trace
    unrelated = api.answer(
        "Viết bài thơ", QAContext(formula_id="gross_margin", reporting_year=2030)
    )
    assert unrelated.status == "unsupported" and not unrelated.tool_trace


def test_snapshot_ambiguity_exact_selection_and_wrong_binding():
    data = fixture()
    descriptor = data["descriptors"][0]
    data["descriptors"].append(
        SnapshotDescriptor(
            **(
                descriptor.model_dump()
                | {
                    "snapshot_id": "recovered",
                    "parent_snapshot_id": descriptor.snapshot_id,
                    "origin": "recovery",
                }
            )
        )
    )
    api = baseline(data)
    ambiguous = api.answer("Doanh thu TEST năm 2030?")
    assert ambiguous.status == "clarification_required" and len(ambiguous.snapshot_candidates) == 2
    assert not ambiguous.tool_trace
    exact = api.answer("Doanh thu TEST năm 2030?", QAContext(snapshot_id=descriptor.snapshot_id))
    assert exact.status == "answered" and exact.snapshot_id == descriptor.snapshot_id
    missing = api.answer("Doanh thu TEST năm 2030?", QAContext(snapshot_id="not-real"))
    assert missing.status == "abstained" and missing.numerical_result is None
    natural = api.answer("Doanh thu TEST năm 2030 bản gốc?")
    assert natural.status == "answered" and natural.snapshot_id == descriptor.snapshot_id
    unknown = api.answer("Doanh thu TEST năm 2030 snapshot imaginary?")
    assert unknown.status == "abstained" and not unknown.tool_trace


@pytest.mark.parametrize(
    "question,context",
    [
        ("So sánh tổng tài sản TEST 2021 với 2025", QAContext()),
        ("ROE TEST năm 2030", QAContext()),
        ("Tỷ lệ doanh thu trên vốn chủ sở hữu TEST năm 2030", QAContext()),
        ("Doanh thu hợp nhất TEST năm 2030", QAContext()),
        ("Doanh thu TEST năm 2030", QAContext(reporting_year=2029)),
        ("Doanh thu TEST năm 2030", QAContext(period="2029")),
        ("Hàng tồn kho TEST năm 2030", QAContext()),
    ],
)
def test_negative_controls_never_emit_number(question, context):
    result = baseline().answer(question, context)
    assert result.status in {"unsupported", "abstained", "clarification_required"}
    assert result.numerical_result is None and not result.citations


@pytest.mark.parametrize("failure", ["quality", "source", "conflict", "duplicate"])
def test_unusable_and_ambiguous_fact_is_not_rendered_as_reliable(failure):
    data = fixture()
    fact = next(f for f in data["facts"] if f.canonical_item_id == "b02.net_revenue")
    if failure == "quality":
        fact.quality_context[0].decision = "insufficient"
    elif failure == "source":
        fact.sources.clear()
    elif failure == "conflict":
        review = next(
            r for r in data["source_reviews"] if r.observation == fact.observation_identity()
        )
        review.period = "2029"
    else:
        duplicate = fact.model_copy(deep=True)
        duplicate.local_observation_id = "duplicate"
        data["facts"].append(duplicate)
    result = baseline(data).answer("Doanh thu TEST năm 2030?")
    assert result.status in {"abstained", "clarification_required"}
    assert result.numerical_result is None and not result.citations


def gateway_for(payload, seen):
    def transport(request):
        seen.append(request)
        return LLMResponse(
            contract_version="llm_gateway_v1",
            request_id=request.request_id,
            status="success",
            finish_reason="stop",
            correlation=request.correlation,
            provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
            usage=Usage(status="unknown", source="unknown"),
            cost=Cost(status="unknown", source="unknown"),
            output=parse_json_output(json.dumps(payload)),
        )

    return SharedLLMGateway({"gemini": transport})


@pytest.mark.parametrize(
    "payload,answered",
    [
        (
            {
                "intent": "direct_fact",
                "canonical_item_id": "b02.net_revenue",
                "reporting_year": 2030,
            },
            True,
        ),
        ({"intent": "direct_fact", "canonical_item_id": "invented", "reporting_year": 2030}, False),
        (
            {
                "intent": "direct_fact",
                "canonical_item_id": "b02.net_revenue",
                "document_id": "invented",
            },
            False,
        ),
        ({"intent": "calculated_metric", "formula_id": "roe", "reporting_year": 2030}, False),
        (
            {
                "intent": "direct_fact",
                "canonical_item_id": "b02.net_revenue",
                "reporting_year": 2029,
            },
            False,
        ),
    ],
)
def test_single_mock_gateway_call_validates_allowlist_and_schema(payload, answered):
    seen = []
    api = baseline(gateway=gateway_for(payload, seen))
    result = api.answer(
        "TEST năm 2030 bán hàng thu được bao nhiêu sau các khoản giảm trừ?",
        QAContext(allow_gateway=True),
    )
    assert len(seen) == result.llm.calls == 1
    assert seen[0].model.model == "gemini-3.5-flash-lite"
    assert (result.status == "answered") == answered
    if not answered:
        assert not result.tool_trace and result.numerical_result is None
    deterministic = api.answer("Doanh thu TEST năm 2030?", QAContext(allow_gateway=True))
    assert deterministic.status == "answered" and len(seen) == 1


def test_gateway_failure_is_bounded_and_rules_still_work():
    api = baseline(gateway=SharedLLMGateway({}))
    failed = api.answer(
        "TEST năm 2030 bán hàng thu được bao nhiêu sau các khoản giảm trừ?",
        QAContext(allow_gateway=True),
    )
    assert failed.llm.calls == 1 and failed.status == "unsupported"
    assert not failed.tool_trace
    assert api.answer("Doanh thu TEST năm 2030?").status == "answered"


def test_catalog_extension_and_ambiguous_alias():
    parsed, errors = understand("Giá vốn hàng bán BBS năm 2025 là bao nhiêu?")
    assert parsed.canonical_item_id == "b02.cost_of_sales" and not errors
    _, errors = understand("Hàng tồn kho BBS năm 2025?")
    assert errors == ["multiple_or_ambiguous_targets"]
    parsed, errors = understand("Tổng cộng nguồn vốn BBS năm 2025?")
    assert parsed.intent == "direct_fact" and parsed.canonical_item_id == "b01.total_funding"
    assert not errors


def test_explicit_dates_opening_balance_and_unsupported_quarter_are_not_year_end():
    api = baseline(fixture(formula="debt_to_assets"))
    opening = api.answer("Tổng tài sản TEST đầu năm 2030?")
    assert opening.period == "2030-01-01" and opening.numerical_result is None
    exact = api.answer("Tổng tài sản TEST ngày 31/12/2030?")
    assert exact.period == "2030-12-31" and exact.status == "answered"
    conflict = api.answer("Tổng tài sản TEST đầu năm 2030?", QAContext(period="2030-12-31"))
    assert conflict.status == "clarification_required" and not conflict.tool_trace
    quarterly = api.answer("Doanh thu TEST quý 1 năm 2030?")
    assert quarterly.status == "unsupported" and not quarterly.tool_trace
