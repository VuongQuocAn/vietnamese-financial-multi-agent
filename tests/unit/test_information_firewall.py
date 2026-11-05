"""Firewall engineering controls; real BBS oracle is evaluated separately."""

import copy
import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.outputs import (
    CitationRenderer,
    FirewallDecision,
    GroundedReportWriter,
    InformationFirewall,
    VietnameseQAComposer,
    VietnameseQARequest,
    validate_qa_response,
)
from vietnamese_financial_multi_agent.outputs.qa_composer import _answer_text
from vietnamese_financial_multi_agent.verification import (
    VerifiedClaimMatches,
    VerifiedClaimQuery,
)

from .test_grounded_report_writer import request_for
from .test_vietnamese_qa_composer import qa as qa_fixture


@pytest.fixture
def qa(tmp_path):
    return qa_fixture.__wrapped__(tmp_path)


@pytest.fixture
def evaluator():
    path = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(path))
    try:
        spec = importlib.util.spec_from_file_location(
            "firewall_evaluator", path / "evaluate_m7_05_firewall.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(path))


def qa_inputs(ledger, context, question="Doanh thu là bao nhiêu?"):
    request = VietnameseQARequest(question=question, **context)
    source = VietnameseQAComposer(ledger).compose(request)
    return request, source, CitationRenderer().render_qa(source)


def evaluate(firewall, mode, inputs):
    request, source, rendered = inputs
    return (
        firewall.evaluate_qa(request=request, response=source, rendered=rendered)
        if mode == "qa"
        else firewall.evaluate_report(request=request, report=source, rendered=rendered)
    )


@pytest.mark.parametrize(
    "question,status",
    [
        ("Doanh thu là bao nhiêu?", "answered"),
        ("Doanh thu và biên lợi nhuận gộp?", "answered"),
        ("Doanh thu và ROE?", "partial"),
        ("Tổng tài sản?", "abstained"),
        ("ROE?", "unsupported"),
        ("Lợi nhuận?", "clarification_required"),
        ("So sánh doanh thu 2024 và 2025", "unsupported"),
    ],
)
def test_qa_valid_release_status_and_no_mutation(qa, question, status):
    repository, ledger, context = qa
    inputs = qa_inputs(ledger, context, question)
    before = [i.model_dump_json() for i in inputs]
    disk = (repository.root / "verified-claims.json").read_bytes()
    result = evaluate(InformationFirewall(ledger), "qa", inputs)
    assert result.original_status == status
    assert result.decision == (
        "CLARIFICATION_REQUIRED"
        if status == "clarification_required"
        else "ALLOW_WITH_CAVEAT"
        if inputs[1].caveats
        else "ALLOW"
    ), result.blockers
    assert result.validation_result.valid
    assert result.ledger_queries == 1
    assert before == [i.model_dump_json() for i in inputs]
    assert disk == (repository.root / "verified-claims.json").read_bytes()
    assert FirewallDecision.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        FirewallDecision.model_validate({**result.model_dump(), "unexpected": True})


@pytest.mark.parametrize(
    "options,status",
    [
        ({}, "partial"),
        ({"report_type": "profitability"}, "generated"),
        ({"period": None}, "clarification_required"),
        ({"snapshot_id": "unknown"}, "abstained"),
        ({"title": "So sánh 2024 và 2025"}, "unsupported"),
    ],
)
def test_report_valid_releases_and_refusals(qa, options, status):
    _, ledger, context = qa
    request = request_for(ledger, context, **options)
    report = GroundedReportWriter(ledger).write(request)
    inputs = request, report, CitationRenderer().render_report(report)
    result = evaluate(InformationFirewall(ledger), "report", inputs)
    assert result.original_status == status
    assert result.decision != "BLOCK", result.blockers
    assert result.release_status == (
        "clarification_required" if status == "clarification_required" else "released"
    )


@pytest.mark.parametrize(
    "mode,mutation",
    [
        ("qa", "fake_verified_id"),
        ("qa", "pending_candidate_id"),
        ("qa", "accepted_changed_content"),
        ("qa", "wrong_document"),
        ("qa", "wrong_snapshot"),
        ("qa", "wrong_period"),
        ("qa", "false_scope"),
        ("qa", "removed_caveat"),
        ("qa", "removed_citation"),
        ("qa", "unsupported_cause"),
        ("qa", "unsupported_recommendation"),
        ("qa", "invented_ratio"),
        ("qa", "numeric_mutation"),
        ("qa", "unit_mutation"),
        ("qa", "modified_answer"),
        ("qa", "forged_validation"),
        ("qa", "changed_original_question"),
        ("qa", "joint_requirement_forgery"),
        ("qa", "empty_answered"),
        ("qa", "wrong_requirements"),
        ("report", "changed_paragraph"),
        ("report", "removed_paragraph"),
        ("report", "reordered_paragraph"),
        ("report", "missing_section"),
        ("report", "fabricated_page"),
        ("report", "fabricated_cell"),
        ("report", "wrong_anchor"),
        ("report", "source_pointer"),
        ("report", "forged_render_status"),
        ("report", "wrong_paragraph_binding"),
        ("report", "rendered_text"),
        ("report", "wrong_marker"),
        ("report", "provenance_upgrade"),
        ("report", "lost_rendered_caveats"),
        ("report", "missing_reference"),
        ("report", "forged_status"),
    ],
)
def test_adversarial_gate_and_safe_body(qa, evaluator, mode, mutation):
    _, ledger, context = qa
    if mode == "qa":
        inputs = qa_inputs(ledger, context)
    else:
        request = request_for(ledger, context)
        report = GroundedReportWriter(ledger).write(request)
        inputs = request, report, CitationRenderer().render_report(report)
    inputs = evaluator.mutate(*inputs, mutation)
    result = evaluate(InformationFirewall(ledger), mode, inputs)
    assert result.decision == "BLOCK", (mutation, result)
    assert result.blockers
    assert result.validated_output.rendered_text is None
    assert not result.validated_output.references
    assert not result.validated_verified_claim_ids
    assert result.validated_output.message_vi


def test_request_binding_gap_is_closed_without_changing_accepted_qa(qa):
    _, ledger, context = qa
    request, response, rendered = qa_inputs(ledger, context)
    request.reporting_scope = "consolidated"
    # M7-01's local validator has no original request input: a P1 cross-module gap.
    assert validate_qa_response(response, ledger.find_claims(VerifiedClaimQuery()).claims).valid
    result = evaluate(InformationFirewall(ledger), "qa", (request, response, rendered))
    assert result.decision == "BLOCK"
    assert "requested_scope_not_confirmed" in result.blockers


def test_untrusted_validation_flags_do_not_grant_or_deny_release(qa):
    _, ledger, context = qa
    request, response, rendered = qa_inputs(ledger, context)
    response.validation_result.valid = False
    response.validation_result.errors = ["caller_says_invalid"]
    rendered.validation_result.valid = False
    result = evaluate(InformationFirewall(ledger), "qa", (request, response, rendered))
    assert result.decision == "ALLOW_WITH_CAVEAT", result.blockers


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "reject", "status", "content", "kind", "source", "identity", "read_failure"],
)
def test_independent_ledger_revalidation(qa, mutation):
    repository, ledger, context = qa
    inputs = qa_inputs(ledger, context)
    entries = copy.deepcopy(repository.query(VerifiedClaimQuery(**context)))
    entry = next(
        e for e in entries if e.identity.verified_claim_id in inputs[1].used_verified_claim_ids
    )
    if mutation == "duplicate":
        entries.append(entry)
    elif mutation == "reject":
        entry.decision.decision = "REJECT"
    elif mutation == "status":
        entry.verification_status = "pending"
    elif mutation == "content":
        entry.accepted_claim.content += " Tăng trưởng mạnh."
    elif mutation == "kind":
        entry.identity.kind = "supported_interpretation"
    elif mutation == "source":
        entry.citations[0].document_id = "other"
    elif mutation == "identity":
        entry.identity.snapshot_id = "other"

    class BadLedger:
        def find_claims(self, query):
            if mutation == "read_failure":
                raise OSError("not for display")
            return VerifiedClaimMatches(claims=entries, status="matched")

    result = evaluate(InformationFirewall(BadLedger()), "qa", inputs)
    assert result.decision == "BLOCK"
    assert result.validated_output.rendered_text is None


