"""QA-Fix-01 mechanism regressions; synthetic evidence is not financial gold."""

from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.outputs import (
    CitationRenderer,
    InformationFirewall,
    VietnameseQAComposer,
    VietnameseQARequest,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import (
    _answer_text,
    _matches_target,
    understand_requirements,
)
from vietnamese_financial_multi_agent.verification import (
    BoundedVerificationLoop,
    VerificationHistory,
    VerificationProofContext,
    VerifiedClaimLedger,
    VerifiedClaimMatches,
    VerifiedClaimRepository,
)

from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_verification_judge import passes
from .test_vietnamese_qa_composer import qa as qa_fixture


@pytest.fixture
def qa(tmp_path):
    return qa_fixture.__wrapped__(tmp_path)


@pytest.mark.parametrize(
    "question,targets,aspects,interpretations",
    [
        (
            "Doanh thu và dòng tiền kinh doanh?",
            {"b02.net_revenue", "b03.operating_cash_flow"},
            set(),
            0,
        ),
        ("Biên lợi nhuận gộp? Nêu công thức.", {"gross_margin"}, {"formula"}, 0),
        (
            "Biên lợi nhuận gộp? Nêu công thức và các số liệu sử dụng.",
            {"gross_margin"},
            {"formula", "operands"},
            0,
        ),
        (
            "Biên lợi nhuận gộp và tỷ lệ nợ trên tài sản nói lên điều gì?",
            {"gross_margin", "debt_to_assets"},
            set(),
            2,
        ),
        ("Doanh thu có cho thấy chất lượng lợi nhuận tốt không?", {"b02.net_revenue"}, set(), 1),
        (
            "Doanh thu, biên lợi nhuận gộp. Nêu cách tính và dữ liệu đầu vào.",
            {"b02.net_revenue", "gross_margin"},
            {"formula", "operands"},
            0,
        ),
        (
            "Tỷ lệ nợ trên tài sản năm 2030?\nCho biết cách tính.",
            {"debt_to_assets"},
            {"formula", "operands"},
            0,
        ),
        (
            "Doanh thu và biên lợi nhuận gộp; công thức của biên lợi nhuận gộp?",
            {"b02.net_revenue", "gross_margin"},
            {"formula"},
            0,
        ),
        (
            "Doanh thu. Đồng thời dòng tiền kinh doanh; có thể nhận xét gì?",
            {"b02.net_revenue", "b03.operating_cash_flow"},
            set(),
            2,
        ),
        (
            "Hãy giải thích cách tính và đầu vào của tỷ lệ nợ trên tài sản năm 2031.",
            {"debt_to_assets"},
            {"formula", "operands"},
            0,
        ),
        (
            "Doanh thu thuần và lợi nhuận sau thuế năm 2030?",
            {"b02.net_revenue", "b02.profit_after_tax"},
            set(),
            0,
        ),
        (
            "Nêu công thức và đầu vào. Biên lợi nhuận gộp năm 2030 là bao nhiêu?",
            {"gross_margin"},
            {"formula", "operands"},
            0,
        ),
        (
            "Biên lợi nhuận gộp? Nêu ý nghĩa và công thức của chỉ tiêu này.",
            {"gross_margin"},
            {"formula"},
            1,
        ),
    ],
)
def test_dependency_aware_plans(question, targets, aspects, interpretations):
    requirements = understand_requirements(question)
    values = [r for r in requirements if r.kind in ("fact", "metric") and not r.interpretation]
    assert {r.target_id for r in values} == targets
    explanations = [r for r in requirements if r.kind == "explanation"]
    assert {r.aspect for r in explanations} == aspects
    assert sum(r.interpretation for r in requirements) == interpretations
    for r in explanations:
        assert r.depends_on
        parents = [v for v in values if v.requirement_id in r.depends_on]
        assert len(parents) == 1 and parents[0].target_id == r.target_id
        assert parents[0].kind == "metric"


def test_broad_analysis_and_ambiguous_explanation_need_clarification(qa):
    _, ledger, context = qa
    broad = VietnameseQAComposer(ledger).compose(
        VietnameseQARequest(question="Phân tích hiệu quả kinh doanh chung.", **context)
    )
    assert broad.status == "clarification_required" and not broad.used_verified_claim_ids
    requirements = understand_requirements(
        "Biên lợi nhuận gộp và tỷ lệ nợ trên tài sản? Nêu công thức của chỉ tiêu này."
    )
    assert any(r.reason == "specify_explanation_target" for r in requirements)


def test_lnst_alias_uses_existing_catalog_and_does_not_ban_accepted_facts(qa):
    from vietnamese_financial_multi_agent.tools.question_understanding import ITEM_RULES
    from vietnamese_financial_multi_agent.verification import VerifiedClaimQuery

    _, ledger, _ = qa
    requirement = understand_requirements("LNST là bao nhiêu?")[0]
    assert requirement.target_id in ITEM_RULES
    # Isolate matching from admission; never persist/release this synthetic copy.
    entry = next(
        e for e in ledger.find_claims(VerifiedClaimQuery()).claims if e.identity.kind == "fact"
    )
    entry.accepted_claim.supporting_evidence[0].canonical_item_id = requirement.target_id
    assert _matches_target(entry, requirement)


def test_explanation_released_through_renderer_and_firewall(qa):
    _, ledger, context = qa
    request = VietnameseQARequest(
        question="Biên lợi nhuận gộp? Nêu công thức và các số liệu sử dụng.", **context
    )
    response = VietnameseQAComposer(ledger).compose(request)
    assert response.status == "answered"
    assert "Công thức:" in response.answer_vi
    assert "Lợi nhuận gộp" in response.answer_vi and "1234.00" in response.answer_vi
    assert "VND" in response.answer_vi
    assert any(s.explanation for s in response.grounded_segments)
    result = InformationFirewall(ledger).evaluate_qa(
        request=request, response=response, rendered=CitationRenderer().render_qa(response)
    )
    assert result.decision == "ALLOW_WITH_CAVEAT", result.blockers


def test_mixed_inference_keeps_accepted_fact(qa):
    _, ledger, context = qa
    request = VietnameseQARequest(
        question="Doanh thu có cho thấy chất lượng lợi nhuận tốt không? Giải thích dựa trên số liệu.",
        **context,
    )
    response = VietnameseQAComposer(ledger).compose(request)
    assert response.status == "partial"
    assert response.used_verified_claim_ids
    assert any(r.interpretation for r in response.unanswered_requirements)
    assert "chất lượng lợi nhuận tốt" not in response.answer_vi
    result = InformationFirewall(ledger).evaluate_qa(
        request=request, response=response, rendered=CitationRenderer().render_qa(response)
    )
    assert result.decision == "ALLOW_WITH_CAVEAT", result.blockers


@pytest.mark.parametrize("missing", ["trace", "operands", "citation", "approval"])
def test_missing_admitted_metadata_retains_result_as_partial(qa, missing):
    _, ledger, context = qa

    class LegacyResultOnlyLedger:
        """Synthetic result-only authority, not persisted/re-admitted evidence."""

        def find_claims(self, query):
            matches = ledger.find_claims(query)
            for entry in matches.claims:
                calc = entry.accepted_claim.calculation
                if not calc:
                    continue
                if missing == "trace":
                    calc.trace = None
                elif missing == "operands":
                    calc.trace.operands = []
                elif missing == "citation":
                    for operand in calc.evidence.operands:
                        operand.facts.matches[0].citations = []
                else:
                    calc.trace.approval.definition_sha256 = "missing"
            return matches

    response = VietnameseQAComposer(LegacyResultOnlyLedger()).compose(
        VietnameseQARequest(
            question="Biên lợi nhuận gộp? Nêu công thức và các số liệu sử dụng.", **context
        )
    )
    assert response.status == "partial"
    assert response.used_verified_claim_ids
    assert not any(s.explanation for s in response.grounded_segments)
    assert any(
        r.reason == "insufficient_admitted_calculation_metadata"
        for r in response.unanswered_requirements
    )


def test_operands_never_become_direct_claims_or_trigger_tools(qa, monkeypatch):
    from vietnamese_financial_multi_agent.tools.financial_calculator import FinancialCalculator

    def forbidden(*args, **kwargs):
        pytest.fail("M7 must not calculate")

    monkeypatch.setattr(FinancialCalculator, "calculate_financial_metric", forbidden)
    _, ledger, context = qa

    class MetricOnlyLedger:
        def find_claims(self, query):
            return VerifiedClaimMatches(
                status="matched",
                claims=[
                    e
                    for e in ledger.find_claims(query).claims
                    if e.identity.kind == "approved_metric"
                ],
            )

    composer = VietnameseQAComposer(MetricOnlyLedger())
    direct = composer.compose(VietnameseQARequest(question="Doanh thu?", **context))
    assert direct.status == "abstained" and not direct.used_verified_claim_ids
    explanation = composer.compose(
        VietnameseQARequest(question="Cách tính biên lợi nhuận gộp?", **context)
    )
    assert explanation.status == "answered" and explanation.grounded_segments[0].explanation


@pytest.mark.parametrize(
    "mutation",
    [
        "result",
        "numerator",
        "denominator",
        "formula",
        "unit",
        "scale",
        "period",
        "snapshot",
        "citation",
        "content",
        "question",
        "coverage",
        "interpretation",
        "caveat",
    ],
)
def test_firewall_blocks_explanation_tampering_even_after_rerender(qa, mutation):
    _, ledger, context = qa
    request = VietnameseQARequest(question="Cách tính biên lợi nhuận gộp?", **context)
    response = VietnameseQAComposer(ledger).compose(request)
    segment = response.grounded_segments[0]
    original_rendered = CitationRenderer().render_qa(response)
    explanation = segment.explanation
    assert explanation
    if mutation == "result":
        explanation.result = "999"
    elif mutation in ("numerator", "denominator"):
        explanation.operands[mutation == "denominator"].operand.value = "999"
    elif mutation == "formula":
        explanation.formula = "revenue / gross_profit"
    elif mutation in ("unit", "scale", "period"):
        operand = explanation.operands[0].operand
        if mutation == "unit":
            operand.unit = "USD"
        else:
            setattr(operand.context, mutation, Decimal("999") if mutation == "scale" else "2031")
    elif mutation == "snapshot":
        segment.context.snapshot_id = "another"
    elif mutation == "citation":
        explanation.operands[0].citations[0].anchor_id = "invented"
    elif mutation == "content":
        segment.content += " Công ty có chất lượng lợi nhuận tốt."
    elif mutation == "question":
        request.question = "Cách tính tỷ lệ nợ trên tài sản?"
    elif mutation == "coverage":
        response = VietnameseQAComposer(ledger).compose(
            VietnameseQARequest(question="Biên lợi nhuận gộp?", **context)
        )
        response.question = request.question
    elif mutation == "interpretation":
        request.question += " Chất lượng lợi nhuận tốt không?"
        response.question = request.question
    else:
        response.caveats = []
    response.answer_vi = _answer_text(response)
    # Attacker can forge the local validation flag and re-render their own source.
    try:
        rendered = CitationRenderer().render_qa(response)
    except ValueError:
        assert mutation == "snapshot"
        rendered = original_rendered
    result = InformationFirewall(ledger).evaluate_qa(
        request=request, response=response, rendered=rendered
    )
    assert result.decision == "BLOCK", (mutation, result)


@pytest.mark.parametrize("state", ["REJECT", "DEFER"])
def test_pending_or_rejected_authority_is_never_selected(qa, state):
    _, ledger, context = qa

    class InvalidLedger:
        def find_claims(self, query):
            result = ledger.find_claims(query)
            for entry in result.claims:
                entry.decision.decision = state
            return result

    response = VietnameseQAComposer(InvalidLedger()).compose(
        VietnameseQARequest(question="Doanh thu và cách tính biên lợi nhuận gộp?", **context)
    )
    assert response.status == "abstained" and not response.used_verified_claim_ids


@pytest.mark.parametrize(
    "formula,label",
    [
        ("debt_to_assets", "Tỷ lệ nợ trên tổng tài sản"),
        ("revenue_yoy", "Tăng trưởng doanh thu"),
    ],
)
def test_explanation_generalizes_to_other_approved_formulas_and_years(tmp_path, formula, label):
    data = fixture(formula, document=1)
    batch = batch_for(data, metric=True)
    validation, evidence, logic = passes(data, batch)
    history = VerificationHistory(
        contexts=[
            VerificationProofContext(
                batch=batch, validation=validation, evidence=evidence, logic=logic
            )
        ],
        outcome=BoundedVerificationLoop().start(
            batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
        ),
    )
    repository = VerifiedClaimRepository(tmp_path)
    assert repository.admit(history).status == "stored"
    entry = repository.list_all()[0]
    ledger = VerifiedClaimLedger(repository)
    request = VietnameseQARequest(
        question=f"Cách tính và dữ liệu đầu vào của {label} năm 2031?",
        company_id=entry.identity.company_id,
        document_id=entry.identity.document_id,
        snapshot_id=entry.identity.snapshot_id,
    )
    response = VietnameseQAComposer(ledger).compose(request)
    assert response.status == "answered", response.reasons
    explanation = response.grounded_segments[0].explanation
    assert explanation.formula_id == formula
    assert explanation.result == entry.accepted_claim.calculation.result
    assert [
        o.operand for o in explanation.operands
    ] == entry.accepted_claim.calculation.trace.operands
    decision = InformationFirewall(ledger).evaluate_qa(
        request=request, response=response, rendered=CitationRenderer().render_qa(response)
    )
    assert decision.decision == "ALLOW_WITH_CAVEAT", decision.blockers
