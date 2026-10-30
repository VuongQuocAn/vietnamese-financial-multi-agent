"""Unified exact retrieval trên catalogs đã materialize; không inference hoặc I/O."""

from collections.abc import Iterable
from typing import Literal

from pydantic import Field, model_validator

from ..accounting.contracts import FinancialModel
from .contracts import (
    CanonicalFinancialFact,
    EvidenceAnchor,
    Identity,
    ObservationIdentity,
    assess_fact_consistency,
)
from .document_evidence import EvidenceIdentity, TableEvidence, TextEvidence, associate_fact
from .graph import graph_id, record_sources
from .lineage import MetricLineage, trace_metric_lineage
from .metrics import DerivedMetric

RecordKind = Literal["fact", "text", "table", "anchor", "metric", "lineage"]
Record = (
    CanonicalFinancialFact
    | TextEvidence
    | TableEvidence
    | EvidenceAnchor
    | DerivedMetric
    | MetricLineage
)


class EvidenceQuery(FinancialModel):
    """Mọi filter là optional và kết hợp AND; None nghĩa là không lọc."""

    document_id: Identity | None = None
    snapshot_id: Identity | None = None
    company_id: Identity | None = None
    canonical_item_id: Identity | None = None
    statement_type: Literal["B01", "B02", "B03", "B09"] | None = None
    period: Identity | None = None
    period_type: Identity | None = None
    reporting_scope: Literal["separate", "consolidated"] | None = None
    source_page: int | None = Field(default=None, ge=1)
    evidence_type: Literal["fact", "text", "table"] | None = None


class CanonicalCoverage(FinancialModel):
    """Caller cung cấp inventory có nguồn; absence trong catalog không là inventory."""

    document_id: Identity
    snapshot_id: Identity | None = None
    canonical_extraction: Literal["missing", "available", "unknown"] = "unknown"
    missing_canonical_items: list[Identity] = Field(default_factory=list)
    inventory_reference: Identity


class RetrievalReference(FinancialModel):
    kind: RecordKind
    observation: ObservationIdentity | None = None
    evidence: EvidenceIdentity | None = None
    record_id: Identity | None = None

    @model_validator(mode="after")
    def typed_identity(self):
        if self.kind == "fact":
            valid = (
                self.observation is not None and self.evidence is None and self.record_id is None
            )
        elif self.kind in {"text", "table"}:
            valid = (
                self.evidence is not None
                and self.evidence.kind == self.kind
                and self.observation is None
                and self.record_id is None
            )
        else:
            valid = (
                self.record_id is not None and self.observation is None and self.evidence is None
            )
        if not valid:
            raise ValueError("Reference kind/identity mismatch")
        return self


class EvidenceCitation(FinancialModel):
    anchor_id: str | None
    document_id: str | None
    snapshot_id: str | None
    pdf_page: int | None
    provenance_level: str | None
    source: EvidenceAnchor
    limitations: list[str]
    # Full source giữ source_ref, image, pointer và real element/table/cell IDs.
    financial_fact_verified: Literal[False] = False


class RetrievalMatch(FinancialModel):
    reference: RetrievalReference
    record: Record
    citations: list[EvidenceCitation] = Field(default_factory=list)
    evidence_references: list[EvidenceIdentity] = Field(default_factory=list)
    display_status: Literal["display_with_caveat", "blocked", "undetermined"] = "undetermined"
    issues: list[str] = Field(default_factory=list)


class RetrievalResult(FinancialModel):
    version: Literal["evidence_retrieval_v1"] = "evidence_retrieval_v1"
    status: Literal["found", "not_found", "ambiguous", "unavailable", "conflicted"]
    matches: list[RetrievalMatch] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    inventory_references: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False


def _ordered(records):
    # Exact payload duplicates idempotent; different payloads never overwritten.
    return [records[key] for key in sorted(records)]


