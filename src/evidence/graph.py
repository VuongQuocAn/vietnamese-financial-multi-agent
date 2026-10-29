"""Typed EF-EG v1: references và kiểm tra deterministic, không financial verification."""

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from .contracts import CanonicalFinancialFact, EvidenceAnchor, Identity, ObservationIdentity
from .document_evidence import EvidenceIdentity, TableEvidence, TextEvidence, associate_fact

EvidenceRecord = TextEvidence | TableEvidence


class SourceFactNode(FinancialModel):
    kind: Literal["source_fact"] = "source_fact"
    node_id: Identity
    reference: ObservationIdentity


class TextEvidenceNode(FinancialModel):
    kind: Literal["text"] = "text"
    node_id: Identity
    reference: EvidenceIdentity


class TableEvidenceNode(FinancialModel):
    kind: Literal["table"] = "table"
    node_id: Identity
    reference: EvidenceIdentity


class EvidenceAnchorNode(FinancialModel):
    kind: Literal["anchor"] = "anchor"
    node_id: Identity
    anchor: EvidenceAnchor


GraphNode = Annotated[
    SourceFactNode | TextEvidenceNode | TableEvidenceNode | EvidenceAnchorNode,
    Field(discriminator="kind"),
]


class GraphEdge(FinancialModel):
    edge_id: Identity
    relation: Literal["from_source", "associated_with"]
    source: Identity
    target: Identity


class GraphAssessment(FinancialModel):
    subject: Literal["node", "edge", "input"]
    reference: str
    status: Literal["valid", "invalid", "unresolved"]
    reasons: list[str] = Field(default_factory=list)


class EvidenceGraph(FinancialModel):
    version: Literal["typed_ef_eg_v1"] = "typed_ef_eg_v1"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    # Input occurrence locators, không phải IDs giả cho records thiếu identity.
    input_issues: list[GraphAssessment] = Field(default_factory=list)


class GraphValidation(FinancialModel):
    nodes: list[GraphAssessment]
    edges: list[GraphAssessment]
    inputs: list[GraphAssessment]
    orphan_nodes: list[str]
    financial_fact_verified: Literal[False] = False


