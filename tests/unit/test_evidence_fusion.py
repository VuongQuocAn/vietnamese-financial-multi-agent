"""QA-01b controls with real M4/M5/M6/M7 logic on small synthetic inputs."""

import pytest
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence.composition import EvidencePin, payload_sha256
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.citation_renderer import CitationRenderer
from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
from vietnamese_financial_multi_agent.outputs.qa_composer import VietnameseQAComposer
from vietnamese_financial_multi_agent.outputs.qa_contracts import VietnameseQARequest
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.verification.ledger import VerifiedClaimLedger
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

from .test_evidence_composition import sample
from .test_m4_execution import fixture


def setup(tmp_path, defect=False):
    data = fixture()
    manifest, repo, row = sample(tmp_path / "sources")
    descriptor = data["descriptors"][0]
    manifest.logical_document_id = descriptor.document_id
    manifest.financial_snapshot = descriptor
    row.document_id = descriptor.document_id
    row.sources[0].document_id = descriptor.document_id
    manifest.sources[0].descriptor.document_id = descriptor.document_id
    row.raw_text = "Kế toán trưởng: Nguyễn Văn An"
    if defect:
        row.resolution_issues = ["pdf_review:known_defect"]
    repo.put(row)
    manifest.sources[0].evidence = [
        EvidencePin(
            identity=row.evidence_identity(),
            payload_sha256=payload_sha256(row.model_dump(mode="json")),
        )
    ]
    service = FinancialQAPipeline(
        catalog=SnapshotCatalog(**data),
        documents=[
            QADocument(
                document_id=descriptor.document_id,
                company_id=data["facts"][0].company_id,
                company_aliases=["TEST"],
                reporting_year=2030,
            )
        ],
        repository=VerifiedClaimRepository(tmp_path / "ledger"),
        compositions=[manifest],
        document_repository=repo,
    )
    request = FinancialQARequest(
        question="Biên lợi nhuận gộp TEST 2030 là bao nhiêu và ai là kế toán trưởng?",
        execution_mode="deterministic",
    )
    return service, request


def test_fusion_actual_tools_verification_release_restart_and_firewall(tmp_path):
    service, request = setup(tmp_path)
    result = service.run(request)
    assert result.status == "completed_with_caveats", result.trace.model_dump()
    assert result.trace.firewall_decision == "ALLOW_WITH_CAVEAT"
    assert len(result.used_verified_claim_ids) == 2
    assert result.trace.provider_calls == 0
    assert result.trace.executed_agents == []  # Baseline Python components are not LLM agents.
    assert (
        any(e["event"] == "TOOL_EXECUTED" for e in result.trace.execution_events)
        or result.trace.tool_calls
    )
    assert {"calculate_financial_metric", "search_document_evidence", "get_graph_context"} <= {
        call["tool"] for call in result.trace.tool_calls
    }
    snapshots = {c.snapshot_id for c in result.citations}
    assert snapshots == {"selected-0", "native"}
    service.repository = VerifiedClaimRepository(service.repository.root)
    cached = service.run(request)
    assert cached.used_verified_claim_ids == result.used_verified_claim_ids
    assert cached.mode == "CACHE_HIT"
    assert not cached.trace.executed_agents
    context = result.trace.fusion_bundle["context"]
    qa = VietnameseQARequest(
        **{k: v for k, v in context.items() if k in VietnameseQARequest.model_fields}
    )
    ledger = VerifiedClaimLedger(service.repository)
    source = VietnameseQAComposer(ledger).compose(qa)
    rendered = CitationRenderer().render_qa(source)
    source.answer_vi += " Doanh thu tăng do chính sách kế toán."
    assert (
        InformationFirewall(ledger)
        .evaluate_qa(request=qa, response=source, rendered=rendered)
        .decision
        == "BLOCK"
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"company_id": "wrong"},
        {"document_id": "wrong"},
        {"snapshot_id": "wrong"},
        {"composition_id": "wrong"},
        {"composition_sha256": "wrong"},
        {"document_snapshots": ["legacy"]},
        {"reporting_scope": "consolidated"},
        {"question": "So sánh TEST 2029 và 2030 và ai là kế toán trưởng?"},
    ],
)
def test_fusion_binding_before_admission(tmp_path, patch):
    service, request = setup(tmp_path)
    result = service.run(request.model_copy(update=patch))
    assert not result.used_verified_claim_ids
    assert not result.citations
    assert not service.repository.list_all()


