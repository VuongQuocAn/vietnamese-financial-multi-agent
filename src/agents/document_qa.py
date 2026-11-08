"""Document branch of M5. Keep the search and candidate trace source-bound."""

import re
from types import SimpleNamespace

from ..evidence.composition import payload_sha256
from ..evidence.document_claim_support import (
    complete_declared_list,
    consecutive,
    declared_list_count,
    document_citations,
    document_projection,
    is_list_item,
    source_assertion,
)
from ..evidence.search import SearchDocumentEvidenceRequest, normalize_search
from .document_qa_contracts import DocumentCandidate, DocumentSearchOperation


def _heading(text):
    text = text.strip()
    if is_list_item(text):
        return False
    return bool(text) and (
        bool(re.match(r"^\d+(?:\.\d+)*\.?\s+\S", text))
        or len(text) <= 180
        and not text.endswith((".", ";"))
    )


def _excerpt_groups(bundle):
    """Join only retrieved contiguous selectors, stopping before the next heading.

    The bounded pool includes original neighbors; it never crosses page, extraction,
    snapshot or pointer family. Every selector is still individually replayed by M6.
    """
    pools, primaries = {}, []
    for match in bundle.result.matches:
        for evidence in [match.evidence, *(n.evidence for n in match.neighbors)]:
            if not evidence.citations:
                continue
            ref = evidence.citations[0].source.reference
            pointer = re.fullmatch(r"(/(?:text_elements|context)/)(\d+)", ref.source_pointer or "")
            if pointer is None:
                continue
            key = (
                evidence.record.document_id,
                evidence.record.snapshot_id,
                evidence.record.source_metadata.get("request_id"),
                ref.anchor.page.model_dump_json(),
                pointer[1],
            )
            order = int(pointer[2])
            pools.setdefault(key, {})[order] = evidence
            if evidence is match.evidence:
                primaries.append((key, order))
    query = normalize_search(bundle.operation.requirement.query)
    heading_query = re.sub(r"^ghi nhan ", "", query)
    groups, seen = [], set()
    for key, order in primaries:
        pool = pools[key]
        start = order
        while start - 1 in pool and not _heading(pool[start].record.raw_text or ""):
            start -= 1
        first = pool[start].record.raw_text or ""
        if _heading(first) and f" {heading_query} " not in f" {normalize_search(first)} ":
            continue
        group = []
        for i in range(start, start + 12):
            if i not in pool or (i > start and _heading(pool[i].record.raw_text or "")):
                break
            group.append(pool[i])
            texts = [e.record.raw_text or "" for e in group]
            declared = declared_list_count(texts)
            if declared is not None and sum(is_list_item(t) for t in texts) == declared:
                break
        signature = tuple(e.reference.model_dump_json() for e in group)
        if (
            signature
            and signature not in seen
            and complete_declared_list([e.record.raw_text or "" for e in group])
        ):
            seen.add(signature)
            groups.append(group)
    return groups


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
                context_radius=12 if r.kind == "source_excerpt" else 3,
            ),
        )
        for i, r in enumerate(requirements, 1)
    ]


def document_candidates(bundle, company_id, manifest):
    requirement = bundle.operation.requirement
    candidates = []
    unresolved = None
    excerpts = _excerpt_groups(bundle) if requirement.kind == "source_excerpt" else None
    matches = bundle.result.matches
    if excerpts is not None:
        # The existing candidate/verification path below remains identical for
        # section-shaped excerpts; no shorter accepted prefix can hide a defect.
        matches = [(group[0], group) for group in excerpts]
    for match in matches:
        excerpt = None
        if isinstance(match, tuple):
            evidence, excerpt = match
            match = SimpleNamespace(
                evidence=evidence,
                document_id=evidence.record.document_id,
                snapshot_id=evidence.record.snapshot_id,
            )
        if not match.evidence.citations:
            continue
        groups = [excerpt] if excerpt is not None else [[match.evidence]]
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
    if requirement.kind == "source_excerpt":

        def references(candidate):
            return {r.model_dump_json() for r in candidate.references}

        # Prefer the complete contiguous excerpt over its own shorter prefixes.
        return [
            c
            for c in candidates
            if not any(references(c) < references(other) for other in candidates)
        ][:3]
    return candidates or ([unresolved] if unresolved else [])
