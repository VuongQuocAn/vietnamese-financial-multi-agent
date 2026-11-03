"""Synthetic engineering controls; real BBS/live measurements live in the evaluator."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.agents import (
    CashFlowEarningsQualitySpecialist,
    PlannerContext,
    RiskAwareSupervisor,
    SpecialistResult,
)
from vietnamese_financial_multi_agent.agents.cash_flow_earnings_quality_specialist import (
    SIGN_TEMPLATE,
    ZERO_TEMPLATE,
)
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog, build_graph

from .test_financial_qa import gateway_for
from .test_m4_execution import fixture
from .test_query_planner import planner


@pytest.fixture(scope="module")
def source():
    data = fixture()
    for fact, review, item in zip(
        data["facts"],
        data["source_reviews"],
        ("b03.operating_cash_flow", "b02.profit_before_tax"),
        strict=True,
    ):
        fact.canonical_item_id = fact.context.mapped_item_code = item
        fact.context.statement_type = review.statement_type = item[:3].upper()
    data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])
    plan = (
        planner(data)
        .plan(
            "Lưu chuyển tiền thuần từ hoạt động kinh doanh và lợi nhuận trước thuế TEST 2030?",
            PlannerContext(mode="deterministic"),
        )
        .plan
    )
    result = RiskAwareSupervisor(SnapshotCatalog(**data)).execute(plan)
    assert result.status == "completed", result.model_dump()
    result.evidence_bundle.facts.sort(key=lambda f: f.record.canonical_item_id, reverse=True)
    return result


def claim(**changes):
    return dict(
        dict(
            evidence_id="E001",
            kind="supported_interpretation",
            meaning="cash_flow_sign",
            period="2030",
            sign="positive",
            statement=SIGN_TEMPLATE,
        ),
        **changes,
    )


def run(source, claims, question="Diễn giải dòng tiền TEST 2030?", model=None):
    seen = []
    result = CashFlowEarningsQualitySpecialist(
        gateway_for(dict(claims=claims, missing_information=[]), seen),
        model=model,
    ).analyze(question=question, supervisor_result=source)
    return result, seen


def test_same_filing_separate_facts_sign_metadata_and_typed_roundtrip(source):
    before = deepcopy(source)
    model = ModelIdentity(provider="gemini", model="configurable-model")
    result, seen = run(
        source,
        [
            claim(),
            claim(kind="fact", meaning="fact_value", sign=None, statement=None),
            claim(evidence_id="E002", kind="fact", meaning="fact_value", sign=None, statement=None),
        ],
        model=model,
    )
    assert result.status == "generated" and len(result.candidates) == 3
    assert result.role == "cash_flow_and_earnings_quality"
    assert "dòng tiền vào thuần từ hoạt động kinh doanh" in result.candidates[0].content
    for candidate in result.candidates:
        match = next(
            f for f in source.evidence_bundle.facts if f.reference == candidate.fact_references[0]
        )
        assert candidate.citations == match.citations and candidate.caveats
        assert len(candidate.supporting_evidence_ids) == len(candidate.fact_references) == 1
        assert not candidate.financial_fact_verified and not candidate.metric_ids
    assert result.llm.calls == len(seen) == 1 and seen[0].model == model
    assert source == before
    assert SpecialistResult.model_validate_json(result.model_dump_json()) == result
    prompt = json.loads(seen[0].messages[0].content)
    assert prompt["evidence"][0]["currency"] == "VND"
    assert "citations" not in prompt["evidence"][0]


@pytest.mark.parametrize(
    "value,sign,phrase",
    [
        ("-0.00010", "negative", "dòng tiền ra thuần"),
        ("0.00000", "zero", "dòng tiền thuần bằng không"),
        ("0.00010", "positive", "dòng tiền vào thuần"),
    ],
)
def test_exact_sign_zero_and_scaled_unit_without_conversion(source, value, sign, phrase):
    changed = deepcopy(source)
    changed.evidence_bundle.facts = changed.evidence_bundle.facts[:1]
    changed.final_plan_state.query.required_indicators = ["b03.operating_cash_flow"]
    fact = changed.evidence_bundle.facts[0].record
    fact.value.normalized_value = Decimal(value)
    fact.value.unit, fact.context.scale = "VND", Decimal("1000000")
    result, _ = run(
        changed, [claim(sign=sign, statement=ZERO_TEMPLATE if sign == "zero" else SIGN_TEMPLATE)]
    )
    assert result.status == "generated" and phrase in result.candidates[0].content
    assert value.replace(".", ",") in result.candidates[0].content
    assert "VND (hệ số đơn vị 1000000)" in result.candidates[0].content
    wrong, _ = run(changed, [claim(sign="positive" if sign != "positive" else "negative")])
    assert not wrong.candidates


def test_prose_ratios_causal_bridge_and_balance_sign_are_rejected(source):
    for proposal in (
        claim(statement=SIGN_TEMPLATE + " Chất lượng lợi nhuận cao."),
        claim(statement=SIGN_TEMPLATE.replace("{value}", "999")),
        claim(statement=SIGN_TEMPLATE.replace("{direction}", "ra")),
        claim(statement=SIGN_TEMPLATE.replace("{sign}", "positive")),
        claim(meaning="cfo_net_income"),
        claim(statement="Closing cash = opening cash + net cash flow."),
        claim(statement="Chênh lệch chắc chắn do hàng tồn kho và khấu hao."),
        claim(citations=[dict(pdf_page=999)]),
        claim(evidence_id="invented"),
        claim(period="2030-12-31"),
        claim(evidence_id="E002"),
    ):
        result, _ = run(source, [proposal])
        assert not result.candidates and result.status == "abstained"
        assert any(t.outcome == "excluded" for t in result.trace)
    changed = deepcopy(source)
    fact = changed.evidence_bundle.facts[0].record
    fact.canonical_item_id = fact.context.mapped_item_code = "b03.closing_cash"
    result, _ = run(changed, [claim()])
    assert not result.candidates  # B03 balance is never a flow sign interpretation.
    result, _ = run(changed, [claim(kind="fact", meaning="fact_value", sign=None, statement=None)])
    assert result.candidates[0].period == "2030" and "cuối kỳ" in result.candidates[0].content


@pytest.mark.parametrize(
    "mutation",
    [
        "statement",
        "period_type",
        "period",
        "unit",
        "scale",
        "company",
        "currency",
        "citation",
        "review",
        "conflict",
    ],
)
def test_source_and_cross_statement_gates_keep_financial_limits(source, mutation):
    changed = deepcopy(source)
    match = changed.evidence_bundle.facts[1]
    if mutation == "statement":
        match.record.context.statement_type = "B03"
    elif mutation == "period_type":
        match.record.context.period_type = "as_of"
    elif mutation == "period":
        match.record.context.period = "2029"
    elif mutation == "unit":
        match.record.value.unit = "USD"
    elif mutation == "scale":
        match.record.context.scale = Decimal("1000")
    elif mutation == "company":
        match.record.company_id = "other-company"
    elif mutation == "currency":
        match.record.context.currency = "USD"
    elif mutation == "citation":
        match.citations[0].pdf_page = 999
    elif mutation == "review":
        match.source_review.matches.clear()
    else:
        other = match.model_copy(deep=True)
        other.record.value.normalized_value += 1
        changed.evidence_bundle.facts.append(other)
    result, _ = run(
        changed,
        [claim(evidence_id="E002", kind="fact", meaning="fact_value", sign=None, statement=None)],
    )
    assert not result.candidates and result.missing_evidence


@pytest.mark.parametrize(
    "question,eligible",
    [
        ("Giữ riêng bằng chứng dòng tiền và lợi nhuận TEST 2030.", True),
        ("Theo báo cáo tài chính riêng TEST 2030.", False),
        ("Theo báo cáo hợp nhất TEST 2030.", False),
        ("Theo báo cáo hợp nhất, giữ riêng nguồn bằng chứng TEST 2030.", False),
        ("Theo báo cáo riêng và báo cáo hợp nhất TEST 2030.", False),
    ],
)
def test_contextual_reporting_scope(source, question, eligible):
    result, seen = run(source, [claim()], question)
    assert bool(result.candidates) == bool(seen) == eligible
    if not eligible and "riêng và" not in question:
        confirmed = deepcopy(source)
        expected = "consolidated" if "hợp nhất" in question else "separate"
        for match in confirmed.evidence_bundle.facts:
            match.reporting_scope.status = "resolved"
            match.reporting_scope.evidence_status = "confirmed"
            match.reporting_scope.reporting_scope = expected
        result, seen = run(confirmed, [claim()], question)
        assert result.status == "generated" and len(seen) == 1
        assert "ambiguous_reporting_scope" not in result.missing_evidence


def test_partial_and_zero_call_controls(source):
    changed = deepcopy(source)
    changed.status = "partial"
    changed.evidence_bundle.facts = changed.evidence_bundle.facts[:1]
    result, _ = run(changed, [claim()], "Dòng tiền và lợi nhuận TEST 2030?")
    assert result.status == "partial" and len(result.candidates) == 1
    assert "missing_fact:b02.profit_before_tax" in result.missing_evidence
    for question in (
        "Tính CFO/Net Income TEST 2030?",
        "Free Cash Flow TEST 2030?",
        "So sánh dòng tiền TEST 2029 và 2030?",
        "Dòng tiền quý 1 TEST 2030?",
        "Dòng tiền tại ngày 31/12/2030?",
    ):
        result, seen = run(source, [claim()], question)
        assert result.status == "abstained" and not seen
    changed.status = "blocked"
    result, seen = run(changed, [claim()])
    assert not seen and "upstream_blocked" in result.missing_evidence


def test_found_lookup_with_unverified_row_keeps_accepted_common_policy_and_caveat(source):
    changed = deepcopy(source)
    for match in changed.evidence_bundle.facts:
        match.source_review.matches[0].reviews.clear()
        match.source_review.matches[0].status = "unverified"
    result, _ = run(changed, [claim()])
    assert result.status == "generated" and not result.financial_fact_verified
    assert "source_review_status:unverified" in result.candidates[0].caveats


def test_independent_evaluator_rejects_changed_sign_citation_and_extra_judgment(
    source, monkeypatch
):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    evaluator = importlib.import_module("evaluate_m5_06_cash_flow")
    result, _ = run(
        source, [claim(), claim(kind="fact", meaning="fact_value", sign=None, statement=None)]
    )
    original = source.evidence_bundle.facts[0].record
    data = dict(facts=[m.record for m in source.evidence_bundle.facts], graph=None)
    case = dict(
        year=2030, items=[original.canonical_item_id], interpretation=original.canonical_item_id
    )
    reference = dict(
        document_id=original.document_id, snapshot_id=original.snapshot_id, expected_targets=2
    )
    assert evaluator.assess(case, result, reference, data)["correct"]
    for mode in ("sign", "citation", "judgment", "empty_evidence"):
        changed = result.model_copy(deep=True)
        candidate = changed.candidates[0]
        if mode == "sign":
            candidate.content = candidate.content.replace("dòng tiền vào", "dòng tiền ra")
        elif mode == "citation":
            candidate.citations[0].pdf_page = 999
        elif mode == "judgment":
            candidate.content += " Chất lượng lợi nhuận cao."
        else:
            candidate.supporting_evidence_ids.clear()
        assert not evaluator.assess(case, changed, reference, data)["correct"]


def test_summary_latency_keeps_zero_call_unknown_and_handles_mixed_controls(monkeypatch):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    evaluator = importlib.import_module("evaluate_m5_06_cash_flow")
    rows = [dict(llm=dict(latency_ms=v)) for v in (None, 10.0, 20.0)]
    assert evaluator.latency_summary(rows) == dict(median=15.0, maximum=20.0)
    assert evaluator.latency_summary(rows[:1]) == dict(median=None, maximum=None)
