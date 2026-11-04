"""Bounded reasoning, upstream compatibility and untrusted Gateway controls."""

import json
from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification import (
    DeterministicFinancialValidator,
    EvidenceCritic,
    FinancialLogicCritic,
    FinancialLogicCriticResult,
)
from vietnamese_financial_multi_agent.verification.logic_rules import classify
from vietnamese_financial_multi_agent.verification.validation_contracts import (
    validation_result_digest,
)

from .test_evidence_critic import response
from .test_financial_validators import batch_for
from .test_m4_execution import fixture


def inputs(tail="", *, metric=True):
    data = fixture()
    batch = batch_for(data, metric=metric)
    if tail:
        batch.claims[0].kind = "supported_interpretation"
        batch.claims[0].content += " " + tail
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    evidence = EvidenceCritic(catalog).assess(batch, validation)
    return data, batch, validation, evidence


def gateway(mutate=None, captured=None, *, status="insufficient_context"):
    def transport(request):
        payload = json.loads(request.messages[-1].content)
        if captured is not None:
            captured.append(payload)
        wire = dict(
            candidate_id=payload["candidate_id"],
            assertions=[
                dict(
                    assertion_id=a["assertion_id"],
                    status=status,
                    reason="missing_premises"
                    if status == "insufficient_context"
                    else "bounded_interpretation",
                    required_premises=a["minimum_required_premises"],
                    missing_evidence=a["minimum_required_premises"]
                    if status == "insufficient_context"
                    else [],
                    premise_ids=payload["allowed_premise_ids"],
                    evidence_ids=[e["evidence_id"] for e in payload["evidence"]],
                    limitations=["bounded_to_supplied_evidence"],
                )
                for a in payload["assertions"]
            ],
        )
        if mutate:
            mutate(wire)
        return response(request, wire)

    return SharedLLMGateway({"gemini": transport})


@pytest.mark.parametrize(
    ("tail", "status", "reason"),
    [
        (
            "Chắc chắn khả năng sinh lời đã cải thiện.",
            "insufficient_context",
            "comparison_evidence_required",
        ),
        ("Do chi phí giảm nên lợi nhuận tăng.", "insufficient_context", "causal_evidence_missing"),
        (
            "Debt-to-Assets cao cho thấy doanh nghiệp chắc chắn mất khả năng thanh toán.",
            "insufficient_context",
            "solvency_requires_additional_context",
        ),
        (
            "Dòng tiền từ hoạt động kinh doanh âm nên doanh nghiệp chắc chắn thua lỗ.",
            "inconsistent",
            "cash_flow_is_not_net_income",
        ),
        ("Doanh thu đồng nghĩa dòng tiền.", "inconsistent", "accrual_is_not_cash_flow"),
        (
            "Dòng tiền đầu tư âm chứng tỏ kinh doanh kém.",
            "insufficient_context",
            "investing_outflow_not_performance_proof",
        ),
        (
            "CFO dương chứng tỏ chất lượng lợi nhuận cao.",
            "insufficient_context",
            "earnings_quality_requires_context",
        ),
    ],
)
def test_deterministic_reasoning_distinguishes_missing_context(tail, status, reason):
    _, batch, validation, evidence = inputs(tail)
    result = FinancialLogicCritic(gateway()).assess(batch, validation, evidence)
    assertions = result.claims[0].assertions
    assert not result.errors and not result.claims[0].errors
    assert assertions[0].status == "not_applicable"
    assert assertions[-1].status == status and reason in assertions[-1].reason_codes
    assert result.claims[0].trace.llm.calls == 0


def test_separate_assertions_roundtrip_and_read_only():
    data, batch, validation, evidence = inputs("Doanh thu tăng và doanh thu giảm.")
    before = [x.model_dump_json() for x in (batch, validation, evidence)]
    original_catalog = deepcopy(data)
    result = FinancialLogicCritic().assess(batch, validation, evidence)
    assert [a.status for a in result.claims[0].assertions] == [
        "not_applicable",
        "inconsistent",
        "inconsistent",
    ]
    assert all(a.support_findings and a.validation_checks for a in result.claims[0].assertions)
    assert FinancialLogicCriticResult.model_validate_json(result.model_dump_json()) == result
    assert [x.model_dump_json() for x in (batch, validation, evidence)] == before
    assert data == original_catalog
    assert batch.claims[0].decision is None and not result.financial_fact_verified


