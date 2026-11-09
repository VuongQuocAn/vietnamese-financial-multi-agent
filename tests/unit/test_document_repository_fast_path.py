"""Source snapshot reuse must preserve detached records and exact invalidation."""

import os

from vietnamese_financial_multi_agent.evidence import (
    DocumentEvidenceRepository,
    evidence_from_persisted_result,
)

from .test_document_evidence import result_fixture


def test_source_reads_detach_and_observe_same_stat_replacement_and_writes(tmp_path):
    repository = DocumentEvidenceRepository(tmp_path)
    text, table = evidence_from_persisted_result(result_fixture())
    repository.put_many([text, table])
    selected = repository.list_by_document(text.document_id, text.snapshot_id)
    selected[0].raw_text = "caller mutation"
    assert repository.list_by_document(text.document_id, text.snapshot_id)[0] == text
    path = tmp_path / "document-evidence.json"
    wire, stat = path.read_bytes(), path.stat()
    # Equal length replacement bypasses a cache keyed only by mtime/size.
    changed = wire.replace(b"Doanh thu", b"doanh thu")
    assert changed != wire and len(changed) == len(wire)
    path.write_bytes(changed)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert repository.list_by_document(text.document_id)[0].raw_text != text.raw_text
    other = DocumentEvidenceRepository(tmp_path)
    additional = text.model_copy(update={"local_evidence_id": "additional"}, deep=True)
    other.put(additional)
    assert len(repository.list_by_document(text.document_id)) == 3
    assert repository.list_by_document(text.document_id) == other.list_by_document(text.document_id)
