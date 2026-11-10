"""Explicit snapshot catalog/closure trên records hiện có; không I/O hoặc latest."""

from collections.abc import Iterable
from copy import deepcopy
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialModel
from .analytical_readiness import AccountingBasisReview, assess_analytical_readiness
from .compatibility import FinancialOperand
from .contracts import Identity, ObservationIdentity, assess_fact_consistency
from .document_evidence import associate_fact
from .execution_compatibility import assess_execution_compatibility
from .graph import graph_id, record_sources
from .metrics import DerivedMetric, MetricRequest, build_metric
from .preparation_policy import check_metric_formula_policy
from .reporting_scope import resolve_reporting_scope
from .retrieval import EvidenceRetrieval


def isolated_catalog(catalog):
    """Internal read-only request snapshots may be shared; public inputs detach."""
    return catalog if getattr(catalog, "_request_snapshot", False) else deepcopy(catalog)


class SnapshotDescriptor(FinancialModel):
    document_id: Identity
    pdf_sha256: Identity
    snapshot_id: Identity
    parent_snapshot_id: Identity | None = None
    origin: Literal["original_extraction", "normalized_projection", "recovery"]


class ClosureIssue(FinancialModel):
    code: str
    reference: str
    severity: Literal["partial", "blocked"]


class MetricSnapshotClosure(FinancialModel):
    metric_id: str
    document_id: str
    snapshot_id: str
    status: Literal["closed", "partial", "blocked"]
    operand_count: int
    resolved_operands: int
    issues: list[ClosureIssue]
    preparation_ready: bool = False
    calculation_eligible: bool = False
    readiness: dict | None = None


class SnapshotEntry(FinancialModel):
    descriptor: SnapshotDescriptor
    snapshot_chain: list[str]
    fact_count: int
    evidence_count: int
    source_review_bindings: list[ObservationIdentity]
    accounting_basis_bindings: list[AccountingBasisReview]
    metrics: list[MetricSnapshotClosure]
    known_limitations: list[str]
    readiness: Literal["closed", "partial", "blocked"]
    preparation_ready_metrics: int
    calculation_eligible_metrics: int


class SnapshotSelection(FinancialModel):
    status: Literal["selected", "ambiguous", "not_found", "blocked"]
    candidates: list[SnapshotEntry] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def rebuild_snapshot_metrics(
    definitions_and_periods: Iterable[tuple], descriptor: SnapshotDescriptor, facts
) -> list[DerivedMetric]:
    """Caller chọn definitions + kỳ cho từng role; không sửa metric/reference cũ."""
    facts = list(facts)
    return [
        build_metric(
            d,
            MetricRequest(
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
                operand_periods=p,
            ),
            facts,
        )
        for d, p in definitions_and_periods
    ]


