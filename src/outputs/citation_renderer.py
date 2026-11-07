"""Deterministic citation projection from validated M7 outputs, with no I/O.

The typed original is the authority for this presentation gate. Upstream ledger
admission/QA/Writer validation remains the caller's responsibility; it is never
replaced by the locator's resolution status.
"""

import hashlib
import json

from pydantic import ValidationError

from ..agents.fusion_contracts import is_mixed
from .citation_contracts import (
    CitationBinding,
    CitationLocator,
    CitationReference,
    RenderedCitationOutput,
)
from .qa_composer import _answer_text, _citations, _unique
from .qa_contracts import QAValidationResult, VietnameseQAResponse
from .report_writer_contracts import GroundedFinancialReport

SourceOutput = VietnameseQAResponse | GroundedFinancialReport


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _identity(citation):
    # source_key already scopes every observed selector by document/snapshot.
    key = citation.source.source_key()
    return _digest(
        key if key is not None else citation.model_dump(mode="json", exclude={"limitations"})
    )


def _locator(c):
    source, r = c.source, c.source.reference
    if not c.document_id or not c.snapshot_id:
        raise ValueError("missing_source_identity")
    if (c.document_id, c.snapshot_id) != (source.document_id, source.snapshot_id):
        raise ValueError("source_identity_conflict")
    fields = dict(
        document_id=c.document_id,
        snapshot_id=c.snapshot_id,
        pdf_page=c.pdf_page,
        provenance_level=c.provenance_level,
    )
    if r is None:
        if c.pdf_page is not None or c.provenance_level is not None:
            raise ValueError("location_without_source_reference")
        return CitationLocator(**fields, resolution_status="location_unavailable")
    a = r.anchor
    if c.pdf_page != a.page.page or c.provenance_level != r.provenance_level:
        raise ValueError("source_location_conflict")
    if r.provenance_level == "cell" and not (a.table_id and a.cell_id):
        raise ValueError("unsupported_cell_provenance")
    if r.provenance_level == "element" and not (a.element_id or a.table_id or a.line_id):
        raise ValueError("unsupported_element_provenance")
    return CitationLocator(
        **fields,
        source_ref=a.page.source_ref,
        source_pointer=r.source_pointer,
        image_reference=a.page.image,
        element_id=a.element_id,
        table_id=a.table_id,
        cell_id=a.cell_id,
        line_id=a.line_id,
        observed_bbox=a.observed_bbox,
        resolution_status="resolved"
        if a.status == "resolved" and c.anchor_id and a.page.image.strip()
        else "unresolved",
    )


def _report_text(source, suffixes):
    return (
        "# "
        + source.report_title
        + "\n\n"
        + "\n\n".join(
            f"## {s.order}. {s.title_vi}\n\n"
            + "\n\n".join(p.text_vi + suffixes.get(p.paragraph_id, "") for p in s.paragraphs)
            for s in source.sections
        )
    )


