"""Request retrieval and admitted-claim integrity, before M7 presentation."""

from ..outputs.citation_renderer import _locator
from ..outputs.qa_composer import claim_scope


def select_claims(request, entries, current_ids=(), *, scope_resolution=None):
    selected, excluded = [], []
    current_ids = set(current_ids)
    for entry in entries:
        i, reason = entry.identity, None
        if entry.verification_status != "verified" or entry.decision.decision != "ACCEPT":
            reason = "not_m6_accept"
        elif any(
            getattr(request, key) is None or getattr(request, key) != getattr(i, key)
            for key in ("company_id", "document_id", "snapshot_id")
        ):
            reason = "scope_identity_mismatch"
        elif (
            i.verified_claim_id not in current_ids
            and entry.history.proof.batch.question != request.question
        ):
            reason = "different_request"
        elif i.kind == "document":
            reason = "financial_claim_required"
        elif (
            request.reporting_scope
            and claim_scope(entry) != request.reporting_scope
            and not (
                scope_resolution is not None
                and scope_resolution.status == "resolved"
                and scope_resolution.evidence_status in {"confirmed", "json_bound"}
                and (scope_resolution.document_id, scope_resolution.snapshot_id)
                == (i.document_id, i.snapshot_id)
                and scope_resolution.reporting_scope == request.reporting_scope
            )
        ):
            reason = "reporting_scope_unconfirmed"
        elif not entry.citations:
            reason = "missing_citations"
        else:
            try:
                for c in entry.citations:
                    if (c.document_id, c.snapshot_id) != (i.document_id, i.snapshot_id):
                        raise ValueError("citation_scope_mismatch")
                    _locator(c)
                    if c not in entry.accepted_claim.citations:
                        raise ValueError("citation_not_in_accepted_claim")
            except ValueError:
                reason = "citation_source_mismatch"
        if reason:
            excluded.append(dict(claim_id=i.verified_claim_id, reason=reason))
        else:
            selected.append(entry)
    selected.sort(key=lambda e: e.identity.verified_claim_id not in current_ids)
    return selected, excluded
