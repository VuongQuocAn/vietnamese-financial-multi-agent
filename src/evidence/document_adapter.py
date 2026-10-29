"""Adapters thuần representation; không replay extraction/normalization/quality."""

from copy import deepcopy

from ..accounting.automated_extraction import ExtractedPage
from ..accounting.contracts import FinancialSourceReference
from ..document_processing.contracts.document_understanding import (
    DocumentUnderstandingResult,
    RawPageIdentity,
    SourceAnchor,
)
from ..document_processing.contracts.unified_document import UnifiedPage
from .contracts import EvidenceAnchor
from .document_evidence import TableEvidence, TextEvidence


def _binding(document_id, snapshot_id, local_id):
    ids = dict(document_id=document_id, snapshot_id=snapshot_id, local_evidence_id=local_id)
    ids = {k: v if v and v.strip() else None for k, v in ids.items()}
    return dict(
        **ids,
        resolution_issues=[f"missing_{k}" for k, v in ids.items() if v is None],
    )


def _source(page, document_id, snapshot_id, pointer, *, anchor=None, level="page"):
    return EvidenceAnchor(
        document_id=document_id if document_id and document_id.strip() else None,
        snapshot_id=snapshot_id if snapshot_id and snapshot_id.strip() else None,
        reference=FinancialSourceReference(
            anchor=(anchor or SourceAnchor(page=page, status="uncertain")).model_copy(deep=True),
            source_pointer=pointer,
            provenance_level=level,
        ),
    )


def _anchor_level(anchor):
    if anchor.table_id and anchor.cell_id:
        return "cell"
    if anchor.element_id or anchor.table_id or anchor.line_id:
        return "element"
    return "page"


def _issues(sources, *, raw_text=True):
    issues = []
    if raw_text is None:
        issues.append("missing_exact_text")
    if not sources:
        issues.append("missing_source_anchor")
    for source in sources:
        r = source.reference
        if r is None:
            issues.append("missing_source_reference")
            continue
        if r.anchor.status != "resolved":
            issues.append("source_reference_uncertain")
        if r.provenance_level == "page":
            issues.append("page_level_provenance")
        if not (r.anchor.element_id or r.anchor.line_id or r.anchor.table_id or r.anchor.cell_id):
            issues.append("missing_source_anchor_id")
    return list(dict.fromkeys(issues))


def evidence_from_understanding(
    result: DocumentUnderstandingResult, *, document_id: str | None, snapshot_id: str | None
) -> list[TextEvidence | TableEvidence]:
    """DU v1 IDs được scope bằng page + loại; giữ toàn bộ region/table metadata."""
    output = []
    for kind, components in (("text", result.text_regions), ("table", result.tables)):
        for component in components:
            local = (
                f"du/page/{result.raw_page.page}/{kind}/{component.id}"
                if component.id.strip()
                else None
            )
            binding = _binding(document_id, snapshot_id, local)
            sources = [
                _source(
                    result.raw_page,
                    document_id,
                    snapshot_id,
                    None,
                    anchor=a,
                    level=_anchor_level(a),
                )
                for a in component.anchors
            ]
            binding["resolution_issues"].extend(_issues(sources))
            metadata = dict(
                component=component.model_dump(mode="json"),
                page=result.raw_page.model_dump(mode="json"),
                document_understanding=result.model_dump(
                    mode="json", exclude={"text_regions", "tables"}
                ),
            )
            if kind == "text":
                output.append(
                    TextEvidence(
                        **binding,
                        raw_text=component.text,
                        sources=sources,
                        source_metadata=metadata,
                    )
                )
            else:
                members = [
                    _source(
                        result.raw_page,
                        document_id,
                        snapshot_id,
                        None,
                        anchor=a,
                        level=_anchor_level(a),
                    )
                    for cell in component.cells
                    for a in cell.anchors
                ]
                output.append(
                    TableEvidence(
                        **binding,
                        original_table_id=component.id or None,
                        structure=component.model_copy(deep=True),
                        sources=sources,
                        member_sources=members,
                        source_metadata=metadata,
                        structural_issues=[i.code for i in component.issues or []]
                        + (
                            ["partial_or_unresolved_structure"]
                            if component.status != "resolved"
                            else []
                        ),
                    )
                )
    return output


