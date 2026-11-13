"""M4 bounded Decimal executor; eligibility luôn lấy từ production catalog."""

from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialContext, FinancialModel
from ..evidence.contracts import Identity, ObservationIdentity, assess_fact_consistency
from ..evidence.preparation_policy import FormulaExecutionApproval, PreparedFormulaPolicy
from ..evidence.retrieval import RetrievalReference
from ..evidence.snapshots import SnapshotCatalog
from .financial_retrieval import (
    FinancialMetricMatch,
    FinancialRetrievalTools,
    GetFinancialFactRequest,
    GetFinancialMetricRequest,
)


class DynamicOperation(FinancialModel):
    operation_id: str = Field(min_length=1, max_length=80)
    operator: Literal[
        "add",
        "subtract",
        "multiply",
        "divide",
        "relative_difference",
        "percentage_change",
        "ratio",
        "greater",
        "less",
        "equal",
        "sum",
        "mean",
    ]
    inputs: list[str] = Field(min_length=2, max_length=16)
    period_relation: Literal["same", "across_periods"] = "same"


class DynamicOperand(FinancialModel):
    reference: RetrievalReference
    value: str
    unit: str
    scale: str
    period: str
    company_id: str
    document_id: str
    snapshot_id: str


class DynamicStep(FinancialModel):
    operation: DynamicOperation
    operands: list[str]
    result: str
    unit: str
    periods: list[str]
    rounding: Literal["Decimal34_HALF_EVEN; display_2dp"] = "Decimal34_HALF_EVEN; display_2dp"


class DynamicCalculation(FinancialModel):
    """Request-local arithmetic proof; never an approved accounting metric."""

    operands: dict[str, DynamicOperand]
    steps: list[DynamicStep]
    standard_metric: Literal[False] = False


def execute_dynamic(operands: dict[str, DynamicOperand], operations: list[DynamicOperation]):
    """Shared bounded Decimal interpreter. Inputs must be independently grounded by caller.

    M5 produces candidates; M4/M6 hydrate exact source identities before replay.
    No constants, Python expressions, implicit period mixing or unit invention.
    """
    if not operands or len(operands) > 16 or not operations or len(operations) > 12:
        raise ValueError("dynamic_graph_bounds")
    contexts = {(o.company_id, o.document_id, o.snapshot_id) for o in operands.values()}
    if len(contexts) != 1 or any(not all(c) for c in contexts):
        raise ValueError("dynamic_source_context_mismatch")
    values, steps = {}, []
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        for key, operand in operands.items():
            value, scale = Decimal(operand.value), Decimal(operand.scale)
            if not value.is_finite() or not scale.is_finite() or scale <= 0:
                raise ValueError("dynamic_non_finite_or_scale")
            if not operand.period or not operand.unit or operand.reference.kind != "fact":
                raise ValueError("dynamic_operand_identity_missing")
            values[key] = (value * scale, operand.unit, {operand.period}, {key})
        for operation in operations:
            key, op = operation.operation_id, operation.operator
            if key in values or any(i not in values for i in operation.inputs):
                raise ValueError("dynamic_dependency_invalid")
            if op not in {"sum", "mean"} and len(operation.inputs) != 2:
                raise ValueError("dynamic_arity_invalid")
            args = [values[i] for i in operation.inputs]
            units = {a[1] for a in args}
            periods = set().union(*(a[2] for a in args))
            sources = set().union(*(a[3] for a in args))
            if len(periods) > 1 and operation.period_relation != "across_periods":
                raise ValueError("dynamic_period_mismatch")
            if len(units) != 1 and op != "multiply":
                raise ValueError("dynamic_unit_mismatch")
            if "boolean" in units:
                raise ValueError("dynamic_boolean_operand")
            a, b = args[0][0], args[1][0]
            unit = args[0][1]
            if op in {"divide", "ratio", "relative_difference", "percentage_change"}:
                if b == 0:
                    raise ValueError("dynamic_zero_denominator")
                value = (a - b) / b if op in {"relative_difference", "percentage_change"} else a / b
                unit = "percent" if op == "percentage_change" else "ratio"
                if unit == "percent":
                    value *= 100
            elif op == "multiply":
                if not units & {"ratio"} or units - {"ratio"} and len(units) > 2:
                    raise ValueError("dynamic_multiplication_units")
                value = a * b
                unit = next(iter(units - {"ratio"}), "ratio")
            elif op in {"greater", "less", "equal"}:
                value = Decimal(a > b if op == "greater" else a < b if op == "less" else a == b)
                unit = "boolean"
            else:
                value = a - b if op == "subtract" else sum((arg[0] for arg in args), Decimal(0))
                if op == "mean":
                    value /= len(args)
            if not value.is_finite():
                raise ValueError("dynamic_result_non_finite")
            values[key] = (value, unit, periods, sources)
            steps.append(
                DynamicStep(
                    operation=operation,
                    operands=sorted(sources),
                    result=str(value),
                    unit=unit,
                    periods=sorted(periods),
                )
            )
    return DynamicCalculation(operands=operands, steps=steps)


