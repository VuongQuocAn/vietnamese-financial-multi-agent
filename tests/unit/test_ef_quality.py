"""EF-CORE-03 regressions; synthetic controls are not financial-quality scores."""

import json
from decimal import Decimal

from vietnamese_financial_multi_agent.agents.profitability_specialist import ProfitabilityProposal
from vietnamese_financial_multi_agent.agents.specialist_common import (
    SpecialistResult,
    _numeric_proposals,
    generate_candidates,
    source_projection,
)
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.lite_runtime import (
    LiteVerificationRuntime,
    semantic_payload,
)

from .test_financial_qa import gateway_for
from .test_multihop_reasoning import reasoning_case


def test_invalid_empty_derived_analysis_preserves_numeric_and_valid_analysis():
    _, batch = reasoning_case()
    evidence = batch.claims[0].supporting_evidence
    result = SpecialistResult(
        question="Đối chiếu", upstream_status="completed", supporting_evidence=evidence
    )
    claims = _numeric_proposals(evidence)
    payload = dict(
        claims=claims,
        missing_information=[],
        analyses=[
            dict(
                statement="Chênh lệch lợi nhuận",
                evidence_ids=["E1", "E2"],
                claim_type="derived_fact",
                operations=[],
            ),
            dict(
                statement="So sánh",
                evidence_ids=["E1", "E2"],
                claim_type="derived_fact",
                operations=[
                    dict(operation_id="difference", operator="subtract", inputs=["E1", "E2"])
                ],
            ),
        ],
    )
    generate_candidates(
        gateway=gateway_for(payload, []),
        model=ModelIdentity(provider="gemini", model="test"),
        result=result,
        prompt={},
        proposal_type=ProfitabilityProposal,
        render=lambda p, e: e.label,
        prefix="test",
    )
    assert len([c for c in result.candidates if c.kind == "fact"]) == len(claims)
    assert len([c for c in result.candidates if c.reasoning]) == 1
    assert Decimal(result.candidates[0].reasoning.calculation.steps[0].result) == (
        Decimal(evidence[0].value) - Decimal(evidence[1].value)
    )
    assert any("derived_fact_requires_computation" in t.reasons for t in result.trace)
    assert all(c.reasoning is None or c.reasoning.calculation for c in result.candidates)


def test_source_projection_page_uncertainty_missing_and_semantic_payload():
    _, batch = reasoning_case()
    claim = batch.claims[0]
    evidence = claim.supporting_evidence[0].model_copy(deep=True)
    projection = source_projection(evidence)
    assert projection["availability"] == "linked"
    assert projection["bindings"][0]["pdf_page"] == evidence.citations[0].pdf_page
    assert projection["bindings"][0]["provenance_level"] == evidence.citations[0].provenance_level
    evidence.citations[0].provenance_level = "page"
    assert source_projection(evidence)["bindings"][0]["provenance_level"] == "page"
    evidence.citations = []
    assert source_projection(evidence)["availability"] == "missing"
    assert semantic_payload(batch, claim)["sources"][0]["bindings"]


def test_semantic_verifier_receives_page_and_rejects_unsupported_implication():
    data, batch = reasoning_case(operator="subtract")
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    claim.content = "Phần chênh lệch này đến từ nguyên liệu."
    seen = []
    runtime = LiteVerificationRuntime(
        SnapshotCatalog(**data),
        gateway_for(
            dict(
                verdicts=[
                    dict(
                        claim_id=claim.candidate_id,
                        verdict="UNSUPPORTED",
                        reason="Không có bằng chứng nguyên liệu",
                    )
                ]
            ),
            seen,
        ),
    )
    histories = runtime.verify(batch)
    assert histories[0].outcome.final.decision == "ABSTAIN"
    assert len(seen) == 1
    row = json.loads(seen[0].messages[-1].content)[0]
    assert row["calculations"] and row["sources"][0]["bindings"][0]["pdf_page"]
    assert "Arithmetic đúng không hỗ trợ" in seen[0].messages[0].content


def test_resolved_node_cache_preserves_detachment_and_selection(tmp_path):
    from vietnamese_financial_multi_agent.tools.graph_retrieval import (
        GetGraphContextRequest,
        GraphRetrievalTools,
    )

    from .test_composition_graph import inputs, project

    manifest, repository, _, _, catalog = inputs(tmp_path)
    projection = project(manifest, repository, catalog)
    tools = GraphRetrievalTools(projection)
    request = GetGraphContextRequest(
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
        node_id=projection.view.contextual_relations[0].source,
    )
    first = tools.get_graph_context(request)
    expected = first.model_dump(mode="json")
    first.start.original_citations.clear()
    first.start.caveats.append("external-mutation")
    projection.financial.facts[0].sources.clear()
    assert tools.get_graph_context(request).model_dump(mode="json") == expected
    assert (
        tools.get_graph_context(request.model_copy(update={"composition_id": "other"})).status
        == "unavailable"
    )
