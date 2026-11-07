"""Document branch of M5. Keep the search and candidate trace source-bound."""

from ..evidence.composition import payload_sha256
from ..evidence.document_claim_support import (
    consecutive,
    document_citations,
    document_projection,
    source_assertion,
)
from ..evidence.search import SearchDocumentEvidenceRequest, normalize_search
from .document_qa_contracts import DocumentCandidate, DocumentSearchOperation


def document_operations(requirements, manifest, snapshot_id):
    return [
        DocumentSearchOperation(
            operation_id=f"document-search-{i}",
            requirement=r,
            request=SearchDocumentEvidenceRequest(
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
                snapshot_id=snapshot_id,
                query=r.query,
                evidence_type="table" if r.kind == "table_labels" else "text",
                top_k=5,
            ),
        )
        for i, r in enumerate(requirements, 1)
    ]


def document_candidates(bundle, company_id, manifest):
    requirement = bundle.operation.requirement
    candidates = []
    unresolved = None
    for match in bundle.result.matches:
        if not match.evidence.citations:
            continue
        groups = [[match.evidence]]
        if requirement.target == "nhan vien quan ly chu chot":
            neighbors = {n.order: n.evidence for n in match.neighbors}
            # Only the forward neighbors following the primary in the saved source.
            pointer = match.evidence.citations[0].source.reference.source_pointer or ""
            if pointer.rsplit("/", 1)[-1].isdigit():
                order = int(pointer.rsplit("/", 1)[-1])
                for length in (1, 2):
                    if all(order + i in neighbors for i in range(1, length + 1)):
                        groups.append(
                            [match.evidence, *(neighbors[order + i] for i in range(1, length + 1))]
                        )
        for group in groups:
            if (
                any(
                    e.record.source_metadata.get("request_id")
                    != group[0].record.source_metadata.get("request_id")
                    for e in group
                )
                or any(
                    (e.record.document_id, e.record.snapshot_id)
                    != (match.document_id, match.snapshot_id)
                    for e in group
                )
                or not consecutive([e.citations for e in group])
            ):
                continue
            source = [document_projection(e.record) for e in group]
            assertion = source_assertion(requirement, source)
            if assertion is None and (
                requirement.kind != "entity_role"
                or normalize_search(source[0].get("text", ""))
                not in {requirement.target, requirement.target + " bieu"}
            ):
                continue
            quotes, content, person = assertion or (
                [source[0]["text"]],
                f"Tài liệu có nhãn «{source[0]['text']}».",
                None,
            )
            fields = dict(
                claim_type=requirement.kind,
                requirement=requirement,
                content=content,
                person=person,
                company_id=company_id,
                document_id=manifest.logical_document_id,
                source_document_id=match.document_id,
                snapshot_id=match.snapshot_id,
                composition_id=manifest.composition_id,
                composition_sha256=payload_sha256(manifest.model_dump(mode="json")),
                references=[e.reference for e in group],
                citations=[c for e in group for c in document_citations(e.record, e.citations)],
                quotations=quotes,
                caveats=sorted({issue for e in group for issue in e.issues}),
            )
            draft = DocumentCandidate(candidate_id="draft", **fields)
            candidate = draft.model_copy(
                update={
                    "candidate_id": "document:"
                    + payload_sha256(draft.model_dump(mode="json", exclude={"candidate_id"}))
                }
            )
            if assertion is not None:
                if candidate not in candidates:
                    candidates.append(candidate)
            elif unresolved is None:
                unresolved = candidate
    return candidates or ([unresolved] if unresolved else [])
