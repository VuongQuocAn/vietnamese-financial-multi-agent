"""Synthetic engineering controls; persisted BBS/live evaluation runs separately."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.agents import (
    ProfitabilitySpecialist,
    RiskAwareSupervisor,
    SpecialistResult,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

from .test_financial_qa import gateway_for
from .test_supervisor import planned


def upstream():
    data, plan = planned()
    return RiskAwareSupervisor(SnapshotCatalog(**data)).execute(plan)


def proposal(evidence_id="E003", **kwargs):
    return dict(
        evidence_id=evidence_id,
        kind="supported_interpretation",
        meaning="gross_profit_per_100_revenue",
        period="2030",
        statement="Trong kỳ {period}, cứ 100 đồng doanh thu thuần tương ứng khoảng {value} đồng lợi nhuận gộp.",
        **kwargs,
    )


def run(result, claims):
    seen = []
    api = ProfitabilitySpecialist(gateway_for(dict(claims=claims, missing_information=[]), seen))
    return api.analyze(
        question="Phân tích khả năng sinh lời TEST 2030", supervisor_result=result
    ), seen


def test_metric_interpretation_exact_lineage_one_call_and_roundtrip():
    source = upstream()
    before = deepcopy(source)
    result, seen = run(source, [proposal()])
    assert result.status == "generated", result.model_dump()
    candidate = result.candidates[0]
    calc = source.evidence_bundle.calculations[0]
    assert candidate.calculation == calc
    assert candidate.citations == calc.evidence.citations
    assert len(candidate.fact_references) == 2 and candidate.metric_ids == [calc.metric_id]
    assert "100 đồng doanh thu thuần" in candidate.content
    assert result.llm.calls == len(seen) == 1
    assert source == before and not candidate.financial_fact_verified
    assert candidate.status == "candidate"
    assert SpecialistResult.model_validate_json(result.model_dump_json()) == result
    prompt = json.loads(seen[0].messages[0].content)
    assert "citations" not in prompt["evidence"][0]  # Digest, not full catalog/PDF.


@pytest.mark.parametrize(
    "mutation", ["unknown_id", "period", "number", "cause", "judgment", "citation", "wrong_kind"]
)
def test_hallucinated_claim_is_excluded_without_repair(mutation):
    claim = proposal()
    if mutation == "unknown_id":
        claim["evidence_id"] = "invented"
    elif mutation == "period":
        claim["period"] = "2025"
    elif mutation == "number":
        claim["statement"] = claim["statement"].replace("{value}", "99,99")
    elif mutation == "cause":
        claim["statement"] += " Do chi phí giảm."
    elif mutation == "judgment":
        claim["statement"] += " Doanh nghiệp hiệu quả cao hơn ngành."
    elif mutation == "citation":
        claim["citations"] = [dict(pdf_page=999)]
    else:
        claim["kind"] = "approved_metric"
    result, _ = run(upstream(), [claim])
    assert result.status == "abstained" and not result.candidates
    assert any(t.outcome == "excluded" for t in result.trace)


@pytest.mark.parametrize(
    "failure",
    [
        "citation",
        "quality",
        "source",
        "anchor",
        "duplicate",
        "lineage",
        "operand",
        "result",
        "formula",
    ],
)
def test_completed_status_does_not_override_evidence_gates(failure):
    source = upstream()
    if failure == "citation":
        source.evidence_bundle.citations.clear()
    elif failure == "quality":
        source.evidence_bundle.facts[0].record.quality_context[0].decision = "conflicted"
    elif failure == "source":
        source.evidence_bundle.facts[0].citations[0].pdf_page = 999
    elif failure == "anchor":
        source.evidence_bundle.facts[0].citations[0].anchor_id = "invented"
    elif failure == "duplicate":
        other = source.evidence_bundle.facts[0].model_copy(deep=True)
        other.record.value.normalized_value = Decimal("999")
        source.evidence_bundle.facts.append(other)
    elif failure == "lineage":
        source.evidence_bundle.calculations[0].evidence.reviewed_lineage.lineage = None
    elif failure == "operand":
        source.evidence_bundle.calculations[0].trace.operands[0].value = "999"
    elif failure == "result":
        source.evidence_bundle.calculations[0].result = "99.99"
    else:
        source.evidence_bundle.calculations[0].formula_digest = "invented"
    result, _ = run(source, [proposal()])
    assert not result.candidates
    assert not any(e.kind == "metric" for e in result.supporting_evidence)
    assert result.missing_evidence


def test_partial_preserves_independent_fact_caveats_and_blocked_never_calls():
    source = upstream()
    source.status = "partial"
    source.evidence_bundle.calculations.clear()
    source.evidence_bundle.facts[0].record.quality_context[0].decision = "usable_with_caveat"
    source.evidence_bundle.facts[0].record.quality_context[0].caveats.append("test_caveat")
    source.evidence_bundle.missing_requirement_ids.append("missing_branch")
    claim = dict(evidence_id="E001", kind="fact", meaning="fact_value", period="2030")
    result, _ = run(source, [claim])
    assert result.status == "partial" and len(result.candidates) == 1
    assert "test_caveat" in result.candidates[0].caveats
    source.status = "blocked"
    result, seen = run(source, [claim])
    assert result.status == "abstained" and not result.candidates and not seen


def test_structured_multi_fact_render_and_reject_numeric_text():
    claims = [
        dict(evidence_id=key, kind="fact", meaning="fact_value", period="2030")
        for key in ["E001", "E002"]
    ]
    claims.append(dict(claims[0], statement="Doanh thu là 999 VND."))
    result, _ = run(upstream(), claims)
    assert result.status == "partial" and len(result.candidates) == 2
    assert all(c.citations and c.fact_references for c in result.candidates)


def test_unsupported_formula_and_wrong_question_period_cannot_reuse_other_evidence():
    source = upstream()
    for question in ("ROE và Net Profit Margin TEST 2030?", "Biên lợi nhuận gộp TEST 2025?"):
        seen = []
        api = ProfitabilitySpecialist(
            gateway_for(dict(claims=[proposal()], missing_information=[]), seen)
        )
        result = api.analyze(question=question, supervisor_result=source)
        assert result.status == "abstained" and not result.candidates
        assert not result.supporting_evidence and result.missing_evidence
        assert len(seen) == 1


def test_exact_literal_gemini_numbers_pass_but_wrong_literals_and_uppercase_placeholders_are_bound():
    source = upstream()
    calc = source.evidence_bundle.calculations[0]
    claim = proposal()
    claim["statement"] = (
        f"Trong kỳ 2030, với mỗi 100 đồng doanh thu thuần tương ứng khoảng {calc.result} đồng lợi nhuận gộp."
    )
    result, _ = run(source, [claim])
    assert result.status == "generated" and len(result.candidates) == 1
    claim["statement"] = claim["statement"].replace(calc.result, "99.99")
    result, _ = run(source, [claim])
    assert result.status == "abstained" and not result.candidates
    claim["statement"] = proposal()["statement"].replace("{value}", "{VALUE}")
    result, _ = run(source, [claim])
    assert result.status == "generated" and "{VALUE}" not in result.candidates[0].content