def _source_parts(source):
    # Reparse even model_copy/model_construct inputs, which can bypass validation.
    if not isinstance(source, (VietnameseQAResponse, GroundedFinancialReport)):
        raise ValueError("unsupported_source_output")
    source = type(source).model_validate_json(source.model_dump_json())
    if not source.validation_result.valid or source.validation_result.errors:
        raise ValueError("source_not_validated")
    if isinstance(source, VietnameseQAResponse):
        if source.answer_vi != _answer_text(source):
            raise ValueError("source_presentation_mismatch")
        segments = source.grounded_segments
        if (
            len(
                {
                    (
                        s.context.company_id,
                        s.context.document_id if s.context.period else None,
                        s.context.snapshot_id if s.context.period else None,
                    )
                    for s in segments
                }
            )
            > 1
        ):
            financial = {
                (s.context.company_id, s.context.document_id, s.context.snapshot_id)
                for s in segments
                if s.context.period
            }
            companies = {s.context.company_id for s in segments}
            if not is_mixed(source.question) or len(financial) > 1 or len(companies) > 1:
                raise ValueError("mixed_qa_contexts")
        parts = [
            (
                s.segment_id,
                s.verified_claim_ids,
                s.citations,
                [s.context],
                [],
                s.caveats,
                s.limitations,
            )
            for s in segments
        ]
    else:
        if source.sections and source.body_vi != _report_text(source, {}):
            raise ValueError("source_presentation_mismatch")
        paragraph_ids = [p.paragraph_id for s in source.sections for p in s.paragraphs]
        if len(set(paragraph_ids)) != len(paragraph_ids):
            raise ValueError("duplicate_output_segment_id")
        parts = []
        for section in source.sections:
            if {c.model_dump_json() for c in section.citations} != {
                c.model_dump_json() for p in section.paragraphs for c in p.citations
            }:
                raise ValueError("section_citation_projection_mismatch")
            for p in section.paragraphs:
                if p.verified_claim_ids or p.citations:
                    parts.append(
                        (
                            p.paragraph_id,
                            p.verified_claim_ids,
                            p.citations,
                            [ctx.claim_context for ctx in p.context],
                            p.source_slot_ids,
                            p.caveats,
                            p.limitations,
                        )
                    )
                elif (
                    p.source_slot_ids
                    or p.context
                    or p.paragraph_type in {"grounded_analysis", "verified_interpretation"}
                ):
                    raise ValueError("missing_paragraph_sources")
        if any(
            (ctx.document_id, ctx.snapshot_id)
            != (source.scope.document_id, source.scope.snapshot_id)
            for _, _, _, contexts, *_ in parts
            for ctx in contexts
        ):
            raise ValueError("report_scope_conflict")
    if len({p[0] for p in parts}) != len(parts):
        raise ValueError("duplicate_output_segment_id")
    if {c.model_dump_json() for c in source.citations} != {
        c.model_dump_json() for _, _, citations, *_ in parts for c in citations
    }:
        raise ValueError("source_citation_projection_mismatch")
    if set(source.used_verified_claim_ids) != {k for _, ids, *_ in parts for k in ids}:
        raise ValueError("source_claim_projection_mismatch")
    grounded_statuses = (
        {"answered", "partial"}
        if isinstance(source, VietnameseQAResponse)
        else {"generated", "partial"}
    )
    if bool(parts) != (source.status in grounded_statuses):
        raise ValueError("source_status_coverage_mismatch")
    for _, ids, citations, contexts, *_ in parts:
        if not ids or not citations or not contexts:
            raise ValueError("missing_required_source_binding")
        pairs = {(ctx.document_id, ctx.snapshot_id) for ctx in contexts}
        if len(pairs) != 1 or any((c.document_id, c.snapshot_id) not in pairs for c in citations):
            raise ValueError("citation_context_conflict")
    return source, parts


def _reference_text(ref):
    loc = ref.source_locator
    location = f"Trang PDF {ref.pdf_page}" if ref.pdf_page is not None else "Chưa có vị trí PDF"
    selectors = []
    if ref.provenance_level in {"element", "cell"}:
        selectors += [
            f"{label} {getattr(loc, field)}"
            for field, label in (
                ("element_id", "phần tử"),
                ("table_id", "bảng"),
                ("line_id", "dòng"),
            )
            if getattr(loc, field) is not None
        ]
    if ref.provenance_level == "cell" and loc.cell_id:
        selectors.append(f"ô {loc.cell_id}")
    if selectors:
        location += ", " + ", ".join(selectors)
    text = (
        f"{ref.display_label} Tài liệu {ref.document_id} — Snapshot {ref.snapshot_id} — {location}."
    )
    if ref.limitations:
        text += " Giới hạn nguồn: " + "; ".join(ref.limitations)
    return text


