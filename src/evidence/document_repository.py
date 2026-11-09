"""Local single-writer persistence text/table; tách canonical-facts.json."""

from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import Field, TypeAdapter

from ..accounting.contracts import FinancialModel
from ..core.persistence import atomic_json
from .document_evidence import DocumentEvidence, EvidenceIdentity

_adapter = TypeAdapter(DocumentEvidence)


class EvidenceConflict(ValueError):
    def __init__(self, existing, incoming):
        super().__init__("Different payload for the same evidence identity")
        self.existing = existing.model_copy(deep=True)
        self.incoming = incoming.model_copy(deep=True)


class _Snapshot(FinancialModel):
    version: Literal["document_evidence_v1"] = "document_evidence_v1"
    records: list[DocumentEvidence] = Field(default_factory=list)
    quarantine: list[DocumentEvidence] = Field(default_factory=list)


class DocumentEvidenceRepository:
    """Một writer/root; share lock giữa instances, không multi-process writers."""

    def __init__(self, root: Path, *, lock=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = lock if lock is not None else RLock()
        self._snapshot_bytes: bytes | None = None
        self._snapshot: _Snapshot | None = None

    def _path(self):
        path = self.root / "document-evidence.json"
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Evidence storage must stay within configured root")
        return path

    def _read(self):
        return self._load().model_copy(deep=True)

    def _load(self):
        """One private parsed snapshot; exact bytes invalidate even same-stat edits."""
        path = self._path()
        wire = path.read_bytes() if path.exists() else None
        if self._snapshot is not None and wire == self._snapshot_bytes:
            return self._snapshot
        snapshot = _Snapshot.model_validate_json(wire) if wire is not None else _Snapshot()
        seen = set()
        for evidence in snapshot.records:
            identity = evidence.evidence_identity()
            if identity is None or identity in seen:
                raise ValueError("Invalid or duplicate identity in evidence storage")
            seen.add(identity)
        if any(e.evidence_identity() is not None for e in snapshot.quarantine):
            raise ValueError("Indexed identity found in quarantine")
        self._snapshot_bytes, self._snapshot = wire, snapshot
        return snapshot

    def put(self, evidence: DocumentEvidence) -> Literal["stored", "idempotent", "quarantined"]:
        evidence = _adapter.validate_json(evidence.model_dump_json())
        with self.lock:
            snapshot = self._read()
            identity = evidence.evidence_identity()
            payload = evidence.model_dump(mode="json")
            if identity is None:
                if not any(e.model_dump(mode="json") == payload for e in snapshot.quarantine):
                    snapshot.quarantine.append(evidence)
                    atomic_json(self._path(), snapshot.model_dump(mode="json"))
                return "quarantined"
            for existing in snapshot.records:
                if existing.evidence_identity() == identity:
                    if existing.model_dump(mode="json") != payload:
                        raise EvidenceConflict(existing, evidence)
                    return "idempotent"
            snapshot.records.append(evidence)
            atomic_json(self._path(), snapshot.model_dump(mode="json"))
            return "stored"

    def get(self, identity: EvidenceIdentity) -> DocumentEvidence | None:
        with self.lock:
            return next(
                (
                    e.model_copy(deep=True)
                    for e in self._load().records
                    if e.evidence_identity() == identity
                ),
                None,
            )

    def put_many(self, records: list[DocumentEvidence]) -> list[str]:
        """Validate a page batch before one atomic write; preserve conflict semantics."""
        incoming = [_adapter.validate_json(row.model_dump_json()) for row in records]
        with self.lock:
            snapshot = self._read()
            indexed = {row.evidence_identity(): row for row in snapshot.records}
            statuses = []
            changed = False
            for row in incoming:
                identity = row.evidence_identity()
                if identity is None:
                    if row not in snapshot.quarantine:
                        snapshot.quarantine.append(row)
                        changed = True
                    statuses.append("quarantined")
                elif identity in indexed:
                    if indexed[identity] != row:
                        raise EvidenceConflict(indexed[identity], row)
                    statuses.append("idempotent")
                else:
                    snapshot.records.append(row)
                    changed = True
                    indexed[identity] = row
                    statuses.append("stored")
            if changed:
                atomic_json(self._path(), snapshot.model_dump(mode="json"))
            return statuses

    def list_by_document(
        self, document_id: str, snapshot_id: str | None = None
    ) -> list[DocumentEvidence]:
        with self.lock:
            return [
                e.model_copy(deep=True)
                for e in self._load().records
                if e.document_id == document_id
                and (snapshot_id is None or e.snapshot_id == snapshot_id)
            ]

    def list_quarantine(self) -> list[DocumentEvidence]:
        with self.lock:
            return [e.model_copy(deep=True) for e in self._load().quarantine]
