"""Bounded synthetic controls for evidence support and untrusted semantic output."""

import json

import pytest
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    JSONOutput,
    LLMResponse,
    ResponseProvenance,
    Usage,
)
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification import (
    DeterministicFinancialValidator,
    EvidenceCritic,
    EvidenceCriticResult,
)

from .test_financial_validators import batch_for
from .test_m4_execution import fixture


def response(request, payload):
    return LLMResponse(
        contract_version="llm_gateway_v1",
        request_id=request.request_id,
        status="success",
        finish_reason="stop",
        correlation=request.correlation,
        provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
        usage=Usage(status="unknown", source="unknown"),
        cost=Cost(status="unknown", source="unknown"),
        output=JSONOutput(
            format="json",
            raw_text=json.dumps(payload),
            payload=payload,
            validation_status="json_valid",
        ),
    )


def semantic_gateway(mutation=None, captured=None):
    def transport(request):
        payload = json.loads(request.messages[-1].content)
        if captured is not None:
            captured.append(payload)
        result = dict(
            candidate_id=payload["candidate_id"],
            assertions=[
                dict(
                    assertion_id=a["assertion_id"],
                    status="insufficient_evidence",
                    evidence_ids=[],
                    reason="missing_evidence",
                    missing=["comparison"],
                )
                for a in payload["assertions"]
            ],
        )
        if mutation:
            mutation(result)
        return response(request, result)

    return SharedLLMGateway({"gemini": transport})


def assess(data, batch, gateway=None, **kwargs):
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    return EvidenceCritic(catalog, gateway, **kwargs).assess(batch, validation)


@pytest.mark.parametrize("metric", [False, True])
def test_numeric_support_page_provenance_and_serialization(metric):
    data = fixture()
    batch = batch_for(data, metric=metric)
    before = batch.model_dump_json()
    result = assess(data, batch)
    claim = result.claims[0]
    assert claim.status == "supported", claim
    assert claim.method == "deterministic" and claim.trace.llm.calls == 0
    assert claim.supporting_citations and claim.deterministic_findings
    assert not result.financial_fact_verified
    assert EvidenceCriticResult.model_validate_json(result.model_dump_json()) == result
    assert batch.model_dump_json() == before and batch.claims[0].verification_status == "pending"


def test_numeric_pass_does_not_certify_interpretation_and_prompt_is_bounded():
    data = fixture()
    batch = batch_for(data, metric=True)
    batch.claims[0].kind = "supported_interpretation"
    batch.claims[0].content += " Cho thấy hoạt động kinh doanh đang cải thiện."
    captured = []
    result = assess(data, batch, semantic_gateway(captured=captured)).claims[0]
    assert result.status == "partially_supported"
    assert [a.status for a in result.assertions] == ["supported", "insufficient_evidence"]
    assert result.method == "combined" and result.trace.llm.calls == 1
    assert result.missing_evidence == ["comparison"]
    assert "financial_logic_assessment_deferred_to_M6_04" in result.caveats
    assert len(captured) == 1 and "question" not in captured[0]
    assert all(
        set(e) == {"evidence_id", "reference", "content", "citations"}
        for e in captured[0]["evidence"]
    )


@pytest.mark.parametrize("control", ["numeric", "citation", "document", "missing_source"])
def test_proven_failure_or_missing_source_never_calls_gemini(control):
    data = fixture()
    batch = batch_for(data)
    if control == "numeric":
        batch.claims[0].content = batch.claims[0].content.replace("20", "99")
    elif control == "citation":
        batch.claims[0].citations[0].pdf_page += 1
    elif control == "document":
        batch.claims[0].document_id = "wrong"
    else:
        data["facts"] = []
    result = assess(data, batch, semantic_gateway()).claims[0]
    assert result.status == (
        "insufficient_evidence" if control == "missing_source" else "unsupported"
    )
    assert result.trace.llm.calls == 0


def test_input_identity_and_legacy_pairing():
    data = fixture()
    batch = batch_for(data)
    catalog = SnapshotCatalog(**data)
    validation = DeterministicFinancialValidator(catalog).validate(batch)
    critic = EvidenceCritic(catalog)
    changed = batch.model_copy(deep=True)
    changed.claims[0].content += " Tốt hơn."
    assert critic.assess(changed, validation).errors[0].code == "validation_batch_identity_mismatch"
    validation.verification_input_sha256 = None
    assert (
        critic.assess(batch, validation).claims[0].errors[0].code
        == "legacy_validation_requires_input_binding"
    )
    assert critic.assess(batch, validation, validated_batch=batch).claims[0].status == "supported"
    assert critic.assess(changed, validation, validated_batch=batch).errors


