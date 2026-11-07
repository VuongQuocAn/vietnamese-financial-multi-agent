"""EXT-01 engineering controls; synthetic fixtures are not research evaluation."""

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import (
    ingest_page,
    load_pages,
)
from vietnamese_financial_multi_agent.evidence import DocumentEvidenceRepository, TextEvidence
from vietnamese_financial_multi_agent.evidence.document_repository import EvidenceConflict


def planner():
    path = Path(__file__).parents[2] / "scripts/complete_document_evidence.py"
    spec = importlib.util.spec_from_file_location("ext_coverage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discovery_and_partial_cache_never_count_as_full_extraction():
    module = planner()
    discovery = dict(
        response=dict(
            status="success",
            finish_reason="stop",
            output=dict(payload=dict(description="Full prose", statement_type="B09")),
        )
    )
    assert module.native_payload(discovery) is None
    native = deepcopy(discovery)
    native["response"]["output"]["payload"] = dict(
        disposition="assessed",
        text_elements=[dict(text="Printed paragraph", reading="observed")],
        tables=[],
    )
    assert module.extraction_complete(native)
    native["response"]["finish_reason"] = "length"
    assert not module.extraction_complete(native)
    native["response"]["finish_reason"] = "stop"
    native["response"]["output"]["payload"]["text_elements"][0]["reading"] = "unknown"
    assert not module.extraction_complete(native)
    native["response"]["output"]["payload"]["text_elements"][0]["reading"] = "observed"
    native["response"]["output"]["payload"]["tables"] = [
        dict(rows=1, columns=1, cells=[dict(text="printed", reading="observed", row=0, column=1)])
    ]
    assert not module.extraction_complete(native)


def test_target_order_and_historical_scope_are_bounded():
    module = planner()
    assert module.target_pages("BBS_2025", 24)[:3] == [4, 7, 8]
    assert module.target_pages("BBS_2022", 26) == [11, 18]
    assert module.target_pages("BBS_2024", 26) == [21, 24]
    assert 6 in module.target_pages("BBS_2025", 24)
    assert 6 in module.target_pages("BCC_2025", 30)
    assert 10 in module.target_pages("BCC_2024", 41)
    for label, total in [("BBS_2025", 24), ("BCC_2025", 30), ("BCC_2024", 41)]:
        pages = module.target_pages(label, total)
        assert len(set(pages)) == len(pages)
        assert min(pages) >= 1 and max(pages) <= total


def test_full_document_prompt_and_original_page_identity(tmp_path):
    path = tmp_path / "page.png"
    Image.new("RGB", (120, 200), "white").save(path)
    page = load_pages(path, symbol="SYNTHETIC", year="2025", pages=[4])[0]
    requests = []

    def generate(request, **kwargs):
        requests.append(request)
        return SimpleNamespace(response=None)

    service = SimpleNamespace(generate=generate)
    record = ingest_page(service, page, credential_ref="synthetic", document_mode=True)
    assert "ENTIRE page" in requests[0].messages[0].content
    assert "never identify" in requests[0].messages[0].content
    assert record["source"]["page"]["page"] == 4
    assert record["provenance"] == page.source
    assert record["output"] is None


def test_page_batch_conflict_is_atomic_and_reload_is_exact(tmp_path):
    repository = DocumentEvidenceRepository(tmp_path)
    first = TextEvidence(
        document_id="synthetic",
        snapshot_id="original",
        local_evidence_id="text/0",
        raw_text="original",
    )
    second = first.model_copy(update={"local_evidence_id": "text/1", "raw_text": "second"})
    assert repository.put_many([first, second, first]) == ["stored", "stored", "idempotent"]
    before = (tmp_path / "document-evidence.json").read_bytes()
    with pytest.raises(EvidenceConflict):
        repository.put_many(
            [
                second.model_copy(update={"local_evidence_id": "text/2"}),
                first.model_copy(update={"raw_text": "conflict"}),
            ]
        )
    assert (tmp_path / "document-evidence.json").read_bytes() == before
    assert DocumentEvidenceRepository(tmp_path).list_by_document("synthetic") == [first, second]
