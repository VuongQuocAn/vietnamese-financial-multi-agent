"""Synthetic controls only; real BBS and live Gemini are evaluated separately."""

import json
from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.agents import (
    LiquidityLeverageSpecialist,
    PlannerContext,
    RiskAwareSupervisor,
    SpecialistResult,
)
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

from .test_financial_qa import gateway_for
from .test_m4_execution import fixture
from .test_query_planner import planner


@pytest.fixture(scope="module")
def source():
    data = fixture("debt_to_assets")
    plan = (
        planner(data)
        .plan("Tỷ lệ nợ trên tổng tài sản TEST 2030?", PlannerContext(mode="deterministic"))
        .plan
    )
    result = RiskAwareSupervisor(SnapshotCatalog(**data)).execute(plan)
    assert result.status == "completed"
    return result


def claim(**changes):
    return dict(
        dict(
            evidence_id="E003",
            kind="supported_interpretation",
            meaning="liabilities_per_100_assets",
            period="2030-12-31",
            statement="Cứ 100 đồng tổng tài sản tại thời điểm báo cáo tương ứng khoảng {value} đồng nợ phải trả.",
        ),
        **changes,
    )


def run(source, claims, question="Giải thích Debt-to-Assets TEST 2030?", model=None):
    seen = []
    result = LiquidityLeverageSpecialist(
        gateway_for(dict(claims=claims, missing_information=[]), seen), model=model
    ).analyze(question=question, supervisor_result=source)
    return result, seen


def test_exact_approved_trace_arithmetic_prose_and_gateway_metadata(source):
    before = deepcopy(source)
    model = ModelIdentity(provider="gemini", model="configurable-model")
    result, seen = run(
        source,
        [claim(), claim(kind="approved_metric", meaning="metric_value", statement=None)],
        model=model,
    )
    assert result.status == "generated", result.missing_evidence
    assert result.role == "liquidity_and_leverage" and len(result.candidates) == 2
    calc = source.evidence_bundle.calculations[0]
    for candidate in result.candidates:
        assert candidate.calculation == calc and candidate.citations == calc.evidence.citations
        assert candidate.metric_ids == [calc.metric_id] and len(candidate.fact_references) == 2
        assert candidate.status == "candidate" and not candidate.financial_fact_verified
    assert result.llm.calls == len(seen) == 1 and seen[0].model == model
    assert source == before
    assert SpecialistResult.model_validate_json(result.model_dump_json()) == result
    prompt = json.loads(seen[0].messages[0].content)
    assert prompt["prompt_version"] and "citations" not in prompt["evidence"][0]
    literal = result.candidates[0].content
    again, _ = run(source, [claim(statement=literal)])
    assert again.candidates[0].content == literal
    alternative, _ = run(
        source,
        [
            claim(
                statement="Nợ phải trả tương ứng khoảng {value} đồng trên mỗi 100 đồng tổng tài sản tại thời điểm báo cáo."
            )
        ],
    )
    assert alternative.status == "generated"


@pytest.mark.parametrize(
    "mutation", ["number", "judgment", "borrowing", "new_ratio", "citation", "period", "unknown_id"]
)
def test_unsupported_model_proposition_is_excluded(source, mutation):
    proposal = claim()
    if mutation == "number":
        proposal["statement"] = proposal["statement"].replace("{value}", "99,99")
    elif mutation == "judgment":
        proposal["statement"] += " Doanh nghiệp an toàn và không mất khả năng thanh toán."
    elif mutation == "borrowing":
        proposal["statement"] = proposal["statement"].replace("nợ phải trả", "nợ vay có lãi")
    elif mutation == "new_ratio":
        proposal["meaning"] = "current_ratio"
    elif mutation == "citation":
        proposal["citations"] = [{"pdf_page": 999}]
    elif mutation == "period":
        proposal["period"] = "2030"
    else:
        proposal["evidence_id"] = "invented"
    result, _ = run(source, [proposal])
    assert not result.candidates and result.status == "abstained"
    assert any(t.outcome == "excluded" for t in result.trace)


@pytest.mark.parametrize(
    "mutation",
    [
        "liabilities",
        "assets",
        "approval",
        "lineage",
        "citation",
        "snapshot",
        "conflict",
        "unit",
        "period",
    ],
)
def test_completed_upstream_does_not_override_grounding_gates(source, mutation):
    changed = deepcopy(source)
    bundle = changed.evidence_bundle
    if mutation in {"liabilities", "assets"}:
        role = next(o for o in bundle.calculations[0].trace.operands if o.role == mutation)
        bundle.facts = [f for f in bundle.facts if f.reference.observation != role.observation]
    elif mutation == "approval":
        bundle.calculations[0].evidence.closure.readiness["formula_policy"][
            "execution_approved"
        ] = False
    elif mutation == "lineage":
        bundle.calculations[0].evidence.reviewed_lineage.lineage = None
    elif mutation == "citation":
        bundle.citations.clear()
    elif mutation == "snapshot":
        bundle.calculations[0].snapshot_id = "wrong"
    elif mutation == "conflict":
        other = bundle.facts[0].model_copy(deep=True)
        other.record.value.normalized_value += 1
        bundle.facts.append(other)
    elif mutation == "unit":
        bundle.calculations[0].trace.operands[0].unit = "USD"
    else:
        bundle.calculations[0].trace.operands[0].context.period = "2030-01-01"
    result, _ = run(changed, [claim()])
    assert not result.candidates
    assert not any(e.kind == "metric" for e in result.supporting_evidence)
    assert result.missing_evidence


def test_partial_independent_facts_unsupported_mixed_request_and_scope(source):
    changed = deepcopy(source)
    changed.status = "partial"
    changed.evidence_bundle.calculations.clear()
    changed.evidence_bundle.missing_requirement_ids.append("metric_missing")
    proposals = [
        dict(evidence_id=f"E00{i}", kind="fact", meaning="fact_value", period="2030-12-31")
        for i in (1, 2)
    ]
    result, _ = run(
        changed, proposals, "Tổng tài sản và tổng nợ phải trả TEST 2030? Current Ratio?"
    )
    assert result.status == "partial" and len(result.candidates) == 2
    assert any(v.startswith("unsupported_capability:") for v in result.missing_evidence)
    assert all(c.citations and c.caveats and c.fact_references for c in result.candidates)
    result, _ = run(source, [claim()], "Current Ratio và Quick Ratio TEST 2030?")
    assert not result.candidates and not result.supporting_evidence
    result, _ = run(source, [claim()], "Debt-to-Assets hợp nhất TEST 2030?")
    assert (
        not result.candidates
        and "reporting_scope_unresolved_or_mismatched" in result.missing_evidence
    )
    result, _ = run(source, [claim()], "Debt-to-Assets TEST tại ngày 30/06/2030?")
    assert not result.candidates and not result.supporting_evidence
    changed = deepcopy(source)
    for selector in changed.final_plan_state.query.selectors:
        selector.snapshot_id = "another-snapshot"
    result, _ = run(changed, [claim()])
    assert not result.candidates and not result.supporting_evidence
    for status in ("blocked", "failed"):
        changed.status = status
        result, seen = run(changed, [claim()])
        assert not result.candidates and not seen
