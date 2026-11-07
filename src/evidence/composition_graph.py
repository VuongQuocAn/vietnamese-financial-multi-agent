"""EF-01: projection EF-EG v1, contextual overlay; không là claim support."""

from collections import Counter, defaultdict
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from .composition import EvidenceComposition, load_composition
from .contracts import EvidenceAnchor, Identity
from .graph import (
    EvidenceGraph,
    GraphAssessment,
    GraphValidation,
    build_graph,
    graph_id,
    record_sources,
    validate_graph,
)
from .retrieval import RetrievalReference
from .snapshots import SnapshotCatalog


class ContextRelation(FinancialModel):
    edge_id: Identity
    relation: Literal["same_extraction_context"] = "same_extraction_context"
    source: Identity
    target: Identity
    source_reference: RetrievalReference
    target_reference: RetrievalReference
    document_id: Identity
    composition_id: Identity
    pdf_sha256: Identity
    request_id: Identity
    source_anchor: EvidenceAnchor
    target_anchor: EvidenceAnchor
    basis: Literal["same_request_bound_page_explicit_selector"] = (
        "same_request_bound_page_explicit_selector"
    )
    verification: Literal["contextual_only"] = "contextual_only"
    caveats: list[str] = Field(default_factory=lambda: ["not_semantic_claim_support"])


class CompositionGraph(FinancialModel):
    version: Literal["composition_graph_v1"] = "composition_graph_v1"
    document_id: Identity
    composition_id: Identity
    pdf_sha256: Identity
    graph: EvidenceGraph
    contextual_relations: list[ContextRelation]
    validation: GraphValidation
    contextual_validation: list[GraphAssessment]
    financial_fact_verified: Literal[False] = False


def node_reference(node):
    if node.kind == "source_fact":
        return RetrievalReference(kind="fact", observation=node.reference)
    if node.kind in {"text", "table"}:
        return RetrievalReference(kind=node.kind, evidence=node.reference)
    return RetrievalReference(
        kind="anchor" if node.kind == "anchor" else "metric", record_id=node.node_id
    )


def select_financial_catalog(catalog, manifest):
    """Induced view đúng explicit snapshot; không chọn latest/ancestor."""
    descriptor = manifest.financial_snapshot
    key = descriptor.document_id, descriptor.snapshot_id
    matches = [d for d in catalog.descriptors if (d.document_id, d.snapshot_id) == key]
    if matches != [descriptor]:
        raise ValueError("financial_descriptor_missing_or_conflicting")
    facts = [f for f in catalog.facts if (f.document_id, f.snapshot_id) == key]
    evidence = [e for e in catalog.evidence if (e.document_id, e.snapshot_id) == key]
    metrics = [m for m in catalog.metrics if (m.request.document_id, m.request.snapshot_id) == key]
    if not facts or catalog.graph is None:
        raise ValueError("approved_financial_graph_required")
    expected = build_graph(facts, evidence, metrics)
    ids = {n.node_id for n in expected.nodes}
    graph = EvidenceGraph(
        nodes=[n for n in catalog.graph.nodes if n.node_id in ids],
        edges=[e for e in catalog.graph.edges if e.source in ids and e.target in ids],
        input_issues=[i for i in catalog.graph.input_issues if i.reference in ids],
    )
    # No silent reconstruction of a missing/changed accepted edge or node.
    if (
        sorted(n.model_dump_json() for n in graph.nodes)
        != sorted(n.model_dump_json() for n in expected.nodes)
        or sorted(e.model_dump_json() for e in graph.edges)
        != sorted(e.model_dump_json() for e in expected.edges)
        or expected.input_issues
        or graph.input_issues
    ):
        raise ValueError("financial_graph_record_mismatch")
    pdf_ref = "sha256:" + descriptor.pdf_sha256
    for fact in facts:
        for anchor in fact.sources:
            if anchor.reference is None or anchor.reference.anchor.page.source_ref != pdf_ref:
                raise ValueError("financial_pdf_binding_mismatch")
    return SnapshotCatalog(
        [descriptor],
        facts,
        evidence,
        metrics,
        graph=graph,
        source_reviews=[
            r
            for r in catalog.reviews
            if (r.observation.document_id, r.observation.snapshot_id) == key
        ],
        accounting_bases=catalog.bases,
        approval=catalog.approval,
        formula_policies=catalog.policies,
        formula_approvals=catalog.formula_approvals,
        execution_approval=catalog.execution_approval,
        reporting_scope_reviews=catalog.scope_reviews,
    )


def _selector_basis(fact, evidence, manifest):
    """Request gốc scope pointer; cùng trang không đủ căn cứ."""
    request = fact.source_metadata.get("request_id")
    if not request or request != evidence.source_metadata.get("request_id"):
        return None
    # Only pinned target sources. Financial image must match the approved render.
    pages = {
        (s.descriptor.document_id, s.descriptor.snapshot_id, p.page): p
        for s in manifest.sources
        if s.status == "verified"
        for p in s.pages
    }
    for left in fact.sources:
        for right in record_sources(evidence):
            if left.reference is None or right.reference is None:
                continue
            a, b = left.reference, right.reference
            lp, rp = a.anchor.page, b.anchor.page
            binding = pages.get((evidence.document_id, evidence.snapshot_id, rp.page))
            if binding is None or (lp.page, lp.image, lp.source_ref) != (
                rp.page,
                "sha256:" + binding.image_sha256,
                binding.source_ref,
            ):
                continue
            x, y = a.source_pointer, b.source_pointer
            # Exact pointer or original cell within an explicitly referenced table.
            same = bool(x and y and x == y)
            table_member = bool(
                evidence.kind == "table"
                and x
                and y
                and y.startswith("/tables/")
                and len(y.strip("/").split("/")) == 2
                and x.startswith(y + "/cells/")
            )
            if same or table_member:
                return request, left, right
    return None