def graph_id(kind, key):
    """Hash namespace + identity có thật; không hash semantic key hoặc missing IDs."""
    payload = json.dumps(key, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return kind + ":" + hashlib.sha256(payload.encode()).hexdigest()


def record_sources(record):
    return [*record.sources, *(record.member_sources if isinstance(record, TableEvidence) else [])]


def _record_identity(record):
    return (
        record.observation_identity()
        if isinstance(record, CanonicalFinancialFact)
        else record.evidence_identity()
    )


def _record_kind(record):
    return "source_fact" if isinstance(record, CanonicalFinancialFact) else record.kind


def _anchor_reasons(anchor):
    invalid, unresolved = [], []
    if anchor.source_key() is None:
        unresolved.append("missing_source_identity_or_reference")
    r = anchor.reference
    if r is not None:
        a = r.anchor
        if a.page.page < 1 or not a.page.image.strip():
            invalid.append("invalid_page_reference")
        if r.provenance_level == "cell" and not (a.table_id and a.cell_id):
            invalid.append("unsupported_cell_provenance")
        if r.provenance_level == "element" and not (a.element_id or a.table_id or a.line_id):
            invalid.append("unsupported_element_provenance")
        if r.provenance_level not in {"page", "element", "cell"}:
            invalid.append("unknown_provenance_level")
        if a.status != "resolved":
            unresolved.append("source_reference_uncertain")
    return invalid, unresolved


def _assessment(subject, reference, invalid, unresolved):
    return GraphAssessment(
        subject=subject,
        reference=reference,
        status="invalid" if invalid else "unresolved" if unresolved else "valid",
        reasons=list(dict.fromkeys([*invalid, *unresolved])),
    )


def build_graph(
    facts: Iterable[CanonicalFinancialFact], evidence: Iterable[EvidenceRecord] = ()
) -> EvidenceGraph:
    """Không sửa inputs; thiếu identity ở input_issues, caller giữ payload quarantine."""
    graph = EvidenceGraph()
    records, anchors, candidates = {}, {}, defaultdict(set)
    for index, record in enumerate([*facts, *evidence]):
        identity, kind = _record_identity(record), _record_kind(record)
        if identity is None:
            graph.input_issues.append(
                _assessment("input", f"records/{index}", [], ["missing_record_identity"])
            )
            continue
        nid = graph_id(kind, identity.model_dump())
        if nid in records:
            code = (
                "duplicate_record_identity"
                if records[nid] == record
                else "record_identity_collision"
            )
            graph.input_issues.append(_assessment("input", f"records/{index}", [code], []))
            continue
        records[nid] = record
        cls = {"source_fact": SourceFactNode, "text": TextEvidenceNode, "table": TableEvidenceNode}[
            kind
        ]
        graph.nodes.append(cls(node_id=nid, reference=identity))
        sources = record_sources(record)
        if not sources:
            graph.input_issues.append(_assessment("input", nid, [], ["missing_source"]))
        for position, source in enumerate(sources):
            key = source.source_key()
            if key is None:
                graph.input_issues.append(
                    _assessment(
                        "input",
                        f"{nid}/sources/{position}",
                        [],
                        ["missing_source_identity_or_reference"],
                    )
                )
                continue
            aid = graph_id("anchor", key)
            if aid in anchors and anchors[aid] != source:
                graph.input_issues.append(
                    _assessment(
                        "input", f"{nid}/sources/{position}", ["anchor_identity_collision"], []
                    )
                )
            elif aid not in anchors:
                anchors[aid] = source
                graph.nodes.append(EvidenceAnchorNode(node_id=aid, anchor=source))
            graph.edges.append(
                GraphEdge(
                    edge_id=graph_id("from_source", [nid, aid]),
                    relation="from_source",
                    source=nid,
                    target=aid,
                )
            )
            if kind != "source_fact":
                candidates[key].add(nid)
    # Exact selectors lấy candidate set; associate_fact vẫn là authority M3-03.
    for nid, record in records.items():
        if not isinstance(record, CanonicalFinancialFact):
            continue
        targets = set().union(*(candidates[s.source_key()] for s in record.sources))
        for target in sorted(targets):
            if associate_fact(record, records[target]) is not None:
                graph.edges.append(
                    GraphEdge(
                        edge_id=graph_id("associated_with", [nid, target]),
                        relation="associated_with",
                        source=nid,
                        target=target,
                    )
                )
    # Một record có thể nhắc cùng anchor nhiều lần; không nhân bản cạnh.
    graph.edges = list({e.edge_id: e for e in graph.edges}.values())
    return graph


def validate_graph(
    graph: EvidenceGraph,
    facts: Iterable[CanonicalFinancialFact],
    evidence: Iterable[EvidenceRecord] = (),
) -> GraphValidation:
    """Resolve references từ records thật; known violations ưu tiên invalid."""
    catalog = defaultdict(list)
    source_catalog = defaultdict(list)
    for record in [*facts, *evidence]:
        identity = _record_identity(record)
        if identity is not None:
            catalog[(_record_kind(record), identity)].append(record)
        for anchor in record_sources(record):
            if anchor.source_key() is not None:
                source_catalog[anchor.source_key()].append(anchor)
    counts = Counter(n.node_id for n in graph.nodes)
    nodes = {n.node_id: n for n in graph.nodes}
    edge_counts = Counter(e.edge_id for e in graph.edges)
    relations = Counter((e.relation, e.source, e.target) for e in graph.edges)
    assessments, resolved = {}, {}
    node_results = []
    for node in graph.nodes:
        bad, missing = [], []
        if counts[node.node_id] > 1:
            bad.append("duplicate_node_identity")
        if isinstance(node, EvidenceAnchorNode):
            a, b = _anchor_reasons(node.anchor)
            bad.extend(a)
            missing.extend(b)
            key = node.anchor.source_key()
            if key is not None and node.node_id != graph_id("anchor", key):
                bad.append("node_identity_mismatch")
            if not any(a == node.anchor for a in source_catalog[key]):
                missing.append("source_anchor_not_in_records")
            if any(a != node.anchor for a in source_catalog[key]):
                bad.append("anchor_identity_collision")
        else:
            matches = catalog[(node.kind, node.reference)]
            if node.node_id != graph_id(node.kind, node.reference.model_dump()):
                bad.append("node_identity_mismatch")
            if (
                isinstance(node, (TextEvidenceNode, TableEvidenceNode))
                and node.reference.kind != node.kind
            ):
                bad.append("node_type_mismatch")
            if not matches:
                missing.append("missing_record_reference")
            elif len(matches) > 1:
                bad.append("record_identity_collision")
            else:
                record = matches[0]
                resolved[node.node_id] = record
                if record.resolution_issues:
                    missing.append("unresolved_record_context")
                sources = record_sources(record)
                if not sources:
                    missing.append("missing_source")
                for source in sources:
                    a, b = _anchor_reasons(source)
                    bad.extend(a)
                    missing.extend(b)
                    for field in ("document_id", "snapshot_id"):
                        actual = getattr(source, field)
                        if actual is not None and actual != getattr(record, field):
                            bad.append(f"source_{field}_mismatch")
        result = _assessment("node", node.node_id, bad, missing)
        node_results.append(result)
        assessments[node.node_id] = result
    edge_results, connected = [], set()
    for edge in graph.edges:
        bad, missing = [], []
        if (
            edge_counts[edge.edge_id] > 1
            or relations[(edge.relation, edge.source, edge.target)] > 1
        ):
            bad.append("duplicate_edge_identity")
        if edge.edge_id != graph_id(edge.relation, [edge.source, edge.target]):
            bad.append("edge_identity_mismatch")
        source, target = nodes.get(edge.source), nodes.get(edge.target)
        if source is None or target is None:
            bad.append("dangling_node_reference")
        else:
            connected.update((edge.source, edge.target))
            allowed = (
                edge.relation == "from_source"
                and source.kind in {"source_fact", "text", "table"}
                and target.kind == "anchor"
            ) or (
                edge.relation == "associated_with"
                and source.kind == "source_fact"
                and target.kind in {"text", "table"}
            )
            if not allowed:
                bad.append("edge_domain_mismatch")
            else:
                record = resolved.get(source.node_id)
                other = resolved.get(target.node_id)
                if record is None:
                    missing.append("missing_record_reference")
                elif edge.relation == "from_source":
                    for field in ("document_id", "snapshot_id"):
                        actual = getattr(target.anchor, field)
                        if actual is not None and actual != getattr(record, field):
                            bad.append(f"source_{field}_mismatch")
                    if not any(s == target.anchor for s in record_sources(record)):
                        if target.anchor.source_key() is None or not record_sources(record):
                            missing.append("missing_source")
                        else:
                            bad.append("source_selector_or_metadata_mismatch")
                elif other is None:
                    missing.append("missing_record_reference")
                else:
                    for field in ("document_id", "snapshot_id"):
                        if getattr(record, field) != getattr(other, field):
                            bad.append(f"association_{field}_mismatch")
                    request_ids = [r.source_metadata.get("request_id") for r in (record, other)]
                    if all(request_ids) and request_ids[0] != request_ids[1]:
                        bad.append("association_request_id_mismatch")
                    if associate_fact(record, other) is None:
                        missing.append("exact_association_not_established")
                # Giữ uncertainty/context cả hai đầu; không nâng thành valid.
                for endpoint in (source, target):
                    assessment = assessments[endpoint.node_id]
                    (bad if assessment.status == "invalid" else missing).extend(assessment.reasons)
        edge_results.append(_assessment("edge", edge.edge_id, bad, missing))
    return GraphValidation(
        nodes=node_results,
        edges=edge_results,
        inputs=graph.input_issues,
        orphan_nodes=sorted(set(nodes) - connected),
    )