def render_dynamic(calculation, labels):
    """Public arithmetic trace, with evidence labels rather than operation IDs."""
    values = {
        key: labels[key] + f" (kỳ {operand.period})"
        for key, operand in calculation.operands.items()
    }
    result = []
    symbols = {
        "add": "+",
        "sum": "+",
        "subtract": "−",
        "multiply": "×",
        "divide": "/",
        "ratio": "/",
        "greater": ">",
        "less": "<",
        "equal": "=",
    }
    for index, step in enumerate(calculation.steps, 1):
        operation = step.operation
        args = [values[key] for key in operation.inputs]
        op = operation.operator
        expression = f" {symbols.get(op, ', ')} ".join(args)
        if op in {"relative_difference", "percentage_change"}:
            expression = f"({args[0]} − {args[1]}) / {args[1]}" + (
                " × 100" if op == "percentage_change" else ""
            )
        elif op == "mean":
            expression = "Trung bình của " + ", ".join(args)
        value = "đúng" if step.result == "1" else "sai"
        if step.unit != "boolean":
            with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
                value = format(Decimal(step.result).quantize(Decimal("0.01")), ",f").translate(
                    str.maketrans({",": ".", ".": ","})
                )
            value += " " + {"ratio": "lần (tỷ số đối chiếu)", "percent": "%"}.get(
                step.unit, step.unit
            )
        result.append(f"{expression}: {value}.")
        values[operation.operation_id] = f"kết quả phép tính thứ {index}"
    return " ".join(result)


class CalculateFinancialMetricRequest(FinancialModel):
    tool: Literal["calculate_financial_metric"] = "calculate_financial_metric"
    metric_id: Identity
    document_id: Identity | None = None
    snapshot_id: Identity | None = None


class CalculationOperand(FinancialModel):
    role: Identity
    observation: ObservationIdentity
    source_fact_node_id: Identity
    value: str
    unit: str
    company_id: Identity
    context: FinancialContext


class CalculationTrace(FinancialModel):
    version: Literal["financial_calculation_trace_v1"] = "financial_calculation_trace_v1"
    formula: PreparedFormulaPolicy
    approval: FormulaExecutionApproval
    operands: list[CalculationOperand]
    # Decimal34 intermediate strings; không quantize operands/intermediates.
    numerator: str
    ratio: str
    scaled_value: str


class FinancialCalculationResponse(FinancialModel):
    version: Literal["financial_calculation_v1"] = "financial_calculation_v1"
    request: CalculateFinancialMetricRequest
    status: Literal["computed", "blocked", "invalid_inputs", "unavailable", "ambiguous"]
    metric_id: Identity
    document_id: Identity | None = None
    snapshot_id: Identity | None = None
    formula_id: Identity | None = None
    formula_version: Identity | None = None
    formula_digest: Identity | None = None
    result: str | None = None
    output_unit: Literal["percent"] = "percent"
    # Full M4-02 payload giữ closure, SourceReviews, basis, MetricLineage và citations.
    evidence: FinancialMetricMatch | None = None
    trace: CalculationTrace | None = None
    reasons: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False


def _arithmetic(formula_id, values):
    """Chỉ ba approved operations, không parse/eval expression hoặc chuyển units."""
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        if formula_id == "gross_margin":
            numerator, denominator = values["gross_profit"], values["revenue"]
        elif formula_id == "debt_to_assets":
            numerator, denominator = values["liabilities"], values["assets"]
        elif formula_id == "revenue_yoy":
            numerator = values["current_revenue"] - values["prior_revenue"]
            denominator = values["prior_revenue"]
        else:
            raise ValueError("unsupported_formula")
        ratio = numerator / denominator
        scaled = ratio * Decimal("100")
        result = scaled.quantize(Decimal("0.01"))
        if not result.is_finite():
            raise ValueError("arithmetic_result_non_finite")
        return str(result), str(numerator), str(ratio), str(scaled)


