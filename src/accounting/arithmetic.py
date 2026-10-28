"""Same-page arithmetic annotations; extraction remains independently usable."""

import json
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import Field, field_validator
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
)

from .automated_extraction import AutomatedLink
from .contracts import (
    ExactDecimal,
    FinancialModel,
    FinancialNormalizationResult,
    _require_exact_decimal,
)


class TolerancePolicy(FinancialModel):
    """Absolute tolerance in the displayed unit; caller must supply its basis."""

    absolute: ExactDecimal = Field(ge=0)
    basis: str = Field(min_length=1)

    _exact = field_validator("absolute", mode="before")(_require_exact_decimal)


@dataclass(frozen=True)
class ArithmeticRule:
    rule_id: str
    statement_type: Literal["B01", "B02", "B03"]
    description: str
    result_item_id: str
    operands: tuple[tuple[str, Literal[1, -1]], ...]
    period_types: tuple[str, ...]
    basis: str
    unavailable_reason: str | None = None


# Unavailable IDs reserve names only; they do not extend ITEM_CATALOG or map labels.
ARITHMETIC_RULES = (
    ArithmeticRule(
        "b01.total_assets",
        "B01",
        "Tổng tài sản = ngắn hạn + dài hạn",
        "b01.total_assets",
        (("b01.current_assets", 1), ("b01.noncurrent_assets", 1)),
        ("as_of",),
        "Ứng viên task M2-05; BBS2025/page5 mã270/100/200",
        "catalog_missing:b01.current_assets,b01.noncurrent_assets",
    ),
    ArithmeticRule(
        "b01.total_funding",
        "B01",
        "Tổng nguồn vốn = nợ phải trả + vốn chủ sở hữu",
        "b01.total_funding",
        (("b01.liabilities", 1), ("b01.equity", 1)),
        ("as_of",),
        "Ứng viên task M2-05; chưa có trang nguồn vốn trong pilot5/7/8",
        "catalog_and_source_missing:b01.total_funding,b01.liabilities,b01.equity",
    ),
    ArithmeticRule(
        "b02.gross_profit",
        "B02",
        "Lợi nhuận gộp = doanh thu thuần - giá vốn",
        "b02.gross_profit",
        (("b02.net_revenue", 1), ("b02.cost_of_sales", -1)),
        ("fiscal_year",),
        "Task M2-05; ảnh BBS2025/page7 mã20 =10 -11; giá vốn in dương; VND",
    ),
    ArithmeticRule(
        "b02.net_revenue",
        "B02",
        "Doanh thu thuần = doanh thu bán hàng - giảm trừ",
        "b02.net_revenue",
        (("b02.sales_revenue", 1), ("b02.revenue_deductions", -1)),
        ("fiscal_year",),
        "Ứng viên task M2-05; BBS2025/page7 mã10/01/02; dấu gạch không là zero",
        "catalog_missing:b02.sales_revenue,b02.revenue_deductions;deductions_not_numeric",
    ),
    ArithmeticRule(
        "b03.net_cash_flow",
        "B03",
        "Lưu chuyển thuần = HĐKD + HĐĐT + HĐTC",
        "b03.net_cash_flow",
        (
            ("b03.operating_cash_flow", 1),
            ("b03.investing_cash_flow", 1),
            ("b03.financing_cash_flow", 1),
        ),
        ("fiscal_year",),
        "Ứng viên task M2-05; BBS2025/page8 mã50/20/30/40; ngoặc là âm",
        "catalog_missing:b03.net_cash_flow",
    ),
)


class ArithmeticInput(FinancialModel):
    item_id: str
    role: Literal["reported", "operand"]
    sign: Literal[1, -1]
    extraction: FinancialNormalizationResult
    automated_link: AutomatedLink | None = None


class ArithmeticCheck(FinancialModel):
    rule_id: str
    statement_type: str
    period: str | None
    period_type: str | None
    reporting_scope: str | None
    unit: str | None = None
    scale: ExactDecimal | None = None
    status: Literal["passed", "failed", "insufficient_data", "not_applicable"]
    reported_value: ExactDecimal | None = None
    computed_value: ExactDecimal | None = None
    difference: ExactDecimal | None = None
    tolerance: ExactDecimal
    tolerance_basis: str
    formula_basis: str
    source_pages: list[RawPageIdentity] = Field(default_factory=list)
    inputs: list[ArithmeticInput] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False

    _exact = field_validator(
        "scale", "reported_value", "computed_value", "difference", "tolerance", mode="before"
    )(_require_exact_decimal)


def _source_key(result: FinancialNormalizationResult) -> tuple[str, ...]:
    # Exact page identity includes source_ref and image hash. Never group by year/symbol alone.
    return tuple(sorted({ref.anchor.page.model_dump_json() for ref in result.provenance}))


