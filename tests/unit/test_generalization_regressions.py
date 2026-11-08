"""GEN-02 general parsing and proof regressions; synthetic engineering evidence only."""

from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.agents.fusion_contracts import decompose
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.evidence.composition import EvidencePin, payload_sha256
from vietnamese_financial_multi_agent.outputs.qa_composer import understand_requirements
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.tools.question_understanding import understand
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

from .test_document_qa_pipeline import setup as document_setup
from .test_m4_execution import fixture
from .test_profitability_specialist import run as profitability_run
from .test_profitability_specialist import upstream
from .test_reporting_scope import fixture as scope_fixture


def test_unexplained_empty_model_output_reuses_numeric_candidates_only():
    result, calls = profitability_run(upstream(), [])
    assert result.candidates and len(calls) == 1
    assert result.raw_output == {"claims": [], "missing_information": []}
    assert any(t.outcome == "deterministic_numeric_fallback" for t in result.trace)
    assert all(
        c.kind in {"fact", "approved_metric"} and not c.financial_fact_verified
        for c in result.candidates
    )


def test_natural_requirements_preserve_topics_growth_and_operand_followup():
    question = "Thuyết minh TEST 2030 nêu những điều kiện nào để ghi nhận doanh thu bán hàng?"
    intent, specs = document_intent(question)
    assert intent == "document"
    assert [s.query for s in specs] == ["doanh thu bán hàng"]
    multi = (
        "Thuyết minh TEST 2030 nói gì về nhân viên quản lý chủ chốt và chính sách chi phí đi vay?"
    )
    assert len(document_intent(multi)[1]) == 2
    mixed = decompose(
        "Tỷ lệ nợ trên tổng tài sản TEST 2030 và thuyết minh gì về vay và nợ thuê tài chính?"
    )
    assert sum(r.lane == "document" for r in mixed.requirements) == 1
    assert not any(r.lane == "unsupported" for r in mixed.requirements)
    assert (
        understand("Doanh thu TEST 2030 tăng hay giảm so với năm trước?")[0].formula_id
        == "revenue_yoy"
    )
    assert (
        "non_annual_period_unsupported"
        not in understand("Chính sách chi phí đi vay quy định thế nào?")[1]
    )
    assert "non_annual_period_unsupported" in understand("Doanh thu TEST quý 1 năm 2030?")[1]
    requirements = understand_requirements(
        "Giải thích công thức biên lợi nhuận gộp và nêu số liệu dùng để tính."
    )
    assert {r.aspect for r in requirements if r.kind == "explanation"} == {"formula", "operands"}


def test_complete_contiguous_policy_section_and_quality_gate(tmp_path):
    service, manifest, template = document_setup(tmp_path)
    texts = [
        "4.1. Ghi nhận doanh thu bán hàng",
        "Doanh thu bán hàng được ghi nhận khi đồng thời thỏa mãn tất cả năm (5) điều kiện sau:",
        "(a) Đã chuyển giao phần lớn rủi ro và lợi ích;",
        "(b) Không còn quyền quản lý hay kiểm soát;",
        "(c) Doanh thu được xác định chắc chắn;",
        "(d) Thu được lợi ích kinh tế; và",
        "(e) Xác định được chi phí liên quan.",
        "4.2. Chi phí đi vay",
        "Chi phí đi vay được ghi nhận khi phát sinh.",
    ]
    rows = []
    for i, text in enumerate(texts, 10):
        row = template.model_copy(
            deep=True, update={"local_evidence_id": f"policy/{i}", "raw_text": text}
        )
        row.sources[0].reference.source_pointer = f"/text_elements/{i}"
        rows.append(row)
    service.document_repository.put_many(rows)
    manifest.sources[0].evidence = [
        EvidencePin(
            identity=r.evidence_identity(), payload_sha256=payload_sha256(r.model_dump(mode="json"))
        )
        for r in rows
    ]
    request = FinancialQARequest(
        question="Thuyết minh TEST 2025 nêu các điều kiện ghi nhận doanh thu bán hàng?"
    )
    result = service.run(request)
    assert result.status == "completed_with_caveats", result.trace.errors
    for text in texts[1:7]:
        assert text in result.answer_vi
    assert texts[8] not in result.answer_vi
    assert len(result.trace.document_candidates[0]["references"]) > 3
    assert result.trace.firewall_decision == "ALLOW_WITH_CAVEAT"
    from vietnamese_financial_multi_agent.agents.document_qa_contracts import DocumentRequirement
    from vietnamese_financial_multi_agent.evidence.document_claim_support import (
        complete_declared_list,
        source_assertion,
    )

    requirement = DocumentRequirement(
        target="doanh thu ban hang",
        label="Doanh thu bán hàng",
        query="doanh thu bán hàng",
        kind="source_excerpt",
    )
    # An old proof of a literal partial quote still replays under the accepted M6
    # policy. Completeness is checked by candidate construction and M7 selection.
    assert source_assertion(requirement, [{"text": t} for t in texts[1:5]]) is not None
    assert not complete_declared_list(texts[1:5])
    # Re-pin a known source defect: longer excerpts must keep every M6 quality gate.
    rows[4].resolution_issues.append("pdf_review:known_defect")
    from vietnamese_financial_multi_agent.evidence.document_repository import (
        DocumentEvidenceRepository,
    )

    updated = DocumentEvidenceRepository(tmp_path / "reviewed-source")
    updated.put_many(rows)
    service.document_repository = updated
    manifest.sources[0].evidence = [
        EvidencePin(
            identity=r.evidence_identity(), payload_sha256=payload_sha256(r.model_dump(mode="json"))
        )
        for r in rows
    ]
    blocked = service.run(request.model_copy(update={"force_refresh": True}))
    assert not blocked.used_verified_claim_ids
    assert "INVESTIGATE" in blocked.trace.native_decisions


def test_explicit_fact_scope_uses_admitted_source_context_only(tmp_path):
    data = fixture()
    _, _, _, reviews = scope_fixture()
    descriptor = data["descriptors"][0]
    for review in reviews:
        review.snapshot_id = descriptor.snapshot_id
        for source in review.sources:
            source.snapshot_id = descriptor.snapshot_id
    data["reporting_scope_reviews"] = reviews
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
    )
    question = "Doanh thu thuần TEST 2030 trên báo cáo riêng là bao nhiêu?"
    result = service.run(FinancialQARequest(question=question, execution_mode="deterministic"))
    assert result.status == "completed_with_caveats", result.trace.errors
    assert result.used_verified_claim_ids
    wrong = service.run(
        FinancialQARequest(
            question=question.replace("riêng", "hợp nhất"), execution_mode="deterministic"
        )
    )
    assert wrong.status == "clarification_required"
    assert not wrong.citations
