"""Document proof and release controls with separate logical/original identities."""

import pytest
from vietnamese_financial_multi_agent.agents.document_qa_contracts import (
    DocumentCandidate,
    document_intent,
)
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence.composition import EvidencePin, payload_sha256
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.citation_renderer import CitationRenderer
from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
from vietnamese_financial_multi_agent.outputs.qa_composer import VietnameseQAComposer
from vietnamese_financial_multi_agent.outputs.qa_contracts import VietnameseQARequest
from vietnamese_financial_multi_agent.tools.evidence_retrieval import EvidenceRetrievalTools
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.verification.document_verification import (
    verify_document_claim,
)
from vietnamese_financial_multi_agent.verification.evidence_context import EvidenceContextBuilder
from vietnamese_financial_multi_agent.verification.ledger import VerifiedClaimLedger
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

from .test_evidence_composition import sample

SOURCE_DOC = "sha256:" + "a" * 64


def setup(tmp_path, *, source_issues=()):
    manifest, sources, role = sample(tmp_path / "evidence")
    role.document_id = SOURCE_DOC
    role.sources[0].document_id = SOURCE_DOC
    manifest.sources[0].descriptor.document_id = SOURCE_DOC
    manifest.financial_snapshot.document_id = SOURCE_DOC
    role.raw_text = "Kế toán trưởng: Nguyễn Văn An"
    role.resolution_issues.extend(source_issues)
    nearby_role = role.model_copy(
        deep=True, update={"local_evidence_id": "text/1", "raw_text": "Giám đốc"}
    )
    nearby_role.sources[0].reference.source_pointer = "/text_elements/1"
    for row in (role, nearby_role):
        sources.put(row)
    manifest.sources[0].evidence = [
        EvidencePin(
            identity=row.evidence_identity(),
            payload_sha256=payload_sha256(row.model_dump(mode="json")),
        )
        for row in (role, nearby_role)
    ]
    repository = VerifiedClaimRepository(tmp_path / "ledger")
    pipeline = FinancialQAPipeline(
        catalog=SnapshotCatalog([]),
        documents=[
            QADocument(
                document_id="logical",
                company_id="test",
                company_aliases=["TEST"],
                reporting_year=2025,
            )
        ],
        repository=repository,
        compositions=[manifest],
        document_repository=sources,
    )
    return pipeline, manifest, nearby_role


def test_document_pipeline_partial_and_firewall(tmp_path):
    pipeline, manifest, _ = setup(tmp_path)
    request = FinancialQARequest(question="Ai là kế toán trưởng và giám đốc của TEST 2025?")
    result = pipeline.run(request)
    assert result.status == "partial_verified_coverage", result.trace.errors
    assert result.trace.native_decisions == {"ACCEPT": 1, "INVESTIGATE": 1}
    assert result.newly_accepted_claims == 1
    assert [r.target_id for r in result.trace.unanswered_requirements] == ["giam doc"]
    assert "Nguyễn Văn An" in result.answer_vi
    assert result.citations[0].document_id == SOURCE_DOC
    assert result.citations[0].snapshot_id == "native"
    assert result.citations[0].pdf_page == 7

    # Restart reads document v1 proofs without migrating financial v1 entries.
    repository = VerifiedClaimRepository(pipeline.repository.root)
    assert repository.list_all()[0].identity.period is None
    ledger = VerifiedClaimLedger(repository)
    qa = VietnameseQARequest(
        question=request.question,
        company_id="test",
        document_id="logical",
        composition_id=manifest.composition_id,
        composition_sha256=payload_sha256(manifest.model_dump(mode="json")),
    )
    source = VietnameseQAComposer(ledger).compose(qa)
    rendered = CitationRenderer().render_qa(source)
    firewall = InformationFirewall(ledger)
    for changed in (
        source.model_copy(update={"status": "answered"}),
        source.model_copy(update={"used_verified_claim_ids": ["pending:fake"]}),
        source.model_copy(
            update={"answer_vi": source.answer_vi.replace("Nguyễn Văn An", "Bịa tên")}
        ),
    ):
        assert (
            firewall.evaluate_qa(request=qa, response=changed, rendered=rendered).decision
            == "BLOCK"
        )
    other = qa.model_copy(update={"question": "Ai là giám đốc?"})
    assert (
        firewall.evaluate_qa(request=other, response=source, rendered=rendered).decision == "BLOCK"
    )


