"""Read-only replay of persisted PERF-01 quarantine and legacy controls."""

import hashlib
import json
from pathlib import Path

from profile_fast_path import save
from vietnamese_financial_multi_agent.verification.ledger import (
    LedgerAdmissionError,
    build_verified_claim,
    validate_entry,
)
from vietnamese_financial_multi_agent.verification.ledger_contracts import (
    VerifiedClaimLedgerSnapshot,
)
from vietnamese_financial_multi_agent.verification.ledger_repository import VerifiedClaimRepository


def main():
    base = Path("artifacts/evidence/PERF-01")
    rows = []
    controls = [
        (
            "H08",
            Path(
                "artifacts/evidence/GEN-02-Fix-B/before-policy/BCC_2024/ledger/verified-claims.json"
            ),
            16,
            "/text_elements/7",
        ),
        (
            "PDF30",
            Path(
                "artifacts/evidence/GEN-02-Fix-B/final/clean-ledger/BCC_2024/ledger/verified-claims.json"
            ),
            30,
            "/text_elements/9",
        ),
    ]
    for label, path, page, selector in controls:
        wire = path.read_bytes()
        entries = VerifiedClaimLedgerSnapshot.model_validate_json(wire).entries
        bad = [
            e
            for e in entries
            if e.identity.kind == "document"
            and any(
                c.pdf_page == page and c.source.reference.source_pointer == selector
                for c in e.citations
            )
        ]
        assert bad, label
        repository = VerifiedClaimRepository(path.parent)
        for _ in range(2):
            visible = {e.identity.verified_claim_id for e in repository.list_all()}
            assert all(e.identity.verified_claim_id not in visible for e in bad)
        for entry in bad:
            try:
                build_verified_claim(entry.history)
            except LedgerAdmissionError:
                pass
            else:
                raise AssertionError("quarantined proof accepted")
        assert wire == path.read_bytes()
        rows.append(
            dict(
                control=label,
                blocked_claims=len(bad),
                warm_read_blocked=True,
                replay_rejected=True,
                source_unchanged=True,
            )
        )
    for row in json.loads(
        Path("artifacts/evidence/GEN-02-Fix-A/legacy-compatibility.json").read_bytes()
    ):
        path = Path(row["path"])
        wire = path.read_bytes()
        assert hashlib.sha256(wire).hexdigest() == row["sha256"]
        repository = VerifiedClaimRepository(path.parent)
        entries = repository.list_all()
        assert len(entries) == row["claims"]
        for entry in entries:
            validate_entry(entry)
        assert entries == repository.list_all() == VerifiedClaimRepository(path.parent).list_all()
        assert wire == path.read_bytes()
        rows.append(
            dict(control="legacy_" + row["label"], replayed=len(entries), restart_exact=True)
        )
    save(
        base / "safety-controls.json",
        dict(
            controls=rows,
            passed=True,
            note="dynamic policy-change and mismatches covered by focused unit regressions",
        ),
    )
    print("Persisted H08/PDF30 blocked; 17 legacy proofs replayed; source bytes unchanged")


if __name__ == "__main__":
    main()
