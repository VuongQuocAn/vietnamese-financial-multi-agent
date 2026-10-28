"""Local PDF/PNG ingestion; source bytes stay read-only, M1 adapter is partial."""

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from .contracts.document_understanding import (
    DocumentUnderstandingResult,
    RawPageIdentity,
)
from .contracts.document_understanding_validation import validate_understanding_quality
from .vision_ocr import VerifiedPageImage, extract_structured

MODEL = "gemini-3.5-flash-lite"


@dataclass(frozen=True)
class IngestionPage:
    image: VerifiedPageImage
    source: dict


def load_pages(path: Path, *, symbol: str, year: str, pages: list[int], dpi=200):
    """One-based PDF pages, or caller-supplied original page number for one PNG.

    Hash the same PDF bytes used by PDFium. Do not rotate, deskew or infer identity.
    Source locators use content hashes; private filesystem paths need not leave host.
    """
    if (
        not symbol.strip()
        or not year.strip()
        or not pages
        or any(type(p) is not int or p < 1 for p in pages)
        or len(set(pages)) != len(pages)
        or type(dpi) is not int
        or dpi < 72
    ):
        raise ValueError("invalid_input_selection")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    kind = path.suffix.lower()
    if kind == ".pdf" and content.startswith(b"%PDF-"):
        with pdfium.PdfDocument(content) as doc:
            count = len(doc)
            if max(pages) > count:
                raise ValueError("page_out_of_range")
            result = []
            for number in pages:
                page = doc[number - 1]
                try:
                    bitmap = page.render(scale=dpi / 72)
                    try:
                        with bitmap.to_pil() as decoded:
                            buffer = io.BytesIO()
                            decoded.save(buffer, format="PNG")
                            result.append(
                                _page(
                                    buffer.getvalue(),
                                    digest,
                                    "pdf",
                                    count,
                                    number,
                                    symbol,
                                    year,
                                    dpi,
                                )
                            )
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            return result
    if kind == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n") and len(pages) == 1:
        return [_page(content, digest, "png", 1, pages[0], symbol, year, None)]
    raise ValueError("unsupported_or_mismatched_source")


def _page(content, digest, kind, count, number, symbol, year, dpi):
    with Image.open(io.BytesIO(content), formats=["PNG"]) as decoded:
        decoded.load()
        width, height = decoded.size
    image_hash = hashlib.sha256(content).hexdigest()
    document_id = f"sha256:{digest}"
    identity = RawPageIdentity(
        symbol=symbol,
        year=year,
        page=number,
        image=f"sha256:{image_hash}",
        source_ref=document_id,
    )
    source = dict(
        document_id=document_id,
        source_sha256=digest,
        pdf_sha256=digest if kind == "pdf" else None,
        source_type=kind,
        page_count=count,
        page_number=number,
        image_sha256=image_hash,
        width=width,
        height=height,
        render_dpi=dpi,
        renderer="pypdfium2" if kind == "pdf" else None,
    )
    return IngestionPage(VerifiedPageImage(identity, image_hash, width, height, content), source)


def adapt_to_m1(components, image):
    """Map retained text to DU v1; no invented raw OCR IDs or element geometry.

    Region IDs are intermediate JSON pointers, NOT OCR IDs. Page-level anchors
    deliberately carry no element bbox. DU quality reports missing region provenance;
    this is schema compatibility only, not a resolved raw-loader substitute.
    Table membership/unknown positions remain exclusively in the intermediate JSON.
    """
    regions, pointers = [], []
    for i, item in enumerate(components.get("text_elements", [])):
        pointers.append((f"/text_elements/{i}", item))
    for i, table in enumerate(components.get("tables", [])):
        for j, cell in enumerate(table["cells"]):
            pointers.append((f"/tables/{i}/cells/{j}", cell))
    for pointer, item in pointers:
        if item["status"] == "accepted":
            regions.append(
                dict(
                    id=pointer,
                    text=item["text"],
                    status="unresolved",
                    anchors=[
                        dict(page=image.identity.model_dump(mode="json"), status="unresolved")
                    ],
                )
            )
    result = DocumentUnderstandingResult.model_validate(
        dict(
            contract_version="document_understanding_v1",
            raw_page=image.identity.model_dump(mode="json"),
            classification=dict(label=None, status="unresolved", anchors=[]),
            text_regions=regions,
            tables=[],
            issues=[
                dict(
                    code="partial_gemini_adapter",
                    path=[],
                    message=(
                        "Text-only schema mapping. No verified region geometry or raw OCR references; "
                        "tables retained in intermediate output. Region IDs are JSON pointers."
                    ),
                )
            ],
        )
    )
    issues = validate_understanding_quality(result)
    return dict(
        level="partial_text_schema" if regions else "unavailable",
        M1_compatible=bool(regions),
        raw_loader_compatible=False,
        quality_accepted=bool(regions) and not issues,
        understanding=result.export_result(),
        quality_issues=[i.model_dump(mode="json") for i in issues],
    )


def ingest_page(service, page, *, credential_ref):
    record = extract_structured(
        service,
        page.image,
        credential_ref=credential_ref,
        model=MODEL,
        component_mode=True,
    )
    components = record.get("output")
    response = record.get("response", {})
    record["provenance"] = page.source
    record["assessment"] = dict(
        schema_valid=(response.get("output") or {}).get("validation_status") == "schema_valid",
        structure_accepted=components is not None and components["status"] == "accepted",
        content_correct=None,
        text_status="unavailable"
        if components is None
        else (
            "accepted"
            if components.get("summary", {}).get("text_accepted", 0)
            or components.get("summary", {}).get("cell_text_accepted", 0)
            else "unresolved"
        ),
        layout_status="unavailable"
        if components is None
        else (
            "accepted"
            if components.get("tables")
            and all(t["status"] == "accepted" for t in components["tables"])
            else "unresolved"
        ),
        geometry_status="unresolved",
    )
    record["m1"] = adapt_to_m1(components or {}, page.image)
    record["assessment"]["M1_compatible"] = record["m1"]["M1_compatible"]
    return record
