"""Task-aware usage annotations; source extraction is never filtered or modified."""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from copy import deepcopy
from typing import Literal

from pydantic import Field
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
    SourceAnchor,
)

from .arithmetic import ArithmeticCheck
from .automated_extraction import AutomatedLink, ExtractedPage, parse_vietnamese_number
from .context_resolution import ContextEvidence, resolve_financial_context
from .contracts import (
    FinancialModel,
    FinancialNormalizationResult,
    FinancialSourceReference,
    FinancialValue,
)
from .relationships import RelationshipCheck

TaskType = Literal["direct_qa", "analytical_qa", "accounting_analysis", "report_generation"]
UsageDecision = Literal["usable", "usable_with_caveat", "insufficient", "conflicted"]


class AssessableEvidence(FinancialModel):
    evidence_id: str
    extraction: FinancialNormalizationResult
    canonical_item_id: str | None = None
    source_item_code: str | None = None
    raw_header: str | None = None
    extraction_issues: list[str] = Field(default_factory=list)
    source_metadata: dict = Field(default_factory=dict)


class QualityIssue(FinancialModel):
    code: str
    detail: str


class EvidenceAssessment(FinancialModel):
    evidence: AssessableEvidence
    decision: UsageDecision
    issues: list[QualityIssue]
    caveats: list[str]


class QualityAssessment(FinancialModel):
    task_type: TaskType
    decision: UsageDecision
    items: list[EvidenceAssessment]
    issues: list[QualityIssue]
    caveats: list[str]
    summary_counts: dict[str, int]
    reason_counts: dict[str, int]
    arithmetic_annotations: list[ArithmeticCheck] = Field(default_factory=list)
    relationship_annotations: list[RelationshipCheck] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False


def _identity(item):
    result = item.extraction
    c = result.context
    documents = tuple(
        sorted({p.anchor.page.source_ref or p.anchor.page.image for p in result.provenance})
    )
    return (
        documents,
        c.statement_type,
        item.canonical_item_id or item.source_item_code or c.raw_item_label,
        c.period,
        c.period_type,
        c.reporting_scope,
        c.currency,
        result.value.unit,
        c.scale,
    )


