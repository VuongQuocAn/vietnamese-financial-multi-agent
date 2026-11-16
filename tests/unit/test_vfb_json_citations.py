"""JSON citations stay bound through M6 context and M7 location rendering."""

from vietnamese_financial_multi_agent.evidence.retrieval import RetrievalReference
from vietnamese_financial_multi_agent.outputs.citation_renderer import _locator
from vietnamese_financial_multi_agent.verification.evidence_context import EvidenceContextBuilder

from .test_json_pipeline import fixture


def test_json_sources_available_without_inventing_pdf_page(tmp_path):
    catalog = fixture(tmp_path)
    fact = catalog.facts[0]
    context = EvidenceContextBuilder(catalog)._resolve(
        RetrievalReference(kind="fact", observation=fact.observation_identity()), 0
    )
    assert context.available
    assert "json_source_not_pdf_verified" in context.caveats
    for citation in context.citations:
        location = _locator(citation)
        assert location.pdf_page is None and location.source_pointer
        assert location.source_ref.startswith("json:sha256:")
    from vietnamese_financial_multi_agent.agents.lite_orchestrator import FinancialLiteOrchestrator
    from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
    from vietnamese_financial_multi_agent.verification.adapter import to_verification_input

    result = FinancialLiteOrchestrator(catalog).run(
        question="Giá vốn hàng bán năm 2025 là bao nhiêu?",
        context=PlannerContext(
            company_id=fact.company_id,
            document_id=fact.document_id,
            snapshot_id=fact.snapshot_id,
            period="2025",
            mode="deterministic",
        ),
    )
    assert result.candidates
    assert not to_verification_input(result).issues
