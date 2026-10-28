"""Synthetic integration/consumer checks; no network or financial quality claims."""

import hashlib
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pypdfium2 as pdfium
import pytest
from PIL import Image
from vietnamese_financial_multi_agent.document_processing import understanding_pipeline as pipeline
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    UnifiedDocument,
)
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import load_pages
from vietnamese_financial_multi_agent.document_processing.understanding_pipeline import (
    PersistedOCRInput,
    UnderstandingOptions,
    run_document_understanding,
)

from .test_gemini_ingestion import payload as native_payload
from .test_gemini_ingestion import run
from .test_ocr_loader import sample as sample
from .test_ocr_loader import write
from .test_path_resolver import config as config
from .test_raw_ocr_contracts import element
from .test_raw_ocr_contracts import payload as payload


def existing(sample):
    return run_document_understanding(
        sample.request, UnderstandingOptions(data_config=sample.config)
    )


def replay(page, record, service=None):
    # PNG fixture's original bytes are at tmp_path/synthetic.png.
    return run_document_understanding(
        page_path(page),
        UnderstandingOptions(
            symbol="SYNTHETIC",
            year="2025",
            pages=(17,),
            persisted_results={17: record},
            service=service,
        ),
    )


@pytest.fixture
def page(tmp_path):
    path = tmp_path / "synthetic.png"
    Image.new("RGB", (120, 200), "white").save(path)
    value = load_pages(path, symbol="SYNTHETIC", year="2025", pages=[17])[0]
    return SimpleNamespace(image=value.image, source=value.source, path=path)


def page_path(page):
    return page.path


def test_existing_loader_retains_source_text_table_and_never_calls_ocr(sample, monkeypatch):
    sample.payload["elements"] = [element("text"), element("table")]
    write(sample)
    before = sample.target.read_bytes()
    ocr = Mock(side_effect=AssertionError("no OCR"))
    monkeypatch.setattr(pipeline, "ingest_page", ocr)
    output = existing(sample).pages[0]
    assert output.source_sha256 == hashlib.sha256(before).hexdigest()
    assert output.source_references["raw_provenance"] == sample.payload["provenance"]
    assert output.identity.image == sample.payload["page"]["image"]
    assert (
        output.source_references["mapping"]["reference"]["source_ref"]
        == sample.request.reference.source_ref
    )
    assert output.text_regions[0].text == sample.payload["elements"][0]["text"]
    cell = output.tables[0].cells[0]
    assert (cell.raw_cell_id, cell.raw_table_id, cell.provenance_level) == (
        "cell_1",
        "table_1",
        "cell",
    )
    assert cell.bbox is None and not cell.quality.geometry_verified
    assert cell.source_component["bbox"] == [1, 2, 30, 40]
    assert sample.target.read_bytes() == before
    ocr.assert_not_called()


def test_replay_keeps_100_cells_when_layout_invalid(page):
    data = native_payload()
    template = data["tables"][0]["cells"][0]
    data["tables"][0]["cells"] = [
        dict(template, text=f"Synthetic {i}", row=999) for i in range(100)
    ]
    record, _ = run(page, data)
    service = Mock()
    output = replay(page, record, service).pages[0]
    assert len(output.tables[0].cells) == 100
    assert output.tables[0].status == "unresolved"
    assert all(
        c.quality.text_accepted and not c.quality.layout_accepted for c in output.tables[0].cells
    )
    assert all(
        c.raw_cell_id is None and c.provenance_level == "page" for c in output.tables[0].cells
    )
    assert all(c.row is None and c.bbox is None for c in output.tables[0].cells)
    assert all(not d.executed for d in output.recovery_decisions)
    assert output.recovery_decisions[0].action == "table_reconstruction"
    service.generate.assert_not_called()


def test_schema_text_layout_geometry_and_usage_are_independent(page):
    data = native_payload()
    data["text_elements"][0]["reading"] = "inferred"
    data["tables"][0]["columns"] = "unknown"
    record, _ = run(page, data)
    record["assessment"]["schema_valid"] = True  # Must not trust persisted flags.
    record["output"]["tables"][0]["status"] = "accepted"
    out = replay(page, record).pages[0]
    assert not out.schema_valid
    assert out.text_regions[0].text == "Synthetic title"
    assert not out.text_regions[0].quality.downstream_usable
    cell = out.tables[0].cells[0]
    assert cell.quality.text_accepted and cell.quality.usable_for == ["text_evidence"]
    assert not cell.quality.layout_accepted and not cell.quality.geometry_verified
    assert cell.source_component["layout"]["column"] == 1


def test_replay_rejects_source_identity_hash_or_image_mismatch(page):
    record, _ = run(page, native_payload())
    for key in ("image_sha256", "page_number", "source_sha256"):
        wrong = deepcopy(record)
        wrong["provenance"][key] = "different"
        with pytest.raises(ValueError, match="persisted_source_mismatch"):
            replay(page, wrong)
    wrong = deepcopy(record)
    wrong["source"]["page"]["symbol"] = "OTHER"
    with pytest.raises(ValueError, match="persisted_source_mismatch"):
        replay(page, wrong)


