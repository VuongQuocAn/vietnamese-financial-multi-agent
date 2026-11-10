"""Typed read-only evidence tools trên M3-07 và M4-02; không suy financial claims."""

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.contracts import Identity
from ..evidence.document_evidence import EvidenceIdentity
from ..evidence.reporting_scope import ReportingScopeResolution
from ..evidence.retrieval import EvidenceQuery, RetrievalReference, RetrievalResult
from ..evidence.search import (
    DocumentSearchResponse,
    EvidenceSearchIndex,
    SearchDocumentEvidenceRequest,
)
from ..evidence.snapshots import SnapshotCatalog, SnapshotDescriptor
from ..evidence.source_reviews import SourceReviewLookup
from .financial_retrieval import (
    FinancialMetricMatch,
    FinancialRetrievalTools,
    GetFinancialMetricRequest,
)

if TYPE_CHECKING:
    from .graph_retrieval import GetGraphContextRequest, GraphContextResponse


class _EvidenceRequest(FinancialModel):
    version: Literal["evidence_tools_request_v1"] = "evidence_tools_request_v1"


class GetEvidenceItemRequest(_EvidenceRequest):
    tool: Literal["get_evidence_item"] = "get_evidence_item"
    document_id: Identity
    snapshot_id: Identity
    local_evidence_id: Identity
    kind: Literal["text", "table"]


class FindDocumentEvidenceRequest(EvidenceQuery):
    version: Literal["evidence_tools_request_v1"] = "evidence_tools_request_v1"
    tool: Literal["find_document_evidence"] = "find_document_evidence"
    document_id: Identity
    snapshot_id: Identity
    evidence_type: Literal["text", "table"] | None = None


class GetEvidenceAnchorRequest(_EvidenceRequest):
    tool: Literal["get_evidence_anchor"] = "get_evidence_anchor"
    anchor_id: Identity
    document_id: Identity | None = None
    snapshot_id: Identity | None = None


class GetEvidenceSourcesRequest(_EvidenceRequest):
    tool: Literal["get_evidence_sources"] = "get_evidence_sources"
    reference: RetrievalReference
    document_id: Identity | None = None
    snapshot_id: Identity | None = None


class GetMetricEvidenceLineageRequest(_EvidenceRequest):
    tool: Literal["get_metric_evidence_lineage"] = "get_metric_evidence_lineage"
    metric_id: Identity
    document_id: Identity | None = None
    snapshot_id: Identity | None = None


EvidenceToolRequest = Annotated[
    GetEvidenceItemRequest
    | FindDocumentEvidenceRequest
    | GetEvidenceAnchorRequest
    | GetEvidenceSourcesRequest
    | GetMetricEvidenceLineageRequest,
    Field(discriminator="tool"),
]


