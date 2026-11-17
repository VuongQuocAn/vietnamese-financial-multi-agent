"""Bounded source context via existing search; never manufactures financial operands."""

from collections import Counter

from ..evidence.json_catalog import json_fact_bound
from ..evidence.search import SearchDocumentEvidenceRequest, normalize_search
from .evidence_retrieval import EvidenceRetrievalTools


def lookup_json_source_context(catalog, manifest, query):
    tools = EvidenceRetrievalTools.from_composition(
        manifest,
        catalog,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    # Token fallback reuses FTS ranking; no model call, accounting rule or Gold input.
    stop = set(
        "tra so lieu nam bao cao tai chinh theo cua va tu cho trong voi dung tinh ket qua ve la nhung cac".split()
    )
    terms = list(
        dict.fromkeys(
            t
            for t in normalize_search(query).split()
            if len(t) >= 3 and not t.isdigit() and t not in stop
        )
    )[:16]
    counts, matches, events = Counter(), {}, []
    try:
        for term in terms:
            request = SearchDocumentEvidenceRequest(
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
                snapshot_id=manifest.financial_snapshot.snapshot_id,
                query=term,
                top_k=2,
                context_radius=0,
            )
            response = tools.search_document_evidence(request)
            events.append(
                dict(
                    request=request.model_dump(mode="json"),
                    status=response.status,
                    references=[
                        m.evidence.reference.model_dump(mode="json") for m in response.matches
                    ],
                )
            )
            for hit in response.matches:
                key = hit.evidence.reference.model_dump_json()
                counts[key] += 1
                # Merge exact cell projections returned for different query terms.
                if key in matches:
                    hit.cells = list(
                        {c.source_pointer: c for c in [*matches[key].cells, *hit.cells]}.values()
                    )
                matches[key] = hit
    finally:
        tools.close_search()
    contexts = []
    for key, _ in counts.most_common(3):
        hit = matches[key]
        record = hit.evidence.record
        facts = [
            f
            for f in catalog.facts
            if f.source_metadata.get("table_id") == getattr(record, "original_table_id", None)
            and f.document_id == record.document_id
            and f.snapshot_id == record.snapshot_id
        ]
        cells = [c.model_dump(mode="json") for c in hit.cells][:40]
        contexts.append(
            dict(
                handle=f"D{len(contexts) + 1}",
                reference=hit.evidence.reference.model_dump(mode="json"),
                source_page=hit.source_page,
                pdf_page=None,
                source_refs=[s.model_dump(mode="json") for s in record.sources],
                snippet=hit.snippet[:1800],
                snippet_truncated=len(hit.snippet) > 1800,
                columns=record.source_metadata.get("original_table", {}).get("columns", []),
                cells=cells,
                cells_truncated=len(hit.cells) > 40,
                caveats=hit.limitations,
                diagnostics=dict(
                    imported_facts=len(facts),
                    mapped_facts=sum(f.canonical_item_id is not None for f in facts),
                    eligible_facts=sum(json_fact_bound(catalog, f) for f in facts),
                    structural_issues=getattr(record, "structural_issues", []),
                ),
                financial_fact_verified=False,
            )
        )
    return dict(
        contexts=contexts,
        tool_calls=events,
        authority="source_context_only; D handles are not numeric evidence_ids; missing mapping/unit/period stays unavailable",
    )