@pytest.mark.parametrize(
    "control",
    [
        "candidate",
        "reference",
        "assertion",
        "extra_value",
        "quality",
        "decision",
        "numeric_override",
        "missing_assertion",
    ],
)
def test_semantic_local_validation_rejects_untrusted_output(control):
    data = fixture()
    batch = batch_for(data, metric=True)
    batch.claims[0].kind = "supported_interpretation"
    batch.claims[0].content += " Hoạt động đang cải thiện."

    def mutate(payload):
        a = payload["assertions"][0]
        if control == "candidate":
            payload["candidate_id"] = "invented"
        elif control == "reference":
            a["evidence_ids"] = ["invented-anchor"]
        elif control in {"assertion", "numeric_override"}:
            a["assertion_id"] = "A1"
        elif control == "missing_assertion":
            payload["assertions"] = []
        else:
            payload[
                {
                    "extra_value": "financial_value",
                    "quality": "source_quality",
                    "decision": "decision",
                }[control]
            ] = "ACCEPT"

    result = assess(data, batch, semantic_gateway(mutate)).claims[0]
    assert result.status == "partially_supported"
    assert result.assertions[0].status == "supported"
    assert result.assertions[1].status == "insufficient_evidence"
    assert result.errors[-1].code == "semantic_output_invalid"
    assert result.trace.semantic_response is None


def test_partial_success_and_budget_include_failed_calls():
    data = fixture()
    batch = batch_for(data)
    semantic = batch.claims[0].model_copy(deep=True)
    semantic.candidate_id = semantic.provenance.m5_candidate_id = "C2"
    semantic.kind = "supported_interpretation"
    semantic.content += " Doanh nghiệp cải thiện."
    batch.claims.extend([semantic, semantic.model_copy(deep=True)])
    batch.claims[-1].candidate_id = batch.claims[-1].provenance.m5_candidate_id = "C3"
    result = assess(data, batch, semantic_gateway(), max_semantic_calls=1)
    assert [c.status for c in result.claims] == [
        "supported",
        "partially_supported",
        "partially_supported",
    ]
    assert [c.trace.llm.calls for c in result.claims] == [0, 1, 0]
    assert result.claims[-1].errors[-1].code == "semantic_call_budget_exhausted"


def test_text_support_uses_retrieved_content_and_keeps_review_limitations():
    from vietnamese_financial_multi_agent.evidence import TextEvidence, build_graph
    from vietnamese_financial_multi_agent.evidence.retrieval import RetrievalReference
    from vietnamese_financial_multi_agent.tools.evidence_retrieval import (
        EvidenceRetrievalTools,
        GetEvidenceSourcesRequest,
    )

    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    text = TextEvidence(
        document_id=claim.document_id,
        snapshot_id=claim.snapshot_id,
        local_evidence_id="note-policy",
        raw_text="Hàng tồn kho được tính theo phương pháp bình quân gia quyền.",
        sources=[c.source.model_copy(deep=True) for c in claim.citations],
        resolution_issues=["source_review_unverified"],
    )
    data["evidence"].append(text)
    data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])
    ref = RetrievalReference(kind="text", evidence=text.evidence_identity())
    citations = (
        EvidenceRetrievalTools(SnapshotCatalog(**data))
        .get_evidence_sources(GetEvidenceSourcesRequest(reference=ref))
        .matches[0]
        .citations
    )
    claim.content = "Hàng tồn kho được tính theo phương pháp bình quân gia quyền."
    claim.fact_references = claim.provenance.supporting_references = [ref]
    claim.supporting_evidence = []
    claim.citations = citations
    captured = []

    def support(payload):
        payload["assertions"][0].update(
            status="supported", evidence_ids=["E1"], reason="direct_support", missing=[]
        )

    result = assess(data, batch, semantic_gateway(support, captured)).claims[0]
    assert result.status == "supported" and result.method == "gemini"
    assert captured[0]["evidence"][0]["content"]["text"] == text.raw_text
    assert "source_review_unverified" in result.caveats


def test_unverified_source_caveat_and_gateway_timeout():
    data = fixture()
    data["source_reviews"] = []
    batch = batch_for(data)
    result = assess(data, batch).claims[0]
    assert result.status == "supported"
    assert "source_review_unverified" in result.caveats
    batch.claims[0].content += " Hoạt động cải thiện."

    def timeout(request):
        raise TimeoutError()

    result = assess(data, batch, SharedLLMGateway({"gemini": timeout})).claims[0]
    assert result.status == "partially_supported" and result.trace.llm.calls == 1
    assert result.errors[-1].code == "semantic_gateway_response_failed"
