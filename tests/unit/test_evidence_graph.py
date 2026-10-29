"""Typed graph controls; synthetic metadata không chứng minh financial accuracy."""

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.evidence import (
    EvidenceGraph,
    GraphEdge,
    TextEvidence,
    build_graph,
    validate_graph,
)
from vietnamese_financial_multi_agent.evidence.graph import graph_id

from .test_evidence_contracts import fact


def pair():
    f = fact()
    e = TextEvidence(
        document_id=f.document_id,
        snapshot_id=f.snapshot_id,
        local_evidence_id="quote",
        raw_text="synthetic",
        sources=[s.model_copy(deep=True) for s in f.sources],
    )
    return f, e


def test_build_references_roundtrip_uncertainty_and_identity():
    f, e = pair()
    other = fact(document="other-document")
    missing = f.model_copy(update={"document_id": None})
    before = [r.model_dump_json() for r in (f, e, other, missing)]
    graph = build_graph([f, other, missing], [e])
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 4
    assert len(graph.input_issues) == 1
    assert graph.input_issues[0].reasons == ["missing_record_identity"]
    assert EvidenceGraph.model_validate_json(graph.model_dump_json()) == graph
    result = validate_graph(graph, [f, other, missing], [e])
    assert {a.status for a in result.nodes + result.edges} == {"valid"}
    assert not result.orphan_nodes
    assert before == [r.model_dump_json() for r in (f, e, other, missing)]
    f.sources[0].reference.anchor.status = "uncertain"
    e.sources[0].reference.anchor.status = "uncertain"
    result = validate_graph(build_graph([f], [e]), [f], [e])
    assert {a.status for a in result.edges} == {"unresolved"}
    assert all("source_reference_uncertain" in a.reasons for a in result.edges)
    assert result.financial_fact_verified is False


@pytest.mark.parametrize(
    "control,expected",
    [
        ("document", "source_document_id_mismatch"),
        ("snapshot", "source_snapshot_id_mismatch"),
        ("dangling", "dangling_node_reference"),
        ("domain", "edge_domain_mismatch"),
        ("page_only", "exact_association_not_established"),
        ("duplicate_node", "duplicate_node_identity"),
        ("duplicate_edge", "duplicate_edge_identity"),
        ("missing_source", "missing_source"),
        ("cell", "unsupported_cell_provenance"),
        ("unknown_level", "unknown_provenance_level"),
    ],
)
def test_negative_controls(control, expected):
    f, e = pair()
    if control in {"document", "snapshot"}:
        setattr(f.sources[0], f"{control}_id", "wrong-binding")
    if control == "page_only":
        for r in (f, e):
            r.sources[0].reference.source_pointer = None
    if control == "missing_source":
        f.sources = []
    if control in {"cell", "unknown_level"}:
        f.sources[0].reference.provenance_level = "cell" if control == "cell" else "unknown"
    graph = build_graph([f], [e])
    if control == "dangling":
        graph.edges[0].target = "absent"
    if control == "domain":
        graph.edges[0].source, graph.edges[0].target = graph.edges[0].target, graph.edges[0].source
    if control == "duplicate_node":
        graph.nodes.append(graph.nodes[0].model_copy(deep=True))
    if control == "duplicate_edge":
        graph.edges.append(graph.edges[0].model_copy(deep=True))
    if control == "page_only":
        assert not any(edge.relation == "associated_with" for edge in graph.edges)
        source, target = [n.node_id for n in graph.nodes if n.kind in {"source_fact", "text"}]
        graph.edges.append(
            GraphEdge(
                edge_id=graph_id("associated_with", [source, target]),
                relation="associated_with",
                source=source,
                target=target,
            )
        )
    result = validate_graph(graph, [f], [e])
    found = [a for a in result.nodes + result.edges + result.inputs if expected in a.reasons]
    assert found
    assert all(
        a.status == ("unresolved" if control in {"page_only", "missing_source"} else "invalid")
        for a in found
    )


def test_collisions_missing_references_and_schema_types():
    f, e = pair()
    changed = f.model_copy(update={"raw_header": "different"})
    graph = build_graph([f, changed, f], [e])
    assert [a.reasons for a in graph.input_issues] == [
        ["record_identity_collision"],
        ["duplicate_record_identity"],
    ]
    result = validate_graph(graph, [f, changed], [e])
    assert "record_identity_collision" in result.nodes[0].reasons
    result = validate_graph(graph, [], [e])
    assert "missing_record_reference" in result.nodes[0].reasons
    with pytest.raises(ValidationError):
        EvidenceGraph.model_validate({"nodes": [{"kind": "derived_metric", "node_id": "x"}]})
    with pytest.raises(ValidationError):
        GraphEdge(edge_id="x", relation="used_in", source="x", target="y")


@pytest.mark.parametrize("field", ["document_id", "snapshot_id", "request_id"])
def test_association_known_binding_conflicts(field):
    f, e = pair()
    if field == "request_id":
        f.source_metadata[field], e.source_metadata[field] = "first", "second"
    else:
        setattr(e, field, "different")
        setattr(e.sources[0], field, "different")
    graph = build_graph([f], [e])
    assert not any(edge.relation == "associated_with" for edge in graph.edges)
    ids = [n.node_id for n in graph.nodes if n.kind in {"source_fact", "text"}]
    graph.edges.append(
        GraphEdge(
            edge_id=graph_id("associated_with", ids),
            relation="associated_with",
            source=ids[0],
            target=ids[1],
        )
    )
    assessment = validate_graph(graph, [f], [e]).edges[-1]
    assert assessment.status == "invalid"
    assert f"association_{field}_mismatch" in assessment.reasons