def test_missing_binding_and_invalid_typed_inputs_fail_safely(qa):
    _, ledger, context = qa
    request, response, rendered = qa_inputs(ledger, context | {"snapshot_id": None})
    result = evaluate(InformationFirewall(ledger), "qa", (request, response, rendered))
    assert result.decision == "CLARIFICATION_REQUIRED"
    assert result.ledger_queries == 0 and result.validated_output.rendered_text is None
    result = evaluate(InformationFirewall(ledger), "qa", (request.model_dump(), response, rendered))
    assert result.decision == "BLOCK" and not result.validated_citation_ids


def test_contract_rejects_blocked_financial_view(qa):
    _, ledger, context = qa
    result = evaluate(InformationFirewall(ledger), "qa", qa_inputs(ledger, context))
    wire = result.model_dump()
    wire.update(decision="BLOCK", release_status="blocked")
    with pytest.raises(ValidationError, match="unreleased_view"):
        FirewallDecision.model_validate(wire)


def test_caveats_do_not_hide_critical_failure_and_no_generation(qa, monkeypatch):
    _, ledger, context = qa
    inputs = qa_inputs(ledger, context)
    inputs[1].grounded_segments[0].content += " Doanh nghiệp tài chính rất tốt."
    inputs[1].answer_vi = _answer_text(inputs[1])

    def forbidden(*args, **kwargs):
        pytest.fail("firewall_must_not_generate")

    monkeypatch.setattr(VietnameseQAComposer, "compose", forbidden)
    monkeypatch.setattr(GroundedReportWriter, "write", forbidden)
    result = evaluate(InformationFirewall(ledger), "qa", inputs)
    assert result.decision == "BLOCK" and result.warnings


