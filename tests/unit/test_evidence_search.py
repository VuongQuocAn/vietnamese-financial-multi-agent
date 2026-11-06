"""Engineering controls; real PDF probes chạy riêng, không phải financial gold."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.evidence.composition import EvidencePin, payload_sha256
from vietnamese_financial_multi_agent.evidence.document_evidence import TableEvidence
from vietnamese_financial_multi_agent.evidence.search import (
    EvidenceSearchIndex,
    SearchDocumentEvidenceRequest,
    normalize_search,
)
from vietnamese_financial_multi_agent.tools import EvidenceRetrievalTools

from .test_evidence_composition import sample


def setup_index(tmp_path):
    manifest, repo, row = sample(tmp_path)
    row.raw_text = "Kế toán trưởng"
    rows = [row]
    for i, text in enumerate(["Giám đốc", "Phạm Thị Thanh Hòa", "Dương Minh Tuấn"]):
        neighbor = row.model_copy(deep=True)
        neighbor.local_evidence_id = f"text/{i + 1}"
        neighbor.raw_text = text
        neighbor.sources[0].reference.source_pointer = f"/text_elements/{i + 1}"
        rows.append(neighbor)
    manifest.sources[0].evidence = []
    for record in rows:
        repo.put(record)
        manifest.sources[0].evidence.append(
            EvidencePin(
                identity=record.evidence_identity(),
                payload_sha256=payload_sha256(record.model_dump(mode="json")),
            )
        )
    return manifest, repo


def request(**kwargs):
    return SearchDocumentEvidenceRequest(
        **(dict(document_id="logical", composition_id="approved", query="kế toán trưởng") | kwargs)
    )


def test_normalization_context_rebuild_and_unchanged_exact_tools(tmp_path):
    manifest, repo = setup_index(tmp_path)
    before = deepcopy(repo.list_by_document("doc", "native"))
    tools = EvidenceRetrievalTools.from_composition(
        manifest, repo, document_id="logical", composition_id="approved"
    )
    result = tools.search_document_evidence(request())
    assert result.status == "found"
    assert result.matches[0].snippet == "Kế toán trưởng"
    assert len(result.matches[0].neighbors) == 3
    assert result.matches[0].evidence.citations[0].pdf_page == 7
    for query in ["ke toan truong", "KẾ TOÁN TRƯỞNG", "kế toán trưởng"]:
        assert tools.search_document_evidence(request(query=query)).matches == result.matches
    tools.close_search()
    rebuilt = EvidenceRetrievalTools.from_composition(
        manifest, repo, document_id="logical", composition_id="approved"
    )
    assert rebuilt.search_document_evidence(request()).matches == result.matches
    assert repo.list_by_document("doc", "native") == before
    assert normalize_search("ĐỐC—đốc") == "doc doc"
    rebuilt.close_search()


@pytest.mark.parametrize(
    "changes",
    [
        {"document_id": "other"},
        {"composition_id": "other"},
        {"snapshot_id": "legacy"},
        {"source_page": 8},
        {"query": ""},
        {"query": "?! --"},
        {"query": "quantum astrophysics"},
        {"query": "ý kiến kiểm toán ngoại trừ"},
        {"query": "kế toán lượng tử thiên văn"},
        {"evidence_type": "table"},
        {"query": "trưởng kế toán", "exact_phrase": True},
    ],
)
def test_negative_selection_query_and_coverage(tmp_path, changes):
    m, repo = setup_index(tmp_path)
    index = EvidenceSearchIndex(m, repo, document_id="logical", composition_id="approved")
    assert index.search(request(**changes)).status == "not_found"
    index.close()


def test_different_source_not_neighbor_and_duplicate_pin_rejected(tmp_path):
    m, repo = setup_index(tmp_path)
    # New request is a separate source even at same PDF/page/reading index.
    rows = repo.list_by_document("doc", "native")
    separate = rows[-1].model_copy(deep=True)
    separate.local_evidence_id = "other-request"
    separate.source_metadata["request_id"] = "different"
    separate.sources[0].reference.source_pointer = "/text_elements/4"
    repo.put(separate)
    m.sources[0].evidence.append(
        EvidencePin(
            identity=separate.evidence_identity(),
            payload_sha256=payload_sha256(separate.model_dump(mode="json")),
        )
    )
    index = EvidenceSearchIndex(m, repo, document_id="logical", composition_id="approved")
    assert len(index.search(request()).matches[0].neighbors) == 3
    index.close()
    m.sources[0].evidence.append(m.sources[0].evidence[0])
    with pytest.raises(ValueError, match="duplicate_composition_evidence"):
        EvidenceSearchIndex(m, repo, document_id="logical", composition_id="approved")
    with pytest.raises(ValidationError):
        request(top_k=21)


def test_table_repeated_terms_keep_cells_and_no_cross_cell_phrase(tmp_path):
    m, repo, row = sample(tmp_path)
    table = TableEvidence(
        document_id=row.document_id,
        snapshot_id=row.snapshot_id,
        local_evidence_id="table/0",
        sources=row.sources,
        structure=dict(
            rows=3,
            columns=2,
            label_column=0,
            code_column=1,
            headers=[],
            cells=[
                dict(text="Tiền gửi ngân hàng", row=1, column=0, reading="observed"),
                dict(text="100", row=1, column=1, reading="observed"),
                dict(text="Tiền mặt", row=2, column=0, reading="observed"),
                dict(text="200", row=2, column=1, reading="observed"),
            ],
        ),
    )
    table.sources[0].reference.source_pointer = "/tables/0"
    repo.put(table)
    m.sources[0].evidence = [
        EvidencePin(
            identity=table.evidence_identity(),
            payload_sha256=payload_sha256(table.model_dump(mode="json")),
        )
    ]
    index = EvidenceSearchIndex(m, repo, document_id="logical", composition_id="approved")
    result = index.search(request(query="Tiền"))
    assert len(result.matches) == 1
    assert len(result.matches[0].cells) == 4
    assert result.matches[0].cells[0].source_pointer == "/tables/0/cells/0"
    assert index.search(request(query="hàng 100", exact_phrase=True)).status == "not_found"
    index.close()