@pytest.mark.parametrize(
    "control", ["input", "validation", "evidence_content", "reference", "support_id", "conflict"]
)
def test_stale_inputs_return_structured_errors(control):
    _, batch, validation, evidence = inputs("Khả năng sinh lời tiến bộ.")
    if control == "input":
        batch.claims[0].content += " Đã cải thiện."
    elif control == "validation":
        validation.claims[0].checks[0].reason_code = "stale"
    elif control == "evidence_content":
        evidence.claims[0].content += " stale"
    elif control == "reference":
        context = evidence.claims[0].evidence[0]
        context.reference = context.reference.model_copy(
            update={
                "observation": context.reference.observation.model_copy(
                    update={"local_id": "unrelated"}
                )
            }
        )
    elif control == "support_id":
        evidence.claims[0].assertions[-1].check_references = ["invented"]
    else:
        validation.claims[0].checks[0].conflict_ids = ["invented"]
        evidence.validation_result_sha256 = validation_result_digest(validation)
    result = FinancialLogicCritic(gateway()).assess(batch, validation, evidence)
    assert result.errors or result.claims[0].errors
    assert all(a.status == "insufficient_context" for a in result.claims[0].assertions)
    assert result.claims[0].trace.llm.calls == 0


def test_legacy_requires_original_paired_inputs():
    _, batch, validation, evidence = inputs()
    validation.verification_input_sha256 = None
    evidence.verification_input_sha256 = evidence.validation_result_sha256 = None
    critic = FinancialLogicCritic()
    assert critic.assess(batch, validation, evidence).errors
    result = critic.assess(
        batch,
        validation,
        evidence,
        validated_batch=batch,
        evidence_batch=batch,
        evidence_validation=validation,
    )
    assert not result.errors and result.claims[0].assertions[0].status == "not_applicable"
    stale = batch.model_copy(deep=True)
    stale.claims[0].content += " stale"
    assert critic.assess(
        batch,
        validation,
        evidence,
        validated_batch=batch,
        evidence_batch=stale,
        evidence_validation=validation,
    ).errors


@pytest.mark.parametrize(
    "control",
    ["candidate", "assertion", "reference", "premise", "fact", "decision", "missing", "promotion"],
)
def test_semantic_output_is_locally_validated(control):
    _, batch, validation, evidence = inputs("Khả năng sinh lời tiến bộ.")

    def mutate(wire):
        item = wire["assertions"][0]
        if control == "candidate":
            wire["candidate_id"] = "invented"
        elif control == "assertion":
            item["assertion_id"] = "A1"
        elif control == "reference":
            item["evidence_ids"] = ["invented"]
        elif control == "premise":
            item["premise_ids"] = ["support:A2"]
        elif control in {"fact", "decision"}:
            item[control] = "invented"
        elif control == "missing":
            item["missing_evidence"] = []
        else:
            item.update(
                status="consistent",
                reason="bounded_interpretation",
                missing_evidence=[],
                required_premises=["numeric_context"],
            )

    captured = []
    result = FinancialLogicCritic(gateway(mutate, captured)).assess(batch, validation, evidence)
    claim = result.claims[0]
    assert claim.errors[-1].code == "semantic_logic_output_invalid"
    assert claim.assertions[-1].status == "insufficient_context"
    assert claim.assertions[0].status == "not_applicable"
    assert claim.trace.llm.calls == 1 and len(captured) == 1
    assert "question" not in captured[0] and "conversation" not in captured[0]
    assert all("citations" not in p for p in captured[0]["numeric_premises"])
    assert all(
        "source" not in citation for e in captured[0]["evidence"] for citation in e["citations"]
    )