def evaluate_arithmetic_rules(
    values: Iterable[FinancialNormalizationResult | AutomatedLink],
    rules: Iterable[ArithmeticRule] = ARITHMETIC_RULES,
    *,
    tolerance_policy: TolerancePolicy | None = None,
) -> list[ArithmeticCheck]:
    """Evaluate per statement/period/type/scope/exact source-page context.

    No conversion, inferred zero, deduplication, mutation or extraction quality gate.
    Unavailable registry entries return insufficient_data, not accounting failures.
    """
    policy = tolerance_policy or TolerancePolicy(absolute=Decimal(0), basis="exact_decimal")
    groups: dict[tuple, list[tuple[FinancialNormalizationResult, AutomatedLink | None]]] = {}
    for value in values:
        link = value if isinstance(value, AutomatedLink) else None
        if link is not None:
            if link.status != "accepted_extraction" or link.result is None:
                continue
            result = link.result
        else:
            result = value
        context = result.context
        key = (
            context.statement_type,
            context.period,
            context.period_type,
            context.reporting_scope,
            _source_key(result),
        )
        groups.setdefault(key, []).append((result, link))

    checks = []
    for rule in rules:
        matching = [(key, rows) for key, rows in groups.items() if key[0] == rule.statement_type]
        if not matching:
            checks.append(
                ArithmeticCheck(
                    rule_id=rule.rule_id,
                    statement_type=rule.statement_type,
                    period=None,
                    period_type=None,
                    reporting_scope=None,
                    status="not_applicable",
                    tolerance=policy.absolute,
                    tolerance_basis=policy.basis,
                    formula_basis=rule.basis,
                    issues=["statement_not_present"],
                )
            )
        for key, rows in matching:
            check = ArithmeticCheck(
                rule_id=rule.rule_id,
                statement_type=rule.statement_type,
                period=key[1],
                period_type=key[2],
                reporting_scope=key[3],
                status="insufficient_data",
                tolerance=policy.absolute,
                tolerance_basis=policy.basis,
                formula_basis=rule.basis,
                source_pages=[RawPageIdentity.model_validate_json(page) for page in key[4]],
            )
            checks.append(check)
            if key[2] is not None and key[2] not in rule.period_types:
                check.status = "not_applicable"
                check.issues.append("period_type_not_applicable")
                continue
            if not key[1] or not key[2]:
                check.issues.append("period_missing")
            if not key[4]:
                check.issues.append("provenance_missing")
            elif len(key[4]) != 1:
                check.issues.append("source_page_context_ambiguous")
            if rule.unavailable_reason:
                check.issues.append(rule.unavailable_reason)
            for item_id, role, sign in [
                (rule.result_item_id, "reported", 1),
                *((item, "operand", sign) for item, sign in rule.operands),
            ]:
                found = [(r, link) for r, link in rows if r.context.mapped_item_code == item_id]
                if not found:
                    check.missing_inputs.append(item_id)
                if len(found) > 1:
                    check.issues.append(f"duplicate_item:{item_id}")
                if role == "reported" and len(found) == 1:
                    check.reported_value = found[0][0].value.normalized_value
                for result, link in found:
                    check.inputs.append(
                        ArithmeticInput(
                            item_id=item_id,
                            role=role,
                            sign=sign,
                            extraction=result.model_copy(deep=True),
                            automated_link=link.model_copy(deep=True) if link else None,
                        )
                    )
                    if link and link.canonical_item_id != item_id:
                        check.issues.append(f"link_item_conflict:{item_id}")
                    if result.value.status != "resolved" or result.value.normalized_value is None:
                        check.issues.append(f"value_unresolved:{item_id}")
                    if not result.provenance:
                        check.issues.append(f"provenance_missing:{item_id}")

            units = {i.extraction.value.unit for i in check.inputs}
            currencies = {i.extraction.context.currency for i in check.inputs}
            scales = {i.extraction.context.scale for i in check.inputs}
            if len(units) != 1 or None in units or "" in units:
                check.issues.append("unit_missing_or_conflict")
            else:
                check.unit = next(iter(units))
            if any(c is not None and c != check.unit for c in currencies):
                check.issues.append("currency_conflict")
            if len(scales) != 1 or None in scales or any(s is not None and s <= 0 for s in scales):
                check.issues.append("scale_missing_or_conflict")
            else:
                check.scale = next(iter(scales))
            if check.missing_inputs or check.issues:
                continue

            numbers = [i.extraction.value.normalized_value for i in check.inputs]
            # Precision covers every aligned digit plus carry and subtraction, even above 28 digits.
            with localcontext() as ctx:
                ctx.prec = max(
                    28,
                    max(n.adjusted() for n in numbers)
                    - min(n.as_tuple().exponent for n in numbers)
                    + len(str(len(numbers)))
                    + 3,
                )
                check.reported_value = numbers[0]
                check.computed_value = sum(
                    (i.extraction.value.normalized_value * i.sign for i in check.inputs[1:]),
                    Decimal(0),
                )
                check.difference = check.computed_value - check.reported_value
                check.status = "passed" if abs(check.difference) <= policy.absolute else "failed"
    return checks


def evaluate_automated_records(records: Iterable[dict]) -> list[dict]:
    """Annotate validated run_automated_pdf records, retaining outer provenance.

    Caller revalidates PDF-bound cache through run_automated_pdf before using this adapter.
    This adapter never calls a model or modifies the records/extraction output.
    """
    output = []
    for record in records:
        extraction = record["extraction"]
        statement = extraction.get("statement_type")
        links = [
            AutomatedLink.model_validate_json(json.dumps(link)) for link in extraction["links"]
        ]
        checks = evaluate_arithmetic_rules(
            links, [rule for rule in ARITHMETIC_RULES if rule.statement_type == statement]
        )
        # The record identifies a statement even when none of its links is usable.
        for check in checks:
            if check.issues == ["statement_not_present"]:
                check.status = "insufficient_data"
                check.issues = ["no_accepted_extractions"]
        output.append(
            dict(
                source=deepcopy(record["source"]),
                provenance=deepcopy(record["provenance"]),
                model=deepcopy(extraction.get("model")),
                request_id=extraction.get("request_id"),
                checks=[check.model_dump(mode="json") for check in checks],
            )
        )
    return output
