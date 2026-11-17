"""Presentation controls only; these synthetic fixtures do not certify finance."""

import json
from copy import deepcopy

from vietnamese_financial_multi_agent.outputs.qa_lite import compose_lite

from . import test_qa_lite as fixtures

admitted = fixtures.admitted
gateway_for = fixtures.gateway_for


def test_natural_synthesis_keeps_joint_claims_once_and_exact_citations(admitted):
    request, entry = admitted
    other = entry.model_copy(deep=True)
    other.identity.verified_claim_id = "second-verified"
    keys = [entry.identity.verified_claim_id, other.identity.verified_claim_id]
    context = dict(
        requirements=[dict(requirement_id=rid, text=rid) for rid in ("G1", "G2")],
        verified_requirements=dict(zip(keys, [["G1"], ["G2"]], strict=True)),
    )
    original = deepcopy(context)
    claims_before = [e.model_dump_json() for e in (entry, other)]
    prose = "Theo các số liệu đã xác minh, " + entry.content
    gateway, calls = gateway_for(dict(segments=[dict(text=prose, claim_ids=keys)], gaps=[]))
    fields, trace = compose_lite(request, [entry, other], gateway=gateway, coverage_context=context)
    assert len(calls) == 1 and len(trace["segments"]) == 1
    assert fields["answer_vi"].count(prose) == 1 and trace["coverage"]["complete"]
    assert trace["rendering_mode"] == "grounded_natural_answer" and not trace["fallback"]
    assert {b["verified_claim_id"] for b in trace["citation_bindings"]} == set(keys)
    assert set(fields["citations"][0].bound_verified_claim_ids) == set(keys)
    payload = json.loads(calls[0].messages[1].content)
    assert payload["goal_bindings"] == context["verified_requirements"]
    assert payload["verified_coverage"] == trace["coverage"]
    assert payload["verified_claims"][0]["citations"][0]["source_id"]
    assert context == original and claims_before == [e.model_dump_json() for e in (entry, other)]


def test_partial_uses_m6_coverage_and_excludes_unbound_claim(admitted):
    request, entry = admitted
    key = entry.identity.verified_claim_id
    unrelated = entry.model_copy(deep=True)
    unrelated.identity.verified_claim_id = "unbound-conclusion"
    unrelated.identity.kind = "interpretation"
    context = dict(
        requirements=[
            dict(requirement_id="G1", text="Số liệu"),
            dict(requirement_id="G2", text="Nhận xét nguyên nhân"),
        ],
        verified_requirements={key: ["G1"]},
    )
    gateway, calls = gateway_for(
        dict(segments=[dict(text=entry.content, claim_ids=[key])], gaps=[])
    )
    fields, trace = compose_lite(
        request, [entry, unrelated], gateway=gateway, coverage_context=context
    )
    assert fields["status"] == "partial_verified_coverage"
    assert "Chưa đáp ứng: Nhận xét nguyên nhân" in fields["answer_vi"]
    assert trace["coverage"]["requirements"][1]["verified_claim_ids"] == []
    assert fields["used_verified_claim_ids"] == [key]
    assert len(json.loads(calls[0].messages[1].content)["verified_claims"]) == 1


def test_numbers_must_belong_to_cited_claim_and_model_cannot_emit_citation(admitted):
    request, entry = admitted
    key = entry.identity.verified_claim_id
    other = entry.model_copy(deep=True)
    other.identity.verified_claim_id = "different-number"
    other.accepted_claim.content = "Kết quả đã xác minh là 987654321 VND."
    gateway, _ = gateway_for(
        dict(
            segments=[
                dict(text="Kết quả là 987654321 VND.", claim_ids=[key]),
                dict(text=entry.content + " [123]", claim_ids=[key]),
            ],
            gaps=[],
        )
    )
    fields, trace = compose_lite(request, [entry, other], gateway=gateway)
    assert [s["reason"] for s in trace["rejected_segments"]] == [
        "unsupported_number",
        "invalid_answer_text_or_citation",
    ]
    assert entry.content in fields["answer_vi"] and "[123]" not in fields["answer_vi"]
    assert set(fields["used_verified_claim_ids"]) == {key, "different-number"}
