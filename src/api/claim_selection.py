"""Request retrieval and admitted-claim integrity, before M7 presentation."""

import re

from ..outputs.citation_renderer import _locator
from ..outputs.qa_composer import claim_scope
from ..tools.question_understanding import EXTRA_ALIASES, ITEM_RULES, normalize


def periods_for(request):
    """Explicit multiple years are allowed within the bound filing/snapshot."""
    years = set(re.findall(r"\b(?:19|20|21)\d{2}\b", request.question))
    if request.period:
        if years and request.period[:4] not in years:
            return set()
        years.add(request.period[:4])
    if len(years) == 1 and "nam truoc" in normalize(request.question):
        years.add(str(int(next(iter(years))) - 1))
    return years


def _targets(question):
    text = normalize(question)
    return {
        key
        for key, rule in ITEM_RULES.items()
        if any(
            re.search(r"(?<!\w)" + re.escape(normalize(a)) + r"(?!\w)", text)
            for a in (*rule.aliases, *EXTRA_ALIASES.get(key, ()))
        )
    }


def _relevant(entry, question):
    # Catalog aliases aid retrieval only; no Planner/formula/coverage admission.
    targets = _targets(question)
    evidence = entry.accepted_claim.supporting_evidence
    # Source labels cover names shortened in the question (e.g. after-tax profit).
    label_match = any(normalize(e.label) in normalize(question) for e in evidence)
    item_ids = {e.canonical_item_id for e in evidence if e.canonical_item_id}
    for e in evidence:
        if e.calculation and e.calculation.evidence:
            item_ids.update(
                m.record.canonical_item_id
                for operand in e.calculation.evidence.operands
                for m in operand.facts.matches
            )
    if targets and item_ids:
        return bool(targets & item_ids) or label_match
    # Unknown vocabulary remains retrievable without inventing financial intent.
    stop = set("cua ky nam la va cac cho biet bao cao tai ngay so lieu dan nguon".split())
    q = set(normalize(question).split()) - stop
    c = set(normalize(entry.content).split()) - stop
    return len({w for w in q & c if not w.isdigit()}) >= 2


def select_claims(request, entries, current_ids=()):
    selected, excluded = [], []
    current_ids = set(current_ids)
    years = periods_for(request)
    for entry in entries:
        i, reason = entry.identity, None
        if entry.verification_status != "verified" or entry.decision.decision != "ACCEPT":
            reason = "not_m6_accept"
        elif any(
            getattr(request, key) is None or getattr(request, key) != getattr(i, key)
            for key in ("company_id", "document_id", "snapshot_id")
        ):
            reason = "scope_identity_mismatch"
        elif i.kind == "document":
            reason = "financial_claim_required"
        elif not years or (i.verified_claim_id not in current_ids and i.period[:4] not in years):
            reason = "period_out_of_scope"
        elif (
            i.verified_claim_id not in current_ids
            and request.period
            and "-" in request.period
            and len(years) == 1
            and i.period != request.period
        ):
            reason = "period_out_of_scope"
        elif request.reporting_scope and claim_scope(entry) != request.reporting_scope:
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
        if (
            reason is None
            and i.verified_claim_id not in current_ids
            and not _relevant(entry, request.question)
        ):
            reason = "not_relevant"
        if reason:
            excluded.append(dict(claim_id=i.verified_claim_id, reason=reason))
        else:
            selected.append(entry)
    selected.sort(key=lambda e: e.identity.verified_claim_id not in current_ids)
    return selected, excluded