def evidence_from_unified_page(
    page: UnifiedPage, *, document_id: str | None, snapshot_id: str | None
) -> list[TextEvidence | TableEvidence]:
    """Giữ structures/reconstruction candidates M1-16, không chọn text thay nguồn."""

    def source(region):
        anchor = SourceAnchor(
            page=page.identity,
            element_id=region.raw_element_id,
            table_id=region.raw_table_id,
            cell_id=region.raw_cell_id,
            status="uncertain",
        )
        # bbox unified có thể là candidate; không quảng bá thành observed_bbox.
        return _source(
            page.identity,
            document_id,
            snapshot_id,
            region.source_pointer,
            anchor=anchor,
            level=region.provenance_level,
        )

    output = []
    for kind, components in (("text", page.text_regions), ("table", page.tables)):
        for component in components:
            local = (
                f"unified/page/{page.identity.page}/{kind}{component.source_pointer}"
                if component.source_pointer.strip()
                else None
            )
            binding = _binding(document_id, snapshot_id, local)
            metadata = dict(
                source_component=deepcopy(component.source_component),
                source_references=deepcopy(page.source_references),
                source_sha256=page.source_sha256,
                page_metadata=page.model_dump(mode="json", exclude={"text_regions", "tables"}),
            )
            if kind == "text":
                sources = [source(component)]
                binding["resolution_issues"].extend(
                    [*component.issues, *_issues(sources, raw_text=component.text)]
                )
                # Nếu M1 chọn corrected/inferred text, chỉ lấy raw text thực sự có.
                raw_text = component.source_component.get("text")
                if not isinstance(raw_text, str):
                    raw_text = None
                    binding["resolution_issues"].append("missing_exact_text")
                metadata["unified_region"] = component.model_dump(mode="json")
                output.append(
                    TextEvidence(
                        **binding, raw_text=raw_text, sources=sources, source_metadata=metadata
                    )
                )
            else:
                anchor = SourceAnchor(
                    page=page.identity, table_id=component.raw_table_id, status="uncertain"
                )
                sources = [
                    _source(
                        page.identity,
                        document_id,
                        snapshot_id,
                        component.source_pointer,
                        anchor=anchor,
                        level="element" if component.raw_table_id else "page",
                    )
                ]
                binding["resolution_issues"].extend(_issues(sources))
                output.append(
                    TableEvidence(
                        **binding,
                        original_table_id=component.raw_table_id,
                        structure=component.model_copy(deep=True),
                        sources=sources,
                        member_sources=[source(c) for c in component.cells],
                        source_metadata=metadata,
                        structural_issues=[*component.issues]
                        + (
                            ["partial_or_unresolved_structure"]
                            if not component.layout_accepted
                            else []
                        ),
                    )
                )
    return output


def evidence_from_persisted_result(result: dict) -> list[TextEvidence | TableEvidence]:
    """W-04 payload context/tables, không dùng response.raw_text hoặc viewer items.

    Local ID là selector scoped record/page, không phải raw anchor ID. Không có
    records thì coverage rỗng tường minh; không tạo quotes từ financial labels.
    """
    output = []
    for index, record in enumerate(result.get("records", [])):
        raw = ((record.get("response") or {}).get("output") or {}).get("payload")
        if raw is None:
            raise ValueError("Source extraction payload unavailable; explicit adapter required")
        payload = ExtractedPage.model_validate(raw)
        page = RawPageIdentity.model_validate(record["source"]["page"])
        doc, snapshot = result.get("document_id"), result.get("attempt_id")
        provenance = record.get("provenance") or {}
        if provenance.get("document_id") and provenance["document_id"] not in {
            doc,
            page.source_ref,
        }:
            raise ValueError("Source document binding mismatch")

        def source(pointer, page=page, doc=doc, snapshot=snapshot):
            return _source(page, doc, snapshot, pointer)

        metadata = deepcopy({k: record[k] for k in ("source", "provenance") if k in record})
        metadata.update(
            request_id=record["response"].get("request_id"),
            limitations=list(payload.limitations),
            record_index=index,
            model=deepcopy(record["response"].get("provenance")),
        )
        for kind, components in (("text", payload.context), ("table", payload.tables)):
            for n, component in enumerate(components):
                pointer = f"/context/{n}" if kind == "text" else f"/tables/{n}"
                binding = _binding(doc, snapshot, f"record/{index}/page/{page.page}{pointer}")
                sources = [source(pointer)]
                binding["resolution_issues"].extend(_issues(sources))
                if kind == "text":
                    output.append(
                        TextEvidence(
                            **binding,
                            raw_text=component,
                            structural_role="context",
                            sources=sources,
                            source_metadata=deepcopy(metadata),
                        )
                    )
                else:
                    issues = list(payload.limitations)
                    if any(
                        c.reading != "observed"
                        or c.row is None
                        or c.column is None
                        or c.text is None
                        for c in [*component.headers, *component.cells]
                    ):
                        issues.append("partial_or_uncertain_cells")
                    issues.append("structure_not_verified")
                    output.append(
                        TableEvidence(
                            **binding,
                            structure=component.model_copy(deep=True),
                            sources=sources,
                            member_sources=[
                                source(f"{pointer}/{field}/{i}")
                                for field in ("headers", "cells")
                                for i in range(len(getattr(component, field)))
                            ],
                            source_metadata=deepcopy(metadata),
                            structural_issues=issues,
                        )
                    )
    return output