class EvidenceRetrieval:
    """Read-only facade; rebuild après restart từ existing repositories/catalogs.

    Graph bắt buộc được caller cung cấp, không rebuild để che broken references.
    Catalog là snapshot bất biến riêng; methods trả deep copies.
    """

    def __init__(self, facts=(), evidence=(), metrics=(), *, graph=None, coverage=()):
        self._facts = _ordered({f.model_dump_json(): f.model_copy(deep=True) for f in facts})
        self._evidence = _ordered({e.model_dump_json(): e.model_copy(deep=True) for e in evidence})
        self._metrics = _ordered({m.model_dump_json(): m.model_copy(deep=True) for m in metrics})
        self._graph = graph.model_copy(deep=True) if graph is not None else None
        self._coverage = [c.model_copy(deep=True) for c in coverage]

    @classmethod
    def from_repositories(
        cls, fact_repositories, evidence_repositories, document_ids: Iterable[str], **kwargs
    ):
        """Explicit document scope; reuse public APIs, không scan filesystem."""
        documents = sorted(set(document_ids))
        return cls(
            [f for r in fact_repositories for d in documents for f in r.list_by_document(d)],
            [e for r in evidence_repositories for d in documents for e in r.list_by_document(d)],
            **kwargs,
        )

    def _citation(self, source, owner=None):
        ref = source.reference
        issues = []
        if source.source_key() is None:
            issues.append("missing_source_identity_or_reference")
        if owner and (source.document_id, source.snapshot_id) != owner:
            issues.append("source_identity_mismatch")
        if ref:
            if ref.anchor.status != "resolved":
                issues.append("source_reference_uncertain")
            if ref.provenance_level == "page":
                issues.append("page_level_only")
        return EvidenceCitation(
            anchor_id=graph_id("anchor", source.source_key()) if source.source_key() else None,
            document_id=source.document_id,
            snapshot_id=source.snapshot_id,
            pdf_page=ref.anchor.page.page if ref else None,
            provenance_level=ref.provenance_level if ref else None,
            source=source.model_copy(deep=True),
            limitations=issues,
        )

    def _match(self, kind, record):
        issues, associations, display = [], [], "undetermined"
        if kind == "fact":
            reference = RetrievalReference(kind=kind, observation=record.observation_identity())
            issues = [i.code for i in assess_fact_consistency(record).issues]
            issues.extend(i.code for i in record.resolution_issues)
            decisions = [q.decision for q in record.quality_context if q.task_type == "direct_qa"]
            consistency = assess_fact_consistency(record)
            has_source = any(
                s.reference is not None
                and s.reference.anchor.page.page > 0
                and s.reference.anchor.page.image.strip()
                and (s.document_id, s.snapshot_id) == (record.document_id, record.snapshot_id)
                for s in record.sources
            )
            display = (
                "blocked"
                if record.value.normalized_value is None
                or not record.value.raw_value.strip()
                or consistency.status == "inconsistent"
                or any(d in {"insufficient", "conflicted"} for d in decisions)
                else "display_with_caveat"
                if len(decisions) == 1 and has_source
                else "undetermined"
            )
            associations = [
                a.evidence for e in self._evidence if (a := associate_fact(record, e)) is not None
            ]
            if associations:
                issues.append("association_is_not_verified_semantic_support")
            sources = record.sources
            owner = (record.document_id, record.snapshot_id)
        elif kind in {"text", "table"}:
            reference = RetrievalReference(kind=kind, evidence=record.evidence_identity())
            sources = record_sources(record)
            issues = [*record.resolution_issues]
            if kind == "table":
                issues.extend(record.structural_issues)
            owner = (record.document_id, record.snapshot_id)
        elif kind == "anchor":
            reference = RetrievalReference(
                kind=kind, record_id=graph_id("anchor", record.source_key())
            )
            sources, owner = [record], None
        else:
            reference = RetrievalReference(kind=kind, record_id=record.metric_id)
            lineage = record if kind == "lineage" else None
            sources = [a for o in lineage.operands for a in o.anchors] if lineage else []
            issues = (
                [*lineage.unresolved, *lineage.tasks.blockers]
                if lineage
                else record.preparation_blockers
            )
            owner = (record.request.document_id, record.request.snapshot_id)
        return RetrievalMatch(
            reference=reference,
            record=record.model_copy(deep=True),
            citations=[self._citation(s, owner) for s in sources],
            evidence_references=sorted(set(associations), key=lambda i: i.model_dump_json()),
            display_status=display,
            issues=sorted(set(issues)),
        )

    def _result(self, kind, records, missing="no_matching_record"):
        records = sorted(records, key=lambda r: r.model_dump_json())
        if not records:
            return RetrievalResult(status="not_found", reasons=[missing])
        matches = [self._match(kind, r) for r in records]
        references = [m.reference.model_dump_json() for m in matches]
        conflict = len(set(references)) < len(references) or any(
            isinstance(r, CanonicalFinancialFact)
            and any(q.decision == "conflicted" for q in r.quality_context)
            for r in records
        )
        return RetrievalResult(
            status="conflicted" if conflict else "ambiguous" if len(matches) > 1 else "found",
            matches=matches,
            reasons=["known_conflict"]
            if conflict
            else ["ambiguous_candidates"]
            if len(matches) > 1
            else [],
        )

    def get_fact(self, identity: ObservationIdentity) -> RetrievalResult:
        return self._result(
            "fact",
            [f for f in self._facts if f.observation_identity() == identity],
            "no_matching_fact",
        )

    def find_facts(self, query: EvidenceQuery) -> RetrievalResult:
        candidates = [f for f in self._facts if f.observation_identity() is not None]
        if query.evidence_type not in {None, "fact"}:
            return RetrievalResult(status="not_found", reasons=["evidence_type_mismatch"])
        for name in ("document_id", "snapshot_id", "company_id", "canonical_item_id"):
            value = getattr(query, name)
            if value is not None:
                candidates = [f for f in candidates if getattr(f, name) == value]
        for name in ("statement_type", "reporting_scope", "period_type"):
            value = getattr(query, name)
            if value is not None:
                candidates = [f for f in candidates if getattr(f.context, name) == value]
        if query.source_page is not None:
            candidates = [
                f
                for f in candidates
                if any(
                    c.pdf_page == query.source_page
                    and "source_identity_mismatch" not in c.limitations
                    for c in [self._citation(s, (f.document_id, f.snapshot_id)) for s in f.sources]
                )
            ]
        before_period = candidates
        if query.period is not None:
            candidates = [f for f in candidates if f.context.period == query.period]
        result = self._result("fact", candidates, "no_matching_fact")
        if result.matches:
            return result
        coverage = [
            c
            for c in self._coverage
            if c.document_id == query.document_id
            and (c.snapshot_id is None or c.snapshot_id == query.snapshot_id)
        ]
        missing = [c for c in coverage if c.canonical_extraction == "missing"]
        mapping = [c for c in coverage if query.canonical_item_id in c.missing_canonical_items]
        if missing or mapping:
            return RetrievalResult(
                status="unavailable",
                reasons=[
                    "canonical_extraction_missing" if missing else "canonical_mapping_missing"
                ],
                inventory_references=sorted({c.inventory_reference for c in (missing or mapping)}),
            )
        if query.period is not None and before_period:
            result.reasons = ["missing_period"]
        return result

    def get_evidence(self, identity: EvidenceIdentity) -> RetrievalResult:
        return self._result(
            identity.kind,
            [e for e in self._evidence if e.evidence_identity() == identity],
            "no_matching_evidence",
        )

    def find_evidence(self, query: EvidenceQuery) -> RetrievalResult:
        if any(
            getattr(query, f) is not None
            for f in (
                "company_id",
                "canonical_item_id",
                "statement_type",
                "period",
                "period_type",
                "reporting_scope",
            )
        ):
            return RetrievalResult(
                status="unavailable", reasons=["financial_filter_unavailable_for_document_evidence"]
            )
        matches = []
        for kind in ("text", "table"):
            records = [
                e
                for e in self._evidence
                if e.evidence_identity() is not None
                and e.kind == kind
                and query.evidence_type in {None, kind}
                and (query.document_id is None or e.document_id == query.document_id)
                and (query.snapshot_id is None or e.snapshot_id == query.snapshot_id)
                and (
                    query.source_page is None
                    or any(
                        s.reference
                        and s.reference.anchor.page.page == query.source_page
                        and (s.document_id, s.snapshot_id) == (e.document_id, e.snapshot_id)
                        for s in record_sources(e)
                    )
                )
            ]
            matches.extend(self._result(kind, records).matches)
        matches.sort(key=lambda m: m.reference.model_dump_json())
        refs = [m.reference.model_dump_json() for m in matches]
        conflict = len(refs) != len(set(refs))
        return RetrievalResult(
            status="conflicted"
            if conflict
            else "ambiguous"
            if len(matches) > 1
            else "found"
            if matches
            else "not_found",
            matches=matches,
            reasons=["known_conflict"]
            if conflict
            else ["ambiguous_candidates"]
            if len(matches) > 1
            else []
            if matches
            else ["no_matching_evidence"],
        )

    def get_metric(self, metric_id: str) -> RetrievalResult:
        return self._result(
            "metric",
            [m for m in self._metrics if m.metric_id == metric_id],
            "missing_derived_metric",
        )

    def get_lineage(self, metric_id: str) -> RetrievalResult:
        metric = self.get_metric(metric_id)
        if metric.status != "found":
            return metric
        if self._graph is None:
            return RetrievalResult(status="unavailable", reasons=["graph_unavailable"])
        lineage = trace_metric_lineage(
            metric.matches[0].record, self._graph, self._facts, self._evidence
        )
        # Kiểm tra cả tập used_in rỗng; traversal không được coi mất toàn bộ edges
        # là lineage hoàn chỉnh chỉ vì SourceFact nodes vẫn tồn tại.
        missing_edges = [
            o.role
            for o in metric.matches[0].record.operands
            if o.status == "bound"
            and not any(
                e.relation == "used_in"
                and e.target == metric_id
                and e.source == o.source_fact_node_id
                and e.operand_role == o.role
                for e in self._graph.edges
            )
        ]
        if missing_edges:
            lineage.completeness = "broken"
            lineage.unresolved = sorted(set([*lineage.unresolved, "missing_used_in_edge"]))
            lineage.tasks.arithmetic_preparation = "incomplete"
            lineage.tasks.analytical_interpretation = "blocked"
            lineage.tasks.blockers = sorted(set([*lineage.tasks.blockers, "missing_used_in_edge"]))
        result = self._result("lineage", [lineage])
        if lineage.completeness == "broken":
            result.status, result.reasons = "unavailable", ["broken_lineage", *lineage.unresolved]
        elif lineage.completeness == "ambiguous":
            result.status, result.reasons = "ambiguous", ["ambiguous_candidates"]
        elif lineage.completeness == "partial":
            result.reasons = ["partial_lineage", *lineage.unresolved]
        return result

    def get_anchor(self, anchor_id: str) -> RetrievalResult:
        if self._graph is None:
            return RetrievalResult(status="unavailable", reasons=["graph_unavailable"])
        nodes = [n for n in self._graph.nodes if n.kind == "anchor" and n.node_id == anchor_id]
        if any(
            n.anchor.source_key() is None or graph_id("anchor", n.anchor.source_key()) != anchor_id
            for n in nodes
        ):
            return RetrievalResult(status="unavailable", reasons=["anchor_identity_mismatch"])
        result = self._result("anchor", [n.anchor for n in nodes], "missing_evidence_anchor")
        catalog_sources = [s for r in [*self._facts, *self._evidence] for s in record_sources(r)]
        if nodes and any(n.anchor not in catalog_sources for n in nodes):
            result.status, result.reasons = "unavailable", ["dangling_evidence_anchor"]
        return result

    def get_sources(self, reference: RetrievalReference) -> RetrievalResult:
        if reference.kind == "fact":
            result = self.get_fact(reference.observation)
        elif reference.kind in {"text", "table"}:
            result = self.get_evidence(reference.evidence)
        elif reference.kind == "anchor":
            result = self.get_anchor(reference.record_id)
        else:
            result = self.get_lineage(reference.record_id)
        if result.status == "found" and not any(m.citations for m in result.matches):
            result.status, result.reasons = "unavailable", ["source_unavailable"]
        return result
