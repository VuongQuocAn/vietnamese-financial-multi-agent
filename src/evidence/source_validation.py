"""Snapshot-bound adapter for M2 source checks; never executes M4 analytical formulas."""

from collections.abc import Iterable
from typing import Literal

from pydantic import Field, field_validator

from ..accounting.arithmetic import (
    ARITHMETIC_RULES,
    ArithmeticRule,
    evaluate_arithmetic_rules,
)
from ..accounting.context_resolution import ContextEvidence
from ..accounting.contracts import (
    ExactDecimal,
    FinancialModel,
    FinancialNormalizationResult,
    _require_exact_decimal,
)
from ..accounting.item_mapping import ITEM_CATALOG, map_item_label
from ..accounting.relationships import (
    RELATIONSHIP_RULES,
    RelationshipRule,
    RelationshipValue,
    _endpoint,
    evaluate_accounting_relationships,
)
from .analytical_readiness import source_review_status
from .contracts import CanonicalFinancialFact, assess_fact_consistency
from .snapshots import SnapshotDescriptor


class SourceValidation(FinancialModel):
    version: Literal["source-validation-v1"] = "source-validation-v1"
    rule_id: str
    rule_version: str
    document_id: str
    snapshot_id: str
    period: str
    status: Literal["consistent", "inconsistent", "insufficient", "undetermined"]
    # Full facts retain exact observation identities, units, periods, quality and sources.
    operands: list[CanonicalFinancialFact] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    # Exact Decimal values/residual and original M2 statuses stay in the shared check.
    check: dict | None = None
    residual: ExactDecimal | None = None
    financial_fact_verified: Literal[False] = False

    _exact = field_validator("residual", mode="before")(_require_exact_decimal)


def _normalization(fact):
    return FinancialNormalizationResult(
        contract_version="financial_normalization_v1",
        value=fact.value,
        context=fact.context,
        provenance=[s.reference for s in fact.sources if s.reference],
    )


def _relationship_value(fact, descriptor):
    value = _normalization(fact)
    return RelationshipValue(
        pdf_sha256=descriptor.pdf_sha256,
        extraction=value,
        context_evidence=ContextEvidence(
            raw_text="\n".join(
                fact.source_metadata.get("unit_semantics", {}).get("raw_unit_context", [])
            ),
            provenance=[
                p for p in value.provenance if (p.source_pointer or "").startswith("/context/")
            ],
        ),
    )


