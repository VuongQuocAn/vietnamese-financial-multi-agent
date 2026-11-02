"""Synthetic controls trên hai documents; không là financial accuracy evaluation."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.evidence import (
    DocumentEvidenceRepository,
    RetrievalReference,
    SnapshotCatalog,
    TextEvidence,
    build_graph,
    build_metric,
)
from vietnamese_financial_multi_agent.tools import (
    CalculateFinancialMetricRequest,
    EvidenceRetrievalTools,
    EvidenceToolResponse,
    FinancialCalculator,
    FindDocumentEvidenceRequest,
    GetEvidenceAnchorRequest,
    GetEvidenceItemRequest,
    GetEvidenceSourcesRequest,
    GetMetricEvidenceLineageRequest,
)

from .test_m4_execution import fixture


def sample():
    data, second = fixture(), fixture(document=1)
    for field in (
        "descriptors",
        "facts",
        "evidence",
        "metrics",
        "source_reviews",
        "accounting_bases",
    ):
        data[field].extend(second[field])
    for document in (0, 1):
        table = data["evidence"][document * 2]
        data["evidence"].append(
            TextEvidence(
                document_id=table.document_id,
                snapshot_id=table.snapshot_id,
                local_evidence_id=table.local_evidence_id,
                raw_text="synthetic text",
                sources=deepcopy(table.member_sources),
                resolution_issues=["uncertain_text"],
            )
        )
    data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])
    return data


def exact(record):
    return GetEvidenceItemRequest(
        document_id=record.document_id,
        snapshot_id=record.snapshot_id,
        local_evidence_id=record.local_evidence_id,
        kind=record.kind,
    )


@pytest.mark.parametrize("document", [0, 1])
def test_exact_types_filters_roundtrip_restart_and_isolation(document, tmp_path):
    data = sample()
    catalog = SnapshotCatalog(**data)
    tools = EvidenceRetrievalTools(catalog)
    table, text = data["evidence"][document * 2], data["evidence"][4 + document]
    repo = DocumentEvidenceRepository(tmp_path / "evidence")
    for record in data["evidence"]:
        repo.put(record)
    for record in (table, text):
        request = exact(record)
        response = tools.get_evidence_item(request)
        assert response.status == "found" and response.matches[0].record == record
        assert response.matches == catalog.api.get_evidence(record.evidence_identity()).matches
        assert not response.financial_fact_verified
        wire = response.model_dump_json()
        assert EvidenceToolResponse.model_validate_json(wire) == response
        data["evidence"] = [
            e
            for d in data["descriptors"]
            for e in DocumentEvidenceRepository(repo.root).list_by_document(
                d.document_id, d.snapshot_id
            )
        ]
        assert (
            EvidenceRetrievalTools(SnapshotCatalog(**data)).get_evidence_item(request) == response
        )
        response.matches[0].record.sources.clear()
        response.matches[0].citations.clear()
        request.local_evidence_id = "mutated"
        assert tools.get_evidence_item(exact(record)).model_dump_json() == wire
    catalog.evidence.clear()
    query = FindDocumentEvidenceRequest(
        document_id=table.document_id,
        snapshot_id=table.snapshot_id,
        source_page=7 + document,
    )
    result = tools.find_document_evidence(query)
    assert result.status == "ambiguous" and len(result.matches) == 3
    assert {m.reference.evidence.document_id for m in result.matches} == {table.document_id}
    assert (
        len(
            tools.find_document_evidence(query.model_copy(update={"evidence_type": "text"})).matches
        )
        == 1
    )
    assert (
        tools.find_document_evidence(query.model_copy(update={"source_page": 999})).status
        == "not_found"
    )
    assert (
        tools.get_evidence_item(
            exact(text).model_copy(update={"local_evidence_id": "absent"})
        ).status
        == "not_found"
    )


@pytest.mark.parametrize("field,value", [("company_id", "synthetic"), ("period", "2030")])
def test_unsupported_financial_filters(field, value):
    data = sample()
    request = FindDocumentEvidenceRequest(
        document_id=data["descriptors"][0].document_id,
        snapshot_id=data["descriptors"][0].snapshot_id,
        **{field: value},
    )
    result = EvidenceRetrievalTools(SnapshotCatalog(**data)).find_document_evidence(request)
    assert result.status == "unavailable"
    assert result.reasons == ["financial_filter_unavailable_for_document_evidence"]


def test_conflicting_records_keep_all_candidates():
    data = sample()
    text = data["evidence"][-1]
    data["evidence"].append(text.model_copy(update={"raw_text": "different"}, deep=True))
    tools = EvidenceRetrievalTools(SnapshotCatalog(**data))
    result = tools.get_evidence_item(exact(text))
    assert result.status == "conflicted" and len(result.matches) == 2
    assert {m.record.raw_text for m in result.matches} == {"synthetic text", "different"}
    result = tools.find_document_evidence(
        FindDocumentEvidenceRequest(
            document_id=text.document_id,
            snapshot_id=text.snapshot_id,
            evidence_type="text",
        )
    )
    assert result.status == "conflicted" and len(result.matches) == 2


def test_no_parent_fallback_or_original_recovery_merge():
    data = sample()
    parent = data["descriptors"][0]
    child = parent.model_copy(
        update={
            "snapshot_id": "recovery",
            "parent_snapshot_id": parent.snapshot_id,
            "origin": "recovery",
        },
        deep=True,
    )
    data["descriptors"].append(child)
    tools = EvidenceRetrievalTools(SnapshotCatalog(**data))
    original = exact(data["evidence"][0])
    assert tools.get_evidence_item(original).status == "found"
    assert (
        tools.get_evidence_item(original.model_copy(update={"snapshot_id": "recovery"})).status
        == "not_found"
    )
    assert (
        tools.get_evidence_item(
            original.model_copy(update={"document_id": data["descriptors"][1].document_id})
        ).status
        == "not_found"
    )


@pytest.mark.parametrize("failure", ["graph", "missing", "dangling", "identity"])
def test_anchor_unavailable(failure):
    data = sample()
    anchor = next(n for n in data["graph"].nodes if n.kind == "anchor")
    anchor_id = anchor.node_id
    if failure == "graph":
        data["graph"] = None
    elif failure == "missing":
        data["graph"].nodes.remove(anchor)
    elif failure == "dangling":
        data["facts"], data["evidence"] = [], []
    else:
        anchor.anchor.reference.source_pointer = "different"
    result = EvidenceRetrievalTools(SnapshotCatalog(**data)).get_evidence_anchor(
        GetEvidenceAnchorRequest(anchor_id=anchor_id)
    )
    assert result.status == "unavailable"
    assert result.reasons == [
        {
            "graph": "graph_unavailable",
            "missing": "missing_evidence_anchor",
            "dangling": "dangling_evidence_anchor",
            "identity": "anchor_identity_mismatch",
        }[failure]
    ]


@pytest.mark.parametrize("field", ["document_id", "snapshot_id"])
def test_optional_guards_no_source_leak(field):
    data = sample()
    tools = EvidenceRetrievalTools(SnapshotCatalog(**data))
    fact, metric = data["facts"][0], data["metrics"][0]
    citation = tools._api.get_fact(fact.observation_identity()).matches[0].citations[0]
    for result in (
        tools.get_evidence_anchor(
            GetEvidenceAnchorRequest(anchor_id=citation.anchor_id, **{field: "wrong"})
        ),
        tools.get_evidence_sources(
            GetEvidenceSourcesRequest(
                reference=RetrievalReference(kind="fact", observation=fact.observation_identity()),
                **{field: "wrong"},
            )
        ),
        tools.get_metric_evidence_lineage(
            GetMetricEvidenceLineageRequest(metric_id=metric.metric_id, **{field: "wrong"})
        ),
    ):
        assert result.status == "not_found" and not result.matches and not result.metric_matches
        assert not result.reporting_scopes and not result.snapshot_candidates


def test_uncertain_page_source_missing_selector_structure_and_associations():
    data = sample()
    table = data["evidence"][0]
    table.structural_issues = ["sparse_table"]
    table.resolution_issues = ["unresolved_header"]
    source = table.member_sources[0]
    source.reference.provenance_level = "page"
    source.reference.source_pointer = None
    source.reference.anchor.element_id = source.reference.anchor.table_id = None
    source.reference.anchor.cell_id = source.reference.anchor.line_id = None
    source.reference.anchor.observed_bbox = None
    data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])
    tools = EvidenceRetrievalTools(SnapshotCatalog(**data))
    result = tools.get_evidence_item(exact(table))
    assert {
        "sparse_table",
        "unresolved_header",
        "page_level_only",
        "source_selector_unavailable",
    } <= set(result.caveats)
    assert result.matches[0].citations[0].source == source
    assert result.matches[0].citations[0].source.reference.anchor.observed_bbox is None
    # Second unchanged table has an exact selector association; first is page-only.
    fact = data["facts"][1]
    result = tools.get_evidence_sources(
        GetEvidenceSourcesRequest(
            reference=RetrievalReference(
                kind="fact",
                observation=fact.observation_identity(),
            )
        )
    )
    assert result.matches[0].evidence_references
    assert "association_is_not_verified_semantic_support" in result.caveats
    assert not result.financial_fact_verified and result.source_reviews
    empty = TextEvidence(
        document_id=table.document_id,
        snapshot_id=table.snapshot_id,
        local_evidence_id="no-source",
        raw_text="unbound",
    )
    data["evidence"].append(empty)
    tools = EvidenceRetrievalTools(SnapshotCatalog(**data))
    result = tools.get_evidence_sources(
        GetEvidenceSourcesRequest(
            reference=RetrievalReference(
                kind="text",
                evidence=empty.evidence_identity(),
            )
        )
    )
    assert result.status == "unavailable" and "source_unavailable" in result.reasons


@pytest.mark.parametrize("failure", [None, "graph", "edge", "partial"])
def test_calculator_to_lineage_and_broken_partial_controls(failure):
    data = sample()
    metric = data["metrics"][0]
    execution = FinancialCalculator(SnapshotCatalog(**data)).calculate_financial_metric(
        CalculateFinancialMetricRequest(metric_id=metric.metric_id)
    )
    assert execution.status == "computed"
    if failure == "graph":
        data["graph"] = None
    elif failure == "edge":
        data["graph"].edges = [e for e in data["graph"].edges if e.relation != "used_in"]
    elif failure == "partial":
        data["facts"] = data["facts"][1:]
        metric = build_metric(metric.definition, metric.request, data["facts"])
        data["metrics"][0] = metric
        data["graph"] = build_graph(data["facts"], data["evidence"], data["metrics"])
    tools = EvidenceRetrievalTools(SnapshotCatalog(**data))
    request = GetMetricEvidenceLineageRequest(metric_id=metric.metric_id)
    result = tools.get_metric_evidence_lineage(request)
    assert EvidenceToolResponse.model_validate_json(result.model_dump_json()) == result
    if failure in {"graph", "edge"}:
        assert result.status == "unavailable"
        assert (
            "graph_unavailable" in result.reasons
            if failure == "graph"
            else "broken_lineage" in result.reasons
        )
    elif failure == "partial":
        assert result.status == "found" and "partial_lineage" in result.reasons
        assert result.matches[0].record.completeness == "partial"
    else:
        assert result.status == "found" and result.matches[0].record.completeness == "complete"
        assert result.metric_matches == [execution.evidence]
        assert result.matches[0].citations == execution.evidence.citations
        assert result.metric_matches[0].record.result is None
        for kind in ("metric", "lineage"):
            sources = tools.get_evidence_sources(
                GetEvidenceSourcesRequest(
                    reference=RetrievalReference(
                        kind=kind,
                        record_id=metric.metric_id,
                    )
                )
            )
            assert sources.matches == result.matches
        result.metric_matches[0].operands.clear()
        assert tools.get_metric_evidence_lineage(request).metric_matches[0].operands
