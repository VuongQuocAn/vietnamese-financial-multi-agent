"""M4 bounded Decimal executor; eligibility luôn lấy từ production catalog."""

from decimal import ROUND_HALF_EVEN, Context, Decimal, DecimalException, localcontext
from typing import Literal

from pydantic import Field, ValidationError

from ..accounting.contracts import FinancialContext, FinancialModel
from ..evidence.contracts import Identity, ObservationIdentity
from ..evidence.preparation_policy import FormulaExecutionApproval, PreparedFormulaPolicy
from ..evidence.snapshots import SnapshotCatalog
from .financial_retrieval import (
    FinancialMetricMatch,
    FinancialRetrievalTools,
    GetFinancialMetricRequest,
)


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
