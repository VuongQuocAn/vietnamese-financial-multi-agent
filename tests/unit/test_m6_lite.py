"""Focused synthetic negative controls; real BBS receipts live outside Git."""

import json
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.api.claim_selection import select_claims
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.core.llm_contracts import (
    Cost,
    LLMResponse,
    ResponseProvenance,
    Usage,
    parse_json_output,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite
from vietnamese_financial_multi_agent.verification.ledger import (
    LedgerAdmissionError,
    build_verified_claim,
)
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_validators import batch_for
from .test_m4_execution import fixture
from .test_multihop_reasoning import reasoning_case


def rename(claim, name):
    claim = claim.model_copy(deep=True)
    claim.candidate_id = claim.provenance.m5_candidate_id = name
    return claim


def semantic_gateway():
    def generate(request):
        rows = json.loads(request.messages[-1].content)
        verdicts = [
            dict(
                claim_id=r["claim_id"],
                verdict="UNSUPPORTED" if r["claim_id"] == "causal" else "SUPPORTED",
                reason="No causal evidence" if r["claim_id"] == "causal" else "Grounded comparison",
            )
            for r in rows
        ]
        return LLMResponse(
            contract_version="llm_gateway_v1",
            request_id=request.request_id,
            status="success",
            finish_reason="stop",
            correlation=request.correlation,
            provenance=ResponseProvenance(requested_model=request.model, metadata_source="unknown"),
            usage=Usage(status="unknown", source="unknown"),
            cost=Cost(status="unknown", source="unknown"),
            output=parse_json_output(json.dumps(dict(verdicts=verdicts))),
        )

    return Mock(generate=Mock(side_effect=generate))


def test_facts_calculations_and_invalid_claims_are_independent(tmp_path):
    data = fixture()
    batch = batch_for(data)
    good = batch.claims[0]
    for field, value in (
        ("content", good.content.replace("200", "999")),
        ("citations", []),
        ("period", "1999"),
        ("company_id", "foreign"),
        ("snapshot_id", "foreign"),
    ):
        bad = rename(good, field)
        setattr(bad, field, value)
        if field == "content" and bad.content == good.content:
            bad.content = "Doanh thu thuần kỳ 2030 là 999 VND."
        batch.claims.append(bad)
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data))
    histories = runtime.verify(batch)
    assert histories[0].outcome.final.decision == "ACCEPT"
    assert all(h.outcome.final.decision != "ACCEPT" for h in histories[1:])
    assert runtime.provider_metadata == []
    repository = VerifiedClaimRepository(tmp_path)
    results = repository.admit_many(histories)
    assert results[0].status == "stored" and all(r.status == "rejected" for r in results[1:])
    assert len(VerifiedClaimRepository(tmp_path).list_all()) == 1
    assert not FinancialQARequest(question="test").m6_lite


def test_dynamic_relations_and_proof_tampering_are_checked_by_python(tmp_path):
    data, batch = reasoning_case(operator="greater")
    batch.claims.append(rename(batch.claims[0], "tampered"))
    batch.claims[-1].reasoning.calculation.steps[0].result = "999"
    histories = LiteVerificationRuntime(SnapshotCatalog(**data)).verify(batch)
    assert [h.outcome.final.decision for h in histories] == ["ACCEPT", "ABSTAIN"]
    good = histories[0]
    assert VerifiedClaimRepository(tmp_path).admit(good).status == "stored"
    good.proof.batch.claims[0].content += " Suy đoán nguyên nhân."
    with pytest.raises(LedgerAdmissionError):
        build_verified_claim(good)


def test_single_semantic_batch_admission_and_provider_failure_keep_facts(tmp_path):
    data, batch = reasoning_case(operator="greater")
    interpretation = batch.claims[0]
    interpretation.reasoning.claim_type = "reasoned_conclusion"
    interpretation.content = "Doanh thu cao hơn lợi nhuận gộp trong kỳ được đối chiếu."
    interpretation.reasoning.limitations = ["Không kết luận nguyên nhân."]
    bad = rename(interpretation, "causal")
    bad.content = "Doanh thu cao hơn lợi nhuận gộp vì doanh nghiệp quản lý chi phí kém."
    fact = rename(batch_for(data).claims[0], "independent-fact")
    wrong = rename(interpretation, "wrong-number")
    wrong.content = "Doanh thu đạt 999 VND."
    batch.claims.extend([bad, fact, wrong])
    gateway = semantic_gateway()
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway)
    histories = runtime.verify(batch)
    assert [h.outcome.final.decision for h in histories] == [
        "ACCEPT",
        "ABSTAIN",
        "ACCEPT",
        "ABSTAIN",
    ]
    assert gateway.generate.call_count == 1
    assert all(len(h.outcome.attempts) == 1 for h in histories)
    admitted = VerifiedClaimRepository(tmp_path).admit_many(histories)
    assert [r.status for r in admitted] == ["stored", "rejected", "stored", "rejected"]
    entries = VerifiedClaimRepository(tmp_path).list_all()
    assert len(entries) == 2
    assert all(e.decision.evidence is None and e.decision.logic is None for e in entries)
    assert any(e.decision.limitations for e in entries)
    owner = entries[0].identity
    request = FinancialQARequest(
        question="Doanh thu thuần và lợi nhuận gộp năm 2030?",
        company_id=owner.company_id,
        document_id=owner.document_id,
        snapshot_id=owner.snapshot_id,
        m5_lite=True,
        m6_lite=True,
        m7_lite=True,
    )
    selected, _ = select_claims(request, entries)
    released, metadata = compose_lite(request, selected)
    assert set(released["used_verified_claim_ids"]) == {
        e.identity.verified_claim_id for e in entries
    }
    assert released["citations"] and metadata["calls"] == 0
    failed = Mock(generate=Mock(side_effect=RuntimeError("provider 503")))
    histories = LiteVerificationRuntime(SnapshotCatalog(**data), failed).verify(batch)
    assert [h.outcome.final.decision for h in histories] == [
        "INVESTIGATE",
        "INVESTIGATE",
        "ACCEPT",
        "ABSTAIN",
    ]
    assert failed.generate.call_count == 1
