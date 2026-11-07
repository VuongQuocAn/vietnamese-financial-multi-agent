"""EF-01 synthetic controls; real PDF cases được chạy riêng bằng script."""

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.evidence.composition_graph import (
    CompositionGraphView,
    validate_context_relations,
)
from vietnamese_financial_multi_agent.evidence.graph import build_graph, graph_id
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog
from vietnamese_financial_multi_agent.tools.evidence_retrieval import EvidenceRetrievalTools
from vietnamese_financial_multi_agent.tools.graph_retrieval import (
    GetGraphContextRequest,
    GraphContextResponse,
    GraphRetrievalTools,
)

from .test_evidence_composition import sample
from .test_evidence_contracts import fact


def inputs(tmp_path):
    manifest, repo, row = sample(tmp_path)
    document = "sha256:" + manifest.financial_snapshot.pdf_sha256
    manifest.financial_snapshot.document_id = document
    manifest.sources[0].descriptor.document_id = document
    row.document_id = document
    row.sources[0].document_id = document
    manifest.sources[0].evidence[0].identity = row.evidence_identity()
    row.source_metadata = {"request_id": "original-request", "limitations": ["pdf_review:defect"]}
    row.resolution_issues = ["unknown_reading", "truncated_paragraph"]
    from vietnamese_financial_multi_agent.evidence.composition import payload_sha256

    manifest.sources[0].evidence[0].payload_sha256 = payload_sha256(row.model_dump(mode="json"))
    repo.put(row)
    f = fact(document=document, snapshot="financial")
    f.sources = [row.sources[0].model_copy(deep=True)]
    f.sources[0].snapshot_id = "financial"
    f.source_metadata = {"request_id": "original-request"}
    catalog = SnapshotCatalog([manifest.financial_snapshot], [f], graph=build_graph([f]))
    return manifest, repo, row, f, catalog


def project(manifest, repo, catalog):
    return CompositionGraphView(
        manifest, repo, catalog, document_id="logical", composition_id="approved"
    )


def test_overlay_preserves_sources_graph_quality_and_bounded_facade(tmp_path):
    m, repo, row, f, catalog = inputs(tmp_path)
    before = catalog.graph.model_dump_json(), f.model_dump_json(), row.model_dump_json()
    projection = project(m, repo, catalog)
    view = projection.view
    assert len(view.contextual_relations) == 1
    edge = view.contextual_relations[0]
    assert edge.verification == "contextual_only"
    assert edge.source_reference.observation.snapshot_id == "financial"
    assert edge.target_reference.evidence.snapshot_id == "native"
    assert all(n in view.graph.nodes for n in catalog.graph.nodes)
    assert all(e in view.graph.edges for e in catalog.graph.edges)
    assert not any(e.relation == "associated_with" for e in view.graph.edges)
    request = GetGraphContextRequest(
        document_id="logical", composition_id="approved", node_id=edge.source, depth=3, limit=50
    )
    tools = EvidenceRetrievalTools.from_composition(
        m, repo, document_id="logical", composition_id="approved", financial_catalog=catalog
    )
    try:
        result = tools.get_graph_context(request)
        assert result.status == "found"
        match = next(n for n in result.matches if n.node.node_id == edge.target)
        assert {"pdf_review:defect", "unknown_reading", "truncated_paragraph"} <= set(match.caveats)
        assert match.evidence.matches[0].record == row
        assert GraphContextResponse.model_validate_json(result.model_dump_json()) == result
        assert (
            tools.get_graph_context(request.model_copy(update={"composition_id": "other"})).status
            == "unavailable"
        )
        assert (
            tools.get_graph_context(request.model_copy(update={"node_id": "legacy"})).status
            == "not_found"
        )
        limited = tools.get_graph_context(request.model_copy(update={"limit": 1}))
        assert len(limited.matches) == 1 and limited.truncated
        filtered = tools.get_graph_context(request.model_copy(update={"relations": ["used_in"]}))
        assert not filtered.edges and not filtered.matches
    finally:
        tools.close_search()
    assert project(m, repo, catalog).view == view
    assert before == (catalog.graph.model_dump_json(), f.model_dump_json(), row.model_dump_json())
    for field, value in [("depth", 4), ("limit", 51)]:
        with pytest.raises(ValidationError):
            GetGraphContextRequest.model_validate({**request.model_dump(), field: value})