def test_document_proof_rejects_tampered_relationship_and_source(tmp_path):
    pipeline, manifest, nearby_role = setup(tmp_path)
    answer = pipeline.run(FinancialQARequest(question="Ai là kế toán trưởng?"))
    assert answer.trace.candidate_count == 1, answer.trace.errors
    candidate = DocumentCandidate.model_validate(answer.trace.document_candidates[0])
    tools = EvidenceRetrievalTools.from_composition(
        manifest,
        pipeline.document_repository,
        document_id="logical",
        composition_id="approved",
    )
    try:
        builder = EvidenceContextBuilder(tools=tools)

        def verify(claim):
            return verify_document_claim(claim, builder, manifest, "test", None)

        assert verify(candidate).final.decision == "ACCEPT"
        wrong_page = candidate.citations[0].model_copy(update={"pdf_page": 8})
        wrong_ref = candidate.references[0].model_copy(
            update={"evidence": nearby_role.evidence_identity()}
        )
        for changes in (
            {"person": "Bịa Tên"},
            {"requirement": candidate.requirement.model_copy(update={"target": "giam doc"})},
            {"content": candidate.content + " Đã ký."},
            {"caveats": ["Tên bổ sung không có trong nguồn."]},
            {"quotations": ["Kế toán trưởng: Bịa Tên"]},
            {"document_id": "foreign"},
            {"source_document_id": "foreign"},
            {"snapshot_id": "legacy"},
            {"composition_id": "unapproved"},
            {"citations": [wrong_page]},
            {"references": [wrong_ref]},
        ):
            bad = verify(candidate.model_copy(update=changes))
            assert bad.final.decision != "ACCEPT", changes
            forged = bad.model_copy(
                update={"final": bad.final.model_copy(update={"decision": "ACCEPT"})}
            )
            assert pipeline.repository.admit(forged).status == "rejected"
    finally:
        tools.close_search()


def test_document_path_is_offline_even_when_gateway_fails(tmp_path):
    assert document_intent('BBS 2025 ghi "lợi nhuận sau thuế" là bao nhiêu?')[0] == "other"
    assert document_intent('BBS 2025 ghi "lợi nhuận sau thuế" ở đâu?')[0] == "document"
    pipeline, _, _ = setup(tmp_path)

    class UnavailableGateway:
        def __getattr__(self, name):
            raise AssertionError("deterministic document QA must not invoke the provider")

    pipeline.gateway = UnavailableGateway()
    question = "Ai là kế toán trưởng?"
    fresh = pipeline.run(FinancialQARequest(question=question, allow_gateway=True))
    assert fresh.status == "completed_with_caveats", fresh.trace.errors
    assert fresh.trace.provider_calls == 0
    cached = pipeline.run(FinancialQARequest(question=question))
    assert cached.mode == "CACHE_HIT"
    assert cached.citations == fresh.citations
    assert cached.used_verified_claim_ids == fresh.used_verified_claim_ids


@pytest.mark.parametrize("known_defect", [False, True])
def test_document_source_quality_gate_and_ledger_replay(tmp_path, known_defect):
    # A source review flag is independent of whether the candidate repeats it.
    issue = "pdf_review:word_omitted" if known_defect else "geometry_not_independently_verified"
    pipeline, manifest, _ = setup(tmp_path, source_issues=[issue])
    answer = pipeline.run(FinancialQARequest(question="Ai là kế toán trưởng?"))
    assert answer.trace.candidate_count == 1, answer.trace.errors
    if not known_defect:
        assert answer.newly_accepted_claims == 1
        assert VerifiedClaimRepository(pipeline.repository.root).list_all()
        return
    assert answer.trace.native_decisions == {"INVESTIGATE": 1}
    assert answer.newly_accepted_claims == 0
    assert not answer.citations
    assert not answer.used_verified_claim_ids
    candidate = DocumentCandidate.model_validate(answer.trace.document_candidates[0])
    candidate.caveats = []
    tools = EvidenceRetrievalTools.from_composition(
        manifest, pipeline.document_repository, document_id="logical", composition_id="approved"
    )
    try:
        history = verify_document_claim(
            candidate, EvidenceContextBuilder(tools=tools), manifest, "test", None
        )
        assert history.final.checks["source_quality"] is False
        assert history.final.reasons == ["source_quality"]
        # Reconstruct the formerly accepted proof: its missing quality check must
        # fail admission/replay, even with an exact quotation and valid citations.
        old = history.model_copy(deep=True)
        old.final.checks.pop("source_quality")
        old.final.decision = "ACCEPT"
        old.final.reasons = ["exact_source_support"]
        assert VerifiedClaimRepository(tmp_path / "restart").admit(old).status == "rejected"
    finally:
        tools.close_search()
