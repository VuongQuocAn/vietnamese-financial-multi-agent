"""Source bookkeeping and replay of saved selection/join proofs; no agent calls."""

import hashlib
import json
from decimal import Decimal
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel


def content_digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def prompt_observation(row):
    """Bounded projection; complete selectors/quality remain in the workspace."""
    return {k: row[k] for k in ("item", "label", "value", "unit", "header", "context")}


def observation(match):
    """Projection of an existing source fact, including unmapped facts, without promotion."""
    fact = match.record
    reference = match.reference.model_dump(mode="json")
    return dict(
        evidence_id="E-"
        + hashlib.sha256(match.reference.model_dump_json().encode()).hexdigest()[:20],
        reference=reference,
        source_digest=content_digest(fact.model_dump(mode="json")),
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        item=fact.canonical_item_id,
        label=fact.context.raw_item_label,
        header=fact.raw_header,
        raw_value=fact.value.raw_value,
        value=str(fact.value.normalized_value) if fact.value.normalized_value is not None else None,
        unit=fact.value.unit,
        context=fact.context.model_dump(mode="json"),
        selectors=[s.model_dump(mode="json") for s in fact.sources],
        citations=[c.model_dump(mode="json") for c in match.citations],
        quality=[q.model_dump(mode="json") for q in fact.quality_context],
        issues=[q.model_dump(mode="json") for q in fact.resolution_issues],
        parser="existing_financial_normalization_v1",
        verification="unverified_source_observation",
    )


class SelectionDemand(FinancialModel):
    item: str
    periods: list[str] = Field(min_length=1, max_length=8)
    comparator: Literal["max", "min", "max_abs", "min_abs"]


def select_observations(demand, rows, sources):
    """Complete declared item/period domain; equal maxima remain a set."""
    domain = [
        r for r in rows if r["item"] == demand.item and r["context"]["period"] in demand.periods
    ]
    expected = {
        f.observation_identity().model_dump_json()
        for s in sources.values()
        if s["kind"] == "fact" and s["item"] == demand.item and s["period"] in demand.periods
        for f in s["records"]
    }
    actual = {json.dumps(r["reference"]["observation"], separators=(",", ":")) for r in domain}
    # Reference identity uses the existing ObservationIdentity serialization.
    if (
        not expected
        or actual != expected
        or {r["context"]["period"] for r in domain} != set(demand.periods)
    ):
        raise ValueError("selection_domain_incomplete")
    contexts = {
        (
            r["company_id"],
            r["document_id"],
            r["snapshot_id"],
            r["unit"],
            r["context"]["currency"],
            r["context"]["scale"],
            r["context"]["reporting_scope"],
            r["context"]["period_type"],
        )
        for r in domain
    }
    if (
        len(contexts) != 1
        or any(
            any(value is None for i, value in enumerate(context) if i != 6) for context in contexts
        )
        or any(r["value"] is None or not r["selectors"] or not r["header"] for r in domain)
    ):
        raise ValueError("selection_context_unresolved")
    by_period = {}
    for row in domain:
        by_period.setdefault(row["context"]["period"], set()).add(row["value"])
    if any(len(values) != 1 for values in by_period.values()):
        raise ValueError("selection_conflicting_values")

    def key(row):
        value = Decimal(row["value"])
        return abs(value) if demand.comparator.endswith("_abs") else value

    best = (max if demand.comparator.startswith("max") else min)(map(key, domain))
    selected = [r for r in domain if key(r) == best]
    record = dict(
        domain=domain,
        domain_scope="declared_item_and_periods_in_pinned_inventory",
        selection=demand.model_dump(mode="json"),
        selected_ids=[r["evidence_id"] for r in selected],
        excluded=[
            dict(evidence_id=r["evidence_id"], reason="comparator_not_equal_to_extremum")
            for r in domain
            if key(r) != best
        ],
        ties=len({r["context"]["period"] for r in selected}) > 1,
        caveats=["reporting_scope_unresolved_within_pinned_snapshot"]
        if any(r["context"]["reporting_scope"] is None for r in domain)
        else [],
        verification="unverified_selection_semantics",
    )
    record["digest"] = content_digest(record)
    return selected, record


def join_observations(parent, current):
    """Exact source context join; no fuzzy entities or inferred accounting meaning."""
    fields = ["company_id", "document_id", "snapshot_id", "period"]
    left, right = parent["selected_observations"], current
    # Exact document/snapshot membership is known even when accounting scope is
    # unresolved. Never manufacture separate/consolidated from that membership.
    missing_scope = all(r["context"]["reporting_scope"] is None for r in [*left, *right])
    if not missing_scope:
        fields.append("reporting_scope")

    def key(row):
        return tuple(row.get(f) if f in row else row["context"].get(f) for f in fields)

    pairs = [(a, b) for a in left for b in right if None not in key(a) and key(a) == key(b)]
    unmatched_left = [a["evidence_id"] for a in left if not any(a == p[0] for p in pairs)]
    unmatched_right = [b["evidence_id"] for b in right if not any(b == p[1] for p in pairs)]
    # Multiple rows for one item/key cannot silently turn into a many-to-many join.
    identities = [
        (side, row["item"] or row["evidence_id"], key(row))
        for side, rows in [("left", left), ("right", right)]
        for row in rows
    ]
    ambiguous = len(identities) != len(set(identities))
    record = dict(
        from_result={k: parent[k] for k in ("handle", "revision", "digest")},
        keys=fields,
        normalization="identity",
        caveats=["reporting_scope_unresolved_within_pinned_snapshot"] if missing_scope else [],
        left=left,
        right=right,
        pairs=[[a["evidence_id"], b["evidence_id"]] for a, b in pairs],
        cardinality=dict(left=len(left), right=len(right), matched=len(pairs)),
        unmatched_left=unmatched_left,
        unmatched_right=unmatched_right,
        status="ambiguous"
        if ambiguous
        else "unmatched"
        if unmatched_left or unmatched_right
        else "matched",
        verification="unverified_join_semantics",
    )
    record["digest"] = content_digest(record)
    return record
