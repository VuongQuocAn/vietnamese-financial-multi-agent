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

    def _path(self):
        path = self.root / "document-evidence.json"
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Evidence storage must stay within configured root")
        return path

    def _read(self):
        path = self._path()
        snapshot = (
            _Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else _Snapshot()
        )
        seen = set()
        for evidence in snapshot.records:
            identity = evidence.evidence_identity()
            if identity is None or identity in seen:
                raise ValueError("Invalid or duplicate identity in evidence storage")
            seen.add(identity)
        if any(e.evidence_identity() is not None for e in snapshot.quarantine):
            raise ValueError("Indexed identity found in quarantine")
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
                (e for e in self._read().records if e.evidence_identity() == identity), None
            )

    def list_by_document(
        self, document_id: str, snapshot_id: str | None = None
    ) -> list[DocumentEvidence]:
        with self.lock:
            return [
                e
                for e in self._read().records
                if e.document_id == document_id
                and (snapshot_id is None or e.snapshot_id == snapshot_id)
            ]

    def list_quarantine(self) -> list[DocumentEvidence]:
        with self.lock:
            return self._read().quarantine
