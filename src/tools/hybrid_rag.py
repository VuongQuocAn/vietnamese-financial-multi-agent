"""Hybrid chunk locators → existing pinned M4 evidence contracts; local only."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.composition import payload_sha256
from ..evidence.document_evidence import EvidenceIdentity
from ..evidence.json_catalog import json_evidence_bound
from ..evidence.search import (
    DocumentSearchMatch,
    DocumentSearchResponse,
    SearchDocumentEvidenceRequest,
    _cells,
)
from .financial_retrieval import (
    FinancialFactMatch,
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)


class SearchHybridEvidenceRequest(FinancialModel):
    document_id: str
    snapshot_id: str
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class HybridEvidenceResponse(FinancialModel):
    request: SearchHybridEvidenceRequest
    status: Literal["found", "not_found"]
    documents: DocumentSearchResponse
    facts: list[FinancialFactMatch] = Field(default_factory=list)
    hits: list[dict] = Field(default_factory=list)
    timing_ms: dict[str, float] = Field(default_factory=dict)
    financial_fact_verified: Literal[False] = False


class HybridRAGTool:
    """Lazy existing index; hydrate against the caller's already loaded catalog."""

    def __init__(self):
        self.projection = Path(
            os.getenv("RAG_PROJECTION_ROOT", "artifacts/evidence/RAG-CHUNK-01/run-02")
        )
        self.index = Path(os.getenv("RAG_INDEX_ROOT", "artifacts/evidence/RAG-HYBRID-01/index-01"))
        self.retrieval = None

    @property
    def available(self):
        return all((p / "manifest.json").is_file() for p in (self.projection, self.index))

    def search(self, request, catalog, composition):
        if self.retrieval is None:
            from .hybrid_retrieval import HybridChunkRetrieval, LocalE5

            self.retrieval = HybridChunkRetrieval(
                self.projection,
                self.index,
                LocalE5(os.getenv("RAG_MODEL_CACHE", "artifacts/models/huggingface")),
            )
        result = self.retrieval.search(
            request.query,
            document_id=request.document_id,
            snapshot_id=request.snapshot_id,
            top_k=request.top_k,
        )
        response = HybridEvidenceResponse(
            request=request,
            status="found" if result["hits"] else "not_found",
            hits=result["hits"],
            timing_ms=result["timing_ms"],
            documents=DocumentSearchResponse(
                request=SearchDocumentEvidenceRequest(
                    document_id=composition.logical_document_id,
                    composition_id=composition.composition_id,
                    snapshot_id=request.snapshot_id,
                    query=request.query,
                    top_k=request.top_k,
                    context_radius=0,
                ),
                status="found" if result["hits"] else "not_found",
                caveats=["hybrid_ranking_is_not_semantic_support", "json_source_not_pdf_verified"],
            ),
        )
        financial = FinancialRetrievalTools(catalog)
        seen = set()
        for hit in result["hits"]:
            for link in hit["evidence_selectors"]:
                identity = EvidenceIdentity.model_validate(link["evidence_ref"])
                matches = catalog.api.get_evidence(identity).matches
                if len(matches) != 1:
                    raise ValueError("hybrid_evidence_not_in_pinned_catalog")
                match = matches[0]
                record = match.record
                if payload_sha256(record.model_dump(mode="json")) != link["payload_sha256"]:
                    raise ValueError("hybrid_evidence_payload_mismatch")
                descriptor = next(
                    d
                    for d in catalog.descriptors
                    if (d.document_id, d.snapshot_id) == (record.document_id, record.snapshot_id)
                )
                if not json_evidence_bound(catalog, descriptor, record):
                    raise ValueError("hybrid_evidence_source_unbound")
                key = identity.model_dump_json()
                if key in seen:
                    continue
                seen.add(key)
                cells = _cells(record) if record.kind == "table" else []
                response.documents.matches.append(
                    DocumentSearchMatch(
                        rank=len(response.documents.matches) + 1,
                        relevance_score=hit["rrf_score"],
                        evidence=match,
                        evidence_ids=[identity],
                        document_id=record.document_id,
                        snapshot_id=record.snapshot_id,
                        pdf_page=None,
                        source_page=hit["source_page"],
                        snippet=record.raw_text
                        if record.kind == "text"
                        else "\n".join(c.text or "" for c in cells),
                        cells=cells,
                        matched_terms=[],
                        ranking_reasons=["hybrid_rrf"],
                        limitations=match.issues,
                    )
                )
            for link in hit["fact_refs"]:
                identity = link["observation"]
                found = financial.get_financial_fact(
                    GetFinancialFactRequest(
                        document_id=request.document_id,
                        snapshot_id=request.snapshot_id,
                        local_observation_id=identity["local_id"],
                    )
                )
                if len(found.matches) != 1:
                    raise ValueError("hybrid_fact_not_in_pinned_catalog")
                fact = found.matches[0]
                if payload_sha256(fact.record.model_dump(mode="json")) != link[
                    "payload_sha256"
                ] and not (
                    fact.json_source_bound
                    and getattr(catalog, "json_import_fact_hashes", {}).get(identity["local_id"])
                    == link["payload_sha256"]
                ):
                    raise ValueError("hybrid_fact_payload_mismatch")
                if fact.record.observation_identity().model_dump_json() not in seen:
                    seen.add(fact.record.observation_identity().model_dump_json())
                    response.facts.append(fact)
        return response

    def close(self):
        if self.retrieval is not None:
            self.retrieval.close()
            self.retrieval = None
