"""Projection FTS5/BM25 rebuildable từ composition; không verified claims."""

import re
import sqlite3
import unicodedata
from collections import defaultdict
from time import perf_counter
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from .composition import load_composition
from .contracts import Identity
from .document_evidence import EvidenceIdentity
from .retrieval import RetrievalMatch


def normalize_search(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return " ".join(
        re.findall(r"[^\W_]+", "".join(c for c in text if not unicodedata.combining(c)))
    )


class SearchDocumentEvidenceRequest(FinancialModel):
    tool: Literal["search_document_evidence"] = "search_document_evidence"
    document_id: Identity
    composition_id: Identity
    query: str = Field(max_length=2000)
    snapshot_id: Identity | None = None
    source_page: int | None = Field(default=None, ge=1)
    evidence_type: Literal["text", "table", "both"] = "both"
    section_hint: str | None = Field(default=None, max_length=200)
    exact_phrase: bool = False
    top_k: int = Field(default=5, ge=1, le=20)


class SearchCell(FinancialModel):
    source_pointer: str
    row: int | None
    column: int | None
    text: str | None


class SearchNeighbor(FinancialModel):
    evidence: RetrievalMatch
    order: int


class DocumentSearchMatch(FinancialModel):
    rank: int
    relevance_score: float
    evidence: RetrievalMatch
    evidence_ids: list[EvidenceIdentity]
    document_id: str
    snapshot_id: str
    pdf_page: int
    snippet: str
    cells: list[SearchCell] = Field(default_factory=list)
    neighbors: list[SearchNeighbor] = Field(default_factory=list)
    matched_terms: list[str]
    ranking_reasons: list[str]
    limitations: list[str]


class DocumentSearchResponse(FinancialModel):
    request: SearchDocumentEvidenceRequest
    status: Literal["found", "not_found", "unavailable"]
    matches: list[DocumentSearchMatch] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(
        default_factory=lambda: [
            "relevance_is_not_claim_confidence",
            "neighbor_proximity_is_not_semantic_support",
        ]
    )
    financial_fact_verified: Literal[False] = False


def _location(record):
    source = record.sources[0].reference
    return source.anchor.page, source.source_pointer or ""


def _order(record):
    page, pointer = _location(record)
    match = re.fullmatch(r"(/text_elements/|/context/)(\d+)", pointer)
    if not match:
        return None
    # Source boundaries include original request, page image and pointer family.
    return (
        record.document_id,
        record.snapshot_id,
        page.model_dump_json(),
        record.source_metadata.get("request_id"),
        match[1],
    ), int(match[2])


def _cells(record):
    if record.structure is None:
        return []
    _, pointer = _location(record)
    output = []
    for field in ("headers", "cells"):
        for i, cell in enumerate(getattr(record.structure, field, [])):
            output.append(
                SearchCell(
                    source_pointer=getattr(cell, "source_pointer", None)
                    or f"{pointer}/{field}/{i}",
                    row=cell.row,
                    column=cell.column,
                    text=cell.text,
                )
            )
    return output


class EvidenceSearchIndex:
    """Một unit/record; context chỉ từ indices liên tiếp cùng source, radius=3.

    Constructor luôn chạy loader pin toàn bộ payload; không nhận catalog tùy ý.
    FTS index chỉ chứa normalized projection trong memory, không persist corpus.
    """

    def __init__(self, manifest, repository, *, document_id, composition_id):
        started = perf_counter()
        self.catalog = load_composition(
            manifest, repository, document_id=document_id, composition_id=composition_id
        )
        self.document_id, self.composition_id = document_id, composition_id
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute("CREATE VIRTUAL TABLE units USING fts5(body, context)")
        self._units = []
        groups = defaultdict(dict)
        for record in self.catalog.evidence:
            if record.kind == "text" and (order := _order(record)):
                groups[order[0]][order[1]] = record
        for record in self.catalog.evidence:
            neighbors = []
            if record.kind == "text":
                body = record.raw_text or ""
                if order := _order(record):
                    group, number = order
                    for step in (-1, 1):
                        for distance in range(1, 4):
                            adjacent = groups[group].get(number + step * distance)
                            if adjacent is None:
                                break
                            neighbors.append((number + step * distance, adjacent))
                    neighbors.sort(key=lambda x: x[0])
                cells = []
            else:
                cells = _cells(record)
                body = "\n".join(c.text for c in cells if c.text)
            context = "\n".join(n.raw_text or "" for _, n in neighbors)
            self._units.append((record, body, cells, neighbors))
            self._db.execute(
                "INSERT INTO units(body, context) VALUES (?, ?)",
                (normalize_search(body), normalize_search(context)),
            )
        self._db.commit()
        self.build_ms = (perf_counter() - started) * 1000

    @property
    def unit_count(self):
        return len(self._units)

    def close(self):
        self._db.close()

    def search(self, request: SearchDocumentEvidenceRequest) -> DocumentSearchResponse:
        response = DocumentSearchResponse(request=request, status="not_found")
        if (request.document_id, request.composition_id) != (self.document_id, self.composition_id):
            response.reasons = ["composition_selection_mismatch"]
            return response
        query = normalize_search(request.query)
        if not query:
            response.reasons = ["empty_search_query"]
            return response
        # Các biến thể nhỏ từ real probes; không tên người hoặc đáp án hardcoded.
        if not request.exact_phrase:
            query = re.sub(r"^(tim thong tin ve|cho biet|thuyet minh ve) ", "", query)
            query = re.sub(r" gi$", "", query)
            query = query.replace("nguoi lap bieu", "nguoi lap")
        terms = list(dict.fromkeys(query.split()))
        expression = (
            '"' + query + '"'
            if request.exact_phrase
            else " OR ".join('"' + term + '"' for term in terms)
        )
        ranked = []
        for rowid, bm25 in self._db.execute(
            "SELECT rowid, bm25(units, 1.0, 0.25) FROM units WHERE units MATCH ?", (expression,)
        ):
            record, body, cells, neighbors = self._units[rowid - 1]
            page, _ = _location(record)
            if request.snapshot_id is not None and record.snapshot_id != request.snapshot_id:
                continue
            if request.source_page is not None and page.page != request.source_page:
                continue
            if request.evidence_type != "both" and record.kind != request.evidence_type:
                continue
            normalized = normalize_search(body)
            phrase = f" {query} " in f" {normalized} "
            if record.kind == "table":
                # Phrase không được tạo bằng cách nối hai cells không liên quan.
                phrase = any(f" {query} " in f" {normalize_search(c.text or '')} " for c in cells)
            matched = [t for t in terms if t in normalized.split()]
            # Context supplies accompanying regions, never standalone unrelated matches.
            if len(matched) / len(terms) < 0.6 or (request.exact_phrase and not phrase):
                continue
            hint = bool(
                request.section_hint
                and normalize_search(request.section_hint)
                in normalize_search(
                    body
                    + " "
                    + (getattr(record, "structural_role", None) or "")
                    + " "
                    + " ".join(n.raw_text or "" for _, n in neighbors)
                )
            )
            ranked.append(
                (
                    (
                        not phrase,
                        -len(matched) / len(terms),
                        -int(hint),
                        bm25,
                        record.evidence_identity().model_dump_json(),
                    ),
                    rowid,
                    -bm25,
                    matched,
                    phrase,
                    hint,
                )
            )
        ranked.sort(key=lambda x: x[0])
        for _, rowid, score, terms, phrase, hint in ranked[: request.top_k]:
            record, body, cells, neighbors = self._units[rowid - 1]
            primary = self.catalog.api.get_evidence(record.evidence_identity()).matches[0]
            context = [
                SearchNeighbor(
                    order=order,
                    evidence=self.catalog.api.get_evidence(n.evidence_identity()).matches[0],
                )
                for order, n in neighbors
            ]
            selected_cells = [
                c for c in cells if any(t in normalize_search(c.text or "").split() for t in terms)
            ]
            rows = {c.row for c in selected_cells if c.row is not None}
            selected_cells = [c for c in cells if c in selected_cells or c.row in rows]
            snippet = (
                body if record.kind == "text" else "\n".join(c.text or "" for c in selected_cells)
            )
            response.matches.append(
                DocumentSearchMatch(
                    rank=len(response.matches) + 1,
                    relevance_score=score,
                    evidence=primary,
                    evidence_ids=[
                        record.evidence_identity(),
                        *[n.evidence.reference.evidence for n in context],
                    ],
                    document_id=record.document_id,
                    snapshot_id=record.snapshot_id,
                    pdf_page=_location(record)[0].page,
                    snippet=snippet,
                    cells=selected_cells,
                    neighbors=context,
                    matched_terms=terms,
                    ranking_reasons=[
                        "bm25",
                        "direct_term_coverage",
                        *(["exact_phrase"] if phrase else []),
                        *(["section_hint"] if hint else []),
                    ],
                    limitations=sorted(
                        set(
                            [
                                *primary.issues,
                                *record.resolution_issues,
                                *getattr(record, "structural_issues", []),
                                *record.source_metadata.get("limitations", []),
                                *[s for c in primary.citations for s in c.limitations],
                            ]
                        )
                    ),
                )
            )
        response.status = "found" if response.matches else "not_found"
        if not response.matches:
            response.reasons = ["no_matching_selected_evidence_coverage_not_guaranteed"]
        return response