class EvidenceToolResponse(RetrievalResult):
    version: Literal["evidence_tools_v1"] = "evidence_tools_v1"
    request: EvidenceToolRequest
    snapshot_candidates: list[SnapshotDescriptor] = Field(default_factory=list)
    reporting_scopes: list[ReportingScopeResolution] = Field(default_factory=list)
    source_reviews: list[SourceReviewLookup] = Field(default_factory=list)
    # M4-02 giữ formula, roles, SourceFact bindings, reviewed lineage và closure.
    metric_matches: list[FinancialMetricMatch] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class EvidenceRetrievalTools:
    """Caller hydrate catalog; exact snapshot, không latest/parent fallback hoặc I/O.

    found chỉ là record presence; source usability nằm trong original records,
    citations và controlled reviews. Không tính lại metric/execution artifacts.
    """

    def __init__(self, catalog: SnapshotCatalog):
        from ..evidence.snapshots import isolated_catalog

        self._catalog = isolated_catalog(catalog)
        self._api = self._catalog.api
        self._financial = FinancialRetrievalTools(self._catalog)
        self._selections = {}
        self._search = None
        self._graph_tools = None

    @classmethod
    def from_composition(
        cls, manifest, repository, *, document_id, composition_id, financial_catalog=None
    ):
        index = EvidenceSearchIndex(
            manifest, repository, document_id=document_id, composition_id=composition_id
        )
        tools = cls(index.catalog)
        tools._search = index
        if financial_catalog is not None:
            from ..evidence.composition_graph import CompositionGraphView
            from .graph_retrieval import GraphRetrievalTools

            tools._graph_tools = GraphRetrievalTools(
                CompositionGraphView(
                    manifest,
                    repository,
                    financial_catalog,
                    document_id=document_id,
                    composition_id=composition_id,
                )
            )
        return tools

    def get_graph_context(self, request: "GetGraphContextRequest") -> "GraphContextResponse":
        from .graph_retrieval import GraphContextResponse

        if self._graph_tools is None:
            return GraphContextResponse(
                request=request, status="unavailable", reasons=["approved_financial_graph_required"]
            )
        return self._graph_tools.get_graph_context(request)

    def search_document_evidence(
        self, request: SearchDocumentEvidenceRequest
    ) -> DocumentSearchResponse:
        if self._search is None:
            return DocumentSearchResponse(
                request=request, status="unavailable", reasons=["explicit_composition_required"]
            )
        return self._search.search(request)

    def close_search(self):
        if self._search is not None:
            self._search.close()
            self._search = None

    def _select(self, response, document_id, snapshot_id):
        key = document_id, snapshot_id
        if key not in self._selections:
            self._selections[key] = self._catalog.select(*key)
        selection = self._selections[key]
        response.snapshot_candidates.extend(c.descriptor for c in selection.candidates)
        if selection.status != "selected":
            response.status = {
                "not_found": "not_found",
                "ambiguous": "ambiguous",
                "blocked": "unavailable",
            }[selection.status]
            response.reasons.extend(selection.reasons)
            return False
        response.reporting_scopes.append(self._catalog.get_reporting_scope(*key))
        return True

    def _result(self, request, result):
        response = EvidenceToolResponse(request=request, status=result.status)
        # Optional guards áp trên record identity, không source gần giống/cùng trang.
        matches = []
        for match in result.matches:
            owner = getattr(match.record, "request", match.record)
            document, snapshot = owner.document_id, owner.snapshot_id
            if any(
                guard is not None and guard != actual
                for guard, actual in (
                    (request.document_id, document),
                    (request.snapshot_id, snapshot),
                )
            ):
                continue
            matches.append(match)
        if result.matches and not matches:
            response.status, response.reasons = "not_found", ["record_binding_mismatch"]
            return self._finish(response)
        for document, snapshot in sorted(
            {
                (
                    getattr(m.record, "request", m.record).document_id,
                    getattr(m.record, "request", m.record).snapshot_id,
                )
                for m in matches
            },
            key=str,
        ):
            if document is None or snapshot is None:
                response.status, response.reasons = "unavailable", ["record_binding_unavailable"]
                return self._finish(response)
            if not self._select(response, document, snapshot):
                return self._finish(response)
        response.matches = matches
        response.reasons.extend(result.reasons)
        response.inventory_references = result.inventory_references
        for match in matches:
            if match.reference.kind == "fact":
                response.source_reviews.append(
                    self._api.get_source_review(match.reference.observation)
                )
        return self._finish(response)

    @staticmethod
    def _finish(response):
        response.caveats.append("found_is_record_presence_not_financial_verification")
        for scope in response.reporting_scopes:
            if scope.status != "resolved":
                response.caveats.extend(["reporting_scope_unresolved", *scope.reasons])
        for match in response.matches:
            response.caveats.extend(match.issues)
            if not match.citations:
                response.caveats.append("source_unavailable")
            for citation in match.citations:
                response.caveats.extend(citation.limitations)
                ref = citation.source.reference
                if ref is not None and not any(
                    (
                        ref.source_pointer,
                        ref.anchor.element_id,
                        ref.anchor.table_id,
                        ref.anchor.cell_id,
                        ref.anchor.line_id,
                    )
                ):
                    response.caveats.append("source_selector_unavailable")
        for review in response.source_reviews:
            response.caveats.extend(review.reasons)
            for view in review.matches:
                response.caveats.extend(view.quality_caveats)
            if review.status == "conflicted":
                response.status = "conflicted"
                response.reasons.append("source_review_conflicted")
        response.reasons = sorted(set(response.reasons))
        response.caveats = sorted(set(response.caveats))
        return response.model_copy(deep=True)

    def get_evidence_item(self, request: GetEvidenceItemRequest) -> EvidenceToolResponse:
        response = EvidenceToolResponse(request=request, status="not_found")
        if not self._select(response, request.document_id, request.snapshot_id):
            return self._finish(response)
        result = self._api.get_evidence(
            EvidenceIdentity(
                document_id=request.document_id,
                snapshot_id=request.snapshot_id,
                local_id=request.local_evidence_id,
                kind=request.kind,
            )
        )
        if not result.matches:
            response.status, response.reasons = result.status, result.reasons
            return self._finish(response)
        return self._result(request, result)

    def find_document_evidence(self, request: FindDocumentEvidenceRequest) -> EvidenceToolResponse:
        response = EvidenceToolResponse(request=request, status="not_found")
        if not self._select(response, request.document_id, request.snapshot_id):
            return self._finish(response)
        result = self._api.find_evidence(
            EvidenceQuery(**request.model_dump(exclude={"tool", "version"}))
        )
        if not result.matches:
            response.status, response.reasons = result.status, result.reasons
            return self._finish(response)
        return self._result(request, result)

    def get_evidence_anchor(self, request: GetEvidenceAnchorRequest) -> EvidenceToolResponse:
        result = self._api.get_anchor(request.anchor_id)
        if result.status == "not_found":
            result.status = "unavailable"
        return self._result(request, result)

    def get_evidence_sources(self, request: GetEvidenceSourcesRequest) -> EvidenceToolResponse:
        response = self._result(request, self._api.get_sources(request.reference))
        if not any(m.citations for m in response.matches):
            response.reasons = sorted(set([*response.reasons, "source_unavailable"]))
            if response.status == "found":
                response.status = "unavailable"
        return response

    def get_metric_evidence_lineage(
        self, request: GetMetricEvidenceLineageRequest
    ) -> EvidenceToolResponse:
        financial = self._financial.get_financial_metric(
            GetFinancialMetricRequest(
                metric_id=request.metric_id,
                document_id=request.document_id,
                snapshot_id=request.snapshot_id,
            )
        )
        response = EvidenceToolResponse(
            request=request,
            status=financial.status,
            reasons=financial.reasons,
            snapshot_candidates=financial.snapshot_candidates,
            reporting_scopes=financial.reporting_scopes,
            caveats=financial.caveats,
            metric_matches=financial.matches,
        )
        if financial.matches:
            result = self._api.get_lineage(request.metric_id)
            response.status, response.reasons = result.status, result.reasons
            response.matches = result.matches
            response.caveats.append("computed_result_is_separate_execution_artifact")
        return self._finish(response)
