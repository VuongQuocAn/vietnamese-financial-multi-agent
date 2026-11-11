"""Synthetic policy controls; real BBS source replay is saved separately."""

import pytest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.financial_calculator import (
    execute_dynamic,
    render_dynamic,
)
from vietnamese_financial_multi_agent.tools.question_understanding import (
    comparison_periods,
    understand,
)
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_validators import batch_for
from .test_multihop_reasoning import reasoning_case


@pytest.mark.parametrize(
    "question,period",
    [
        ("Tài sản tại 31/12/2025?", "2025-12-31"),
        ("Tài sản đầu năm 2025?", "2025-01-01"),
        ("So với đầu năm 2025, tài sản cuối năm thay đổi bao nhiêu?", None),
    ],
)
def test_request_exact_date_and_comparison_are_distinct(question, period):
    assert understand(question)[0].period == period
    assert bool(comparison_periods(question)) == (period is None)


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "direction",
        "denominator",
        "company",
        "snapshot",
        "period",
        "relation",
        "citation",
        "request_period",
    ],
)
def test_comparison_replays_sources_and_preserves_negative_controls(mutation):
    data, batch = reasoning_case(formula="revenue_yoy", operator="percentage_change")
    batch.question = "Doanh thu năm 2030 so với 2029 thay đổi bao nhiêu phần trăm?"
    batch.context.period = "2029"
    claim = batch.claims[0]
    # Use unequal source-backed synthetic values so a wrong denominator differs.
    from decimal import Decimal

    from vietnamese_financial_multi_agent.tools.financial_calculator import FinancialCalculator

    data["facts"][0].value.normalized_value = Decimal("2468")
    data["facts"][0].value.raw_value = "2.468"
    data["source_reviews"][0].raw_value = "2.468"
    claim.supporting_evidence[0].value = "2468"
    claim.analysis_premises[0] = claim.analysis_premises[0].replace("1.234", "2.468")
    old = claim.reasoning.calculation
    claim.reasoning.calculation = FinancialCalculator(SnapshotCatalog(**data)).calculate_dynamic(
        {s.evidence_id: s.reference for s in claim.supporting_evidence},
        [step.operation for step in old.steps],
    )
    computation = claim.reasoning.calculation
    claim.content = render_dynamic(
        computation, {s.evidence_id: s.label for s in claim.supporting_evidence}
    )
    if mutation == "direction":
        operation = computation.steps[0].operation.model_copy(deep=True)
        operation.inputs.reverse()
        claim.reasoning.calculation = execute_dynamic(computation.operands, [operation])
        claim.content = render_dynamic(
            claim.reasoning.calculation, {s.evidence_id: s.label for s in claim.supporting_evidence}
        )
    elif mutation == "denominator":
        # Keep a plausible signed percentage but use the closing denominator.
        a, b = (
            Decimal(computation.operands[k].value) for k in computation.steps[0].operation.inputs
        )
        computation.steps[0].result = str((a - b) / a * 100)
    elif mutation in {"company", "snapshot", "period"}:
        setattr(
            claim.supporting_evidence[1],
            {"company": "company_id", "snapshot": "snapshot_id", "period": "period"}[mutation],
            "1999" if mutation == "period" else "wrong",
        )
    elif mutation == "relation":
        computation.steps[0].operation.period_relation = "same"
    elif mutation == "citation":
        claim.citations[0].pdf_page += 99
    elif mutation == "request_period":
        batch.context.period = "1999"
    histories = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)
    decision = histories[0].outcome.final
    assert (decision.decision == "ACCEPT") == (mutation is None), decision.model_dump()


def test_single_date_does_not_accept_other_period_or_cross_period_analysis():
    data, batch = reasoning_case(formula="revenue_yoy", operator="percentage_change")
    batch.question = "Doanh thu năm 2029 là bao nhiêu?"
    batch.context.period = "2029"
    assert (
        LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0].outcome.final.decision
        != "ACCEPT"
    )
    direct = batch_for(data)
    direct.context.period = "2029"
    assert (
        LiteVerificationRuntime(SnapshotCatalog(**data)).verify(direct)[0].outcome.final.decision
        != "ACCEPT"
    )
    direct.context.period = direct.claims[0].period
    assert (
        LiteVerificationRuntime(SnapshotCatalog(**data)).verify(direct)[0].outcome.final.decision
        == "ACCEPT"
    )


def test_m7_restores_omitted_accepted_comparison_without_new_verification():
    from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
    from vietnamese_financial_multi_agent.outputs.qa_lite import _proof_text, compose_lite
    from vietnamese_financial_multi_agent.verification.ledger import build_verified_claim

    from .test_qa_lite import gateway_for

    data, batch = reasoning_case(formula="revenue_yoy", operator="percentage_change")
    history = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)[0]
    entry = build_verified_claim(history)
    key = entry.identity.verified_claim_id
    request = FinancialQARequest(
        question="So sánh doanh thu hai năm", m7_lite=True, allow_gateway=True
    )
    omitted = "Biến động doanh thu đã được tính toán từ các kỳ được cung cấp."
    gateway, calls = gateway_for(dict(segments=[dict(text=omitted, claim_ids=[key])], gaps=[]))
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert len(calls) == 1
    assert trace["restored_calculation_claims"] == [key]
    assert trace["llm_segments_released"] == 1
    assert _proof_text(entry) in fields["answer_vi"]
    assert fields["used_verified_claim_ids"] == [key]
    assert all(c.bound_verified_claim_ids == [key] for c in fields["citations"])
    complete = _proof_text(entry)
    gateway, _ = gateway_for(dict(segments=[dict(text=complete, claim_ids=[key])], gaps=[]))
    _, trace = compose_lite(request, [entry], gateway=gateway)
    assert trace["restored_calculation_claims"] == []
