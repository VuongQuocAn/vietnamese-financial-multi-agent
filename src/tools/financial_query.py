"""Finite structured query probe; no natural-language understanding or verified ledger."""

from dataclasses import dataclass
from decimal import localcontext
from typing import Literal

from vietnamese_financial_multi_agent.accounting.quality import assess_evidence_for_task


@dataclass(frozen=True)
class EvidenceSelector:
    document_id: str
    page: int
    statement: str
    code: str
    period: str

    def matches(self, evidence):
        context = evidence.extraction.context
        return (
            context.statement_type == self.statement
            and evidence.source_item_code == self.code
            and context.period == self.period
            and any(
                ref.anchor.page.source_ref == self.document_id and ref.anchor.page.page == self.page
                for ref in evidence.extraction.provenance
            )
        )


@dataclass(frozen=True)
class FinancialQuery:
    query_id: str
    operands: tuple[EvidenceSelector, ...]
    operation: Literal["retrieve", "difference", "residual", "match"] = "retrieve"

    def __post_init__(self):
        counts = {"retrieve": (1,), "difference": (2,), "residual": (3,), "match": (2,)}
        if self.operation not in counts or len(self.operands) not in counts[self.operation]:
            raise ValueError("invalid_query_operation_or_operand_count")


def answer_query(query, evidence, *, arithmetic_checks=(), relationship_checks=()):
    """Exact source/code/period selection, Decimal computation, per-operand citations.

    Duplicate observations are retained for conflict detection. Missing operands
    produce a partial answer containing available raw facts, never a computed value.
    """
    evidence = list(evidence)
    selected, missing, ambiguous = [], [], []
    for index, selector in enumerate(query.operands):
        found = [e for e in evidence if selector.matches(e)]
        if not found:
            missing.append(str(index))
        # Same source code in multiple rows/labels is not a unique identity.
        if len({e.extraction.context.raw_item_label for e in found}) > 1:
            ambiguous.append(str(index))
        selected.extend(found)
    selected = list({e.evidence_id: e for e in selected}.values())
    direct = assess_evidence_for_task(selected)
    conflicts = any(i.decision == "conflicted" for i in direct.items)
    # Keep original evidence in storage; unreadable originals need not block a
    # readable recovery. Conflicting readable observations always block the query.
    selected = [i.evidence for i in direct.items if i.decision in {"usable", "usable_with_caveat"}]
    missing = [
        str(i) for i, s in enumerate(query.operands) if not any(s.matches(e) for e in selected)
    ]
    task = (
        "direct_qa"
        if query.operation == "retrieve"
        else "analytical_qa"
        if query.operation == "difference"
        else "accounting_analysis"
    )
    assessment = assess_evidence_for_task(
        selected,
        task,
        required_evidence_ids=[f"missing:{i}" for i in missing],
        arithmetic_checks=arithmetic_checks,
        relationship_checks=relationship_checks,
        require_check=query.operation == "match",
    )
    facts = []
    for item in assessment.items:
        e = item.evidence
        if item.decision not in {"usable", "usable_with_caveat"}:
            continue
        facts.append(
            dict(
                evidence_id=e.evidence_id,
                value=str(e.extraction.value.normalized_value),
                raw_value=e.extraction.value.raw_value,
                label=e.extraction.context.raw_item_label,
                code=e.source_item_code,
                period=e.extraction.context.period,
                unit=e.extraction.value.unit,
                scale=str(e.extraction.context.scale),
                citations=[p.model_dump(mode="json") for p in e.extraction.provenance],
                source_metadata=e.source_metadata,
            )
        )
    can_answer = (
        not missing
        and not ambiguous
        and not conflicts
        and assessment.decision in {"usable", "usable_with_caveat"}
        and all(i.decision in {"usable", "usable_with_caveat"} for i in assessment.items)
    )
    value = None
    reasons = list(assessment.reason_counts)
    reasons.extend(code for code in direct.reason_counts if code not in reasons)
    if ambiguous:
        reasons.append("ambiguous_source_code")
    if len({s.document_id for s in query.operands}) != 1:
        can_answer = False
        reasons.append("mixed_documents")
    if can_answer:
        values = [
            next(e.extraction.value.normalized_value for e in selected if s.matches(e))
            for s in query.operands
        ]
        with localcontext() as ctx:
            ctx.prec = 50
            if query.operation == "retrieve":
                value = str(values[0])
            elif query.operation == "difference":
                value = str(values[0] - values[1])
            elif query.operation == "residual":
                value = str(values[0] - values[1] - values[2])
            else:
                value = values[0] == values[1]
    return dict(
        query_id=query.query_id,
        operation=query.operation,
        status="answered" if can_answer else "partial" if facts else "abstained",
        value=value,
        facts=facts,
        reasons=reasons,
        missing_operands=missing,
        caveats=assessment.caveats,
        quality="conflicted" if conflicts else assessment.decision,
        financial_fact_verified=False,
    )
