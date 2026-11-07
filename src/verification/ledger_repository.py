"""Local JSON ledger; one writer/root, optional shared process lock, no candidate fallback."""

from pathlib import Path
from threading import RLock

from ..core.persistence import atomic_json
from .ledger import LedgerAdmissionError, build_verified_claim, validate_entry
from .ledger_contracts import (
    DocumentVerificationHistory,
    LedgerAdmissionResult,
    LedgerEntry,
    VerificationHistory,
    VerifiedClaimLedgerSnapshot,
    VerifiedClaimQuery,
)
from .validation_contracts import verification_input_digest


class LedgerConflict(ValueError):
    def __init__(self, existing, incoming):
        super().__init__("Different payload for the same verified claim identity")
        self.existing = existing.model_copy(deep=True)
        self.incoming = incoming.model_copy(deep=True)


class VerifiedClaimRepository:
    def __init__(self, root: Path, *, lock=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = lock if lock is not None else RLock()
        # Cache only hashes of fully validated wire payloads, never mutable records.
        self._validated_payloads: set[str] = set()

    def _path(self):
        path = self.root / "verified-claims.json"
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Ledger storage must stay within configured root")
        return path

    def _read(self):
        path = self._path()
        snapshot = (
            VerifiedClaimLedgerSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else VerifiedClaimLedgerSnapshot()
        )
        seen = set()
        for entry in snapshot.entries:
            key = entry.identity.verified_claim_id
            if key in seen:
                raise ValueError("Duplicate identity in verified ledger")
            seen.add(key)
            digest = verification_input_digest(entry)
            if digest not in self._validated_payloads:
                validate_entry(entry)
                self._validated_payloads.add(digest)
        snapshot.entries.sort(key=lambda e: e.identity.verified_claim_id)
        return snapshot

    def admit(
        self, history: VerificationHistory | DocumentVerificationHistory
    ) -> LedgerAdmissionResult:
        return self.admit_many([history])[0]

    def admit_many(
        self, histories: list[VerificationHistory | DocumentVerificationHistory]
    ) -> list[LedgerAdmissionResult]:
        """One atomic snapshot for a batch; each claim still needs its own exact proof.

        A payload conflict aborts the write, preserving the existing snapshot.
        Rejected decisions do not prevent independent valid claims being stored.
        """
        results = []
        with self.lock:
            snapshot = self._read()
            indexed = {e.identity.verified_claim_id: e for e in snapshot.entries}
            changed = False
            for history in histories:
                try:
                    entry = build_verified_claim(history)
                except LedgerAdmissionError as error:
                    results.append(LedgerAdmissionResult(status="rejected", reason=str(error)))
                    continue
                self._validated_payloads.add(verification_input_digest(entry))
                key = entry.identity.verified_claim_id
                existing = indexed.get(key)
                if existing is not None:
                    if existing != entry:
                        raise LedgerConflict(existing, entry)
                    results.append(
                        LedgerAdmissionResult(status="idempotent", verified_claim_id=key)
                    )
                    continue
                indexed[key] = entry
                changed = True
                results.append(LedgerAdmissionResult(status="stored", verified_claim_id=key))
            if changed:
                snapshot.entries = sorted(
                    indexed.values(), key=lambda e: e.identity.verified_claim_id
                )
                atomic_json(self._path(), snapshot.model_dump(mode="json"))
        return results

    def list_all(self) -> list[LedgerEntry]:
        with self.lock:
            return self._read().entries

    def get(self, verified_claim_id: str) -> LedgerEntry | None:
        return next(
            (e for e in self.list_all() if e.identity.verified_claim_id == verified_claim_id), None
        )

    def list_by_document(
        self, document_id: str, snapshot_id: str | None = None
    ) -> list[LedgerEntry]:
        return self.query(VerifiedClaimQuery(document_id=document_id, snapshot_id=snapshot_id))

    def query(self, query: VerifiedClaimQuery) -> list[LedgerEntry]:
        query = VerifiedClaimQuery.model_validate_json(query.model_dump_json())
        matches = []
        for entry in self.list_all():
            document = entry.identity.kind == "document"
            if document != (query.kind == "document"):
                continue
            if document and (
                query.composition_id != entry.identity.composition_id
                or query.composition_sha256 != entry.identity.composition_sha256
                or query.metric_id is not None
                or query.canonical_item_id is not None
            ):
                continue
            claim = entry.accepted_claim
            if any(
                value is not None and getattr(entry.identity, field) != value
                for field, value in query.model_dump(exclude_none=True).items()
                if field in {"company_id", "document_id", "snapshot_id", "period", "kind"}
            ):
                continue
            if query.metric_id is not None and query.metric_id not in claim.metric_ids:
                continue
            if query.canonical_item_id is not None:
                items = {e.canonical_item_id for e in claim.supporting_evidence}
                if claim.calculation and claim.calculation.evidence:
                    lineage = claim.calculation.evidence.reviewed_lineage.lineage
                    if lineage:
                        items.update(
                            fact.canonical_item_id
                            for operand in lineage.operands
                            for fact in operand.observations
                        )
                if query.canonical_item_id not in items:
                    continue
            if (
                query.reference is not None
                and query.reference not in entry.decision.supporting_references
            ):
                continue
            matches.append(entry)
        return matches