def test_annual_native_periods_and_equivalent_wordings_are_released(qa):
    from vietnamese_financial_multi_agent.verification import (
        BoundedVerificationLoop,
        VerificationHistory,
        VerificationProofContext,
    )

    from .test_financial_validators import batch_for
    from .test_m4_execution import fixture
    from .test_verification_judge import passes

    repository, ledger, context = qa
    for metric in (False, True):
        data = fixture("debt_to_assets") if metric else fixture()
        data["facts"].sort(key=lambda f: f.canonical_item_id != "b02.net_revenue")
        batch = batch_for(data, metric=metric)
        if not metric:
            batch.claims[0].content = batch.claims[0].content.replace(" là ", " đạt ")
            batch.caveats.append("variant_mandatory_caveat")
        validation, evidence, logic = passes(data, batch)
        result = repository.admit(
            VerificationHistory(
                contexts=[
                    VerificationProofContext(
                        batch=batch, validation=validation, evidence=evidence, logic=logic
                    )
                ],
                outcome=BoundedVerificationLoop().start(
                    batch, validation, evidence, logic, candidate_id=batch.claims[0].candidate_id
                ),
            )
        )
        assert result.status == "stored"
    request = request_for(ledger, context, period_context={"period_end": "2030-12-31"})
    source = GroundedReportWriter(ledger).write(request)
    rendered = CitationRenderer().render_report(source)
    decision = evaluate(InformationFirewall(ledger), "report", (request, source, rendered))
    assert decision.decision == "ALLOW_WITH_CAVEAT", decision.blockers
    assert decision.ledger_queries == 2
    assert source.scope.included_periods == ["2030", "2030-12-31"]
    assert "variant_mandatory_caveat" in decision.validated_output.caveats
    facts = [
        s
        for section in request.outline.sections
        for s in section.claim_slots
        if s.claim_kind == "fact"
    ]
    assert len(facts) == 2
    assert sum(s.accepted_content in source.body_vi for s in facts) == 1
    for slot in facts:
        assert set(slot.verified_claim_ids) <= set(decision.validated_verified_claim_ids)
    # Removing an equivalent identity/caveat breaks the full outline inventory.
    next(section for section in request.outline.sections if section.claim_slots).claim_slots.pop()
    assert (
        evaluate(InformationFirewall(ledger), "report", (request, source, rendered)).decision
        == "BLOCK"
    )


def test_frozen_oracle_pin_detects_label_tampering(evaluator, tmp_path):
    from hashlib import sha256

    root = Path(__file__).resolve().parents[2]
    raw = (root / "evaluation/m7-05-scenarios.json").read_bytes()
    assert sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == evaluator.ORACLE_SHA256
    mutated = raw.replace(b'"ALLOW_WITH_CAVEAT"', b'"ALLOW"', 1)
    assert sha256(mutated.replace(b"\r\n", b"\n")).hexdigest() != evaluator.ORACLE_SHA256


def test_changed_percentage_is_blocked_with_matching_rendered_view(qa, evaluator):
    _, ledger, context = qa
    inputs = qa_inputs(ledger, context, "Biên lợi nhuận gộp là bao nhiêu?")
    assert "%" in inputs[1].grounded_segments[0].content
    mutated = evaluator.mutate(*inputs, "numeric_mutation")
    assert mutated[1].grounded_segments[0].content != inputs[1].grounded_segments[0].content
    result = evaluate(InformationFirewall(ledger), "qa", mutated)
    assert result.decision == "BLOCK" and result.validated_output.rendered_text is None