def _project(original):
    source, parts = _source_parts(original)
    references, bindings, registry, anchors, suffixes = [], [], {}, {}, {}
    for sid, claims, citations, contexts, slots, _caveats, _limitations in parts:
        selected = []
        for c in citations:
            loc = _locator(c)
            identity = _identity(c)
            if c.anchor_id:
                if c.anchor_id in anchors and anchors[c.anchor_id] != identity:
                    raise ValueError("anchor_identity_conflict")
                anchors[c.anchor_id] = identity
            if identity not in registry:
                limits = list(c.limitations)
                if c.provenance_level == "page":
                    limits = _unique(
                        limits + ["Vị trí chứng cứ hiện chỉ được xác định ở cấp trang."]
                    )
                if loc.resolution_status != "resolved":
                    limits = _unique(limits + ["Vị trí nguồn chưa được phân giải đầy đủ."])
                number = len(references) + 1
                ref = CitationReference(
                    citation_id="citation:" + identity,
                    display_number=number,
                    display_label=f"[{number}]",
                    document_id=c.document_id,
                    snapshot_id=c.snapshot_id,
                    pdf_page=c.pdf_page,
                    provenance_level=c.provenance_level,
                    anchor_id=c.anchor_id,
                    source_locator=loc,
                    source_citations=[c],
                    limitations=limits,
                    bound_verified_claim_ids=list(claims),
                    bound_output_segment_ids=[sid],
                )
                registry[identity] = ref
                references.append(ref)
            else:
                ref = registry[identity]
                if ref.source_locator != loc:
                    raise ValueError("exact_source_metadata_conflict")
                ref.source_citations = _citations(ref.source_citations + [c])
                ref.limitations = _unique(ref.limitations + c.limitations)
                ref.bound_verified_claim_ids = _unique(ref.bound_verified_claim_ids + claims)
                ref.bound_output_segment_ids = _unique(ref.bound_output_segment_ids + [sid])
            if ref.citation_id not in [r.citation_id for r in selected]:
                selected.append(ref)
        suffixes[sid] = " " + "".join(r.display_label for r in selected)
        bindings.append(
            CitationBinding(
                output_segment_id=sid,
                verified_claim_ids=claims,
                citation_ids=[r.citation_id for r in selected],
                display_numbers=[r.display_number for r in selected],
                source_slot_ids=slots,
                contexts=contexts,
            )
        )
    if isinstance(source, VietnameseQAResponse):
        view = source.model_copy(deep=True)
        for s in view.grounded_segments:
            s.content += suffixes[s.segment_id]
        text, mode = _answer_text(view), "qa"
    else:
        text = _report_text(source, suffixes) if source.sections else source.body_vi
        mode = "report"
    annotations = [source]
    if isinstance(source, GroundedFinancialReport):
        annotations += [s for s in source.sections]
        annotations += [p for s in source.sections for p in s.paragraphs]
    else:
        annotations += source.grounded_segments
    caveats = _unique([v for item in annotations for v in item.caveats])
    limits = _unique(
        [v for item in annotations for v in item.limitations]
        + [v for r in references for v in r.limitations]
    )
    # Upstream reports may keep some limitations only as metadata. Present them
    # explicitly too, without rewriting the original text or deleting duplicates.
    if caveats:
        text += "\n\nLưu ý nguồn: " + "; ".join(caveats)
    if limits:
        text += "\n\nGiới hạn nguồn: " + "; ".join(limits)
    if references:
        text += "\n\n## Nguồn tham chiếu\n\n" + "\n\n".join(map(_reference_text, references))
    return RenderedCitationOutput(
        source_output_type=mode,
        source_fingerprint=_digest(source.model_dump(mode="json")),
        status="location_limited"
        if any(r.source_locator.resolution_status != "resolved" for r in references)
        else "rendered",
        original_status=source.status,
        rendered_text=text,
        references=references,
        citation_bindings=bindings,
        caveats=caveats,
        limitations=limits,
        validation_result=QAValidationResult(valid=True),
    )


def validate_rendered_citations(output: RenderedCitationOutput, source: SourceOutput):
    """Compare the complete deterministic projection against the typed original.

    This validates identity, bindings, locators and exact presentation together;
    regex marker counts cannot establish attribution or preserve financial prose.
    """
    try:
        actual = RenderedCitationOutput.model_validate_json(output.model_dump_json())
        expected = _project(source)
    except (ValueError, ValidationError, TypeError) as error:
        return QAValidationResult(valid=False, errors=[str(error)])
    errors = [
        "citation_output_mismatch:" + key
        for key in type(expected).model_fields
        if getattr(actual, key) != getattr(expected, key)
    ]
    return QAValidationResult(valid=not errors, errors=errors)


class CitationRenderer:
    def render_qa(self, source: VietnameseQAResponse) -> RenderedCitationOutput:
        if not isinstance(source, VietnameseQAResponse):
            raise ValueError("qa_source_required")
        return _project(source)

    def render_report(self, source: GroundedFinancialReport) -> RenderedCitationOutput:
        if not isinstance(source, GroundedFinancialReport):
            raise ValueError("report_source_required")
        return _project(source)
