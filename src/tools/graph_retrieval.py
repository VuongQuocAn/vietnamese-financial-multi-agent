"""Bounded M4 graph traversal; không verification hoặc natural language reasoning."""

from collections import defaultdict, deque
from copy import deepcopy
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.composition_graph import ContextRelation, node_reference, validate_context_relations
from ..evidence.contracts import Identity
from ..evidence.graph import (
    EvidenceQualityContext,
    GraphEdge,
    GraphNode,
    SourceGrounding,
    build_graph,
    graph_id,
    record_sources,
    validate_graph,
)
from ..evidence.retrieval import EvidenceCitation
from ..evidence.snapshots import SnapshotCatalog
from .evidence_retrieval import (
    EvidenceRetrievalTools,
    EvidenceToolResponse,
    GetEvidenceSourcesRequest,
    GetMetricEvidenceLineageRequest,
)

Relation = Literal["from_source", "associated_with", "used_in", "same_extraction_context"]


class GetGraphContextRequest(FinancialModel):
    tool: Literal["get_graph_context"] = "get_graph_context"
    document_id: Identity
    composition_id: Identity
    node_id: Identity
    relations: list[Relation] = Field(
        default_factory=lambda: [
            "from_source",
            "associated_with",
            "used_in",
            "same_extraction_context",
        ]
    )
    depth: int = Field(default=1, ge=1, le=3)
    limit: int = Field(default=20, ge=1, le=50)


class GetSnapshotGraphContextRequest(FinancialModel):
    """Explicit catalog selection; never impersonates an approved composition."""

    tool: Literal["get_graph_context"] = "get_graph_context"
    document_id: Identity
    snapshot_id: Identity
    node_id: Identity
    relations: list[Relation] = Field(
        default_factory=lambda: ["from_source", "associated_with", "used_in"]
    )
    depth: int = Field(default=2, ge=1, le=3)
    limit: int = Field(default=12, ge=1, le=50)


class GraphContextNode(FinancialModel):
    node: GraphNode
    depth: int
    evidence: EvidenceToolResponse
    caveats: list[str]
    quality: EvidenceQualityContext = Field(default_factory=EvidenceQualityContext)
    grounding: SourceGrounding = Field(default_factory=SourceGrounding)
    source_metadata: dict = Field(default_factory=dict)
    original_citations: list[EvidenceCitation] = Field(default_factory=list)


class GraphContextEdge(FinancialModel):
    edge: GraphEdge | ContextRelation
    basis: str
    verification: Literal["structural_only", "contextual_only"]


class GraphContextResponse(FinancialModel):
    request: GetGraphContextRequest | GetSnapshotGraphContextRequest
    status: Literal["found", "not_found", "unavailable", "ambiguous"]
    start: GraphContextNode | None = None
    matches: list[GraphContextNode] = Field(default_factory=list)
    edges: list[GraphContextEdge] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    truncated: bool = False
    caveats: list[str] = Field(
        default_factory=lambda: [
            "graph_relation_is_not_claim_support",
            "original_source_requires_M6_verification",
        ]
    )
    financial_fact_verified: Literal[False] = False