@pytest.mark.parametrize("case", ["pointer", "page", "request", "snapshot", "company", "legacy"])
def test_no_context_from_same_page_unbound_snapshot_or_other_pdf(tmp_path, case):
    m, repo, row, f, catalog = inputs(tmp_path)
    if case == "pointer":
        f.sources[0].reference.source_pointer = "/text_elements/unrelated"
    elif case == "page":
        f.sources[0].reference.anchor.page.page += 1
    elif case == "request":
        f.source_metadata["request_id"] = "independent-request"
    elif case == "snapshot":
        m.financial_snapshot.snapshot_id = "unbound"
    elif case == "company":
        m.sources[0].descriptor.pdf_sha256 = "different-company-pdf"
    else:
        m.sources[0].status = "quarantine"
    catalog = SnapshotCatalog(catalog.descriptors, [f], graph=build_graph([f]))
    if case in {"snapshot", "company"}:
        with pytest.raises(ValueError):
            project(m, repo, catalog)
    else:
        assert not project(m, repo, catalog).view.contextual_relations


@pytest.mark.parametrize("case", ["duplicate", "endpoint", "pointer", "page", "identity"])
def test_overlay_validation_rejects_tampering(tmp_path, case):
    m, repo, row, f, catalog = inputs(tmp_path)
    projection = project(m, repo, catalog)
    view = projection.view.model_copy(deep=True)
    edge = view.contextual_relations[0]
    if case == "duplicate":
        view.contextual_relations.append(edge.model_copy(deep=True))
    elif case == "endpoint":
        edge.target = "absent"
    elif case == "pointer":
        edge.target_anchor.reference.source_pointer = "/invented"
    elif case == "page":
        edge.target_anchor.reference.anchor.page.page += 1
    else:
        edge.target_reference.evidence = edge.target_reference.evidence.model_copy(
            update={"snapshot_id": "other"}
        )
    assert all(a.status == "invalid" for a in validate_context_relations(view, m, [f], [row]))
    # Only the untouched validated projection is admitted to the public facade.
    assert (
        GraphRetrievalTools(projection)
        .get_graph_context(
            GetGraphContextRequest(
                document_id="logical",
                composition_id="approved",
                node_id=graph_id("source_fact", f.observation_identity().model_dump()),
            )
        )
        .status
        == "found"
    )


def test_original_uuid_citations_remain_visible_without_bypassing_m4_gate(tmp_path):
    m, repo, row, f, catalog = inputs(tmp_path)
    row.document_id = "original-uuid"
    row.sources[0].document_id = row.document_id
    m.sources[0].descriptor.document_id = row.document_id
    m.sources[0].evidence[0].identity = row.evidence_identity()
    from vietnamese_financial_multi_agent.evidence.composition import payload_sha256

    m.sources[0].evidence[0].payload_sha256 = payload_sha256(row.model_dump(mode="json"))
    repo.put(row)
    projection = project(m, repo, catalog)
    edge = projection.view.contextual_relations[0]
    result = GraphRetrievalTools(projection).get_graph_context(
        GetGraphContextRequest(
            document_id="logical",
            composition_id="approved",
            node_id=edge.target,
        )
    )
    assert result.start.evidence.status == "unavailable"
    assert "snapshot_blocked" in result.start.caveats
    assert result.start.original_citations[0].document_id == "original-uuid"
    assert result.start.original_citations[0].source == row.sources[0]
    assert "pdf_review:defect" in result.start.caveats