def _context_edges(manifest, facts, evidence):
    edges = []
    # Small request index; never construct same-PDF Cartesian relations.
    by_request = defaultdict(list)
    for row in evidence:
        if row.source_metadata.get("request_id"):
            by_request[row.source_metadata["request_id"]].append(row)
    for fact in facts:
        for row in by_request[fact.source_metadata.get("request_id")]:
            if fact.snapshot_id == row.snapshot_id and fact.document_id == row.document_id:
                continue  # exact M3 authority remains associate_fact
            basis = _selector_basis(fact, row, manifest)
            if basis is None:
                continue
            request, left, right = basis
            fid, eid = fact.observation_identity(), row.evidence_identity()
            source = graph_id("source_fact", fid.model_dump())
            target = graph_id(row.kind, eid.model_dump())
            edges.append(
                ContextRelation(
                    edge_id=graph_id(
                        "same_extraction_context", [manifest.composition_id, source, target]
                    ),
                    source=source,
                    target=target,
                    source_reference=RetrievalReference(kind="fact", observation=fid),
                    target_reference=RetrievalReference(kind=row.kind, evidence=eid),
                    document_id=manifest.logical_document_id,
                    composition_id=manifest.composition_id,
                    pdf_sha256=manifest.financial_snapshot.pdf_sha256,
                    request_id=request,
                    source_anchor=left,
                    target_anchor=right,
                )
            )
    return sorted(edges, key=lambda e: e.edge_id)


def validate_context_relations(view, manifest, facts, evidence):
    """Reproduce allowed relations from original pins/selectors, reject forged basis."""
    expected = {e.edge_id: e for e in _context_edges(manifest, facts, evidence)}
    nodes = {n.node_id: n for n in view.graph.nodes}
    counts = Counter(e.edge_id for e in view.contextual_relations)
    results = []
    for edge in view.contextual_relations:
        reasons = []
        if counts[edge.edge_id] > 1:
            reasons.append("duplicate_context_relation")
        if edge.source not in nodes or edge.target not in nodes:
            reasons.append("dangling_context_endpoint")
        elif (node_reference(nodes[edge.source]), node_reference(nodes[edge.target])) != (
            edge.source_reference,
            edge.target_reference,
        ):
            reasons.append("context_endpoint_identity_mismatch")
        if expected.get(edge.edge_id) != edge:
            reasons.append("context_composition_or_selector_mismatch")
        results.append(
            GraphAssessment(
                subject="edge",
                reference=edge.edge_id,
                status="invalid" if reasons else "valid",
                reasons=reasons,
            )
        )
    return results


class CompositionGraphView:
    """Caller supplies explicit approved manifest/catalog. All copies stay read-only."""

    def __init__(self, manifest, repository, financial_catalog, *, document_id, composition_id):
        self.manifest = EvidenceComposition.model_validate_json(manifest.model_dump_json())
        self.documents = load_composition(
            self.manifest, repository, document_id=document_id, composition_id=composition_id
        )
        self.financial = select_financial_catalog(financial_catalog, self.manifest)
        records = {}
        for row in [*self.financial.evidence, *self.documents.evidence]:
            identity = row.evidence_identity()
            if identity in records and records[identity] != row:
                raise ValueError("graph_evidence_identity_collision")
            records[identity] = row
        self.evidence = sorted(
            records.values(), key=lambda e: e.evidence_identity().model_dump_json()
        )
        graph = self.financial.graph.model_copy(deep=True)
        addition = build_graph(self.financial.facts, self.evidence, self.financial.metrics)
        existing_nodes = {n.node_id: n for n in graph.nodes}
        existing_edges = {e.edge_id: e for e in graph.edges}
        for node in addition.nodes:
            if node.node_id in existing_nodes and existing_nodes[node.node_id] != node:
                raise ValueError("graph_node_identity_collision")
            existing_nodes[node.node_id] = node
        existing_edges.update({e.edge_id: e for e in addition.edges})
        graph.nodes = sorted(existing_nodes.values(), key=lambda n: n.node_id)
        graph.edges = sorted(existing_edges.values(), key=lambda e: e.edge_id)
        graph.input_issues.extend(addition.input_issues)
        validation = validate_graph(
            graph, self.financial.facts, self.evidence, self.financial.metrics
        )
        if any(
            a.status != "valid" for a in [*validation.nodes, *validation.edges, *validation.inputs]
        ):
            raise ValueError("composition_graph_validation_failed")
        self.view = CompositionGraph(
            document_id=document_id,
            composition_id=composition_id,
            pdf_sha256=self.manifest.financial_snapshot.pdf_sha256,
            graph=graph,
            validation=validation,
            contextual_relations=_context_edges(
                self.manifest, self.financial.facts, self.documents.evidence
            ),
            contextual_validation=[],
        )
        self.view.contextual_validation = validate_context_relations(
            self.view, self.manifest, self.financial.facts, self.documents.evidence
        )
