"""Negative controls synthetic; không chứng minh PDF financial accuracy."""

import pytest
from vietnamese_financial_multi_agent.evidence import (
    CanonicalCoverage,
    CanonicalFactRepository,
    DocumentEvidenceRepository,
    EvidenceIdentity,
    EvidenceQuery,
    EvidenceRetrieval,
    RetrievalReference,
    RetrievalResult,
    TaskQualityContext,
    TextEvidence,
    build_graph,
    build_metric,
)
from vietnamese_financial_multi_agent.evidence.graph import graph_id

from .test_derived_metrics import inputs


def setup():
    definition, request, facts = inputs()
    metric = build_metric(definition, request, facts)
    text = TextEvidence(
        document_id=facts[0].document_id,
        snapshot_id=facts[0].snapshot_id,
        local_evidence_id="text",
        raw_text="synthetic",
        sources=facts[0].sources,
    )
    graph = build_graph(facts, [text], [metric])
    return facts, text, metric, graph


def test_exact_sources_restart_and_json(tmp_path):
    facts, text, metric, graph = setup()
    repo = CanonicalFactRepository(tmp_path / "facts")
    docs = DocumentEvidenceRepository(tmp_path / "evidence")
    for fact in facts:
        repo.put(fact)
    docs.put(text)
    api = EvidenceRetrieval.from_repositories(
        [repo], [docs], [facts[0].document_id], metrics=[metric], graph=graph
    )
    result = api.get_fact(facts[0].observation_identity())
    assert result.status == "found"
    assert result.matches[0].record == facts[0]
    assert result.matches[0].evidence_references == [text.evidence_identity()]
    assert not result.financial_fact_verified
    assert RetrievalResult.model_validate_json(result.model_dump_json()) == result
    restarted = EvidenceRetrieval.from_repositories(
        [CanonicalFactRepository(repo.root)],
        [DocumentEvidenceRepository(docs.root)],
        [facts[0].document_id],
        metrics=[metric],
        graph=graph,
    )
    assert (
        restarted.get_fact(facts[0].observation_identity()).model_dump_json()
        == result.model_dump_json()
    )
    assert api.get_sources(result.matches[0].reference) == result
    aid = result.matches[0].citations[0].anchor_id
    assert api.get_anchor(aid).status == "found"
    assert api.get_evidence(text.evidence_identity()).matches[0].record == text
    assert api.find_evidence(EvidenceQuery(evidence_type="text")).status == "found"
    assert api.get_metric(metric.metric_id).status == "found"
    assert api.get_lineage(metric.metric_id).matches[0].record.completeness == "complete"
    result.matches[0].record.value.raw_value = "mutated"
    assert api.get_fact(facts[0].observation_identity()).matches[0].record == facts[0]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("document_id", "wrong", "no_matching_fact"),
        ("snapshot_id", "wrong", "no_matching_fact"),
        ("period", "1900", "missing_period"),
        ("canonical_item_id", "wrong", "no_matching_fact"),
    ],
)
def test_wrong_filters(field, value, reason):
    facts, _, _, _ = setup()
    result = EvidenceRetrieval(facts).find_facts(EvidenceQuery(**{field: value}))
    assert result.status == "not_found" and result.reasons == [reason]


def test_no_latest_no_merge_and_known_conflict():
    facts, _, _, _ = setup()
    f = facts[0]
    others = [f.model_copy(deep=True) for _ in range(2)]
    others[0].document_id = "other-document"
    others[1].snapshot_id = "zzz-newest"
    api = EvidenceRetrieval([f, *others])
    query = EvidenceQuery(canonical_item_id=f.canonical_item_id, period=f.context.period)
    result = api.find_facts(query)
    assert result.status == "ambiguous" and len(result.matches) == 3
    assert (
        result.model_dump_json()
        == EvidenceRetrieval(reversed([f, *others])).find_facts(query).model_dump_json()
    )
    assert (
        len(
            api.find_facts(
                EvidenceQuery(document_id=f.document_id, snapshot_id=f.snapshot_id)
            ).matches
        )
        == 1
    )
    conflicting = f.model_copy(deep=True)
    conflicting.value.raw_value = "different payload"
    assert (
        EvidenceRetrieval([f, conflicting]).get_fact(f.observation_identity()).status
        == "conflicted"
    )


