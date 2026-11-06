"""Controls composition; không thay thế đối chiếu PDF thật INT-01a."""

from copy import deepcopy

import pytest
from vietnamese_financial_multi_agent.evidence import DocumentEvidenceRepository, TextEvidence
from vietnamese_financial_multi_agent.evidence.composition import (
    CompositionSource,
    EvidenceComposition,
    EvidencePin,
    PageBinding,
    load_composition,
    payload_sha256,
    verify_saved_pages,
)
from vietnamese_financial_multi_agent.evidence.document_repository import EvidenceConflict
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotDescriptor


def sample(tmp_path):
    descriptor = SnapshotDescriptor(
        document_id="doc", snapshot_id="native", pdf_sha256="a" * 64, origin="original_extraction"
    )
    row = TextEvidence(
        document_id="doc",
        snapshot_id="native",
        local_evidence_id="text/0",
        raw_text="synthetic",
        sources=[
            dict(
                document_id="doc",
                snapshot_id="native",
                reference=dict(
                    anchor=dict(
                        page=dict(
                            symbol="TEST",
                            year="2025",
                            page=7,
                            image="sha256:" + "b" * 64,
                            source_ref="sha256:" + "a" * 64,
                        ),
                        status="uncertain",
                    ),
                    source_pointer="/text_elements/0",
                    provenance_level="page",
                ),
            )
        ],
    )
    source = CompositionSource(
        descriptor=descriptor,
        original_source="cache.json",
        artifact_sha256="c" * 64,
        status="verified",
        pages=[PageBinding(page=7, image_sha256="b" * 64, source_ref="sha256:" + "a" * 64)],
        evidence=[
            EvidencePin(
                identity=row.evidence_identity(),
                payload_sha256=payload_sha256(row.model_dump(mode="json")),
            )
        ],
    )
    manifest = EvidenceComposition(
        composition_id="approved",
        logical_document_id="logical",
        financial_snapshot=descriptor.model_copy(update={"snapshot_id": "financial"}),
        sources=[source],
    )
    repo = DocumentEvidenceRepository(tmp_path)
    return manifest, repo, row


def load(manifest, repo, **kwargs):
    return load_composition(
        manifest,
        repo,
        document_id=kwargs.get("document_id", "logical"),
        composition_id=kwargs.get("composition_id", "approved"),
    )


def test_exact_restart_idempotence_conflict_and_quarantine(tmp_path):
    manifest, repo, row = sample(tmp_path)
    assert repo.put(row) == "stored"
    assert repo.put(row) == "idempotent"
    assert load(manifest, DocumentEvidenceRepository(tmp_path)).evidence == [row]
    with pytest.raises(EvidenceConflict):
        repo.put(row.model_copy(update={"raw_text": "changed"}))
    # Unselected source có identity hoàn chỉnh vẫn không vào approved catalog.
    extra = row.model_copy(update={"snapshot_id": "legacy"})
    repo.put(extra)
    quarantine = manifest.sources[0].model_copy(deep=True)
    quarantine.status = "quarantine"
    quarantine.reasons = ["unverified_legacy_ocr"]
    manifest.sources.append(quarantine)
    assert load(manifest, repo).evidence == [row]
    assert load(manifest, repo).api.get_evidence(extra.evidence_identity()).status == "not_found"


@pytest.mark.parametrize(
    "case",
    [
        "wrong_document",
        "wrong_composition",
        "wrong_snapshot",
        "wrong_page",
        "wrong_image",
        "missing_fingerprint",
        "duplicate",
        "conflicting_payload",
        "partial_materialization",
        "different_pdf",
        "conflicting_descriptor",
    ],
)
def test_fail_closed_before_catalog(tmp_path, case):
    manifest, repo, row = sample(tmp_path)
    kwargs = {}
    if case == "wrong_document":
        kwargs["document_id"] = "other"
    elif case == "wrong_composition":
        kwargs["composition_id"] = "other"
    elif case == "wrong_snapshot":
        manifest.sources[0].descriptor.snapshot_id = "other"
    elif case == "wrong_page":
        manifest.sources[0].pages[0].page = 8
    elif case == "wrong_image":
        manifest.sources[0].pages[0].image_sha256 = "d" * 64
    elif case == "missing_fingerprint":
        manifest.sources[0].artifact_sha256 = ""
    elif case == "duplicate":
        manifest.sources[0].evidence *= 2
    elif case == "conflicting_payload":
        row.raw_text = "changed"
    elif case == "different_pdf":
        manifest.sources[0].descriptor.pdf_sha256 = "e" * 64
    elif case == "conflicting_descriptor":
        manifest.sources[0].descriptor.snapshot_id = "financial"
        manifest.sources[0].descriptor.origin = "recovery"
    if case != "partial_materialization":
        repo.put(row)
    with pytest.raises(ValueError):
        load(manifest, repo, **kwargs)


def test_saved_page_binding_requires_exact_source_and_fingerprint(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from vietnamese_financial_multi_agent.evidence import composition

    source = dict(page=dict(symbol="TEST", year="2025", page=7), width=10, height=10)
    provenance = dict(
        pdf_sha256="a" * 64,
        image_sha256="b" * 64,
        render_dpi=200,
        renderer="pypdfium2",
        page_number=7,
    )
    image = SimpleNamespace(
        sha256="b" * 64, identity=SimpleNamespace(source_ref="sha256:" + "a" * 64)
    )
    monkeypatch.setattr(
        composition,
        "load_pages",
        lambda *a, **kw: [SimpleNamespace(source=provenance, image=image)],
    )
    monkeypatch.setattr(composition, "image_source", lambda value: source)
    record = dict(source=source, provenance=provenance)
    assert verify_saved_pages(tmp_path / "test.pdf", [record])[0].page == 7
    changed = deepcopy(record)
    changed["source"]["page"]["page"] = 8
    with pytest.raises(ValueError, match="binding_mismatch"):
        verify_saved_pages(tmp_path / "test.pdf", [changed])
    changed["provenance"].pop("pdf_sha256")
    with pytest.raises(ValueError, match="missing_source_fingerprint"):
        verify_saved_pages(tmp_path / "test.pdf", [changed])
