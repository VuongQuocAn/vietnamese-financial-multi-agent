"""Read-only source overlays và explicit binding; không mở PDF hay kế thừa review."""

from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from .analytical_readiness import SourceReview, source_review_status
from .contracts import CanonicalFinancialFact, EvidenceAnchor, ObservationIdentity
from .lineage import MetricLineage


class SourceReviewView(FinancialModel):
    observation: ObservationIdentity
    status: Literal[
        "page_resolved", "value_row_verified", "unverified", "source_inconsistent", "source_missing"
    ]
    original_sources: list[EvidenceAnchor]
    original_anchor_statuses: list[str]
    reviews: list[SourceReview]
    verified_source_count: int
    source_count: int
    quality_caveats: list[str]


class SourceReviewLookup(FinancialModel):
    status: Literal["found", "not_found", "conflicted"]
    matches: list[SourceReviewView] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class OperandSourceReview(FinancialModel):
    role: str
    bindings: list[SourceReviewLookup]


class ReviewedMetricLineage(FinancialModel):
    lineage: MetricLineage | None = None
    status: Literal["found", "not_found", "ambiguous", "unavailable", "conflicted"]
    reasons: list[str] = Field(default_factory=list)
    operands: list[OperandSourceReview] = Field(default_factory=list)
    # Selected snapshot rồi đến ancestors; chỉ provenance, không resolve fallback.
    snapshot_chain: list[str] = Field(default_factory=list)


def review_view(fact: CanonicalFinancialFact, reviews) -> SourceReviewView:
    selected = [
        r.model_copy(deep=True) for r in reviews if r.observation == fact.observation_identity()
    ]
    status = source_review_status(fact, selected)
    return SourceReviewView(
        observation=fact.observation_identity(),
        status=status,
        original_sources=[s.model_copy(deep=True) for s in fact.sources],
        original_anchor_statuses=[s.reference.anchor.status for s in fact.sources if s.reference],
        reviews=selected,
        verified_source_count=sum(
            s.reference is not None
            and s.reference.source_pointer
            in {selected[0].value_selector, selected[0].label_selector, selected[0].header_selector}
            for s in fact.sources
        )
        if status == "value_row_verified"
        else 0,
        source_count=len(fact.sources),
        quality_caveats=sorted(
            {
                *[i.code for i in fact.resolution_issues],
                *[q.decision for q in fact.quality_context],
                *[c for q in fact.quality_context for c in q.caveats],
            }
        ),
    )


def bind_source_review(fact: CanonicalFinancialFact, reading: dict, payload: dict) -> SourceReview:
    """Bind a NEW controlled reading to exact selectors/row/column in selected payload.

    Caller phải đối chiếu PDF/render/hash và ghi explicit verification_reference
    khi reuse evidence. Numeric equality không tự tạo review hoặc chứng minh nguồn.
    """

    def pointer(selector):
        value = payload
        for part in selector.strip("/").split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value

    selectors = [s.reference.source_pointer for s in fact.sources if s.reference]

    def select(text, kind):
        matches = [
            s for s in selectors if s and f"/{kind}/" in s and pointer(s).get("text") == text
        ]
        if len(matches) != 1:
            raise ValueError("ambiguous_or_missing_review_selector")
        return matches[0]

    value = select(reading["raw_value"], "cells")
    label = select(reading["raw_label"], "cells")
    header = select(reading["raw_header"], "headers")
    vc, lc, hc = [pointer(s) for s in (value, label, header)]
    tables = {s.split("/cells/")[0].split("/headers/")[0] for s in (value, label, header)}
    if (
        len(tables) != 1
        or value == label
        or None in (vc["row"], lc["row"], vc["column"], hc["column"])
        or vc["row"] != lc["row"]
        or vc["column"] != hc["column"]
        or any(c["reading"] != "observed" for c in (vc, lc, hc))
    ):
        raise ValueError("review_row_column_mismatch")
    table = pointer(next(iter(tables)))
    for cell in (vc, lc, hc):
        if (
            sum(
                c["row"] == cell["row"] and c["column"] == cell["column"]
                for c in table["cells"] + table["headers"]
            )
            != 1
        ):
            raise ValueError("ambiguous_review_position")
    review = SourceReview(
        **reading,
        sources=fact.sources,
        value_selector=value,
        label_selector=label,
        header_selector=header,
    )
    if review.reused_from is not None and not review.verification_reference:
        raise ValueError("explicit_reverification_required")
    if source_review_status(fact, [review]) != "value_row_verified":
        raise ValueError("review_fact_mismatch")
    return review
