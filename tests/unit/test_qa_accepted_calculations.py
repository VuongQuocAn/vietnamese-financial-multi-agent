"""M6-admitted arithmetic survives M7 projection without recomputation."""

import json
from decimal import ROUND_HALF_UP, Decimal

from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.qa_lite import _numbers_supported, compose_lite
from vietnamese_financial_multi_agent.tools.financial_calculator import (
    DynamicOperation,
    FinancialCalculator,
    render_dynamic,
)
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_multihop_reasoning import reasoning_case
from .test_qa_lite import gateway_for


def admitted_decrease(tmp_path):
    data, batch = reasoning_case(formula="revenue_yoy", operator="percentage_change")
    claim = batch.claims[0]
    sources = sorted(claim.supporting_evidence, key=lambda e: Decimal(e.value))
    operation = DynamicOperation(
        operation_id="change",
        operator="percentage_change",
        inputs=[s.evidence_id for s in sources],
        period_relation="across_periods",
    )
    claim.reasoning.calculation = FinancialCalculator(SnapshotCatalog(**data)).calculate_dynamic(
        {s.evidence_id: s.reference for s in sources}, [operation]
    )
    claim.content = render_dynamic(
        claim.reasoning.calculation, {s.evidence_id: s.label for s in sources}
    )
    repository = VerifiedClaimRepository(tmp_path)
    histories = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)
    assert histories[0].outcome.final.decision == "ACCEPT"
    repository.admit_many(histories)
    return VerifiedClaimRepository(tmp_path).list_all()[0]


def test_admitted_steps_values_and_denominator_reach_m7_verbatim(tmp_path):
    entry = admitted_decrease(tmp_path)
    proof = entry.accepted_claim.reasoning.calculation
    before = entry.model_dump_json()
    key = entry.identity.verified_claim_id
    magnitude = (-Decimal(proof.steps[0].result)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"Chỉ tiêu giảm {str(magnitude).replace('.', ',')}% so với kỳ gốc."
    gateway, calls = gateway_for(dict(segments=[dict(text=text, claim_ids=[key])], gaps=[]))
    request = FinancialQARequest(question="Mức thay đổi so với kỳ gốc?")
    fields, trace = compose_lite(request, [entry], gateway=gateway)
    payload = json.loads(calls[0].messages[-1].content)["verified_claims"][0]
    calculation = payload["reasoning_calculation"]
    step = calculation["steps"][0]
    target, base = proof.steps[0].operation.inputs
    assert calculation["operands"] == proof.model_dump(mode="json")["operands"]
    assert step["operation"] == proof.steps[0].operation.model_dump(mode="json")
    assert step["result"] == proof.steps[0].result and step["unit"] == "percent"
    assert step["base_periods"] == [proof.operands[base].period]
    assert step["target_periods"] == [proof.operands[target].period]
    assert step["expression"] == "(target - base) / base * 100"
    assert payload["calculation_display"] == entry.content
    assert fields["used_verified_claim_ids"] == [key] and not trace["rejected_segments"]
    assert text in fields["answer_vi"] and fields["citations"]
    assert entry.model_dump_json() == before


def test_negative_step_allows_decrease_magnitude_but_not_positive_assertion(tmp_path):
    from types import SimpleNamespace

    from vietnamese_financial_multi_agent.tools.financial_calculator import execute_dynamic

    entry = admitted_decrease(tmp_path)
    # Isolated presentation control with unequal synthetic scalars, not a new
    # financial admission or a mutated Ledger entry.
    proof = entry.accepted_claim.reasoning.model_copy(deep=True)
    operands = proof.calculation.operands
    for operand, value in zip(operands.values(), ("100", "200"), strict=True):
        operand.value = value
    proof.calculation = execute_dynamic(operands, [proof.calculation.steps[0].operation])
    displayed = SimpleNamespace(
        content="",
        accepted_claim=SimpleNamespace(
            reasoning=proof,
            calculation=None,
            supporting_evidence=entry.accepted_claim.supporting_evidence,
        ),
    )
    value = (-Decimal(proof.calculation.steps[0].result)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    rendered = str(value).replace(".", ",")
    assert _numbers_supported(f"Giảm {rendered}% so với kỳ gốc.", [displayed])
    assert not _numbers_supported(f"Tăng {rendered}% so với kỳ gốc.", [displayed])
    assert not _numbers_supported("Giảm 99999% so với kỳ gốc.", [displayed])