def assess_evidence_for_task(
    evidence: Iterable[AssessableEvidence],
    task_type: TaskType = "direct_qa",
    *,
    required_evidence_ids: Iterable[str] = (),
    arithmetic_checks: Iterable[ArithmeticCheck] = (),
    relationship_checks: Iterable[RelationshipCheck] = (),
    require_check: bool = False,
) -> QualityAssessment:
    """Caller selects operands/checks for a task; no question parser or hidden rule run.

    required_evidence_ids names missing operands explicitly. Item decisions always
    describe direct retrieval; aggregate decision describes the requested operation.
    Reports keep available sections even when another section is insufficient.
    """
    values = [e.model_copy(deep=True) for e in evidence]
    groups = defaultdict(list)
    for e in values:
        groups[_identity(e)].append(e)
    conflicts = {
        e.evidence_id
        for group in groups.values()
        if len(
            {
                e.extraction.value.normalized_value
                for e in group
                if e.extraction.value.normalized_value is not None
            }
        )
        > 1
        for e in group
    }
    arithmetic_checks = list(arithmetic_checks)
    relationship_checks = list(relationship_checks)
    checks = [*arithmetic_checks, *relationship_checks]
    relevant_checks = []
    for check in checks:
        inputs = [i.value.extraction if hasattr(i, "value") else i.extraction for i in check.inputs]
        if inputs and all(any(e.extraction == r for e in values) for r in inputs):
            relevant_checks.append(check)
    items = []
    for e in values:
        r = e.extraction
        issues, caveats = [], []
        blocked = False

        def issue(code, detail, blocking=False, issues=issues):
            nonlocal blocked
            issues.append(QualityIssue(code=code, detail=detail))
            blocked |= blocking

        if not ((r.context.raw_item_label or "").strip() or (e.source_item_code or "").strip()):
            issue("ambiguous_item", "No distinguishing label or source code", True)
        if not r.value.raw_value.strip() or r.value.normalized_value is None:
            issue("missing_source_data", "No readable numeric value; missing is not zero", True)
        if not r.context.period or not r.context.period_type:
            issue("missing_period", "Period not established from source", True)
        if not any(
            p.anchor.page.page > 0 and (p.anchor.page.source_ref or p.anchor.page.image)
            for p in r.provenance
        ):
            issue("provenance_missing", "Document/page source required", True)
        if not e.canonical_item_id:
            issue("missing_canonical_mapping", "Raw item identity retained")
        if not r.value.unit or r.context.scale is None:
            issue("missing_unit", "Display raw value; unit/scale unconfirmed")
        if e.extraction_issues or r.value.status != "resolved":
            issue("extraction_error", ", ".join(e.extraction_issues) or r.value.status, True)
        mismatch = False
        for check in checks:
            inputs = [
                i.value.extraction if hasattr(i, "value") else i.extraction for i in check.inputs
            ]
            if r not in inputs:
                continue
            if check.status in {"failed", "inconsistent"}:
                code = (
                    "arithmetic_mismatch"
                    if isinstance(check, ArithmeticCheck)
                    else "relationship_mismatch"
                )
                issue(code, check.rule_id)
                mismatch = True
            caveats.extend(check.caveats if hasattr(check, "caveats") else [])
        if e.evidence_id in conflicts:
            issue("conflicting_values", "Multiple values for the same document/item/context")
            decision = "conflicted"
        elif blocked:
            decision = "insufficient"
        else:
            decision = "usable_with_caveat" if issues or caveats or mismatch else "usable"
        caveats.extend(i.code for i in issues)
        items.append(
            EvidenceAssessment(
                evidence=e, decision=decision, issues=issues, caveats=list(dict.fromkeys(caveats))
            )
        )
    operation_issues, caveats = [], []

    def operation_issue(code, detail):
        operation_issues.append(QualityIssue(code=code, detail=detail))

    missing = set(required_evidence_ids) - {e.evidence_id for e in values}
    if missing:
        operation_issue("missing_source_data", "Missing operands: " + ", ".join(sorted(missing)))
    available = [i for i in items if i.decision in {"usable", "usable_with_caveat"}]
    decision = "usable_with_caveat" if any(i.decision != "usable" for i in items) else "usable"
    if task_type in {"analytical_qa", "accounting_analysis"}:
        contexts = {
            (e.extraction.value.unit, e.extraction.context.currency, e.extraction.context.scale)
            for e in values
        }
        if len(contexts) > 1 or any(
            not unit or scale is None or scale <= 0 for unit, _, scale in contexts
        ):
            operation_issue("incompatible_units", "Operands require compatible currency/unit/scale")
        scopes = {e.extraction.context.reporting_scope for e in values}
        if len(scopes) > 1:
            operation_issue("incompatible_scope", "Operand scopes differ")
        elif scopes == {None}:
            caveats.append("scope_unconfirmed")
        periods = {(e.extraction.context.period, e.extraction.context.period_type) for e in values}
        completed_checks = [
            c
            for c in relevant_checks
            if c.status in {"passed", "failed", "consistent", "inconsistent"}
        ]
        if task_type == "analytical_qa" and len({kind for _, kind in periods}) > 1:
            operation_issue("incompatible_period", "Comparison requires matching period types")
        if task_type == "accounting_analysis" and len(periods) > 1 and not completed_checks:
            operation_issue(
                "incompatible_period", "Cross-period/endpoint alignment requires a relevant check"
            )
        if require_check and not completed_checks:
            operation_issue("unsupported_rule", "Requested check unavailable or lacks inputs")
        if any(i.decision == "conflicted" for i in items):
            decision = "conflicted"
        elif operation_issues or len(available) != len(items) or not items:
            decision = "insufficient"
    elif missing or len(available) != len(items):
        decision = (
            "usable_with_caveat"
            if available
            else "conflicted"
            if any(i.decision == "conflicted" for i in items)
            else "insufficient"
        )
    if not items:
        decision = "insufficient"
    if caveats and decision == "usable":
        decision = "usable_with_caveat"
    return QualityAssessment(
        task_type=task_type,
        decision=decision,
        items=items,
        issues=operation_issues,
        caveats=caveats,
        summary_counts=dict(Counter(i.decision for i in items)),
        reason_counts=dict(
            Counter(i.code for item in items for i in item.issues)
            + Counter(i.code for i in operation_issues)
        ),
        arithmetic_annotations=[c.model_copy(deep=True) for c in arithmetic_checks],
        relationship_annotations=[c.model_copy(deep=True) for c in relationship_checks],
    )