@pytest.mark.parametrize("decision", ["usable", "usable_with_caveat", "insufficient", "conflicted"])
def test_quality_is_separate_and_uncertain_page(decision):
    facts, _, _, _ = setup()
    f = facts[0]
    f.sources[0].reference.anchor.status = "uncertain"
    f.sources[0].reference.provenance_level = "page"
    f.quality_context = [
        TaskQualityContext(
            task_type="direct_qa", decision=decision, evidence_ids=["original"], caveats=["keep"]
        )
    ]
    result = EvidenceRetrieval([f]).get_fact(f.observation_identity())
    assert result.status == ("conflicted" if decision == "conflicted" else "found")
    match = result.matches[0]
    assert match.record.quality_context == f.quality_context
    assert match.display_status == (
        "blocked" if decision in {"insufficient", "conflicted"} else "display_with_caveat"
    )
    assert "source_reference_uncertain" in match.citations[0].limitations
    assert match.citations[0].provenance_level == "page"
    assert not match.record.financial_fact_verified


@pytest.mark.parametrize("damage", ["fact", "anchor", "lineage"])
def test_broken_lineage(damage):
    facts, text, metric, graph = setup()
    if damage == "fact":
        facts = facts[1:]
    elif damage == "anchor":
        graph.nodes = [n for n in graph.nodes if n.kind != "anchor"]
    else:
        graph.edges = [e for e in graph.edges if e.relation != "used_in"]
    result = EvidenceRetrieval(facts, [text], [metric], graph=graph).get_lineage(metric.metric_id)
    assert result.status == "unavailable" and "broken_lineage" in result.reasons
    assert result.matches[0].record.completeness == "broken"


def test_missing_inventory_identity_and_dangling_anchor():
    facts, text, metric, graph = setup()
    api = EvidenceRetrieval(
        facts,
        [text],
        [metric],
        graph=graph,
        coverage=[
            CanonicalCoverage(
                document_id="historical",
                canonical_extraction="missing",
                inventory_reference="inventory:checked",
            ),
            CanonicalCoverage(
                document_id=facts[0].document_id,
                missing_canonical_items=["liabilities"],
                inventory_reference="mapping:checked",
            ),
        ],
    )
    assert api.find_facts(EvidenceQuery(document_id="historical")).reasons == [
        "canonical_extraction_missing"
    ]
    assert api.find_facts(
        EvidenceQuery(document_id=facts[0].document_id, canonical_item_id="liabilities")
    ).reasons == ["canonical_mapping_missing"]
    assert (
        EvidenceRetrieval().find_facts(EvidenceQuery(document_id="historical")).status
        == "not_found"
    )
    assert (
        api.get_fact(
            facts[0].observation_identity().model_copy(update={"local_id": "absent"})
        ).status
        == "not_found"
    )
    wrong_kind = EvidenceIdentity(
        **text.evidence_identity().model_dump(exclude={"kind"}), kind="table"
    )
    assert api.get_evidence(wrong_kind).status == "not_found"
    assert api.get_metric("absent").reasons == ["missing_derived_metric"]
    assert api.get_lineage("absent").status == "not_found"
    assert EvidenceRetrieval(facts, metrics=[metric]).get_lineage(metric.metric_id).reasons == [
        "graph_unavailable"
    ]
    anchor = next(n for n in graph.nodes if n.kind == "anchor")
    assert EvidenceRetrieval(graph=graph).get_anchor(anchor.node_id).reasons == [
        "dangling_evidence_anchor"
    ]
    assert api.get_anchor(graph_id("anchor", "absent")).status == "not_found"
    with pytest.raises(ValueError):
        RetrievalReference(kind="table", evidence=text.evidence_identity())
