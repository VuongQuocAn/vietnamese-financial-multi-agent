"""Focused Fix-A engineering controls; real-source results live in local artifacts."""

import pytest
from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.agents.fusion_contracts import decompose
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.evidence.document_claim_support import excerpt_topic_matches
from vietnamese_financial_multi_agent.evidence.metric_preparation import prepare_missing_metric
from vietnamese_financial_multi_agent.tools.financial_qa import QADocument
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

from .test_m4_execution import fixture


@pytest.mark.parametrize(
    "topics",
    [
        ["các khoản nợ phải trả", "vay và nợ thuê tài chính"],
        ["hàng tồn kho", "chi phí đi vay", "ghi nhận doanh thu"],
    ],
)
def test_original_document_conjuncts_survive_without_duplicate_noun_phrases(topics):
    question = "Thuyết minh TEST 2030 nói gì về " + " và về ".join(topics) + "?"
    specs = document_intent(question)[1]
    assert len(specs) == len(topics)
    plan = decompose(question)
    assert len(plan.requirements) == len(topics)
    assert len({r.requirement_id for r in plan.requirements}) == len(topics)
    assert all(r.lane == "document" for r in plan.requirements)
    repeated = "Thuyết minh gì về hàng tồn kho và về hàng tồn kho?"
    assert len(decompose(repeated).requirements) == 1


def test_predicate_reordering_keeps_exact_subject_and_same_sentence():
    query = "khấu hao phần mềm máy tính"
    assert excerpt_topic_matches(
        "Phần mềm máy tính được khấu hao theo phương pháp đường thẳng.", query
    )
    assert not excerpt_topic_matches("Tài sản hữu hình được khấu hao theo đường thẳng.", query)
    assert not excerpt_topic_matches("Phần mềm máy tính được mua. Tòa nhà được khấu hao.", query)


@pytest.mark.parametrize("missing_operand", [False, True])
def test_missing_prepared_metric_runs_verification_or_reports_gap(tmp_path, missing_operand):
    data = fixture("revenue_yoy")
    original_metrics = data["metrics"]
    data["metrics"] = []
    if missing_operand:
        data["facts"] = data["facts"][:1]
    from vietnamese_financial_multi_agent.evidence.graph import build_graph

    data["graph"] = build_graph(data["facts"], data["evidence"], [])
    catalog = SnapshotCatalog(**data)
    descriptor = data["descriptors"][0]
    period = original_metrics[0].request.operand_periods["current_revenue"]
    year = int(period[:4])
    prepared = prepare_missing_metric(
        catalog, descriptor.document_id, descriptor.snapshot_id, year, "revenue_yoy"
    )
    assert not catalog.metrics
    assert len(prepared.metrics) == int(not missing_operand)
    service = FinancialQAPipeline(
        catalog=catalog,
        documents=[
            QADocument(
                document_id=descriptor.document_id,
                company_id=data["facts"][0].company_id,
                company_aliases=["TEST"],
                reporting_year=year,
            )
        ],
        repository=VerifiedClaimRepository(tmp_path / "ledger"),
    )
    response = service.run(
        FinancialQARequest(
            question=f"Tăng trưởng doanh thu TEST {year} là bao nhiêu?",
            execution_mode="deterministic",
        )
    )
    assert response.status != "internal_error"
    if missing_operand:
        assert response.status == "unsupported"
        assert not response.used_verified_claim_ids
        assert "metric_operands_missing_or_ambiguous" in response.trace.errors
    else:
        assert response.used_verified_claim_ids, response.trace.errors
        assert "ACCEPT" in response.trace.native_decisions


def test_firewall_rechecks_original_conjunct_when_only_one_topic_is_verified(tmp_path):
    from vietnamese_financial_multi_agent.evidence.composition import EvidencePin, payload_sha256
    from vietnamese_financial_multi_agent.outputs.citation_renderer import CitationRenderer
    from vietnamese_financial_multi_agent.outputs.information_firewall import InformationFirewall
    from vietnamese_financial_multi_agent.outputs.qa_composer import VietnameseQAComposer
    from vietnamese_financial_multi_agent.outputs.qa_contracts import VietnameseQARequest
    from vietnamese_financial_multi_agent.verification.ledger import VerifiedClaimLedger

    from .test_document_qa_pipeline import setup

    service, manifest, template = setup(tmp_path)
    row = template.model_copy(
        deep=True,
        update={
            "local_evidence_id": "policy/inventory",
            "raw_text": "Hàng tồn kho được xác định theo giá thấp hơn giữa giá gốc và giá trị thuần có thể thực hiện được.",
        },
    )
    row.sources[0].reference.source_pointer = "/text_elements/10"
    service.document_repository.put(row)
    manifest.sources[0].evidence = [
        EvidencePin(
            identity=row.evidence_identity(),
            payload_sha256=payload_sha256(row.model_dump(mode="json")),
        )
    ]
    question = "Thuyết minh TEST 2025 nói gì về hàng tồn kho và về chi phí đi vay?"
    response = service.run(FinancialQARequest(question=question))
    assert response.status == "partial_verified_coverage", response.trace.errors
    assert len(response.trace.unanswered_requirements) == 1
    ledger = VerifiedClaimLedger(service.repository)
    request = VietnameseQARequest(
        question=question,
        company_id="test",
        document_id="logical",
        composition_id=manifest.composition_id,
        composition_sha256=payload_sha256(manifest.model_dump(mode="json")),
    )
    composed = VietnameseQAComposer(ledger).compose(request)
    forged = composed.model_copy(update={"status": "answered"})
    assert (
        InformationFirewall(ledger)
        .evaluate_qa(
            request=request, response=forged, rendered=CitationRenderer().render_qa(composed)
        )
        .decision
        == "BLOCK"
    )