class SnapshotCatalog:
    """Rebuild từ persisted descriptors và repositories do caller chọn.

    Parent relations chỉ để trace; tuyệt đối không lấy facts/reviews từ ancestors.
    Duplicate descriptors/identity conflicts giữ blocked, không last-write-wins.
    """

    def __init__(
        self,
        descriptors,
        facts=(),
        evidence=(),
        metrics=(),
        *,
        graph=None,
        source_reviews=(),
        accounting_bases=(),
        approval=None,
        formula_policies=(),
        formula_approvals=(),
        execution_approval=None,
        reporting_scope_reviews=(),
    ):
        self.descriptors = [d.model_copy(deep=True) for d in descriptors]
        self.facts = [f.model_copy(deep=True) for f in facts]
        self.evidence = [e.model_copy(deep=True) for e in evidence]
        self.metrics = [m.model_copy(deep=True) for m in metrics]
        self.reviews = [r.model_copy(deep=True) for r in source_reviews]
        self.bases = [b.model_copy(deep=True) for b in accounting_bases]
        self.approval = approval
        self.policies = list(formula_policies)
        self.formula_approvals = list(formula_approvals)
        self.execution_approval = execution_approval
        self.scope_reviews = [r.model_copy(deep=True) for r in reporting_scope_reviews]
        self.graph = graph.model_copy(deep=True) if graph is not None else None
        self.api = EvidenceRetrieval(
            self.facts, self.evidence, self.metrics, graph=graph, source_reviews=self.reviews
        )

    def ancestry(self, descriptor):
        chain, issues, seen = [], [], set()
        current = descriptor
        while current is not None:
            if current.snapshot_id in seen:
                issues.append("snapshot_parent_cycle")
                break
            seen.add(current.snapshot_id)
            chain.append(current.snapshot_id)
            matches = [
                d
                for d in self.descriptors
                if (d.document_id, d.snapshot_id) == (current.document_id, current.snapshot_id)
            ]
            if len(matches) != 1:
                issues.append("snapshot_descriptor_ambiguous")
                break
            if matches[0] != current:
                issues.append("snapshot_descriptor_mismatch")
            if (
                current.document_id != "sha256:" + current.pdf_sha256
                or current.pdf_sha256 != descriptor.pdf_sha256
            ):
                issues.append("document_hash_mismatch")
            if current.parent_snapshot_id is None:
                break
            parents = [
                d
                for d in self.descriptors
                if d.document_id == current.document_id
                and d.snapshot_id == current.parent_snapshot_id
            ]
            if len(parents) != 1:
                issues.append("snapshot_parent_missing_or_ambiguous")
                break
            current = parents[0]
        return chain, issues

    def request_snapshot(self):
        """One detached owner for synchronous read-only tools/critics in a request.

        Never stored on the caller's catalog or reused across requests. Results
        leave tool boundaries as detached models; current release policy remains
        independently checked by verification/admission, outside these caches.
        """
        snapshot = deepcopy(self)
        # Catalog records are mutable at public boundaries; rebuild once from
        # this exact detached state rather than trust a possibly older API view.
        snapshot.api = EvidenceRetrieval(
            snapshot.facts,
            snapshot.evidence,
            snapshot.metrics,
            graph=snapshot.graph,
            source_reviews=snapshot.reviews,
        )
        snapshot._request_snapshot = True
        snapshot._entry_cache = {}
        snapshot.api._lineage_cache = {}
        return snapshot

    def get_reporting_scope(self, document_id, snapshot_id):
        """Separate read-only context overlay; không thay metric/fact compatibility."""
        descriptors = [
            d
            for d in self.descriptors
            if (d.document_id, d.snapshot_id) == (document_id, snapshot_id)
        ]
        if len(descriptors) != 1:
            from .reporting_scope import ReportingScopeResolution

            return ReportingScopeResolution(
                document_id=document_id,
                snapshot_id=snapshot_id,
                status="unresolved",
                evidence_status="insufficient",
                reasons=["scope_snapshot_missing_or_ambiguous"],
                reviews=[],
            )
        result = resolve_reporting_scope(descriptors[0], self.scope_reviews)
        _, issues = self.ancestry(descriptors[0])
        if issues:
            result.reporting_scope = None
            result.status, result.evidence_status = "unresolved", "insufficient"
            result.reasons = sorted(set([*result.reasons, *issues]))
        return result

    def assess_metric(self, descriptor, metric) -> MetricSnapshotClosure:
        issues, supplied = [], []

        def issue(code, reference, severity="blocked"):
            record = ClosureIssue(code=code, reference=reference, severity=severity)
            if record not in issues:
                issues.append(record)

        selected = (descriptor.document_id, descriptor.snapshot_id)
        metric_valid = True
        try:
            DerivedMetric.model_validate_json(metric.model_dump_json())
        except ValidationError:
            metric_valid = False
            issue("invalid_metric_record", metric.metric_id)
        records = [m for m in self.metrics if m.metric_id == metric.metric_id]
        if len(records) != 1 or records[0] != metric:
            issue("metric_catalog_mismatch", metric.metric_id)
        _, parent_issues = self.ancestry(descriptor)
        for code in parent_issues:
            issue(code, descriptor.snapshot_id)
        if (metric.request.document_id, metric.request.snapshot_id) != selected:
            issue("metric_snapshot_mismatch", metric.metric_id)
        for operand in metric.operands:
            ref = operand.observation
            locator = ref.model_dump_json() if ref else operand.role
            if operand.status != "bound" or ref is None:
                issue(
                    "operand_" + operand.status,
                    operand.role,
                    "partial" if operand.status == "missing" else "blocked",
                )
                continue
            if (ref.document_id, ref.snapshot_id) != selected:
                issue("operand_snapshot_mismatch", locator)
                continue
            matches = [f for f in self.facts if f.observation_identity() == ref]
            if len(matches) != 1:
                issue(
                    "operand_missing" if not matches else "operand_ambiguous",
                    locator,
                    "partial" if not matches else "blocked",
                )
                continue
            fact = matches[0]
            supplied.append(FinancialOperand(role=operand.role, fact=fact))
            consistency = assess_fact_consistency(fact)
            if consistency.status == "inconsistent":
                for reason in consistency.issues:
                    issue(reason.code, locator)
            review = self.api.get_source_review(ref).matches[0]
            if review.status != "value_row_verified":
                issue(
                    review.status,
                    locator,
                    "blocked" if review.status == "source_inconsistent" else "partial",
                )
            for source in fact.sources:
                if source.reference is None:
                    issue("source_missing", locator, "partial")
                elif (source.document_id, source.snapshot_id) != selected:
                    issue("source_snapshot_mismatch", locator)
                elif source.reference.anchor.page.source_ref != descriptor.document_id:
                    issue("source_document_hash_mismatch", locator)
                elif not any(
                    associate_fact(fact, e) is not None and source in record_sources(e)
                    for e in self.evidence
                ):
                    issue("document_evidence_missing", repr(source.source_key()), "partial")
            for evidence in self.evidence:
                association = associate_fact(fact, evidence)
                if (
                    association is not None
                    and self.graph is not None
                    and not any(
                        e.relation == "associated_with"
                        and e.source == graph_id("source_fact", ref.model_dump())
                        and e.target == graph_id(evidence.kind, association.evidence.model_dump())
                        for e in self.graph.edges
                    )
                ):
                    issue("missing_associated_with_edge", association.evidence.model_dump_json())
            bases = [
                b
                for b in self.bases
                if (b.document_id, b.snapshot_id) == selected
                and fact.context.statement_type in b.statement_types
            ]
            if len(bases) != 1:
                issue(
                    "accounting_basis_missing" if not bases else "accounting_basis_ambiguous",
                    locator,
                    "partial" if not bases else "blocked",
                )
            elif bases[0].pdf_sha256 != descriptor.pdf_sha256 or (
                bases[0].reused_from_snapshot and not bases[0].verification_reference
            ):
                issue("accounting_basis_source_inconsistent", locator)
        lineage = self.api.get_lineage(metric.metric_id) if metric_valid else None
        if lineage is not None and (lineage.status not in {"found"} or lineage.reasons):
            for reason in lineage.reasons or ["lineage_unavailable"]:
                issue(
                    reason,
                    metric.metric_id,
                    "blocked"
                    if lineage.status in {"conflicted", "ambiguous", "unavailable"}
                    else "partial",
                )
        readiness = None
        if len(supplied) == len(metric.operands) or self.execution_approval is not None:
            policies = [p for p in self.policies if p.formula_id == metric.definition.name]
            readiness = assess_analytical_readiness(
                metric.definition.compatibility,
                supplied,
                self.reviews,
                self.bases,
                approval=self.approval,
                formula_policy=policies[0] if len(policies) == 1 else None,
                formula_approvals=self.formula_approvals,
            )
        status = (
            "blocked"
            if any(i.severity == "blocked" for i in issues)
            else "partial"
            if issues
            else "closed"
        )
        eligible = False
        if self.execution_approval is not None and readiness is not None:
            execution = assess_execution_compatibility(
                metric.definition.compatibility,
                supplied,
                self.reviews,
                self.bases,
                approval=self.execution_approval,
                formula_policy=policies[0] if len(policies) == 1 else None,
            ).model_dump(mode="json")
            formula = check_metric_formula_policy(
                policies[0] if len(policies) == 1 else None,
                metric.definition,
                supplied,
                self.formula_approvals,
            )
            blockers = execution["execution_blockers"] + formula["blockers"]
            if not formula["execution_approved"]:
                blockers.append("formula_policy_not_approved")
            if status != "closed":
                blockers.append("snapshot_closure_not_closed")
                blockers.extend(i.code for i in issues)
            eligible = (
                status == "closed"
                and execution["execution_profile_approved"]
                and execution["approved_execution_compatibility"]["status"] == "compatible"
                and formula["execution_approved"]
                and not blockers
            )
            readiness.update(execution)
            readiness.update(
                formula_policy=formula,
                execution_blockers=sorted(set(blockers)),
                eligibility_blockers=sorted(set(blockers)),
                calculation_eligible=eligible,
            )
        return MetricSnapshotClosure(
            metric_id=metric.metric_id,
            document_id=descriptor.document_id,
            snapshot_id=descriptor.snapshot_id,
            status=status,
            operand_count=len(metric.operands),
            resolved_operands=len(supplied),
            issues=issues,
            readiness=readiness,
            preparation_ready=status == "closed"
            and bool(readiness and readiness["preparation_ready"]),
            calculation_eligible=eligible,
        )

    def entry(self, descriptor):
        cache = getattr(self, "_entry_cache", None)
        key = descriptor.model_dump_json()
        if cache is not None and key in cache:
            return cache[key].model_copy(deep=True)

        def belongs(record):
            return (record.document_id, record.snapshot_id) == (
                descriptor.document_id,
                descriptor.snapshot_id,
            )

        chain, limitations = self.ancestry(descriptor)
        facts = [f for f in self.facts if belongs(f)]
        metrics = [self.assess_metric(descriptor, m) for m in self.metrics if belongs(m.request)]
        limitations.extend(i.code for f in facts for i in f.resolution_issues)
        limitations.extend(
            q.decision
            for f in facts
            for q in f.quality_context
            if q.decision in {"insufficient", "conflicted"}
        )
        limitations.extend(i.code for m in metrics for i in m.issues)
        result = SnapshotEntry(
            descriptor=descriptor.model_copy(deep=True),
            snapshot_chain=chain,
            fact_count=len(facts),
            evidence_count=sum(belongs(e) for e in self.evidence),
            source_review_bindings=[
                r.observation.model_copy(deep=True) for r in self.reviews if belongs(r.observation)
            ],
            accounting_basis_bindings=[b.model_copy(deep=True) for b in self.bases if belongs(b)],
            metrics=metrics,
            known_limitations=sorted(set(limitations)),
            preparation_ready_metrics=sum(m.preparation_ready for m in metrics),
            calculation_eligible_metrics=sum(m.calculation_eligible for m in metrics),
            readiness="blocked"
            if self.ancestry(descriptor)[1] or any(m.status == "blocked" for m in metrics)
            else "partial"
            if not metrics or any(m.status != "closed" for m in metrics)
            else "closed",
        )
        if cache is not None:
            cache[key] = result.model_copy(deep=True)
        return result

    def select(self, document_id: str, snapshot_id: str | None = None) -> SnapshotSelection:
        candidates = [
            self.entry(d)
            for d in self.descriptors
            if d.document_id == document_id
            and (snapshot_id is None or d.snapshot_id == snapshot_id)
        ]
        status = (
            "not_found"
            if not candidates
            else "ambiguous"
            if len(candidates) > 1
            else "blocked"
            if self.ancestry(candidates[0].descriptor)[1]
            else "selected"
        )
        return SnapshotSelection(
            status=status,
            candidates=candidates,
            reasons=[] if status == "selected" else ["snapshot_" + status],
        )

    def reviewed_lineage(self, descriptor, metric_id):
        chain, issues = self.ancestry(descriptor)
        metric = self.api.get_metric(metric_id)
        if (
            issues
            or metric.status != "found"
            or (
                metric.matches[0].record.request.document_id,
                metric.matches[0].record.request.snapshot_id,
            )
            != (descriptor.document_id, descriptor.snapshot_id)
        ):
            from .source_reviews import ReviewedMetricLineage

            return ReviewedMetricLineage(
                status="unavailable", reasons=issues or ["metric_snapshot_mismatch"]
            )
        return self.api.get_reviewed_lineage(metric_id, snapshot_chain=chain)
