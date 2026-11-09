"""Synthetic geometry/ingest controls; these are not real financial OCR evidence."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import load_pages
from vietnamese_financial_multi_agent.document_processing.region_geometry import (
    bind_selectors,
    crop_region,
    raw_ocr_geometry,
    resolve_region,
)
from vietnamese_financial_multi_agent.document_processing.understanding_pipeline import (
    UnderstandingOptions,
    run_document_understanding,
)
from vietnamese_financial_multi_agent.evidence.document_adapter import evidence_from_unified_page

from .test_gemini_ingestion import run


def text_pdf(path, rotation=0):
    stream = b"BT /F1 12 Tf 40 140 Td (Loan matures 25 March 2021.) Tj 0 -45 Td (Collateral heading) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Rotate {rotation} /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    position = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{position}\n%%EOF\n".encode()
    )
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("dpi,rotation", [(144, 0), (216, 90)])
def test_pdf_text_layer_automatic_mapping_scale_rotation_and_crop(tmp_path, dpi, rotation):
    page = load_pages(
        text_pdf(tmp_path / "text.pdf", rotation), symbol="NEW", year="2026", pages=[1], dpi=dpi
    )[0]
    text = "Loan matures 25 March 2021."
    geometry = bind_selectors(page.geometry, [("/text_elements/0", text, None)])
    resolved = resolve_region(page.image, geometry, "/text_elements/0", text)
    assert resolved["status"] == "resolved", resolved
    crop = crop_region(page.image, resolved)
    assert crop.parent_sha256 == page.image.sha256 and crop.sha256 != page.image.sha256
    assert crop.width < page.image.width and crop.height < page.image.height
    (tmp_path / f"crop-{dpi}-{rotation}.png").write_bytes(crop.content)
    stale = deepcopy(geometry)
    stale["image_sha256"] = "wrong"
    assert resolve_region(page.image, stale, "/text_elements/0", text)["status"] == "unresolved"
    assert (
        resolve_region(page.image, geometry, "/text_elements/0", text + " changed")["status"]
        == "unresolved"
    )


def test_raw_binding_requires_image_frame_and_layout_not_just_bbox(tmp_path):
    page = load_pages(text_pdf(tmp_path / "raw.pdf"), symbol="NEW", year="2026", pages=[1])[0]
    raw = dict(
        page=dict(width=page.image.width, height=page.image.height),
        elements=[dict(id="line-1", type="text", text="target", bbox=[10, 10, 150, 30])],
    )
    geometry = bind_selectors(
        raw_ocr_geometry(raw, page.image), [("/elements/0", "target", ["line-1"])]
    )
    assert (
        resolve_region(page.image, geometry, "/elements/0", "target")["reason"]
        == "raw_image_hash_or_coordinate_frame_unverified"
    )
    raw["page"].update(
        image_sha256=page.image.sha256,
        coordinate_space="original_image_pixels",
        symbol="NEW",
        year="2026",
        page=1,
    )
    raw["elements"].append(dict(id="table-1", type="table", bbox=[20, 12, 100, 25]))
    geometry = bind_selectors(
        raw_ocr_geometry(raw, page.image), [("/elements/0", "target", ["line-1"])]
    )
    assert (
        resolve_region(page.image, geometry, "/elements/0", "target")["reason"]
        == "crop_contains_unselected_region"
    )
    raw["elements"] = [
        dict(id="a", type="text", text="first", bbox=[10, 10, 150, 30]),
        dict(id="b", type="text", text="heading", bbox=[10, 120, 150, 140]),
    ]
    geometry = bind_selectors(
        raw_ocr_geometry(raw, page.image), [("/text_elements/0", "first heading", None)]
    )
    assert (
        resolve_region(page.image, geometry, "/text_elements/0", "first heading")["reason"]
        == "paragraph_layout_discontinuous"
    )


def test_new_pdf_ingest_persists_selector_geometry_through_evidence(tmp_path):
    path = text_pdf(tmp_path / "ingest.pdf")
    page = load_pages(path, symbol="NEW", year="2026", pages=[1])[0]
    payload = dict(
        disposition="assessed",
        limitations=[],
        text_elements=[dict(text="Loan matures 25 March 2021.", reading="observed", bbox=None)],
        tables=[],
    )
    record, _ = run(page, payload)
    assert record["geometry"]["selectors"]["/text_elements/0"]["status"] == "mapped"
    unified = run_document_understanding(
        path,
        UnderstandingOptions(symbol="NEW", year="2026", pages=(1,), persisted_results={1: record}),
    ).pages[0]
    row = evidence_from_unified_page(
        unified, document_id=page.image.identity.source_ref, snapshot_id="new-ingestion"
    )[0]
    geometry = row.source_metadata["source_references"]["region_geometry"]
    assert (
        resolve_region(page.image, geometry, row.sources[0].reference.source_pointer, row.raw_text)[
            "status"
        ]
        == "resolved"
    )