def test_fusion_partial_ocr_missing_document_and_causal_never_completed(tmp_path):
    service, request = setup(tmp_path, defect=True)
    result = service.run(request)
    assert result.status == "partial_verified_coverage", result.trace.errors
    assert result.trace.native_decisions["INVESTIGATE"] == 1
    assert {c.snapshot_id for c in result.citations} == {"selected-0"}
    result = service.run(
        request.model_copy(
            update={"question": "Biên lợi nhuận gộp TEST 2030 là bao nhiêu và nguyên nhân là gì?"}
        )
    )
    assert result.status == "partial_verified_coverage"
    assert "chưa đủ bằng chứng" in result.answer_vi
    assert len(result.used_verified_claim_ids) == 1


def test_missing_financial_graph_operand_preserves_document_lane(tmp_path):
    service, request = setup(tmp_path)
    service.catalog.facts.pop()
    result = service.run(request)
    assert result.status == "partial_verified_coverage", result.trace.errors
    assert {c.snapshot_id for c in result.citations} == {"native"}
    assert not any(e.identity.kind != "document" for e in service.repository.list_all())


def test_policy_topic_cannot_hide_a_causal_requirement():
    from vietnamese_financial_multi_agent.agents.fusion_contracts import decompose

    for question in (
        "Biên lợi nhuận gộp TEST 2030 và có phải do thay đổi chính sách ghi nhận doanh thu không?",
        "Biên lợi nhuận gộp TEST 2030 và chính sách doanh thu có giải thích biến động không?",
    ):
        plan = decompose(question)
        assert plan.requirements[-1].kind == "causal_explanation"
        assert plan.requirements[-1].support_status == "unsupported"


def test_source_topic_is_not_a_bag_of_cooccurring_words():
    from vietnamese_financial_multi_agent.agents.document_qa_contracts import DocumentRequirement
    from vietnamese_financial_multi_agent.evidence.document_claim_support import source_assertion

    requirement = DocumentRequirement(
        target="ghi nhan doanh thu",
        label="Ghi nhận doanh thu",
        query="ghi nhận doanh thu",
        kind="source_excerpt",
    )
    unrelated = (
        "Các khoản phải thu được ghi nhận không vượt quá giá trị có thể thu hồi của doanh nghiệp."
    )
    assert source_assertion(requirement, [{"text": unrelated}]) is None
    relevant = "Công ty chỉ được ghi nhận doanh thu khi những điều kiện trả lại sản phẩm không còn tồn tại."
    assert source_assertion(requirement, [{"text": relevant}])[0] == [relevant]


def test_cross_filing_comparison_preserves_D03_reason(tmp_path):
    service = FinancialQAPipeline(
        catalog=SnapshotCatalog([]), documents=[], repository=VerifiedClaimRepository(tmp_path)
    )
    result = service.run(
        FinancialQARequest(
            question="So sánh doanh thu BCC 2024 hợp nhất và BCC 2025 riêng và thuyết minh gì về doanh thu?"
        )
    )
    assert result.status == "unsupported"
    assert result.trace.errors == ["cross_document_comparison_blocked_D03_B10"]
    assert not result.used_verified_claim_ids


@pytest.mark.parametrize("invalid_proposal", [False, True])
def test_provider_failure_or_arbitrary_tool_cannot_erase_document_coverage(
    tmp_path, invalid_proposal
):
    from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway

    from .test_financial_qa import gateway_for

    service, request = setup(tmp_path)

    def unavailable(_request):
        raise TimeoutError("synthetic_provider_unavailable")

    service.gateway = (
        gateway_for(
            {
                "intent": "calculated_metric",
                "operations": [{"operation_id": "evil", "operation": "execute_arbitrary_code"}],
            },
            [],
        )
        if invalid_proposal
        else SharedLLMGateway({"gemini": unavailable})
    )
    result = service.run(
        request.model_copy(update={"execution_mode": "gemini", "allow_gateway": True})
    )
    assert result.status == "partial_verified_coverage", result.trace.errors
    assert {c.snapshot_id for c in result.citations} == {"native"}
    assert not any(c["tool"] == "calculate_financial_metric" for c in result.trace.tool_calls)
