"""Typed read-only M4 adapters; không tính toán, rebuild metric hoặc chọn latest."""

from typing import Annotated, Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.analytical_readiness import AccountingBasisReview
from ..evidence.contracts import CanonicalFinancialFact, Identity, ObservationIdentity
from ..evidence.metrics import DerivedMetric, MetricOperand
from ..evidence.reporting_scope import ReportingScopeResolution
from ..evidence.retrieval import (
    EvidenceCitation,
    EvidenceQuery,
    EvidenceRetrieval,
    RetrievalMatch,
    RetrievalResult,
)
from ..evidence.snapshots import MetricSnapshotClosure, SnapshotCatalog, SnapshotDescriptor
from ..evidence.source_reviews import ReviewedMetricLineage, SourceReviewLookup


class GetFinancialFactRequest(FinancialModel):
    tool: Literal["get_financial_fact"] = "get_financial_fact"
    document_id: Identity
    snapshot_id: Identity
    local_observation_id: Identity


class FindFinancialFactsRequest(EvidenceQuery):
    tool: Literal["find_financial_facts"] = "find_financial_facts"
    evidence_type: Literal["fact"] = "fact"


class GetFinancialMetricRequest(FinancialModel):
    tool: Literal["get_financial_metric"] = "get_financial_metric"
    metric_id: Identity
    document_id: Identity | None = None
    snapshot_id: Identity | None = None


class ListFinancialMetricsRequest(FinancialModel):
    tool: Literal["list_financial_metrics"] = "list_financial_metrics"
    document_id: Identity
    snapshot_id: Identity | None = None
    formula_id: Identity | None = None


FinancialToolRequest = Annotated[
    GetFinancialFactRequest
    | FindFinancialFactsRequest
    | GetFinancialMetricRequest
    | ListFinancialMetricsRequest,
    Field(discriminator="tool"),
]


class FinancialFactMatch(RetrievalMatch):
    kind: Literal["fact"] = "fact"
    record: CanonicalFinancialFact
    source_review: SourceReviewLookup
    reporting_scope: ReportingScopeResolution


class FinancialMetricOperand(FinancialModel):
    binding: MetricOperand
    facts: RetrievalResult
    source_review: SourceReviewLookup | None


class FinancialMetricMatch(FinancialModel):
    kind: Literal["metric"] = "metric"
    record: DerivedMetric
    selected_snapshot: SnapshotDescriptor
    closure: MetricSnapshotClosure
    operands: list[FinancialMetricOperand]
    accounting_bases: list[AccountingBasisReview]
    reviewed_lineage: ReviewedMetricLineage
    citations: list[EvidenceCitation]
    reporting_scope: ReportingScopeResolution
    financial_fact_verified: Literal[False] = False


class FinancialToolResponse(FinancialModel):
    version: Literal["financial_retrieval_tools_v1"] = "financial_retrieval_tools_v1"
    request: FinancialToolRequest
    status: Literal["found", "not_found", "ambiguous", "unavailable", "conflicted"]
    matches: list[
        Annotated[FinancialFactMatch | FinancialMetricMatch, Field(discriminator="kind")]
    ] = Field(default_factory=list)
    snapshot_candidates: list[SnapshotDescriptor] = Field(default_factory=list)
    reporting_scopes: list[ReportingScopeResolution] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    inventory_references: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False


