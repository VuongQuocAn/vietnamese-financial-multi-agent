"""Exact-byte reuse must retain proof checks, detached reads and external updates."""

import json
import os

import pytest
from vietnamese_financial_multi_agent.verification.ledger import LedgerAdmissionError
from vietnamese_financial_multi_agent.verification.ledger_contracts import VerifiedClaimQuery
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository

from .test_verified_claim_ledger import history_for


def test_warm_snapshot_detaches_results_and_detects_same_stat_tampering(tmp_path):
    repository = VerifiedClaimRepository(tmp_path)
    result = repository.admit(history_for())
    entry = repository.get(result.verified_claim_id)
    entry.accepted_claim.content = "caller mutation"
    assert repository.get(result.verified_claim_id).accepted_claim.content != "caller mutation"
    path = tmp_path / "verified-claims.json"
    stat = path.stat()
    wire = path.read_bytes()
    payload = json.loads(wire)
    digest = payload["entries"][0]["payload_sha256"]
    replacement = ("0" if digest[0] != "0" else "1") + digest[1:]
    # Change a proof-bound field while preserving wire length and file timestamps.
    updated = wire.replace(
        digest.encode(),
        replacement.encode(),
        1,
    )
    assert updated != wire and len(updated) == len(wire)
    path.write_bytes(updated)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises((LedgerAdmissionError, ValueError)):
        repository.query(VerifiedClaimQuery())


def test_warm_reader_observes_other_writer_deletion_and_restart(tmp_path):
    reader = VerifiedClaimRepository(tmp_path)
    assert reader.list_all() == []
    writer = VerifiedClaimRepository(tmp_path)
    history = history_for()
    result = writer.admit(history)
    assert reader.get(result.verified_claim_id) is not None
    assert reader.list_all() == VerifiedClaimRepository(tmp_path).list_all()
    (tmp_path / "verified-claims.json").unlink()
    assert reader.list_all() == []
    writer.admit(history)
    assert reader.get(result.verified_claim_id) is not None
