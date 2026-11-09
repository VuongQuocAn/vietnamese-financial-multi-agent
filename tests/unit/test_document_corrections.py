"""Synthetic authority fixtures test states only; no production approval is invented."""

from datetime import UTC, datetime

import pytest
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence.composition import EvidencePin, payload_sha256
from vietnamese_financial_multi_agent.evidence.document_corrections import (
    CorrectionApproval,
    DocumentCorrection,
    DocumentSourcePolicy,
    PDFTextReview,
    build_correction_version,
    save_source_policy,
    validate_correction,
)
from vietnamese_financial_multi_agent.evidence.document_repository import DocumentEvidenceRepository
from vietnamese_financial_multi_agent.tools.evidence_retrieval import EvidenceRetrievalTools
from vietnamese_financial_multi_agent.verification.document_verification import (
    judge_document,
    verify_document_claim,
)
from vietnamese_financial_multi_agent.verification.evidence_context import EvidenceContextBuilder
from vietnamese_financial_multi_agent.verification.ledger import (
    LedgerAdmissionError,
    build_verified_claim,
)

from .test_document_qa_pipeline import setup


@pytest.fixture
def correction_case(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_SOURCE_POLICY_ROOT", str(tmp_path / "policy"))
    service, manifest, template = setup(tmp_path)
    original = template.model_copy(
        deep=True,
        update={
            "local_evidence_id": "reviewed-text",
            "raw_text": "Chi phí kiểm định được phân bổ trong thời gian sử dụng 12 tháng.",
        },
    )
    original.sources[0].reference.source_pointer = "/text_elements/10"
    clean = template.model_copy(
        deep=True,
        update={
            "local_evidence_id": "unaffected-text",
            "raw_text": "Chi phí bảo trì được ghi nhận theo thực tế phát sinh trong kỳ.",
        },
    )
    clean.sources[0].reference.source_pointer = "/text_elements/20"
    service.document_repository.put_many([original, clean])
    manifest.sources[0].evidence = [
        EvidencePin(
            identity=r.evidence_identity(), payload_sha256=payload_sha256(r.model_dump(mode="json"))
        )
        for r in [original, clean]
    ]
    question = "Thuyết minh TEST 2025 nói gì về chi phí kiểm định?"
    before = service.run(FinancialQARequest(question=question, force_refresh=True))
    assert before.used_verified_claim_ids
    old_entry = service.repository.list_all()[0]
    page = original.sources[0].reference.anchor.page
    correction = DocumentCorrection(
        original=original.evidence_identity(),
        source_composition_sha256=payload_sha256(manifest.model_dump(mode="json")),
        original_evidence_digest=payload_sha256(original.model_dump(mode="json")),
        page=page.page,
        source_selector="/text_elements/10",
        pdf_source_reference=page.source_ref,
        source_image_digest=page.image.removeprefix("sha256:"),
        original_text=original.raw_text,
        corrected_text=original.raw_text.replace("12", "24"),
        correction_type="material_transcription",
        reason="synthetic visual-review fixture; no actual PDF acceptance",
        review_provenance=PDFTextReview(
            reviewer="unit-test fixture",
            method="controlled_original_pdf_visual_read",
            review_reference="synthetic/review-only",
            observed_text=original.raw_text.replace("12", "24"),
        ),
        validation_status="VALIDATED",
        correction_version="test-v1",
        created_at=datetime.now(UTC),
    )
    rows, updated, release = build_correction_version(
        correction, manifest, service.document_repository
    )
    policy = DocumentSourcePolicy(corrections=[correction], releases=[release])
    new_repository = DocumentEvidenceRepository(tmp_path / "candidate")
    new_repository.put_many([original, clean, *rows])
    return (
        service,
        manifest,
        original,
        clean,
        question,
        old_entry,
        correction,
        rows,
        updated,
        release,
        policy,
        new_repository,
    )


def approve_fixture(policy, release):
    policy.approvals = [
        CorrectionApproval(
            authority="Tech Lead",
            purpose="document_correction_release",
            release_sha256=release.digest,
            decision_reference="synthetic/unit-only-not-production-approval",
        )
    ]
    save_source_policy(policy)


def test_pending_and_approved_versions_keep_inputs_and_require_fresh_verification(correction_case):
    (
        service,
        manifest,
        original,
        clean,
        question,
        old,
        correction,
        rows,
        updated,
        release,
        policy,
        repo,
    ) = correction_case
    original_digest = payload_sha256(original.model_dump(mode="json"))
    save_source_policy(policy)
    service.compositions = (updated,)
    service.document_repository = repo
    pending = service.run(FinancialQARequest(question=question, force_refresh=True))
    assert not pending.used_verified_claim_ids and not pending.citations
    assert "INVESTIGATE" in pending.trace.native_decisions
    approve_fixture(policy, release)
    answer = service.run(FinancialQARequest(question=question, force_refresh=True))
    assert answer.used_verified_claim_ids, answer.trace.errors
    assert correction.corrected_text in answer.answer_vi
    assert all(
        c.snapshot_id == release.snapshot_id and c.pdf_page == correction.page
        for c in answer.citations
    )
    assert repo.get(original.evidence_identity()) == original
    assert payload_sha256(original.model_dump(mode="json")) == original_digest
    assert manifest.composition_id != updated.composition_id
    assert rows[0].evidence_identity() != original.evidence_identity()
    assert clean.evidence_identity() in [p.identity for s in updated.sources for p in s.evidence]
    assert original.evidence_identity() not in [
        p.identity for s in updated.sources for p in s.evidence
    ]
    with pytest.raises(LedgerAdmissionError):
        build_verified_claim(old.history)


def test_current_revocation_filters_warmed_ledger_without_rewriting_or_hiding_clean_claims(
    correction_case,
):
    (
        service,
        manifest,
        original,
        clean,
        question,
        old,
        correction,
        rows,
        updated,
        release,
        policy,
        repo,
    ) = correction_case
    clean_answer = service.run(
        FinancialQARequest(
            question="Thuyết minh TEST 2025 nói gì về chi phí bảo trì?", force_refresh=True
        )
    )
    assert clean_answer.used_verified_claim_ids
    assert len(service.repository.list_all()) == 2
    path = service.repository.root / "verified-claims.json"
    before = path.read_bytes()
    save_source_policy(policy)
    visible = service.repository.list_all()
    assert (
        len(visible) == 1
        and visible[0].identity.verified_claim_id in clean_answer.used_verified_claim_ids
    )
    assert path.read_bytes() == before
    assert service.repository.admit(old.history).status == "rejected"
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="validated_source_review_is_immutable"):
        save_source_policy(DocumentSourcePolicy())


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_document",
        "wrong_snapshot",
        "wrong_release",
        "changed_payload",
        "wrong_selector",
        "unapproved",
        "old_proof",
        "removed_flag",
        "no_pdf_proof",
        "suspected_review",
    ],
)
def test_correction_negative_bindings_and_authority(correction_case, defect):
    (
        service,
        manifest,
        original,
        clean,
        question,
        old,
        correction,
        rows,
        updated,
        release,
        policy,
        repo,
    ) = correction_case
    if defect == "suspected_review":
        proposed = correction.model_copy(update={"validation_status": "PROPOSED"})
        save_source_policy(DocumentSourcePolicy(corrections=[proposed]))
        decision = judge_document(old.accepted_claim, old.decision.evidence)
        assert decision.decision != "ACCEPT" and "source_review_required" in decision.caveats
        return
    approve_fixture(policy, release)
    service.compositions = (updated,)
    service.document_repository = repo
    result = service.run(FinancialQARequest(question=question, force_refresh=True))
    assert result.used_verified_claim_ids, result.trace.errors
    entry = next(
        e for e in service.repository.list_all() if e.identity.snapshot_id == release.snapshot_id
    )
    claim = entry.accepted_claim.model_copy(deep=True)
    contexts = [c.model_copy(deep=True) for c in entry.decision.evidence]
    if defect == "wrong_document":
        claim.source_document_id = "other"
    elif defect == "wrong_snapshot":
        claim.snapshot_id = "other"
    elif defect == "wrong_release":
        claim.composition_sha256 = "0" * 64
    elif defect == "changed_payload":
        contexts[0].content["evidence_payload_sha256"] = "0" * 64
    elif defect == "wrong_selector":
        contexts[0].citations[0].source.reference.source_pointer = "/text_elements/999"
    elif defect == "unapproved":
        policy.approvals = []
        save_source_policy(policy)
        assert (
            not service.repository.list_all()
        )  # Even previously cached ACCEPT is no longer current.
    elif defect == "old_proof":
        tools = EvidenceRetrievalTools.from_composition(
            updated, repo, document_id="logical", composition_id=updated.composition_id
        )
        replay = verify_document_claim(
            old.accepted_claim, EvidenceContextBuilder(tools=tools), updated, "test", None
        )
        assert replay.final.decision != "ACCEPT"
        return
    elif defect == "removed_flag":
        claim = old.accepted_claim.model_copy(deep=True)
        claim.caveats = []
        contexts = [c.model_copy(deep=True) for c in old.decision.evidence]
        for c in contexts:
            c.caveats = []
    elif defect == "no_pdf_proof":
        proposed = correction.model_copy(update={"validation_status": "PROPOSED"})
        with pytest.raises(ValueError, match="missing_source_fingerprint"):
            validate_correction(proposed, original, manifest, "missing.pdf", {})
        return
    decision = judge_document(claim, contexts)
    assert decision.decision != "ACCEPT", (defect, decision)