class FinancialRetrievalTools:
    """Isolated catalog, deep-copy outputs; mọi eligibility do M4-01 closure quyết định.

    Caller hydrate persisted records/graph/reviews/approvals trước khi tạo tools.
    Coverage là inventory explicit của M3-07; không suy mapping gap từ absence.
    Exact metric ID tự chứa selection; optional document/snapshot là AND guards.
    """

    def __init__(self, catalog: SnapshotCatalog, *, coverage=()):
        from ..evidence.snapshots import isolated_catalog

        self._catalog = isolated_catalog(catalog)
        self._api = (
            self._catalog.api
            if not coverage and getattr(self._catalog, "_request_snapshot", False)
            else EvidenceRetrieval(
                self._catalog.facts,
                self._catalog.evidence,
                self._catalog.metrics,
                graph=self._catalog.graph,
                source_reviews=self._catalog.reviews,
                coverage=coverage,
            )
        )
        self._selections = {}

    def _selection(self, document_id, snapshot_id):
        key = document_id, snapshot_id
        if key not in self._selections:
            self._selections[key] = self._catalog.select(*key)
        return self._selections[key]

    def _select(self, response, document_id, snapshot_id):
        documents = (
            [document_id]
            if document_id is not None
            else sorted(
                {
                    d.document_id
                    for d in self._catalog.descriptors
                    if snapshot_id is None or d.snapshot_id == snapshot_id
                }
            )
        )
        selected = []
        failures = []
        if not documents:
            response.reasons.append("snapshot_not_found")
        for document in documents:
            selection = self._selection(document, snapshot_id)
            response.snapshot_candidates.extend(c.descriptor for c in selection.candidates)
            if selection.status == "selected":
                selected.append(selection.candidates[0])
            else:
                failures.append(selection.status)
                response.reasons.extend(selection.reasons)
        if failures:
            response.status = (
                "ambiguous"
                if "ambiguous" in failures
                else "unavailable"
                if "blocked" in failures
                else "not_found"
            )
            return []
        return selected

    def _scope(self, descriptor):
        return self._catalog.get_reporting_scope(descriptor.document_id, descriptor.snapshot_id)

    def _fact_matches(self, result, scope):
        return [
            FinancialFactMatch(
                **match.model_dump(),
                source_review=self._api.get_source_review(match.reference.observation),
                reporting_scope=scope,
            )
            for match in result.matches
        ]

    @staticmethod
    def _finish(response):
        caveats = ["found_is_record_presence_not_financial_verification"]
        for scope in response.reporting_scopes:
            if scope.status != "resolved":
                caveats.extend(["reporting_scope_unresolved", *scope.reasons])
        for match in response.matches:
            if isinstance(match, FinancialFactMatch):
                caveats.extend(match.issues)
                caveats.extend(c for citation in match.citations for c in citation.limitations)
                for view in match.source_review.matches:
                    caveats.extend(view.quality_caveats)
                if match.display_status != "display_with_caveat":
                    caveats.append("fact_display_" + match.display_status)
                if match.source_review.status == "conflicted" or any(
                    v.status == "source_inconsistent" for v in match.source_review.matches
                ):
                    response.status = "conflicted"
                    response.reasons.append("source_review_conflicted")
            else:
                caveats.append("calculation_eligible_does_not_mean_computed")
                caveats.extend(match.record.preparation_blockers)
                caveats.extend(i.code for i in match.closure.issues)
                caveats.extend((match.closure.readiness or {}).get("execution_blockers", []))
                caveats.extend(match.reviewed_lineage.reasons)
                caveats.extend(c for citation in match.citations for c in citation.limitations)
        response.reasons = sorted(set(response.reasons))
        response.caveats = sorted(set([*response.caveats, *caveats]))
        response.inventory_references = sorted(set(response.inventory_references))
        response.snapshot_candidates.sort(key=lambda d: d.model_dump_json())
        response.matches.sort(key=lambda m: m.record.model_dump_json())
        return response.model_copy(deep=True)

    def get_financial_fact(self, request: GetFinancialFactRequest) -> FinancialToolResponse:
        response = FinancialToolResponse(request=request, status="not_found")
        entries = self._select(response, request.document_id, request.snapshot_id)
        if entries:
            scope = self._scope(entries[0].descriptor)
            response.reporting_scopes.append(scope)
            result = self._api.get_fact(
                ObservationIdentity(
                    document_id=request.document_id,
                    snapshot_id=request.snapshot_id,
                    local_id=request.local_observation_id,
                )
            )
            response.status, response.reasons = result.status, result.reasons
            response.matches = self._fact_matches(result, scope)
        return self._finish(response)

    def find_financial_facts(self, request: FindFinancialFactsRequest) -> FinancialToolResponse:
        response = FinancialToolResponse(request=request, status="not_found")
        entries = self._select(response, request.document_id, request.snapshot_id)
        statuses = []
        unresolved_scope = False
        for entry in entries:
            descriptor = entry.descriptor
            scope = self._scope(descriptor)
            response.reporting_scopes.append(scope)
            if request.reporting_scope is not None:
                if scope.status != "resolved":
                    statuses.append("conflicted" if scope.status == "conflicted" else "unavailable")
                    if scope.status != "conflicted":
                        unresolved_scope = True
                    response.reasons.append("reporting_scope_unresolved")
                    continue
                if scope.reporting_scope != request.reporting_scope:
                    statuses.append("not_found")
                    response.reasons.append("reporting_scope_mismatch")
                    continue
            # Scope overlay được kiểm ở trên; không sửa FinancialContext hoặc áp
            # review cho ancestors. Mọi filter còn lại do M3 AND-query thực hiện.
            query = EvidenceQuery(
                **request.model_dump(
                    exclude={"tool", "document_id", "snapshot_id", "reporting_scope"}
                ),
                document_id=descriptor.document_id,
                snapshot_id=descriptor.snapshot_id,
            )
            result = self._api.find_facts(query)
            statuses.append(result.status)
            response.reasons.extend(result.reasons)
            response.inventory_references.extend(result.inventory_references)
            response.matches.extend(self._fact_matches(result, scope))
        if entries:
            response.status = (
                "conflicted"
                if "conflicted" in statuses
                else "ambiguous"
                if "ambiguous" in statuses or len(response.matches) > 1
                else "found"
                if response.matches
                else "unavailable"
                if "unavailable" in statuses
                else "not_found"
            )
            if response.matches and unresolved_scope:
                response.caveats.append("partial_scope_coverage")
            if response.status == "ambiguous":
                response.reasons.append("ambiguous_candidates")
        return self._finish(response)

    def _metric_match(self, metric, entry):
        descriptor = entry.descriptor
        closure = next(c for c in entry.metrics if c.metric_id == metric.metric_id)
        lineage = self._catalog.reviewed_lineage(descriptor, metric.metric_id)
        sources = self._api.get_lineage(metric.metric_id)

        def belongs(operand):
            return operand.observation is not None and (
                operand.observation.document_id,
                operand.observation.snapshot_id,
            ) == (descriptor.document_id, descriptor.snapshot_id)

        return FinancialMetricMatch(
            record=metric,
            selected_snapshot=descriptor,
            closure=closure,
            operands=[
                FinancialMetricOperand(
                    binding=operand,
                    facts=self._api.get_fact(operand.observation)
                    if belongs(operand)
                    else RetrievalResult(
                        status="unavailable",
                        reasons=[
                            "operand_snapshot_mismatch"
                            if operand.observation
                            else "operand_" + operand.status
                        ],
                    ),
                    source_review=self._api.get_source_review(operand.observation)
                    if belongs(operand)
                    else None,
                )
                for operand in metric.operands
            ],
            accounting_bases=entry.accounting_basis_bindings,
            reviewed_lineage=lineage,
            citations=[c for m in sources.matches for c in m.citations],
            reporting_scope=self._scope(descriptor),
        )

    def get_financial_metric(self, request: GetFinancialMetricRequest) -> FinancialToolResponse:
        response = FinancialToolResponse(request=request, status="not_found")
        result = self._api.get_metric(request.metric_id)
        # Filter before returning anything; wrong caller scope cannot reveal a
        # metric, operands, citations hoặc selected snapshot của document khác.
        matches = [
            m.record
            for m in result.matches
            if (request.document_id is None or m.record.request.document_id == request.document_id)
            and (request.snapshot_id is None or m.record.request.snapshot_id == request.snapshot_id)
        ]
        if not matches:
            response.reasons = ["missing_derived_metric"]
            return self._finish(response)
        for metric in matches:
            entries = self._select(response, metric.request.document_id, metric.request.snapshot_id)
            if entries:
                response.matches.append(self._metric_match(metric, entries[0]))
        if response.matches:
            response.status = result.status
            response.reasons.extend(result.reasons)
            response.reporting_scopes = [m.reporting_scope for m in response.matches]
        return self._finish(response)

    def list_financial_metrics(self, request: ListFinancialMetricsRequest) -> FinancialToolResponse:
        response = FinancialToolResponse(request=request, status="not_found")
        entries = self._select(response, request.document_id, request.snapshot_id)
        if entries:
            entry = entries[0]
            response.reporting_scopes = [self._scope(entry.descriptor)]
            for metric in self._catalog.metrics:
                if (metric.request.document_id, metric.request.snapshot_id) == (
                    entry.descriptor.document_id,
                    entry.descriptor.snapshot_id,
                ) and (request.formula_id is None or metric.definition.name == request.formula_id):
                    response.matches.append(self._metric_match(metric, entry))
            # Listing nhiều distinct metrics là found; conflict identity giữ nguyên.
            ids = [m.record.metric_id for m in response.matches]
            response.status = (
                "conflicted" if len(ids) != len(set(ids)) else "found" if ids else "not_found"
            )
            response.reasons = ["known_conflict"] if response.status == "conflicted" else []
            if not ids:
                response.reasons = ["missing_derived_metric"]
        return self._finish(response)