def test_missing_replay_fails_closed_even_with_service(page):
    service = Mock()
    with pytest.raises(ValueError, match="live_ocr_disabled"):
        run_document_understanding(
            page_path(page),
            UnderstandingOptions(
                symbol="SYNTHETIC",
                year="2025",
                pages=(17,),
                service=service,
            ),
        )
    service.generate.assert_not_called()


def test_multipage_pdf_replay_preserves_original_order_and_source(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.pdf"
    with pdfium.PdfDocument.new() as doc:
        for _ in range(3):
            doc.new_page(144, 216).close()
        doc.save(path)
    before = path.read_bytes()
    pages = load_pages(path, symbol="SYNTHETIC", year="2025", pages=[3, 1])
    records = {p.image.identity.page: run(p, native_payload())[0] for p in pages}
    monkeypatch.setattr(pipeline, "ingest_page", Mock(side_effect=AssertionError("no live")))
    out = run_document_understanding(
        path,
        UnderstandingOptions(
            symbol="SYNTHETIC",
            year="2025",
            pages=(3, 1),
            persisted_results=records,
        ),
    )
    assert [p.identity.page for p in out.pages] == [3, 1]
    assert all(p.source_type == "pdf" and p.source_references["page_count"] == 3 for p in out.pages)
    assert path.read_bytes() == before
    replay_dir = tmp_path / "persisted"
    replay_dir.mkdir()
    for p in pages:
        (replay_dir / f"page-{p.image.identity.page}.png").write_bytes(p.image.content)
    manifest = dict(pages=[p.source for p in pages])
    replayed = run_document_understanding(
        PersistedOCRInput(manifest, replay_dir),
        UnderstandingOptions(
            symbol="SYNTHETIC",
            year="2025",
            pages=(3, 1),
            persisted_results=records,
        ),
    )
    assert [p.identity for p in replayed.pages] == [p.identity for p in out.pages]
    assert all("not_rehashed" in p.source_references["integrity_scope"] for p in replayed.pages)
    (replay_dir / "page-3.png").write_bytes(b"invalid PNG")
    with pytest.raises(ValueError, match="mismatched_source"):
        run_document_understanding(
            PersistedOCRInput(manifest, replay_dir),
            UnderstandingOptions(
                symbol="SYNTHETIC",
                year="2025",
                pages=(3, 1),
                persisted_results=records,
            ),
        )


def test_explicit_native_png_uses_ingestion_once_and_replay_never_retries(page, monkeypatch):
    record, _ = run(page, native_payload())
    ingest = Mock(return_value=record)
    monkeypatch.setattr(pipeline, "ingest_page", ingest)
    options = UnderstandingOptions(
        symbol="SYNTHETIC",
        year="2025",
        pages=(17,),
        service=Mock(),
        allow_live_ocr=True,
        credential_ref="synthetic",
    )
    out = run_document_understanding(page_path(page), options)
    assert out.pages[0].source_type == "png"
    assert out.pages[0].identity.page == 17
    assert ingest.call_count == 1
    replay(page, record)
    assert ingest.call_count == 1


def test_failed_record_produces_unavailable_page_without_retry(page, monkeypatch):
    record, _ = run(page, fail=True)
    ingest = Mock(side_effect=AssertionError("no retry"))
    monkeypatch.setattr(pipeline, "ingest_page", ingest)
    out = replay(page, record).pages[0]
    assert not out.schema_valid and not out.tables and not out.text_regions
    assert {i["code"] for i in out.issues} >= {"ocr_output_unavailable"}
    assert out.recovery_decisions[0].action == "human_review"
    ingest.assert_not_called()


def test_existing_classification_reuses_disjoint_evidence_gate(sample):
    sample.payload["elements"] = [
        dict(element("text"), id="code", text="B01", bbox=[0, 0, 40, 10]),
        dict(element("text"), id="title", text="Bảng cân đối kế toán", bbox=[0, 20, 80, 30]),
    ]
    write(sample)
    assert existing(sample).pages[0].classification["label"] == "B01"
    sample.payload["elements"][1]["bbox"] = [0, 0, 40, 10]
    write(sample)
    assert existing(sample).pages[0].classification["status"] == "unresolved"


def test_downstream_consumer_reads_both_branches_without_branch_logic(sample, page):
    sample.payload["elements"] = [element("text"), element("table")]
    write(sample)
    record, _ = run(page, native_payload())
    for output in (existing(sample), replay(page, record)):
        # Consumer chỉ biết contract và purpose; không biết raw OCR hay Gemini.
        parsed = UnifiedDocument.model_validate_json(output.model_dump_json())
        assert parsed.export_result() == output.export_result()
        evidence = [
            (p.identity.source_ref, r.source_pointer, r.text)
            for p in parsed.pages
            for r in [*p.text_regions, *(c for t in p.tables for c in t.cells)]
            if r.quality.downstream_usable and "text_evidence" in r.quality.usable_for
        ]
        assert len(evidence) == 2
        assert all(source and pointer and text for source, pointer, text in evidence)
