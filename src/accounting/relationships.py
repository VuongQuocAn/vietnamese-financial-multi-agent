"""Optional document-level accounting annotations; never an extraction quality gate."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import Field, field_validator

from .arithmetic import TolerancePolicy
from .automated_extraction import AutomatedLink
from .context_resolution import ContextEvidence, resolve_financial_context
from .contracts import (
    ExactDecimal,
    FinancialModel,
    FinancialNormalizationResult,
    _require_exact_decimal,
)


class RelationshipValue(FinancialModel):
    """Caller supplies proven PDF metadata and, for annual flows, explicit end-date evidence."""

    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction: FinancialNormalizationResult
    automated_link: AutomatedLink | None = None
    period_end_evidence: ContextEvidence | None = None
    source_metadata: dict = Field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipItem:
    item_id: str
    statement_type: str
    source_code: str | None = None
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipRule:
    rule_id: str
    description: str
    reported: RelationshipItem
    operands: tuple[RelationshipItem, ...]
    basis: str
    unavailable_reason: str | None = None

    @property
    def statements(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(i.statement_type for i in (self.reported, *self.operands)))


RELATIONSHIP_RULES = (
    RelationshipRule(
        "b01_b03.closing_cash",
        "Tiền và tương đương tiền B01 = tiền cuối kỳ B03 tại cùng ngày",
        RelationshipItem(
            "b01.cash_equivalents", "B01", "110", ("I. Tiền và các khoản tương đương tiền",)
        ),
        (
            RelationshipItem(
                "b03.closing_cash", "B03", "70", ("Tiền và tương đương tiền cuối năm",)
            ),
        ),
        "Task M2-06 C; đối chiếu mẫu BBS2025 trang5 mã110/trang8 mã70; "
        "chỉ so sánh số dư cuối kỳ có cùng ngày/scope/currency/unit/scale",
    ),
    RelationshipRule(
        "b01.balance_identity",
        "Tổng tài sản = tổng nguồn vốn",
        RelationshipItem("b01.total_assets", "B01"),
        (RelationshipItem("b01.total_funding", "B01"),),
        "Task M2-06 A; chưa xác nhận trang nguồn vốn trong bounded pilot",
        "source_unconfirmed:b01.total_funding;funding_page_not_in_pilot",
    ),
    RelationshipRule(
        "b01_b02.retained_earnings",
        "Lợi nhuận giữ lại cần đầy đủ phân phối và điều chỉnh để đối chiếu B02",
        RelationshipItem("b01.retained_earnings", "B01"),
        (RelationshipItem("b02.profit_after_tax", "B02"),),
        "Task M2-06 B; KHÔNG áp dụng đẳng thức trực tiếp lợi nhuận và biến động giữ lại",
        "adjustments_and_distributions_missing;no_direct_equality",
    ),
    RelationshipRule(
        "b03.cash_reconciliation",
        "Tiền cuối kỳ = đầu kỳ + lưu chuyển thuần + ảnh hưởng tỷ giá",
        RelationshipItem("b03.closing_cash", "B03"),
        (
            RelationshipItem("b03.opening_cash", "B03"),
            RelationshipItem("b03.net_cash_flow", "B03"),
            RelationshipItem("b03.exchange_effect", "B03"),
        ),
        "Task M2-06 D; BBS2025 trang8 có mã60/50/70, không có dòng ảnh hưởng tỷ giá",
        "exchange_effect_not_present;missing_is_not_zero;source_mapping_unconfirmed",
    ),
)


class RelationshipInput(FinancialModel):
    item_id: str
    role: Literal["reported", "operand"]
    matching: Literal["canonical", "source_code"]
    value: RelationshipValue


class RelationshipCheck(FinancialModel):
    rule_id: str
    description: str
    statements: list[str]
    pdf_sha256: str | None = None
    period: str | None = None
    reporting_scope: str | None = None
    currency: str | None = None
    unit: str | None = None
    scale: ExactDecimal | None = None
    status: Literal["consistent", "inconsistent", "insufficient_data", "not_applicable"]
    reported_value: ExactDecimal | None = None
    computed_value: ExactDecimal | None = None
    difference: ExactDecimal | None = None
    tolerance: ExactDecimal
    tolerance_basis: str
    formula_basis: str
    inputs: list[RelationshipInput] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False

    _exact = field_validator(
        "scale", "reported_value", "computed_value", "difference", "tolerance", mode="before"
    )(_require_exact_decimal)


def _endpoint(value: RelationshipValue) -> tuple[str, list[str]]:
    context = value.extraction.context
    if context.period_type in {"as_of", "fiscal_year_end"} and context.period:
        try:
            return date.fromisoformat(context.period).isoformat(), []
        except ValueError:
            pass
    evidence = value.period_end_evidence
    if context.period_type == "fiscal_year" and evidence and evidence.provenance:
        resolution = resolve_financial_context(
            [
                evidence.model_copy(update={"raw_text": line})
                for line in evidence.raw_text.splitlines()
            ]
        )
        resolved = resolution.period
        endpoint = resolution.context.period
        if (
            resolved.status == "resolved"
            and resolution.context.period_type == "fiscal_year_end"
            and endpoint[:4] == context.period
            and all(
                ref.anchor.page.source_ref == f"sha256:{value.pdf_sha256}"
                for ref in evidence.provenance
            )
        ):
            return endpoint, []
    return f"unconfirmed:{context.period_type}:{context.period}", ["period_end_unconfirmed"]


def _matching(value: RelationshipValue, item: RelationshipItem) -> str | None:
    context = value.extraction.context
    if context.statement_type != item.statement_type:
        return None
    if context.mapped_item_code == item.item_id:
        return "canonical"
    # Exact approved code AND label AND statement; no fuzzy/global numeric-code match.
    link = value.automated_link
    code = link.source_item_code if link else context.mapped_item_code
    label = link.raw_label if link else context.raw_item_label
    if (
        context.mapped_item_code in {None, item.source_code}
        and item.source_code is not None
        and code == item.source_code
        and label in item.labels
    ):
        return "source_code"
    return None


def evaluate_accounting_relationships(
    values: Iterable[RelationshipValue],
    rules: Iterable[RelationshipRule] = RELATIONSHIP_RULES,
    *,
    tolerance_policy: TolerancePolicy | None = None,
) -> list[RelationshipCheck]:
    """Group by proven PDF, endpoint, exact scope/currency/unit/scale; retain each page.

    Unknown scopes only join other unknown scopes, with scope_unconfirmed caveat.
    Different known contexts produce separate insufficient checks, never cross joins.
    """
    policy = tolerance_policy or TolerancePolicy(absolute=Decimal(0), basis="exact_decimal")
    groups: dict[tuple, list[tuple[RelationshipValue, list[str]]]] = {}
    for value in values:
        result = value.extraction
        context = result.context
        endpoint, issues = _endpoint(value)
        key = (
            value.pdf_sha256,
            endpoint,
            context.reporting_scope,
            context.currency,
            result.value.unit,
            context.scale,
        )
        groups.setdefault(key, []).append((value, issues))
    checks = []
    for rule in rules:
        matching_groups = [
            (key, rows)
            for key, rows in groups.items()
            if any(v.extraction.context.statement_type in rule.statements for v, _ in rows)
        ]
        if not matching_groups:
            checks.append(
                RelationshipCheck(
                    rule_id=rule.rule_id,
                    description=rule.description,
                    statements=list(rule.statements),
                    status="not_applicable",
                    tolerance=policy.absolute,
                    tolerance_basis=policy.basis,
                    formula_basis=rule.basis,
                    issues=["statements_not_present"],
                )
            )
        for key, rows in matching_groups:
            digest, endpoint, scope, currency, unit, scale = key
            check = RelationshipCheck(
                rule_id=rule.rule_id,
                description=rule.description,
                statements=list(rule.statements),
                pdf_sha256=digest,
                period=endpoint,
                reporting_scope=scope,
                currency=currency,
                unit=unit,
                scale=scale,
                status="insufficient_data",
                tolerance=policy.absolute,
                tolerance_basis=policy.basis,
                formula_basis=rule.basis,
                caveats=["scope_unconfirmed"] if scope is None else [],
            )
            checks.append(check)
            if rule.unavailable_reason:
                check.issues.append(rule.unavailable_reason)
            if not currency or not unit or currency != unit:
                check.issues.append("currency_unit_missing_or_conflict")
            if scale is None or scale <= 0:
                check.issues.append("scale_missing_or_invalid")
            for item, role in [
                (rule.reported, "reported"),
                *((i, "operand") for i in rule.operands),
            ]:
                found = [
                    (v, issues, _matching(v, item)) for v, issues in rows if _matching(v, item)
                ]
                if not found:
                    check.missing_inputs.append(item.item_id)
                if len(found) > 1:
                    check.issues.append(f"duplicate_or_conflicting_item:{item.item_id}")
                for value, issues, method in found:
                    result = value.extraction
                    check.inputs.append(
                        RelationshipInput(
                            item_id=item.item_id,
                            role=role,
                            matching=method,
                            value=value.model_copy(deep=True),
                        )
                    )
                    check.issues.extend(issues)
                    if not result.provenance or any(
                        ref.anchor.page.source_ref != f"sha256:{digest}"
                        for ref in result.provenance
                    ):
                        check.issues.append(f"document_binding_missing_or_conflict:{item.item_id}")
                    if result.value.status != "resolved" or result.value.normalized_value is None:
                        check.issues.append(f"value_unresolved:{item.item_id}")
                    if value.automated_link and (
                        value.automated_link.status != "accepted_extraction"
                        or value.automated_link.result != result
                        or value.automated_link.canonical_item_id != result.context.mapped_item_code
                    ):
                        check.issues.append(f"link_conflict:{item.item_id}")
                    if (
                        rule.rule_id == "b01_b03.closing_cash"
                        and result.context.statement_type == "B01"
                        and result.context.period_type != "as_of"
                    ):
                        check.issues.append("balance_requires_as_of")
                    if (
                        rule.rule_id == "b01_b03.closing_cash"
                        and result.context.statement_type == "B03"
                        and result.context.period_type not in {"fiscal_year", "fiscal_year_end"}
                    ):
                        check.issues.append("cash_flow_period_type_unconfirmed")
            check.issues = list(dict.fromkeys(check.issues))
            if check.missing_inputs or check.issues:
                continue
            numbers = [i.value.extraction.value.normalized_value for i in check.inputs]
            with localcontext() as ctx:
                ctx.prec = max(
                    28,
                    max(n.adjusted() for n in numbers)
                    - min(n.as_tuple().exponent for n in numbers)
                    + len(str(len(numbers)))
                    + 3,
                )
                check.reported_value = numbers[0]
                check.computed_value = sum(numbers[1:], Decimal(0))
                check.difference = check.computed_value - check.reported_value
                check.status = (
                    "consistent" if abs(check.difference) <= policy.absolute else "inconsistent"
                )
    return checks


def evaluate_automated_relationships(
    records: Iterable[dict],
    rules: Iterable[RelationshipRule] = RELATIONSHIP_RULES,
    *,
    tolerance_policy: TolerancePolicy | None = None,
) -> list[RelationshipCheck]:
    """Consume records revalidated by run_automated_pdf; no API calls, no mutation.

    Full outer source/model/request/PDF metadata is retained per operand. Unmapped
    raw payload stays in original records for QA; this adapter consumes accepted links.
    """
    rules = tuple(rules)
    documents: dict[str, list[RelationshipValue]] = {}
    statements: dict[str, set[str]] = {}
    for record in records:
        metadata = record["provenance"]
        extraction = record["extraction"]
        digest = metadata["pdf_sha256"]
        if metadata.get("document_id") != f"sha256:{digest}":
            raise ValueError("document_metadata_conflict")
        values = documents.setdefault(digest, [])
        statements.setdefault(digest, set()).add(extraction.get("statement_type"))
        for raw_link in extraction["links"]:
            link = AutomatedLink.model_validate_json(json.dumps(raw_link))
            if link.status != "accepted_extraction" or link.result is None:
                continue
            for ref in link.result.provenance:
                page = ref.anchor.page
                if (
                    page.page != metadata["page_number"]
                    or page.image != f"sha256:{metadata['image_sha256']}"
                    or page.source_ref != metadata["document_id"]
                ):
                    raise ValueError("page_metadata_conflict")
            # Context text is taken from the same validated response, not filename/year.
            evidence = ContextEvidence(
                raw_text="\n".join(record["response"]["output"]["payload"]["context"]),
                provenance=[
                    ref.model_copy(deep=True)
                    for ref in link.result.provenance
                    if (ref.source_pointer or "").startswith("/context/")
                ],
            )
            values.append(
                RelationshipValue(
                    pdf_sha256=digest,
                    extraction=link.result,
                    automated_link=link,
                    period_end_evidence=evidence,
                    source_metadata={
                        "source": record["source"],
                        "provenance": metadata,
                        "model": extraction.get("model"),
                        "request_id": extraction.get("request_id"),
                    },
                )
            )
    output = []
    for digest, values in documents.items():
        checks = evaluate_accounting_relationships(values, rules, tolerance_policy=tolerance_policy)
        for check in checks:
            check.pdf_sha256 = digest
            if check.status == "not_applicable" and statements[digest].intersection(
                check.statements
            ):
                check.status = "insufficient_data"
                check.issues = ["no_accepted_extractions_for_relationship"]
                rule = next(rule for rule in rules if rule.rule_id == check.rule_id)
                check.missing_inputs = [i.item_id for i in (rule.reported, *rule.operands)]
        output.extend(checks)
    return output
