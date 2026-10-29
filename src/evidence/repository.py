"""Canonical facts JSON snapshot; một repository writer trong local process."""

from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.persistence import atomic_json
from .contracts import CanonicalFinancialFact, ObservationIdentity, SemanticFactKey


class ObservationConflict(ValueError):
    """Giữ cả payload cũ/mới cho caller xử lý; repository không overwrite."""

    def __init__(self, existing: CanonicalFinancialFact, incoming: CanonicalFinancialFact):
        super().__init__("Different payload for the same observation identity")
        self.existing = existing.model_copy(deep=True)
        self.incoming = incoming.model_copy(deep=True)


class _Snapshot(FinancialModel):
    version: Literal["canonical_facts_v1"] = "canonical_facts_v1"
    observations: list[CanonicalFinancialFact] = Field(default_factory=list)
    quarantine: list[CanonicalFinancialFact] = Field(default_factory=list)


def _payload(fact):
    return fact.model_dump(mode="json")


class CanonicalFactRepository:
    """Reuse atomic JSON convention, không có engine/index file song song.

    Một instance/writer cho mỗi root; caller có thể truyền shared lock của storage.
    Truy vấn scan snapshot phù hợp local demo; semantic key không là unique key.
    """

    def __init__(self, root: Path, *, lock=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = lock if lock is not None else RLock()

    def _path(self):
        path = self.root / "canonical-facts.json"
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Canonical storage must stay within configured root")
        return path

    def _read(self):
        path = self._path()
        snapshot = (
            _Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else _Snapshot()
        )
        seen = set()
        for fact in snapshot.observations:
            identity = fact.observation_identity()
            if identity is None or identity in seen:
                raise ValueError("Invalid or duplicate identity in canonical storage")
            seen.add(identity)
        if any(f.observation_identity() is not None for f in snapshot.quarantine):
            raise ValueError("Indexed identity found in quarantine")
        return snapshot

    def put(self, fact: CanonicalFinancialFact) -> Literal["stored", "idempotent", "quarantined"]:
        """Thiếu identity được lưu quarantine nguyên payload, không global ID giả."""
        # Validate lại mutable nested models bằng JSON, giữ exact Decimal strings.
        fact = CanonicalFinancialFact.model_validate_json(fact.model_dump_json())
        with self.lock:
            snapshot = self._read()
            identity = fact.observation_identity()
            if identity is None:
                if not any(_payload(f) == _payload(fact) for f in snapshot.quarantine):
                    snapshot.quarantine.append(fact)
                    atomic_json(self._path(), snapshot.model_dump(mode="json"))
                return "quarantined"
            for existing in snapshot.observations:
                if existing.observation_identity() == identity:
                    if _payload(existing) != _payload(fact):
                        raise ObservationConflict(existing, fact)
                    return "idempotent"
            snapshot.observations.append(fact)
            atomic_json(self._path(), snapshot.model_dump(mode="json"))
            return "stored"

    def get(self, identity: ObservationIdentity) -> CanonicalFinancialFact | None:
        with self.lock:
            return next(
                (f for f in self._read().observations if f.observation_identity() == identity), None
            )

    def list_by_document(
        self, document_id: str, snapshot_id: str | None = None
    ) -> list[CanonicalFinancialFact]:
        with self.lock:
            return [
                f
                for f in self._read().observations
                if f.document_id == document_id
                and (snapshot_id is None or f.snapshot_id == snapshot_id)
            ]

    def query_by_semantic_key(self, key: SemanticFactKey) -> list[CanonicalFinancialFact]:
        with self.lock:
            return [f for f in self._read().observations if f.semantic_key() == key]

    def list_quarantine(self) -> list[CanonicalFinancialFact]:
        with self.lock:
            return self._read().quarantine
