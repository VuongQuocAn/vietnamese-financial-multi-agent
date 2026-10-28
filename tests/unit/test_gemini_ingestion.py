"""Synthetic engine checks only; no financial accuracy claims or live calls."""

import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pypdfium2 as pdfium
import pytest
from PIL import Image
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import (
    ingest_page,
    load_pages,
)
from vietnamese_financial_multi_agent.document_processing.vision_ocr import vision_schema_registry

from .test_classification_pilot import sdk_response


@pytest.fixture
def page(tmp_path):
    path = tmp_path / "synthetic.png"
    Image.new("RGB", (120, 200), "white").save(path)
    return load_pages(path, symbol="SYNTHETIC", year="2025", pages=[17])[0]


def run(page, payload=None, *, fail=False):
    client = Mock()
    if fail:
        client.models.generate_content.side_effect = TimeoutError()
    else:
        client.models.generate_content.return_value = sdk_response(payload)
    registry = vision_schema_registry()
    gateway = SharedLLMGateway(
        {"gemini": GeminiAdapter(client, schema_registry=registry)},
        schema_registry=registry,
    )
    service = SimpleNamespace(
        generate=lambda request, **kwargs: SimpleNamespace(response=gateway.generate(request))
    )
    return ingest_page(service, page, credential_ref="synthetic"), client


def payload():
    return dict(
        disposition="assessed",
        limitations=[],
        text_elements=[dict(text="Synthetic title", reading="observed", bbox=None)],
        tables=[
            dict(
                rows=1,
                columns=2,
                cells=[
                    dict(text="(1.234)", reading="observed", bbox=None, row=0, column=1),
                ],
            )
        ],
    )


def test_pdf_render_selected_pages_and_hashes(tmp_path):
    path = tmp_path / "synthetic.pdf"
    with pdfium.PdfDocument.new() as doc:
        for _ in range(3):
            doc.new_page(144, 216).close()
        doc.save(path)
    before = path.read_bytes()
    pages = load_pages(path, symbol="SYNTHETIC", year="2025", pages=[3, 1], dpi=144)
    assert [p.source["page_number"] for p in pages] == [3, 1]
    assert pages[0].source["page_count"] == 3
    assert pages[0].source["pdf_sha256"] == hashlib.sha256(before).hexdigest()
    assert (pages[0].image.width, pages[0].image.height) == (288, 432)
    assert hashlib.sha256(pages[0].image.content).hexdigest() == pages[0].source["image_sha256"]
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="page_out_of_range"):
        load_pages(path, symbol="SYNTHETIC", year="2025", pages=[4])


def test_png_preserves_original_bytes_number_and_dimensions(page):
    assert page.source["page_number"] == 17
    assert page.source["pdf_sha256"] is None
    assert page.source["image_sha256"] == page.source["source_sha256"]
    assert (page.image.width, page.image.height) == (120, 200)


def test_invalid_selection_and_source_fail_before_api(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    for pages in ([], [0], [True], [1, 1]):
        with pytest.raises(ValueError, match="invalid_input_selection"):
            load_pages(path, symbol="SYNTHETIC", year="2025", pages=pages)
    with pytest.raises(ValueError, match="mismatched_source"):
        load_pages(path, symbol="SYNTHETIC", year="2025", pages=[1])


def test_real_inline_bytes_reach_sdk_and_partial_adapter(page):
    record, client = run(page, payload())
    args = client.models.generate_content.call_args.kwargs
    assert args["model"] == "gemini-3.5-flash-lite"
    assert args["contents"][0].parts[1].inline_data.data == page.image.content
    assert record["assessment"]["schema_valid"] is True
    assert record["assessment"]["content_correct"] is None
    assert record["m1"]["M1_compatible"] is True
    assert record["m1"]["raw_loader_compatible"] is False
    assert record["m1"]["quality_accepted"] is False
    view = record["m1"]["understanding"]
    assert view["tables"] == []
    assert view["text_regions"][1]["text"] == "(1.234)"
    assert view["text_regions"][1]["id"] == "/tables/0/cells/0"
    assert all(r["status"] == "unresolved" for r in view["text_regions"])
    assert all(r["anchors"][0].get("observed_bbox") is None for r in view["text_regions"])
    assert record["provenance"] == page.source


def test_unresolved_layout_retains_text_and_cells(page):
    data = payload()
    data["tables"][0]["cells"][0]["row"] = 10
    record, _ = run(page, data)
    assert record["output"]["tables"][0]["status"] == "unresolved"
    assert record["output"]["summary"]["cell_text_accepted"] == 1
    assert record["m1"]["understanding"]["text_regions"][1]["text"] == "(1.234)"
    assert record["assessment"]["structure_accepted"] is False


def test_schema_invalid_components_salvaged_without_promotion(page):
    data = payload()
    data["tables"][0]["columns"] = "unknown"
    record, _ = run(page, data)
    assert record["assessment"]["schema_valid"] is False
    assert record["output"]["summary"]["text_accepted"] == 1
    assert record["output"]["summary"]["cell_layout_accepted"] == 0


def test_unknown_reading_not_mapped_to_accepted_m1_text(page):
    data = payload()
    data["text_elements"][0]["reading"] = "inferred"
    data["tables"][0]["cells"][0]["reading"] = "unknown"
    record, _ = run(page, data)
    assert record["m1"]["M1_compatible"] is False
    assert record["output"]["text_elements"][0]["text"] == "Synthetic title"


def test_provider_failure_preserves_provenance_without_retry(page):
    record, client = run(page, fail=True)
    assert client.models.generate_content.call_count == 1
    assert record["output"] is None
    assert record["m1"]["M1_compatible"] is False
    assert record["assessment"]["text_status"] == "unavailable"
    assert record["provenance"] == page.source