def evaluate_source_validations(
    descriptor: SnapshotDescriptor,
    facts: Iterable[CanonicalFinancialFact],
    *,
    period: str,
    arithmetic_rules: Iterable[ArithmeticRule] = ARITHMETIC_RULES,
    relationship_rules: Iterable[RelationshipRule] = RELATIONSHIP_RULES,
    source_reviews=(),
) -> list[SourceValidation]:
    """Explicit document/snapshot/period only, no parent lookup or silent inheritance.

    Unknown scope allows direct arithmetic with caveat; never approves compatibility,
    preparation readiness, SourceReview or formula execution. No arithmetic is duplicated.
    """
    selected = [
        f
        for f in facts
        if (f.document_id, f.snapshot_id) == (descriptor.document_id, descriptor.snapshot_id)
    ]
    source_reviews = list(source_reviews)
    output = []
    for rule in (*arithmetic_rules, *relationship_rules):
        arithmetic = isinstance(rule, ArithmeticRule)
        items = (
            [
                (rule.result_item_id, rule.statement_type),
                *((item, rule.statement_type) for item, _ in rule.operands),
            ]
            if arithmetic
            else [(i.item_id, i.statement_type) for i in (rule.reported, *rule.operands)]
        )
        # Cross-statement joins require the existing source-backed endpoint resolver.
        rows = [
            f
            for f in selected
            if (f.canonical_item_id, f.context.statement_type) in items
            and (
                _endpoint(_relationship_value(f, descriptor))[0] == period
                if not arithmetic and len(rule.statements) > 1
                else f.context.period == period
            )
        ]
        result = SourceValidation(
            rule_id=rule.rule_id,
            rule_version=rule.version,
            document_id=descriptor.document_id,
            snapshot_id=descriptor.snapshot_id,
            period=period,
            status="insufficient",
            operands=[f.model_copy(deep=True) for f in rows],
        )
        output.append(result)
        if descriptor.document_id != "sha256:" + descriptor.pdf_sha256:
            result.reasons.append("document_hash_mismatch")
        for item, statement in items:
            found = [
                f
                for f in rows
                if (f.canonical_item_id, f.context.statement_type) == (item, statement)
            ]
            if not found:
                result.missing_inputs.append(item)
            if len(found) > 1:
                result.reasons.append(f"duplicate_canonical_candidates:{item}")
        for fact in rows:
            item = fact.canonical_item_id
            consistency = assess_fact_consistency(fact)
            review_status = source_review_status(fact, source_reviews)
            if review_status in {"source_inconsistent", "source_missing"}:
                result.reasons.append(f"{review_status}:{item}")
            elif review_status != "value_row_verified":
                result.caveats.append(f"source_unverified:{item}")
            if fact.observation_identity() is None:
                result.reasons.append(f"missing_observation_identity:{item}")
            if consistency.status == "inconsistent":
                result.reasons.extend(f"{i.code}:{item}" for i in consistency.issues)
            if not fact.sources or any(
                s.reference is None
                or s.document_id != descriptor.document_id
                or s.snapshot_id != descriptor.snapshot_id
                or s.reference.anchor.page.source_ref != descriptor.document_id
                or s.reference.anchor.page.page < 1
                or not s.reference.anchor.page.image.strip()
                or not s.reference.source_pointer
                for s in fact.sources
            ):
                result.reasons.append(f"source_binding_missing_or_conflict:{item}")
            if any(q.decision in {"insufficient", "conflicted"} for q in fact.quality_context):
                result.reasons.append(f"quality_blocked:{item}")
            for issue in fact.resolution_issues:
                if issue.code == "m2_extraction_issue":
                    result.reasons.append(f"extraction_issue:{item}:{issue.detail}")
            if fact.value.status != "resolved" or fact.value.normalized_value is None:
                result.reasons.append(f"value_unresolved:{item}")
            if fact.value.issues:
                result.reasons.extend(f"value_issue:{item}:{i}" for i in fact.value.issues)
            if fact.context.mapped_item_code != item:
                result.reasons.append(f"canonical_context_conflict:{item}")
            mapping = map_item_label(
                ContextEvidence(
                    raw_text=fact.context.raw_item_label or "",
                    provenance=[s.reference for s in fact.sources if s.reference],
                ),
                fact.context.statement_type,
                source_code=fact.source_item_code,
            )
            if mapping.status != "resolved" or mapping.canonical_item_id != item:
                result.reasons.append(f"mapping_unresolved_or_conflict:{item}")
            catalog = [r for r in ITEM_CATALOG if r.canonical_item_id == item]
            if catalog and fact.context.period_type not in catalog[0].period_types:
                result.reasons.append(f"period_type_not_applicable:{item}")
            if (
                catalog
                and catalog[0].semantic_role != "monetary_amount"
                and fact.semantic_role is not None
                and fact.semantic_role != catalog[0].semantic_role
            ):
                result.reasons.append(f"semantic_role_conflict:{item}")
            result.caveats.extend(f"{i.code}:{item}" for i in consistency.issues)
            result.caveats.extend(c for q in fact.quality_context for c in q.caveats)
            if fact.context.reporting_scope is None:
                result.caveats.append("scope_unconfirmed")
        if rule.unavailable_reason:
            result.reasons.append(rule.unavailable_reason)
        result.reasons = list(dict.fromkeys(result.reasons))
        result.caveats = list(dict.fromkeys(result.caveats))
        if result.reasons or result.missing_inputs:
            continue
        if arithmetic:
            checks = evaluate_arithmetic_rules([_normalization(f) for f in rows], [rule])
        else:
            checks = evaluate_accounting_relationships(
                [_relationship_value(f, descriptor) for f in rows],
                [rule],
            )
        if len(checks) != 1:
            result.reasons.append("operand_contexts_do_not_join")
            continue
        check = checks[0]
        result.check = check.model_dump(mode="json")
        result.residual = check.difference
        result.missing_inputs = check.missing_inputs
        result.reasons.extend(check.issues)
        result.caveats.extend(getattr(check, "caveats", []))
        result.caveats = list(dict.fromkeys(result.caveats))
        result.status = {
            "passed": "consistent",
            "failed": "inconsistent",
            "consistent": "consistent",
            "inconsistent": "inconsistent",
            "insufficient_data": "insufficient",
            "not_applicable": "undetermined",
        }[check.status]
    return output
