"""Coverage controls: goals must be met by released ACCEPT claims, not gap prose."""

from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite

from .test_qa_accepted_calculations import admitted_decrease
from .test_qa_lite import admitted as admitted
from .test_qa_lite import gateway_for


def test_model_gap_does_not_override_satisfied_goal(admitted):
    request, entry = admitted
    key = entry.identity.verified_claim_id
    gateway, calls = gateway_for(
        dict(
            segments=[dict(claim_ids=[key])],
            gaps=[dict(type="B", text="There is no verified finding.")],
        )
    )
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert fields["status"] in {"completed", "completed_with_caveats"}
    assert trace["coverage"]["complete"] and not trace["gaps"]
    assert trace["proposed_gaps"] and len(calls) == 1


def test_missing_requested_evidence_is_partial_even_when_model_reports_no_gaps(admitted):
    request, entry = admitted
    request.question += " Dòng tiền kinh doanh là bao nhiêu?"
    gateway, _ = gateway_for(
        dict(
            segments=[dict(claim_ids=[entry.identity.verified_claim_id])],
            gaps=[],
        )
    )
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert fields["status"] == "partial_verified_coverage"
    assert {g["type"] for g in trace["gaps"]} == {"B"}
    missing = [r for r in trace["coverage"]["requirements"] if not r["verified_claim_ids"]]
    assert [r["target_id"] for r in missing] == ["b03.operating_cash_flow"]
    assert entry.content in fields["answer_vi"]


def test_accepted_dynamic_calculation_covers_only_its_requested_periods(tmp_path):
    entry = admitted_decrease(tmp_path)
    periods = sorted(
        {o.period for o in entry.accepted_claim.reasoning.calculation.operands.values()}
    )
    base, target = periods
    question = f"Doanh thu thuần năm {target} tăng hay giảm bao nhiêu phần trăm so với năm {base}?"
    request = FinancialQARequest(question=question)
    gateway, _ = gateway_for(
        dict(
            segments=[dict(claim_ids=[entry.identity.verified_claim_id])],
            gaps=[dict(type="B", text="Missing percentage calculation.")],
        )
    )
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert fields["status"] in {"completed", "completed_with_caveats"}
    assert trace["coverage"]["complete"]
    request.question = question.replace(target, str(int(target) + 1))
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    assert fields["status"] == "partial_verified_coverage"
    assert not trace["coverage"]["complete"]