def test_numeric_fail_and_undetermined_never_promoted_or_sent_to_gemini():
    for mode in ("fail", "undetermined", "unsupported"):
        _, batch, validation, evidence = inputs("Quản trị chi phí là động lực chính của kết quả.")
        check = next(c for c in validation.claims[0].checks if c.check_id == "numeric")
        if mode in {"fail", "undetermined"}:
            check.status = mode
            evidence.claims[0].deterministic_findings = validation.claims[0].checks
            evidence.validation_result_sha256 = validation_result_digest(validation)
        else:
            evidence.claims[0].assertions[0].status = "unsupported"
        result = FinancialLogicCritic(gateway(status="consistent")).assess(
            batch, validation, evidence
        )
        assert result.claims[0].trace.llm.calls == 0
        assert result.claims[0].assertions[-1].status == "insufficient_context"


@pytest.mark.parametrize("context", ["scope", "snapshot"])
def test_comparability_gates_remain_blocked(context):
    _, batch, validation, evidence = inputs("Khả năng sinh lời đã cải thiện.")
    check = next(
        c
        for c in validation.claims[0].checks
        if c.check_id == ("reporting_scope" if context == "scope" else "cross_document")
    )
    check.status = "fail" if context == "scope" else "undetermined"
    evidence.claims[0].deterministic_findings = validation.claims[0].checks
    evidence.validation_result_sha256 = validation_result_digest(validation)
    result = FinancialLogicCritic(gateway()).assess(batch, validation, evidence)
    assert all(a.status == "insufficient_context" for a in result.claims[0].assertions)
    assert result.claims[0].trace.llm.calls == 0


def test_semantic_budget_counts_failed_calls_and_keeps_other_claims():
    _, batch, validation, evidence = inputs("Khả năng sinh lời tiến bộ.")
    critic = FinancialLogicCritic(
        gateway(lambda wire: wire.update(decision="forbidden")), max_semantic_calls=1
    )
    first = critic.assess(batch, validation, evidence)
    assert first.claims[0].errors[-1].code == "semantic_logic_output_invalid"
    assert first.claims[0].trace.llm.calls == 1
    second = critic.assess(batch, validation, evidence)
    assert second.claims[0].errors[-1].code == "semantic_call_budget_exhausted"
    assert second.claims[0].trace.llm.calls == 0
    with pytest.raises(ValueError):
        FinancialLogicCritic(max_semantic_calls=7)
    # Candidate-local corruption preserves the other candidate's independent result.
    other = batch.claims[0].model_copy(deep=True)
    other.candidate_id = other.provenance.m5_candidate_id = "C2"
    batch.claims.append(other)
    data = fixture()
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    evidence = EvidenceCritic(catalog).assess(batch, validation)
    evidence.claims[0].content = "stale"
    result = FinancialLogicCritic(gateway()).assess(batch, validation, evidence)
    assert result.claims[0].errors and not result.claims[1].errors


def test_approved_yoy_and_financial_sign_are_bound_to_target():
    from types import SimpleNamespace

    claim = SimpleNamespace(
        content="Revenue YoY năm 2025 đạt -14,32%.",
        calculation=SimpleNamespace(trace=SimpleNamespace(numerator="-100")),
    )
    check = SimpleNamespace(check_id="numeric", status="pass", expected={"value": "-14.32"})
    assert (
        classify("Tăng trưởng doanh thu kỳ 2025 là -14,32%", claim, [check])[0] == "not_applicable"
    )
    assert classify("Doanh thu tăng.", claim, [check])[:2] == (
        "inconsistent",
        "approved_yoy_direction_contradiction",
    )
    assert classify("Doanh thu giảm.", claim, [check])[0] == "consistent"
    assert classify("Lợi nhuận tăng.", claim, [check])[0] == "insufficient_context"
    claim.content = "Revenue YoY năm 2025 đạt 0,00%."
    claim.calculation.trace.numerator = "0.001"
    check.expected = {"value": "0.00"}
    assert classify("Doanh thu ổn định.", claim, [check])[0] == "inconsistent"
    assert classify("Doanh thu tăng.", claim, [check])[0] == "consistent"
    claim.content = "Doanh thu thuần năm 2025 là 20 VND."
    check.expected = {"value": "20"}
    assert classify("Doanh thu dương.", claim, [check])[0] == "consistent"
    assert classify("Doanh thu âm.", claim, [check])[0] == "inconsistent"
    assert classify("Lợi nhuận dương.", claim, [check]) is None
    assert classify("Doanh thu dương, chứng tỏ doanh nghiệp hiệu quả.", claim, [check]) is None