class FinancialCalculator:
    """Read-only execution trên catalog đã hydrate; không nhận caller eligibility.

    Giống M4-02, inputs/outputs được copy; restart hydrate cùng persisted records
    rồi gọi lại exact request để replay qua production gates và so trace/result.
    """

    def __init__(self, catalog: SnapshotCatalog):
        from ..evidence.snapshots import isolated_catalog

        self._catalog = isolated_catalog(catalog)
        self._retrieval = FinancialRetrievalTools(self._catalog)

    def calculate_dynamic(self, references, operations, *, independent_branches=False):
        """Hydrate operands from canonical sources, never caller-provided values."""
        operands, contexts = {}, {}
        for key, reference in references.items():
            if reference.kind != "fact" or reference.observation is None:
                raise ValueError("dynamic_fact_reference_required")
            identity = reference.observation
            response = self._retrieval.get_financial_fact(
                GetFinancialFactRequest(
                    document_id=identity.document_id,
                    snapshot_id=identity.snapshot_id,
                    local_observation_id=identity.local_id,
                )
            )
            if response.status != "found" or len(response.matches) != 1:
                raise ValueError("dynamic_operand_unavailable_or_conflicting")
            match = response.matches[0]
            fact = match.record
            consistency = assess_fact_consistency(fact)
            if (
                consistency.status == "inconsistent"
                or not fact.context.period_type
                or not fact.context.currency
                or fact.context.currency != fact.value.unit
            ):
                raise ValueError("dynamic_operand_context_or_source_invalid")
            peers = [
                f
                for f in self._catalog.facts
                if (
                    f.document_id,
                    f.snapshot_id,
                    f.company_id,
                    f.canonical_item_id,
                    f.context.period,
                    f.context.period_type,
                    f.context.reporting_scope,
                    f.value.unit,
                )
                == (
                    fact.document_id,
                    fact.snapshot_id,
                    fact.company_id,
                    fact.canonical_item_id,
                    fact.context.period,
                    fact.context.period_type,
                    fact.context.reporting_scope,
                    fact.value.unit,
                )
                and f.value.normalized_value is not None
                and f.context.scale is not None
            ]
            if len({f.value.normalized_value * f.context.scale for f in peers}) > 1:
                raise ValueError("dynamic_conflicting_source_values")
            decisions = [q.decision for q in fact.quality_context if q.task_type == "direct_qa"]
            if (
                match.reference != reference
                or match.display_status == "blocked"
                or fact.value.status != "resolved"
                or not decisions
                or any(d in {"insufficient", "conflicted"} for d in decisions)
                or not match.citations
                or match.source_review.status != "found"
                or not match.source_review.matches
                or any(
                    r.status in {"source_missing", "source_inconsistent"}
                    for r in match.source_review.matches
                )
            ):
                raise ValueError("dynamic_operand_unverified")
            contexts[key] = {
                (fact.context.period_type, fact.context.reporting_scope, fact.context.currency)
            }
            operands[key] = DynamicOperand(
                reference=reference,
                value=str(fact.value.normalized_value),
                unit=fact.value.unit,
                scale=str(fact.context.scale),
                period=fact.context.period,
                company_id=fact.company_id,
                document_id=fact.document_id,
                snapshot_id=fact.snapshot_id,
            )
        if independent_branches:
            for operation in operations:
                if any(key not in contexts for key in operation.inputs):
                    raise ValueError("dynamic_dependency_invalid")
                context = set().union(*(contexts[key] for key in operation.inputs))
                if len(context) != 1:
                    raise ValueError("dynamic_reporting_context_mismatch")
                contexts[operation.operation_id] = context
        elif len(set().union(*contexts.values())) != 1:
            raise ValueError("dynamic_reporting_context_mismatch")
        # Across-period operations are explicit and same-filing. Stock/flow mixing
        # and cross-document accounting comparability remain unavailable.
        return execute_dynamic(operands, operations)

    def _numeric_contract_errors(self, request):
        # Mutable Pydantic records có thể bị sửa sau validation. Chặn malformed
        # Decimals trước khi M4-01 so sánh guards (NaN/sNaN có thể raise).
        metrics = [
            m
            for m in self._catalog.metrics
            if m.metric_id == request.metric_id
            and (request.document_id is None or m.request.document_id == request.document_id)
            and (request.snapshot_id is None or m.request.snapshot_id == request.snapshot_id)
        ]
        if len(metrics) != 1:
            return []
        errors = []
        for binding in metrics[0].operands:
            for fact in self._catalog.facts:
                if (
                    binding.observation is None
                    or fact.observation_identity() != binding.observation
                ):
                    continue
                for name, value in (
                    ("value", fact.value.normalized_value),
                    ("scale", fact.context.scale),
                ):
                    if value is not None and not isinstance(value, Decimal):
                        errors.append(f"{binding.role}:{name}_invalid_decimal")
                    elif value is not None and not value.is_finite():
                        errors.append(f"{binding.role}:{name}_non_finite")
        return sorted(set(errors))

    def calculate_financial_metric(
        self, request: CalculateFinancialMetricRequest
    ) -> FinancialCalculationResponse:
        request = CalculateFinancialMetricRequest.model_validate_json(request.model_dump_json())
        response = FinancialCalculationResponse(
            request=request,
            status="unavailable",
            metric_id=request.metric_id,
            document_id=request.document_id,
            snapshot_id=request.snapshot_id,
        )
        errors = self._numeric_contract_errors(request)
        if errors:
            response.status, response.reasons = "invalid_inputs", errors
            return response
        try:
            retrieved = self._retrieval.get_financial_metric(
                GetFinancialMetricRequest(**request.model_dump(exclude={"tool"}))
            )
        except DecimalException as error:
            response.status = "invalid_inputs"
            response.reasons = ["eligibility_arithmetic_" + type(error).__name__]
            return response
        except (ValidationError, ValueError, TypeError):
            response.status, response.reasons = "invalid_inputs", ["invalid_evidence_contract"]
            return response
        response.caveats = retrieved.caveats
        if retrieved.status != "found" or len(retrieved.matches) != 1:
            response.status = (
                "ambiguous"
                if retrieved.status == "ambiguous" or len(retrieved.matches) > 1
                else "blocked"
                if retrieved.status == "conflicted"
                else "unavailable"
            )
            response.reasons = retrieved.reasons or ["metric_not_uniquely_available"]
            return response
        match = retrieved.matches[0]
        response.evidence = match
        response.document_id = match.record.request.document_id
        response.snapshot_id = match.record.request.snapshot_id
        response.formula_id = match.record.definition.name
        readiness = match.closure.readiness or {}
        approved = readiness.get("formula_policy", {})
        response.formula_version = approved.get("version")
        response.formula_digest = approved.get("definition_sha256")
        if match.closure.status != "closed" or not match.closure.calculation_eligible:
            response.status = "blocked"
            response.reasons = sorted(
                set(
                    ["metric_not_calculation_eligible"]
                    + readiness.get("eligibility_blockers", [])
                    + [i.code for i in match.closure.issues]
                )
            )
            return response
        # Approval/policy có trong isolated catalog, không lấy definition từ request.
        policy = next(p for p in self._catalog.policies if p.formula_id == response.formula_id)
        approval = next(
            a for a in self._catalog.formula_approvals if a.formula_id == response.formula_id
        )
        operands = [
            CalculationOperand(
                role=o.binding.role,
                observation=o.binding.observation,
                source_fact_node_id=o.binding.source_fact_node_id,
                value=str(o.facts.matches[0].record.value.normalized_value),
                unit=o.facts.matches[0].record.value.unit,
                company_id=o.facts.matches[0].record.company_id,
                context=o.facts.matches[0].record.context.model_copy(deep=True),
            )
            for o in match.operands
        ]
        try:
            value, numerator, ratio, scaled = _arithmetic(
                policy.formula_id, {o.role: Decimal(o.value) for o in operands}
            )
        except (DecimalException, ValueError) as error:
            response.status = "invalid_inputs"
            response.reasons = ["arithmetic_" + type(error).__name__]
            return response
        response.trace = CalculationTrace(
            formula=policy.model_copy(deep=True),
            approval=approval.model_copy(deep=True),
            operands=operands,
            numerator=numerator,
            ratio=ratio,
            scaled_value=scaled,
        )
        response.result, response.status = value, "computed"
        response.caveats = sorted(
            set(
                [c for c in response.caveats if c != "calculation_eligible_does_not_mean_computed"]
                + ["computed_does_not_mean_financial_fact_verified"]
            )
        )
        return response.model_copy(deep=True)
