"""Synthetic source-preserving invariants M3-03, không phải PDF accuracy."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    DocumentClassification,
    DocumentUnderstandingResult,
    UnderstoodCell,
    UnderstoodTable,
    UnderstoodTextRegion,
)
from vietnamese_financial_multi_agent.document_processing.contracts.unified_document import (
    ComponentQuality,
    UnifiedPage,
    UnifiedRegion,
    UnifiedTable,
)
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFactRepository,
    DocumentEvidenceRepository,
    EvidenceConflict,
    TableEvidence,
    TextEvidence,
    associate_fact,
    evidence_from_persisted_result,
    evidence_from_understanding,
    evidence_from_unified_page,
)

from .test_evidence_contracts import fact

RAW_TEXT = "Doanh thu thuần — năm 2025\nĐơn vị: đồng; (chưa xác minh).  "


def result_fixture():
    f = fact(document="doc", snapshot="attempt")
    page = f.sources[0].reference.anchor.page.model_dump(mode="json")
    cell = dict(text="1.234,00", row=2, column=3, reading="observed")
    return dict(
        document_id="doc",
        attempt_id="attempt",
        records=[
            dict(
                source=dict(page=page),
                response=dict(
                    request_id="synthetic-request",
                    output=dict(
                        raw_text="JSON envelope is not document text",
                        payload=dict(
                            statement_type=None,
                            context=[RAW_TEXT],
                            limitations=["partial"],
                            tables=[
                                dict(
                                    rows=4,
                                    columns=4,
                                    label_column=0,
                                    code_column=1,
                                    headers=[
                                        dict(text="Năm trước", row=0, column=3, reading="observed")
                                    ],
                                    cells=[
                                        cell,
                                        dict(text=None, row=None, column=2, reading="unknown"),
                                    ],
                                )
                            ],
                        ),
                    ),
                ),
            )
        ],
    )


def test_persisted_text_structure_and_restart_without_mutating_facts(tmp_path):
    raw = result_fixture()
    before = deepcopy(raw)
    text, table = evidence_from_persisted_result(raw)
    assert text.raw_text == RAW_TEXT and text.structural_role == "context"
    assert text.sources[0].reference.source_pointer == "/context/0"
    assert (
        table.structure.model_dump(mode="json")
        == raw["records"][0]["response"]["output"]["payload"]["tables"][0]
    )
    assert len(table.structure.cells) == 2  # Không lấp 4x4 cells.
    assert table.original_table_id is None
    assert "partial_or_uncertain_cells" in table.structural_issues
    for source in [*text.sources, *table.sources, *table.member_sources]:
        assert source.reference.provenance_level == "page"
        assert source.reference.anchor.cell_id is None
        assert source.reference.anchor.observed_bbox is None
    assert "missing_source_anchor_id" in text.resolution_issues
    canonical = CanonicalFactRepository(tmp_path)
    f = fact()
    canonical.put(f)
    canonical_before = (tmp_path / "canonical-facts.json").read_bytes()
    repo = DocumentEvidenceRepository(tmp_path)
    for evidence in (text, table):
        assert repo.put(evidence) == "stored"
        assert repo.put(evidence) == "idempotent"
        assert DocumentEvidenceRepository(tmp_path).get(evidence.evidence_identity()) == evidence
    assert (tmp_path / "canonical-facts.json").read_bytes() == canonical_before
    assert raw == before


@pytest.mark.parametrize("kind", ["text", "table"])
def test_identity_conflict_quarantine_and_cross_source(tmp_path, kind):
    evidence = next(e for e in evidence_from_persisted_result(result_fixture()) if e.kind == kind)
    repo = DocumentEvidenceRepository(tmp_path)
    variants = [
        evidence,
        evidence.model_copy(update={"document_id": "BBS_2024"}),
        evidence.model_copy(update={"snapshot_id": "attempt-2"}),
    ]
    for e in variants:
        assert repo.put(e) == "stored"
    assert len({e.evidence_identity() for e in variants}) == 3
    assert len(repo.list_by_document("doc")) == 2
    assert repo.list_by_document("doc", "attempt") == [evidence]
    changed = evidence.model_copy(deep=True)
    changed.source_metadata["different"] = True
    with pytest.raises(EvidenceConflict) as error:
        repo.put(changed)
    assert error.value.existing == evidence and error.value.incoming == changed
    assert repo.get(evidence.evidence_identity()) == evidence
    missing = result_fixture()
    missing["document_id"] = " "
    missing["attempt_id"] = None
    e = next(e for e in evidence_from_persisted_result(missing) if e.kind == kind)
    assert e.evidence_identity() is None
    assert "missing_document_id" in e.resolution_issues
    assert repo.put(e) == repo.put(e) == "quarantined"
    assert DocumentEvidenceRepository(tmp_path).list_quarantine() == [e]


def test_explicit_associations_and_unknown_financial_fact_preserved():
    text, table = evidence_from_persisted_result(result_fixture())
    f = fact(document="doc", snapshot="attempt")
    f.canonical_item_id = None
    f.sources = [table.member_sources[1].model_copy(deep=True)]
    f.source_metadata["request_id"] = "synthetic-request"
    before = f.model_dump_json()
    association = associate_fact(f, table)
    assert association is not None
    assert association.fact == f.observation_identity()
    assert association.matching_sources == [table.member_sources[1]]
    assert associate_fact(f, text) is None  # Cùng trang chưa đủ.
    f.sources = [table.sources[0].model_copy(deep=True)]
    f.sources[0].reference.source_pointer = None
    assert associate_fact(f, table) is None
    page_only = table.model_copy(deep=True)
    page_only.sources[0].reference.source_pointer = None
    page_only.member_sources = []
    assert associate_fact(f, page_only) is None
    f.sources = [table.member_sources[1].model_copy(deep=True)]
    assert f.model_dump_json() == before
    for field in ("document_id", "snapshot_id"):
        altered = table.model_copy(update={field: "mismatch"})
        assert associate_fact(f, altered) is None
        altered = table.model_copy(deep=True)
        setattr(altered.member_sources[0], field, "mismatch")
        assert associate_fact(f, altered) is None
    table.source_metadata["request_id"] = "different-request"
    assert associate_fact(f, table) is None


def test_du_anchor_and_partial_table_roundtrip(tmp_path):
    f = fact(document="doc", snapshot="attempt")
    anchor = f.sources[0].reference.anchor.model_copy(deep=True)
    anchor.element_id = "raw-text"
    cell_anchor = anchor.model_copy(update={"element_id": None, "table_id": "t", "cell_id": "c"})
    region = UnderstoodTextRegion(
        id="r", text=RAW_TEXT, anchors=[anchor], status="uncertain", reading_order=2
    )
    table = UnderstoodTable(
        id="t",
        origin="ocr_table",
        anchors=[anchor],
        status="unresolved",
        cells=[
            UnderstoodCell(
                id="c", row=2, col=3, text="-", anchors=[cell_anchor], status="uncertain"
            )
        ],
    )
    du = DocumentUnderstandingResult(
        contract_version="document_understanding_v1",
        raw_page=anchor.page,
        classification=DocumentClassification(label=None, status="unresolved", anchors=[]),
        text_regions=[region],
        tables=[table],
        issues=[],
    )
    before = du.model_dump_json()
    text, wrapped = evidence_from_understanding(du, document_id="doc", snapshot_id="attempt")
    assert text.raw_text == RAW_TEXT
    assert text.sources[0].reference.provenance_level == "element"
    assert wrapped.member_sources[0].reference.provenance_level == "cell"
    assert wrapped.structure == table
    assert "partial_or_unresolved_structure" in wrapped.structural_issues
    repo = DocumentEvidenceRepository(tmp_path)
    for e in (text, wrapped):
        repo.put(e)
        assert DocumentEvidenceRepository(tmp_path).get(e.evidence_identity()) == e
    assert du.model_dump_json() == before
    region.id = " "
    missing = evidence_from_understanding(du, document_id="doc", snapshot_id="attempt")[0]
    assert missing.evidence_identity() is None
    assert repo.put(missing) == "quarantined"


def test_unified_keeps_candidates_without_fabricating_text_or_cells(tmp_path):
    page = fact().sources[0].reference.anchor.page
    region = UnifiedRegion(
        source_pointer="/text/0",
        text="LLM candidate",
        status="unresolved",
        quality=ComponentQuality(),
        source_component={"text": RAW_TEXT},
        bbox=[1, 2, 3, 4],
        row=0,
        column=1,
    )
    table = UnifiedTable(
        source_pointer="/tables/0",
        status="unresolved",
        layout_accepted=False,
        cells=[region],
        source_component={"candidate": "kept"},
        issues=["partial"],
    )
    unified = UnifiedPage(
        identity=page,
        source_type="pdf",
        source_sha256="synthetic",
        source_references={},
        schema_valid=True,
        text_regions=[region],
        tables=[table],
        classification={},
        issues=[],
        processing_history=[],
    )
    text, wrapped = evidence_from_unified_page(unified, document_id="doc", snapshot_id="attempt")
    assert text.raw_text == RAW_TEXT
    assert wrapped.structure == table and len(wrapped.structure.cells) == 1
    assert text.sources[0].reference.anchor.observed_bbox is None
    assert text.sources[0].reference.provenance_level == "page"
    repo = DocumentEvidenceRepository(tmp_path)
    for e in (text, wrapped):
        repo.put(e)
        assert DocumentEvidenceRepository(tmp_path).get(e.evidence_identity()) == e
    region.source_component = {"candidate_text": "unverified"}
    unresolved = evidence_from_unified_page(unified, document_id=None, snapshot_id=None)[0]
    assert unresolved.raw_text is None and "missing_exact_text" in unresolved.resolution_issues


def test_no_payload_does_not_fabricate_evidence():
    assert evidence_from_persisted_result({"items": [{"page": 1}]}) == []
    r = result_fixture()
    del r["records"][0]["response"]["output"]["payload"]
    with pytest.raises(ValueError, match="payload unavailable"):
        evidence_from_persisted_result(r)


def test_text_and_table_identity_namespaces_differ():
    text = TextEvidence(
        document_id="doc", snapshot_id="attempt", local_evidence_id="same", raw_text=None
    )
    table = TableEvidence(document_id="doc", snapshot_id="attempt", local_evidence_id="same")
    assert text.evidence_identity() != table.evidence_identity()
