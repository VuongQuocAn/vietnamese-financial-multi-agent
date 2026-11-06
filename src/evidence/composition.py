"""Composition nguồn đã kiểm tra; giữ identities/citations và M4 gates hiện có."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..document_processing.gemini_ingestion import load_pages
from ..document_processing.vision_ocr import image_source
from .document_evidence import EvidenceIdentity
from .snapshots import SnapshotCatalog, SnapshotDescriptor


def payload_sha256(value):
    """Fingerprint payload typed; độc lập thứ tự keys, không đổi text/cells."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


class PageBinding(FinancialModel):
    page: int = Field(ge=1)
    image_sha256: str
    source_ref: str
    method: Literal["pdf_sha256_and_exact_render"] = "pdf_sha256_and_exact_render"


class EvidencePin(FinancialModel):
    identity: EvidenceIdentity
    payload_sha256: str


class CompositionSource(FinancialModel):
    descriptor: SnapshotDescriptor
    original_source: str
    artifact_sha256: str
    status: Literal["verified", "quarantine"]
    reasons: list[str] = Field(default_factory=list)
    pages: list[PageBinding] = Field(default_factory=list)
    unverified_pages: list[int] = Field(default_factory=list)
    evidence: list[EvidencePin] = Field(default_factory=list)


class EvidenceComposition(FinancialModel):
    version: Literal["evidence_composition_v1"] = "evidence_composition_v1"
    composition_id: str
    logical_document_id: str
    financial_snapshot: SnapshotDescriptor
    sources: list[CompositionSource]


def verify_saved_pages(pdf: Path, records: list[dict]):
    """Hash cùng PDF bytes đã render, so source/image/page/dimensions đầy đủ.

    Không dùng tên file, symbol/year hoặc text similarity để chứng minh binding.
    Caller giữ các lỗi ở quarantine; hàm này không gọi OCR/Gateway.
    """
    bindings = []
    for record in records:
        source, provenance = record.get("source", {}), record.get("provenance", {})
        page = source.get("page", {})
        if not provenance.get("pdf_sha256") or not provenance.get("image_sha256"):
            raise ValueError("missing_source_fingerprint")
        if provenance.get("renderer") != "pypdfium2":
            raise ValueError("unsupported_binding_renderer")
        dpi = provenance.get("render_dpi")
        if type(dpi) is not int:
            raise ValueError("missing_render_dpi")
        rendered = load_pages(
            pdf, symbol=page["symbol"], year=page["year"], pages=[page["page"]], dpi=dpi
        )[0]
        if rendered.source != provenance or image_source(rendered.image) != source:
            raise ValueError("pdf_page_image_binding_mismatch")
        bindings.append(
            PageBinding(
                page=page["page"],
                image_sha256=rendered.image.sha256,
                source_ref=rendered.image.identity.source_ref,
            )
        )
    if len({p.page for p in bindings}) != len(bindings):
        raise ValueError("duplicate_page_binding")
    return bindings


def _check_evidence(record, source):
    descriptor = source.descriptor
    if (record.document_id, record.snapshot_id) != (descriptor.document_id, descriptor.snapshot_id):
        raise ValueError("evidence_snapshot_mismatch")
    pages = {p.page: p for p in source.pages}
    if len(pages) != len(source.pages) or set(pages) & set(source.unverified_pages):
        raise ValueError("conflicting_page_binding")
    anchors = [*record.sources, *getattr(record, "member_sources", [])]
    if not anchors:
        raise ValueError("missing_evidence_source")
    for anchor in anchors:
        if (anchor.document_id, anchor.snapshot_id) != (record.document_id, record.snapshot_id):
            raise ValueError("source_identity_mismatch")
        if anchor.reference is None:
            raise ValueError("missing_source_reference")
        page = anchor.reference.anchor.page
        binding = pages.get(page.page)
        if (
            binding is None
            or (page.image, page.source_ref)
            != ("sha256:" + binding.image_sha256, binding.source_ref)
            or binding.source_ref != "sha256:" + descriptor.pdf_sha256
        ):
            raise ValueError("evidence_page_image_binding_mismatch")


def load_composition(manifest, repository, *, document_id, composition_id):
    """Preflight toàn composition trước hydrate; không latest/partial fallback.

    Manifest là explicit source selection của caller, không financial approval.
    Repository vẫn là DocumentEvidenceRepository duy nhất. Financial facts/graph
    không được copy hoặc ghép vào document catalog này.
    """
    manifest = EvidenceComposition.model_validate(manifest.model_dump(mode="json"))
    if (document_id, composition_id) != (manifest.logical_document_id, manifest.composition_id):
        raise ValueError("composition_selection_mismatch")
    descriptors = {}

    def add(descriptor):
        key = descriptor.document_id, descriptor.snapshot_id
        if key in descriptors and descriptors[key] != descriptor:
            raise ValueError("conflicting_snapshot_descriptor")
        descriptors[key] = descriptor

    add(manifest.financial_snapshot)
    rows, seen = [], set()
    for source in manifest.sources:
        if source.status != "verified":
            continue
        if source.descriptor.pdf_sha256 != manifest.financial_snapshot.pdf_sha256:
            raise ValueError("composition_pdf_mismatch")
        if not source.pages or not source.artifact_sha256:
            raise ValueError("missing_source_fingerprint")
        add(source.descriptor)
        persisted = {
            e.evidence_identity().model_dump_json(): e
            for e in repository.list_by_document(
                source.descriptor.document_id, source.descriptor.snapshot_id
            )
        }
        for pin in source.evidence:
            key = pin.identity.model_dump_json()
            if key in seen:
                raise ValueError("duplicate_composition_evidence")
            seen.add(key)
            record = persisted.get(key)
            if record is None:
                raise ValueError("partial_materialization")
            if payload_sha256(record.model_dump(mode="json")) != pin.payload_sha256:
                raise ValueError("conflicting_evidence_payload")
            _check_evidence(record, source)
            rows.append(record)
    return SnapshotCatalog(list(descriptors.values()), evidence=rows)