class GraphRetrievalTools:
    @classmethod
    def from_catalog(cls, catalog, *, document_id, snapshot_id):
        """Reuse traversal/resolution on the existing, explicitly pinned EF-EG."""
        from ..evidence.snapshots import isolated_catalog

        catalog = isolated_catalog(catalog)
        selected = [
            d
            for d in catalog.descriptors
            if (d.document_id, d.snapshot_id) == (document_id, snapshot_id)
        ]
        if len(selected) != 1 or catalog.ancestry(selected[0])[1]:
            raise ValueError("graph_snapshot_missing_or_ambiguous")
        if catalog.graph is None:
            raise ValueError("pinned_graph_missing")
        validation = validate_graph(catalog.graph, catalog.facts, catalog.evidence, catalog.metrics)
        if any(
            a.status != "valid" for a in [*validation.nodes, *validation.edges, *validation.inputs]
        ):
            raise ValueError("invalid_pinned_graph")
        tools = cls.__new__(cls)
        tools._view = None
        tools._selection = (document_id, snapshot_id)
        tools._financial = tools._documents = EvidenceRetrievalTools(catalog)
        tools._financial_sources = tools._document_sources = catalog.api
        tools._document_ids = set()
        tools._quality = validation.evidence_context
        tools._grounding = {a.reference: a.grounding for a in validation.nodes}
        tools._metadata, tools._anchor_metadata = {}, defaultdict(list)
        for record in [*catalog.facts, *catalog.evidence]:
            identity = (
                record.observation_identity()
                if hasattr(record, "observation_identity")
                else record.evidence_identity()
            )
            kind = "source_fact" if hasattr(record, "observation_identity") else record.kind
            nid = graph_id(kind, identity.model_dump())
            tools._metadata[nid] = deepcopy(record.source_metadata)
            for source in record_sources(record):
                aid = graph_id("anchor", source.source_key())
                tools._anchor_metadata[aid].append(
                    dict(
                        node_id=nid,
                        quality=tools._quality[nid].model_dump(mode="json"),
                        source_metadata=deepcopy(record.source_metadata),
                    )
                )
        # Every endpoint must belong to this exact snapshot. No ancestor fallback.
        tools._nodes = {}
        for node in catalog.graph.nodes:
            ref = node_reference(node)
            if ref.kind == "metric":
                matches = [m for m in catalog.metrics if m.metric_id == ref.record_id]
                binding = (
                    (matches[0].request.document_id, matches[0].request.snapshot_id)
                    if len(matches) == 1
                    else None
                )
            elif ref.kind == "anchor":
                binding = (node.anchor.document_id, node.anchor.snapshot_id)
            else:
                identity = ref.observation if ref.kind == "fact" else ref.evidence
                binding = (identity.document_id, identity.snapshot_id)
            if binding == tools._selection:
                tools._nodes[node.node_id] = node
        tools._adjacency = defaultdict(list)
        for edge in catalog.graph.edges:
            if edge.source in tools._nodes and edge.target in tools._nodes:
                tools._adjacency[edge.source].append(edge)
                tools._adjacency[edge.target].append(edge)
        for edges in tools._adjacency.values():
            edges.sort(key=lambda e: e.edge_id)
        return tools

    def __init__(self, projection):
        # Capture a validated immutable-by-ownership projection; external mutation
        # after construction cannot change traversal or strip caveats.
        self._view = projection.view.model_copy(deep=True)
        validation = validate_graph(
            self._view.graph,
            projection.financial.facts,
            projection.evidence,
            projection.financial.metrics,
        )
        contexts = validate_context_relations(
            self._view,
            projection.manifest,
            projection.financial.facts,
            projection.documents.evidence,
        )
        if any(
            a.status != "valid"
            for a in [*validation.nodes, *validation.edges, *validation.inputs, *contexts]
        ):
            raise ValueError("invalid_composition_graph_projection")
        self._quality = validation.evidence_context
        self._grounding = {a.reference: a.grounding for a in validation.nodes}
        self._metadata = {}
        self._anchor_metadata = defaultdict(list)
        for record in [*projection.financial.facts, *projection.evidence]:
            identity = (
                record.observation_identity()
                if hasattr(record, "observation_identity")
                else record.evidence_identity()
            )
            kind = "source_fact" if hasattr(record, "observation_identity") else record.kind
            nid = graph_id(kind, identity.model_dump())
            self._metadata[nid] = record.source_metadata.copy()
            for source in record_sources(record):
                aid = graph_id("anchor", source.source_key())
                self._anchor_metadata[aid].append(
                    {
                        "node_id": nid,
                        "quality": self._quality[nid].model_dump(mode="json"),
                        "source_metadata": record.source_metadata.copy(),
                    }
                )
        self._financial = EvidenceRetrievalTools(projection.financial)
        self._documents = EvidenceRetrievalTools(
            SnapshotCatalog(
                projection.documents.descriptors,
                evidence=projection.documents.evidence,
                graph=build_graph([], projection.documents.evidence),
            )
        )
        self._document_ids = {e.evidence_identity() for e in projection.documents.evidence}
        # Structural source projection keeps citations even when M4 usability is
        # blocked (e.g. an approved original UUID namespace). Never replace the
        # guarded evidence.status or feed this projection into M6 as ACCEPT proof.
        self._financial_sources = projection.financial.api
        self._document_sources = self._documents._catalog.api
        self._nodes = {n.node_id: n for n in self._view.graph.nodes}
        self._adjacency = defaultdict(list)
        checks = {a.reference: a.status for a in contexts}
        for edge in [*self._view.graph.edges, *self._view.contextual_relations]:
            if isinstance(edge, ContextRelation) and checks.get(edge.edge_id) != "valid":
                continue
            self._adjacency[edge.source].append(edge)
            self._adjacency[edge.target].append(edge)
        for edges in self._adjacency.values():
            edges.sort(key=lambda e: e.edge_id)

    def _resolve(self, node, depth):
        ref = node_reference(node)
        tools = self._documents if ref.evidence in self._document_ids else self._financial
        if ref.kind == "anchor":
            # Anchors can originate in either catalog; no cross-document fallback.
            key = (node.anchor.document_id, node.anchor.snapshot_id)
            if key != (
                self._financial._catalog.descriptors[0].document_id,
                self._financial._catalog.descriptors[0].snapshot_id,
            ):
                tools = self._documents
        result = (
            tools.get_metric_evidence_lineage(
                GetMetricEvidenceLineageRequest(metric_id=ref.record_id)
            )
            if ref.kind == "metric"
            else tools.get_evidence_sources(GetEvidenceSourcesRequest(reference=ref))
        )
        caveats = [*result.caveats, *result.reasons]
        metadata = self._metadata.get(node.node_id, {})
        caveats.extend(metadata.get("limitations", []))
        quality = self._quality.get(node.node_id, EvidenceQualityContext())
        caveats.extend(i for i in quality.resolution_issues if isinstance(i, str))
        caveats.extend(quality.structural_issues)
        for match in result.matches:
            record = match.record
            caveats.extend(getattr(record, "source_metadata", {}).get("limitations", []))
            caveats.extend(
                getattr(record, "resolution_issues", []) if ref.kind in {"text", "table"} else []
            )
            caveats.extend(getattr(record, "structural_issues", []))
        return GraphContextNode(
            node=node,
            depth=depth,
            evidence=result,
            caveats=sorted(set(caveats)),
            quality=quality,
            grounding=self._grounding[node.node_id],
            source_metadata=(
                deepcopy(metadata)
                if node.kind != "anchor"
                else {"source_records": deepcopy(self._anchor_metadata[node.node_id])}
            ),
            original_citations=[
                c
                for match in (
                    self._document_sources if tools is self._documents else self._financial_sources
                )
                .get_sources(ref)
                .matches
                for c in match.citations
            ],
        )

    def get_graph_context(self, request) -> GraphContextResponse:
        request = type(request).model_validate_json(request.model_dump_json())
        response = GraphContextResponse(request=request, status="not_found")
        if self._view is None:
            valid = (
                isinstance(request, GetSnapshotGraphContextRequest)
                and (request.document_id, request.snapshot_id) == self._selection
            )
        else:
            valid = isinstance(request, GetGraphContextRequest) and (
                request.document_id,
                request.composition_id,
            ) == (self._view.document_id, self._view.composition_id)
        if not valid:
            response.status, response.reasons = (
                "unavailable",
                ["explicit_graph_selection_mismatch"],
            )
            return response
        if request.node_id not in self._nodes:
            response.reasons = ["node_not_in_approved_composition"]
            return response
        response.start = self._resolve(self._nodes[request.node_id], 0)
        response.status = "found"
        seen, used, queue = {request.node_id}, set(), deque([(request.node_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= request.depth:
                continue
            priority = {relation: i for i, relation in enumerate(request.relations)}
            # Interleave requested relation groups. Many source anchors or exact
            # associations must not exhaust the bound before any contextual link
            # or operand is visited. Within each group retain stable edge order.
            ranks, ordered = defaultdict(int), []
            for edge in self._adjacency[current]:
                if edge.relation in priority:
                    ordered.append(
                        (ranks[edge.relation], priority[edge.relation], edge.edge_id, edge)
                    )
                    ranks[edge.relation] += 1
            for _, _, _, edge in sorted(ordered, key=lambda item: item[:3]):
                if edge.relation not in request.relations:
                    continue
                neighbor = edge.target if edge.source == current else edge.source
                if neighbor not in seen:
                    if len(response.matches) >= request.limit:
                        response.truncated = True
                        continue
                    seen.add(neighbor)
                    response.matches.append(self._resolve(self._nodes[neighbor], depth + 1))
                    queue.append((neighbor, depth + 1))
                if edge.edge_id not in used:
                    used.add(edge.edge_id)
                    contextual = isinstance(edge, ContextRelation)
                    response.edges.append(
                        GraphContextEdge(
                            edge=edge,
                            basis=edge.basis
                            if contextual
                            else {
                                "from_source": "original_source_anchor",
                                "associated_with": "M3_exact_source_selector",
                                "used_in": "accepted_metric_operand_role",
                            }[edge.relation],
                            verification="contextual_only" if contextual else "structural_only",
                        )
                    )
        if not response.matches:
            response.reasons = ["no_relation_matching_filters_missing_selector_or_metadata"]
        return GraphContextResponse.model_validate_json(response.model_dump_json())
