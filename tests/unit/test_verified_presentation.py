"""Small synthetic controls for verified presentation and independent arithmetic."""

import json

from vietnamese_financial_multi_agent.agents import profitability_specialist as profit
from vietnamese_financial_multi_agent.agents.specialist_common import (
    SpecialistResult,
    _prepare_analysis,
    generate_candidates,
)
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification.contracts import CandidateClaim
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_multihop_reasoning import reasoning_case
from .test_qa_lite import admitted as admitted
from .test_qa_lite import gateway_for


def test_m7_presents_only_accepted_statements_with_or_without_legacy_text(admitted):
    request, entry = admitted
    key = entry.identity.verified_claim_id
    for segment in (
        {"claim_ids": [key]},
        {"claim_ids": [key], "text": "Tài sản tài trợ cho nợ; chắc chắn mất thanh khoản, 999%."},
    ):
        gateway, calls = gateway_for({"segments": [segment], "gaps": []})
        fields, trace = compose_lite(request, [entry], gateway=gateway)
        assert entry.content in fields["answer_vi"]
        assert "tài trợ" not in fields["answer_vi"] and "999%" not in fields["answer_vi"]
        assert fields["used_verified_claim_ids"] == [key] and not trace["rejected_segments"]
        assert trace["rendering_mode"] == "accepted_claims" and len(calls) == 1


def test_source_caveats_and_existing_metric_do_not_become_model_computation():
    source = batch_for(fixture(), metric=True).claims[0].supporting_evidence[0]
    source.caveats = [f"source_caveat_{i}" for i in range(9)]
    raw = dict(
        statement="Diễn giải chỉ tiêu đã có.",
        evidence_ids=[source.evidence_id],
        limitations=source.caveats + ["Chưa suy ra nguyên nhân."],
        operations=[dict(operation_id="redundant", operator="ratio", inputs=["E2", "E3"])],
    )
    original = json.dumps(raw)
    analysis = _prepare_analysis(raw, {source.evidence_id: source})
    assert analysis.operations == [] and analysis.limitations == ["Chưa suy ra nguyên nhân."]
    assert len(source.caveats) == 9 and json.dumps(raw) == original


def test_wrong_model_numbers_do_not_remove_independent_calculator_candidates():
    # Different operations/period relations; no BBS constants in implementation.
    for formula, operator in (("revenue_yoy", "percentage_change"), ("gross_margin", "subtract")):
        data, batch = reasoning_case(formula=formula, operator=operator)
        sources = batch.claims[0].supporting_evidence
        operation = batch.claims[0].reasoning.calculation.steps[0].operation
        result = SpecialistResult(
            question="So sánh hai nguồn được giao.",
            role="profitability",
            upstream_status="completed",
            supporting_evidence=sources,
        )
        body = dict(
            claims=[],
            missing_information=[],
            analyses=[
                dict(
                    statement="Kết quả tăng 999999999%.",
                    evidence_ids=[sources[0].evidence_id],
                    operations=[operation.model_dump(mode="json")],
                    claim_type="reasoned_conclusion"
                    if operator == "percentage_change"
                    else "conditional_inference",
                )
            ],
        )
        gateway, _ = gateway_for(body)
        generate_candidates(
            gateway=gateway,
            model=ModelIdentity(provider="gemini", model="synthetic"),
            result=result,
            prompt={"instruction": "synthetic"},
            proposal_type=profit.ProfitabilityProposal,
            render=profit._render,
            prefix="control",
        )
        claims = []
        for c in result.candidates:
            wire = c.model_dump(mode="json")
            wire.update(
                supporting_evidence=[
                    s.model_dump(mode="json")
                    for s in sources
                    if s.evidence_id in c.supporting_evidence_ids
                ],
                provenance=dict(
                    m5_candidate_id=c.candidate_id,
                    origins=[],
                    origin_roles=[],
                    supporting_references=[r.model_dump(mode="json") for r in c.fact_references],
                ),
            )
            claims.append(CandidateClaim.model_validate_json(json.dumps(wire)))
        batch.claims = claims
        histories = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)
        derived = next(
            h
            for h in histories
            if h.proof.batch.claims[0].reasoning
            and h.proof.batch.claims[0].reasoning.claim_type == "derived_fact"
        )
        assert derived.outcome.final.decision == "ACCEPT"
        analysis = next(
            h
            for h in histories
            if h.proof.batch.claims[0].reasoning
            and h.proof.batch.claims[0].reasoning.claim_type != "derived_fact"
        )
        assert analysis.outcome.final.decision == "ABSTAIN"
        assert "999999999" not in derived.outcome.final.original_claim.content