def evidence_from_automated_records(records: Iterable[dict]) -> list[AssessableEvidence]:
    """Consume run_automated_pdf records after image-bound validation, including raw rows.

    Mapping-only failures can be usable without becoming accepted_extraction.
    Structural/reading/binding errors remain blocking. No bbox is invented.
    """
    evidence = []
    for record in records:
        payload = ExtractedPage.model_validate(record["response"]["output"]["payload"])
        identity = RawPageIdentity.model_validate(record["source"]["page"])
        anchor = SourceAnchor(page=identity, status="uncertain")

        def ref(pointer, anchor=anchor):
            return FinancialSourceReference(anchor=anchor, source_pointer=pointer)

        context = resolve_financial_context(
            [
                ContextEvidence(raw_text=t, provenance=[ref(f"/context/{i}")])
                for i, t in enumerate(payload.context)
            ]
        )
        for index, raw in enumerate(record["extraction"]["links"]):
            link = AutomatedLink.model_validate_json(json.dumps(raw))
            period_text = link.raw_header or ""
            if payload.statement_type == "B01" and re.fullmatch(r"\d{2}/\d{2}/\d{4}", period_text):
                period_text = f"Tại ngày {period_text}"
            period = resolve_financial_context(
                [
                    ContextEvidence(
                        raw_text=period_text, provenance=[ref(f"/tables/{link.table}/headers")]
                    )
                ]
            )
            refs = [ref(f"/context/{i}") for i in range(len(payload.context))]
            table = payload.tables[link.table]
            refs.extend(
                ref(f"/tables/{link.table}/headers/{i}")
                for i, h in enumerate(table.headers)
                if h.column == link.column
            )
            refs.extend(
                ref(f"/tables/{link.table}/cells/{i}")
                for i, c in enumerate(table.cells)
                if c.row == link.row
                and c.column in {link.column, table.label_column, table.code_column}
            )
            result = link.result or FinancialNormalizationResult(
                contract_version="financial_normalization_v1",
                value=FinancialValue(
                    raw_value=link.raw_value or "",
                    normalized_value=parse_vietnamese_number(link.raw_value or ""),
                    unit=context.context.currency,
                    status="resolved",
                ),
                context=period.context.model_copy(
                    update=dict(
                        statement_type=payload.statement_type,
                        raw_item_label=link.raw_label,
                        currency=context.context.currency,
                        scale=context.context.scale,
                        reporting_scope=context.context.reporting_scope,
                    )
                ),
                provenance=refs,
            )
            nonblocking = {
                "unsupported_label_or_statement",
                "unit_conflict_or_unresolved",
                "period_unresolved",
                "numeric_unresolved",
                "missing_or_uncertain_cell",
            }
            errors = [
                i for i in [*record["extraction"]["issues"], *link.issues] if i not in nonblocking
            ]
            # Missing code is allowed when the label identifies the item. Other
            # uncertain selected cells must still block raw fallback.
            selected = [
                c
                for c in [*table.headers, *table.cells]
                if (
                    c.row == link.row
                    and c.column
                    in {
                        link.column,
                        table.label_column,
                        table.code_column
                        if not (link.raw_label or "").strip()
                        else table.label_column,
                    }
                )
                or c in table.headers
                and c.column == link.column
            ]
            if any(c.reading != "observed" for c in selected):
                errors.append("uncertain_reading")
            if len({c.value.model_dump_json() for c in context.unit.candidates}) > 1:
                errors.append("unit_conflict")
            evidence.append(
                AssessableEvidence(
                    evidence_id=f"{identity.source_ref or identity.image}/page/{identity.page}/link/{index}",
                    extraction=result.model_copy(deep=True),
                    canonical_item_id=link.canonical_item_id,
                    source_item_code=link.source_item_code,
                    raw_header=link.raw_header,
                    extraction_issues=errors,
                    source_metadata=deepcopy(
                        {
                            "source": record["source"],
                            "provenance": record.get("provenance"),
                            "model": record["response"].get("provenance"),
                            "request_id": record["response"].get("request_id"),
                        }
                    ),
                )
            )
    return evidence


def assess_automated_records(records: Iterable[dict], task_type: TaskType = "direct_qa", **kwargs):
    return assess_evidence_for_task(evidence_from_automated_records(records), task_type, **kwargs)
