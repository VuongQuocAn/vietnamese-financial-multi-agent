"""Projection FTS5/BM25 rebuildable từ composition; không verified claims."""

import re
import sqlite3
import unicodedata
from collections import defaultdict
from itertools import zip_longest
from time import perf_counter
from typing import Literal

from pydantic import Field, model_serializer

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


def rank_search_candidates(candidates, queries, *, top_k=20):
    """Interleave BM25 hits for question/objective/goals without dropping a query."""
    handles = list(candidates)
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE VIRTUAL TABLE candidates USING fts5(body)")
        db.executemany(
            "INSERT INTO candidates(body) VALUES (?)",
            [(normalize_search(candidates[handle]),) for handle in handles],
        )
        rankings = []
        for query in dict.fromkeys(normalize_search(q) for q in queries):
            terms = list(dict.fromkeys(query.split()))
            if terms:
                expression = " OR ".join('"' + term + '"' for term in terms)
                rankings.append(
                    [
                        handles[rowid - 1]
                        for (rowid,) in db.execute(
                            "SELECT rowid FROM candidates WHERE candidates MATCH ? "
                            "ORDER BY bm25(candidates), rowid LIMIT ?",
                            (expression, top_k),
                        )
                    ]
                )
        return list(
            dict.fromkeys(
                handle for group in zip_longest(*rankings) for handle in group if handle is not None
            )
        )
    finally:
        db.close()


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
    context_radius: int = Field(default=3, ge=0, le=12)


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
    pdf_page: int | None
    source_page: int | None = None
    snippet: str
    cells: list[SearchCell] = Field(default_factory=list)
    neighbors: list[SearchNeighbor] = Field(default_factory=list)
    matched_terms: list[str]
    ranking_reasons: list[str]
    limitations: list[str]

    @model_serializer(mode="wrap")
    def preserve_pdf_payload(self, handler):
        value = handler(self)
        if self.source_page is None:
            value.pop("source_page", None)
        return value


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


def text_pointer_position(pointer):
    """Return the source array and index for an original text selector."""
    fields = (pointer or "").split("/")
    match fields:
        case ["", "text_elements" | "context" as family, index]:
            pass
        case ["", "blocks" as family, index, "text"]:
            pass
        case _:
            return None
    if index.isascii() and index.isdecimal():
        return family, int(index)
    return None


def text_source_order(record):
    page, pointer = _location(record)
    position = text_pointer_position(pointer)
    if position is None:
        return None
    # Source boundaries include original request, page image and pointer family.
    return (
        record.document_id,
        record.snapshot_id,
        page.model_dump_json(),
        record.source_metadata.get("request_id"),
        position[0],
    ), position[1]


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
                    or (
                        getattr(cell, "id", "")
                        if getattr(cell, "id", "").startswith(pointer + "/")
                        else None
                    )
                    or f"{pointer}/{field}/{i}",
                    row=cell.row,
                    column=getattr(cell, "column", getattr(cell, "col", None)),
                    text=cell.text,
                )
            )
    return output


class EvidenceSearchIndex:
    """Một unit/record; ranking context radius=3, returned neighbors bounded 0–12.

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
            if record.kind == "text" and (order := text_source_order(record)):
                groups[order[0]][order[1]] = record
        self._groups = groups
        for record in self.catalog.evidence:
            neighbors = []
            if record.kind == "text":
                body = record.raw_text or ""
                if order := text_source_order(record):
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
                title = record.source_metadata.get("original_table", {}).get("title") or ""
                body = "\n".join([title, *(c.text for c in cells if c.text)])
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
                labels = [record.source_metadata.get("original_table", {}).get("title") or ""]
                labels.extend(c.text or "" for c in cells)
                phrase = any(f" {query} " in f" {normalize_search(label)} " for label in labels)
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
            if (
                record.kind == "text"
                and request.context_radius != 3
                and (order := text_source_order(record))
            ):
                neighbors = []
                group, number = order
                for step in (-1, 1):
                    for distance in range(1, request.context_radius + 1):
                        adjacent = self._groups[group].get(number + step * distance)
                        if adjacent is None:
                            break
                        neighbors.append((number + step * distance, adjacent))
                neighbors.sort(key=lambda x: x[0])
            context = [
                SearchNeighbor(
                    order=order,
                    evidence=self.catalog.api.get_evidence(n.evidence_identity()).matches[0],
                )
                for order, n in neighbors
            ]
            # A table hit is one source unit. Matching a header must retain its
            # data rows and original cell pointers for the Specialist's selection.
            selected_cells = cells
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
                    pdf_page=None
                    if record.source_metadata.get("source_kind") == "refined_json"
                    else _location(record)[0].page,
                    source_page=_location(record)[0].page
                    if record.source_metadata.get("source_kind") == "refined_json"
                    else None,
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
