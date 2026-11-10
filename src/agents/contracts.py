"""M5 contracts và read-only preflight; không planner, dispatch hoặc tính toán."""

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, ValidationError, model_validator

from ..accounting.contracts import FinancialModel
from ..accounting.quality import UsageDecision
from ..evidence.contracts import Identity
from ..evidence.retrieval import EvidenceCitation, EvidenceQuery, RetrievalReference
from ..evidence.snapshots import SnapshotCatalog, SnapshotSelection
from ..tools.evidence_retrieval import (
    EvidenceToolResponse,
    FindDocumentEvidenceRequest,
    GetEvidenceAnchorRequest,
    GetEvidenceItemRequest,
    GetEvidenceSourcesRequest,
    GetMetricEvidenceLineageRequest,
)
from ..tools.financial_calculator import (
    CalculateFinancialMetricRequest,
    FinancialCalculationResponse,
)
from ..tools.financial_retrieval import (
    FinancialToolResponse,
    FindFinancialFactsRequest,
    GetFinancialFactRequest,
    GetFinancialMetricRequest,
    ListFinancialMetricsRequest,
)
from ..tools.question_understanding import QAUnderstanding

ExecutionState = Literal[
    "pending", "ready", "running", "completed", "partial", "blocked", "failed", "skipped"
]
StopCondition = Literal[
    "all_required_evidence_resolved",
    "missing_required_inputs",
    "unresolved_ambiguity",
    "conflicting_evidence",
    "unsupported_operation",
    "compatibility_gate_blocked",
    "execution_limit_reached",
]
SpecialistRole = Literal[
    "profitability", "liquidity_and_leverage", "cash_flow_and_earnings_quality"
]
RiskCode = Literal[
    "missing_evidence",
    "conflicting_evidence",
    "ambiguous_snapshot",
    "insufficient_quality",
    "reporting_scope_unresolved",
    "period_unit_mismatch",
    "formula_not_approved",
    "cross_document_compatibility_unresolved",
    "incomplete_lineage",
]


class SpecialistBoundary(FinancialModel):
    role: SpecialistRole
    responsibility: Identity
    capabilities: list[Identity]
    output_boundary: Literal["candidate_claim_inputs_for_M6"] = "candidate_claim_inputs_for_M6"
    can_verify_claims: Literal[False] = False
    can_approve_formulas_or_compatibility: Literal[False] = False


SPECIALIST_BOUNDARIES = (
    SpecialistBoundary(
        role="profitability",
        responsibility="Phân tích khả năng sinh lời",
        capabilities=["profitability_evidence", "approved_profitability_metrics"],
    ),
    SpecialistBoundary(
        role="liquidity_and_leverage",
        responsibility="Thanh khoản và đòn bẩy",
        capabilities=["liquidity_evidence", "approved_leverage_metrics"],
    ),
    SpecialistBoundary(
        role="cash_flow_and_earnings_quality",
        responsibility="Dòng tiền và chất lượng lợi nhuận",
        capabilities=["cash_flow_evidence", "earnings_quality_evidence"],
    ),
)


class EvidenceSelector(EvidenceQuery):
    """Một selector cho một đầu vào; so sánh nhiều kỳ giữ nhiều selectors riêng."""


class QuerySpecification(FinancialModel):
    original_question: Identity
    intent: Literal[
        "direct_fact",
        "calculated_metric",
        "evidence_explanation",
        "multi_step_analysis",
        "unsupported",
        "ambiguous",
    ]
    company_alias: Identity | None = None
    selectors: list[EvidenceSelector] = Field(default_factory=list)
    reporting_periods: list[Identity] = Field(default_factory=list)
    required_indicators: list[Identity] = Field(default_factory=list)
    requested_formula_ids: list[Identity] = Field(default_factory=list)
    analysis_type: Identity
    reporting_scope: Literal["separate", "consolidated"] | None = None
    reporting_year: int | None = Field(default=None, ge=1900, le=2200)
    missing_information: list[Identity] = Field(default_factory=list)
    ambiguity_flags: list[Identity] = Field(default_factory=list)
    cross_document_comparison: bool = False

    @classmethod
    def from_understanding(cls, question: str, parsed: QAUnderstanding, *, reasons=()):
        """Adapter thuần dữ liệu; không suy selector/document từ alias hoặc năm."""
        return cls(
            original_question=question,
            intent=parsed.intent,
            company_alias=parsed.company_alias,
            selectors=[
                EvidenceSelector(
                    canonical_item_id=parsed.canonical_item_id,
                    period=parsed.period,
                    reporting_scope=parsed.reporting_scope,
                )
            ],
            reporting_periods=[parsed.period] if parsed.period else [],
            required_indicators=[parsed.canonical_item_id] if parsed.canonical_item_id else [],
            requested_formula_ids=[parsed.formula_id] if parsed.formula_id else [],
            analysis_type=parsed.intent,
            reporting_scope=parsed.reporting_scope,
            reporting_year=parsed.reporting_year,
            ambiguity_flags=list(reasons),
        )


class EvidenceRequirement(FinancialModel):
    requirement_id: Identity
    evidence_type: Literal[
        "snapshot",
        "fact",
        "formula",
        "compatibility",
        "metric",
        "lineage",
        "citations",
        "text",
        "table",
        "analysis_bundle",
    ]
    canonical_item_id: Identity | None = None
    formula_id: Identity | None = None
    selector: EvidenceSelector = Field(default_factory=EvidenceSelector)
    dependencies: list[Identity] = Field(default_factory=list)
    importance: Literal["required", "optional"] = "required"
    resolution: Literal["unresolved", "found", "resolved", "missing", "conflicted"] = "unresolved"
    reasons: list[Identity] = Field(default_factory=list)
    references: list[RetrievalReference] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    quality_decisions: list[UsageDecision] = Field(default_factory=list)
    caveats: list[Identity] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False

    @model_validator(mode="after")
    def consistent_resolution(self):
        if self.canonical_item_id and self.selector.canonical_item_id not in (
            None,
            self.canonical_item_id,
        ):
            raise ValueError("requirement_item_binding_conflict")
        if self.resolution in {"missing", "conflicted"} and not self.reasons:
            raise ValueError("unresolved_evidence_requires_reason")
        if self.resolution == "resolved":
            if any(q in {"insufficient", "conflicted"} for q in self.quality_decisions):
                raise ValueError("resolved_evidence_has_blocking_quality")
            if "usable_with_caveat" in self.quality_decisions and not self.caveats:
                raise ValueError("quality_caveat_must_be_preserved")
            if (
                self.evidence_type in {"fact", "metric", "lineage", "text", "table"}
                and not self.references
            ):
                raise ValueError("resolved_evidence_requires_reference")
            if self.evidence_type == "citations" and not self.citations:
                raise ValueError("resolved_citations_require_sources")
        return self


class RiskSignal(FinancialModel):
    code: RiskCode
    reason: Identity
    requirement_ids: list[Identity] = Field(default_factory=list)
    step_ids: list[Identity] = Field(default_factory=list)
    blocking: bool = True
    # Tín hiệu thiếu căn cứ không phải kết luận dữ liệu tài chính sai.
    financial_error_established: Literal[False] = False


class InputBinding(FinancialModel):
    argument: Identity
    source_step_id: Identity
    output_path: Identity


# Registry dùng chính M4 models; không duy trì một schema arguments thứ hai.
TOOL_CONTRACTS = {
    "get_financial_fact": (GetFinancialFactRequest, FinancialToolResponse),
    "find_financial_facts": (FindFinancialFactsRequest, FinancialToolResponse),
    "get_financial_metric": (GetFinancialMetricRequest, FinancialToolResponse),
    "list_financial_metrics": (ListFinancialMetricsRequest, FinancialToolResponse),
    "calculate_financial_metric": (CalculateFinancialMetricRequest, FinancialCalculationResponse),
    "get_evidence_item": (GetEvidenceItemRequest, EvidenceToolResponse),
    "find_document_evidence": (FindDocumentEvidenceRequest, EvidenceToolResponse),
    "get_evidence_anchor": (GetEvidenceAnchorRequest, EvidenceToolResponse),
    "get_evidence_sources": (GetEvidenceSourcesRequest, EvidenceToolResponse),
    "get_metric_evidence_lineage": (GetMetricEvidenceLineageRequest, EvidenceToolResponse),
}


class PlanStep(FinancialModel):
    step_id: Identity
    step_type: Literal["resolve_snapshot", "tool", "check_compatibility", "prepare_bundle"]
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    input_bindings: list[InputBinding] = Field(default_factory=list)
    selector: EvidenceSelector = Field(default_factory=EvidenceSelector)
    prerequisite_step_ids: list[Identity] = Field(default_factory=list)
    required_evidence_ids: list[Identity] = Field(default_factory=list)
    output_evidence_ids: list[Identity] = Field(default_factory=list)
    formula_id: Identity | None = None
    expected_result_type: Identity
    status: ExecutionState = "pending"
    failure_or_skip_reason: Identity | None = None

    @model_validator(mode="after")
    def operation_contract(self):
        if self.status in {"failed", "blocked", "skipped"} and not self.failure_or_skip_reason:
            raise ValueError("step_status_requires_reason")
        if self.step_type != "tool":
            if self.tool or self.arguments or self.input_bindings:
                raise ValueError("non_tool_step_uses_selector_and_evidence_ids_only")
            expected = {
                "resolve_snapshot": "SnapshotSelection",
                "check_compatibility": "MetricSnapshotClosure",
                "prepare_bundle": "candidate_claim_inputs_for_M6",
            }[self.step_type]
            if self.expected_result_type != expected:
                raise ValueError("operation_result_type_mismatch")
            return self
        if self.tool not in TOOL_CONTRACTS:
            raise ValueError("unsupported_tool")
        request, response = TOOL_CONTRACTS[self.tool]
        if self.expected_result_type != response.__name__:
            raise ValueError("tool_result_type_mismatch")
        targets = [b.argument for b in self.input_bindings]
        if len(set(targets)) != len(targets) or set(targets) & self.arguments.keys():
            raise ValueError("duplicate_or_conflicting_input_binding")
        if any(t not in request.model_fields or t in {"tool", "version"} for t in targets):
            raise ValueError("unknown_binding_argument")
        if self.arguments.get("tool", self.tool) != self.tool:
            raise ValueError("tool_argument_conflict")
        # Missing được phép chỉ khi có binding đúng field, mọi lỗi khác giữ nguyên.
        try:
            request.model_validate(self.arguments)
        except ValidationError as error:
            if any(e["type"] != "missing" or e["loc"][0] not in targets for e in error.errors()):
                raise ValueError("invalid_tool_arguments") from error
        _guard_selector(self.selector, self.arguments)
        return self


def _guard_selector(selector, arguments):
    for field in (
        "document_id",
        "snapshot_id",
        "company_id",
        "canonical_item_id",
        "period",
        "period_type",
        "reporting_scope",
        "statement_type",
    ):
        expected = getattr(selector, field)
        actual = arguments.get(field)
        if expected is not None and actual is not None and expected != actual:
            raise ValueError("selector_binding_conflict:" + field)
    reference = arguments.get("reference")
    if reference is not None:
        reference = RetrievalReference.model_validate(reference)
        identity = reference.observation or reference.evidence
        if identity:
            _guard_selector(selector, identity.model_dump())


def _check_graph(edges, name):
    visited, visiting = set(), set()

    def visit(key):
        if key not in edges:
            raise ValueError("unknown_" + name + "_reference:" + key)
        if key in visiting:
            raise ValueError(name + "_dependency_cycle")
        if key in visited:
            return
        visiting.add(key)
        for dependency in edges[key]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in edges:
        visit(key)


@lru_cache(maxsize=64)
def _contract_schema(model):
    # Private, read-only traversal cache keyed by the actual contract class.
    # Never return it to callers/prompts that may mutate schema dictionaries.
    return model.model_json_schema()


def _schema_path_exists(model, path):
    """Schema traversal support union/$ref/list; runtime vẫn kiểm concrete payload."""
    root = _contract_schema(model)

    def walk(schema, parts):
        if "$ref" in schema:
            schema = root["$defs"][schema["$ref"].split("/")[-1]]
        if not parts:
            return True
        for union in ("anyOf", "oneOf"):
            if union in schema:
                return any(walk(s, parts) for s in schema[union])
        head, *tail = parts
        if schema.get("type") == "array" and head.isdigit():
            return walk(schema["items"], tail)
        return head in schema.get("properties", {}) and walk(schema["properties"][head], tail)

    return walk(root, path.split("."))


class EvidencePlan(FinancialModel):
    plan_id: Identity
    version: Literal["evidence_plan_v1"] = "evidence_plan_v1"
    query: QuerySpecification
    steps: list[PlanStep] = Field(min_length=1)
    requirements: list[EvidenceRequirement] = Field(min_length=1)
    stop_conditions: list[StopCondition] = Field(min_length=1)
    evidence_limitations: list[Identity] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    specialist_roles: list[SpecialistRole] = Field(default_factory=list)
    state: ExecutionState = "pending"
    execution_limit: int | None = Field(default=None, ge=1)
    output_boundary: Literal["candidate_claim_inputs_for_M6"] = "candidate_claim_inputs_for_M6"
    financial_fact_verified: Literal[False] = False

    @model_validator(mode="after")
    def structural_contract(self):
        steps = {s.step_id: s for s in self.steps}
        requirements = {r.requirement_id: r for r in self.requirements}
        if len(steps) != len(self.steps) or len(requirements) != len(self.requirements):
            raise ValueError("duplicate_step_or_requirement_id")
        if not any(r.importance == "required" for r in self.requirements):
            raise ValueError("plan_requires_required_evidence")
        _check_graph({k: s.prerequisite_step_ids for k, s in steps.items()}, "step")
        _check_graph({k: r.dependencies for k, r in requirements.items()}, "requirement")
        # Evidence dependencies cũng là dependencies thực; hai DAG riêng có thể
        # hợp lệ nhưng kết hợp lại tạo deadlock producer/consumer.
        combined = {
            "step:" + k: ["step:" + p for p in s.prerequisite_step_ids]
            + ["requirement:" + r for r in s.required_evidence_ids]
            for k, s in steps.items()
        }
        combined.update(
            {
                "requirement:" + k: ["requirement:" + d for d in r.dependencies]
                for k, r in requirements.items()
            }
        )
        for step in self.steps:
            for key in step.output_evidence_ids:
                if key in requirements:
                    combined["requirement:" + key].append("step:" + step.step_id)
        _check_graph(combined, "plan")
        positions = {s.step_id: i for i, s in enumerate(self.steps)}
        for step in self.steps:
            for key in [*step.required_evidence_ids, *step.output_evidence_ids]:
                if key not in requirements:
                    raise ValueError("unknown_requirement_reference:" + key)
            if any(positions[p] >= positions[step.step_id] for p in step.prerequisite_step_ids):
                raise ValueError("steps_must_be_dependency_ordered")
            if step.status in {"ready", "running", "completed"} and any(
                steps[p].status != "completed" for p in step.prerequisite_step_ids
            ):
                raise ValueError("active_step_has_unfinished_prerequisite")
            for binding in step.input_bindings:
                if binding.source_step_id not in step.prerequisite_step_ids:
                    raise ValueError("binding_requires_explicit_prerequisite")
                source = steps[binding.source_step_id]
                model = (
                    TOOL_CONTRACTS[source.tool][1]
                    if source.tool
                    else SnapshotSelection
                    if source.step_type == "resolve_snapshot"
                    else None
                )
                if model is None or not _schema_path_exists(model, binding.output_path):
                    raise ValueError("unknown_binding_output_path")
            for key in step.output_evidence_ids:
                req = requirements[key]
                _guard_selector(req.selector, step.selector.model_dump(exclude_none=True))
                _guard_selector(req.selector, step.arguments)
            if step.status == "completed" and any(
                requirements[k].resolution != "resolved"
                for k in [*step.required_evidence_ids, *step.output_evidence_ids]
                if requirements[k].importance == "required"
            ):
                raise ValueError("completed_step_has_unresolved_required_evidence")
            if self.query.selectors:
                merged = {**step.selector.model_dump(exclude_none=True), **step.arguments}
                if not any(_selector_matches(q, merged) for q in self.query.selectors):
                    raise ValueError("step_conflicts_with_query_selectors")
            if self.query.reporting_scope:
                _guard_selector(
                    EvidenceSelector(reporting_scope=self.query.reporting_scope),
                    {**step.selector.model_dump(exclude_none=True), **step.arguments},
                )
        for req in self.requirements:
            if self.query.selectors and not any(
                _selector_matches(q, req.selector.model_dump(exclude_none=True))
                for q in self.query.selectors
            ):
                raise ValueError("requirement_conflicts_with_query_selectors")
            if self.query.reporting_scope:
                _guard_selector(
                    EvidenceSelector(reporting_scope=self.query.reporting_scope),
                    req.selector.model_dump(exclude_none=True),
                )
            if req.resolution == "resolved" and any(
                requirements[k].resolution != "resolved" for k in req.dependencies
            ):
                raise ValueError("resolved_requirement_has_unresolved_dependency")
            for reference in req.references:
                _guard_selector(req.selector, {"reference": reference})
            for citation in req.citations:
                _guard_selector(req.selector, citation.model_dump())
        for risk in self.risks:
            if set(risk.step_ids) - steps.keys() or set(risk.requirement_ids) - requirements.keys():
                raise ValueError("unknown_risk_reference")
        if "all_required_evidence_resolved" not in self.stop_conditions:
            raise ValueError("completion_condition_required")
        if self.state == "completed" and (
            any(
                r.importance == "required" and r.resolution != "resolved" for r in self.requirements
            )
            or any(
                s.status != "completed"
                for s in self.steps
                if not s.output_evidence_ids
                or any(requirements[k].importance == "required" for k in s.output_evidence_ids)
            )
        ):
            raise ValueError("completed_plan_has_unresolved_required_work")
        if self.state == "completed" and any(r.blocking for r in self.risks):
            raise ValueError("completed_plan_has_blocking_risk")
        return self


def _selector_matches(selector, arguments):
    try:
        _guard_selector(selector, arguments)
        return True
    except ValueError:
        return False


def _query_scope(query, selector):
    scopes = {
        q.reporting_scope
        for q in query.selectors
        if q.reporting_scope and _selector_matches(q, selector.model_dump(exclude_none=True))
    }
    scopes.update(s for s in (query.reporting_scope, selector.reporting_scope) if s)
    return scopes


def bind_step_request(plan: EvidencePlan, step_id: str, outputs: dict[str, Any]):
    """Tạo một request M4 từ outputs đã có; kiểm bindings, không dispatch."""
    plan = EvidencePlan.model_validate_json(plan.model_dump_json())
    step = next(s for s in plan.steps if s.step_id == step_id)
    if step.tool is None:
        raise ValueError("step_is_not_a_tool")
    arguments = dict(step.arguments)
    for binding in step.input_bindings:
        source = next(s for s in plan.steps if s.step_id == binding.source_step_id)
        response_model = TOOL_CONTRACTS[source.tool][1] if source.tool else SnapshotSelection
        payload = outputs[binding.source_step_id]
        if isinstance(payload, FinancialModel):
            payload = payload.model_dump(mode="json")
        payload = response_model.model_validate_json(json.dumps(payload)).model_dump(mode="json")
        if payload.get("status") not in {"found", "computed", "selected"}:
            raise ValueError("binding_source_not_successful")
        value = payload
        try:
            for token in binding.output_path.split("."):
                value = value[int(token)] if isinstance(value, list) else value[token]
        except (IndexError, KeyError, TypeError) as error:
            raise ValueError("binding_output_unavailable") from error
        arguments[binding.argument] = value
    request = TOOL_CONTRACTS[step.tool][0].model_validate_json(json.dumps(arguments))
    _guard_selector(step.selector, request.model_dump())
    for scope in _query_scope(plan.query, step.selector):
        _guard_selector(EvidenceSelector(reporting_scope=scope), request.model_dump())
    for requirement in plan.requirements:
        if requirement.requirement_id in step.output_evidence_ids:
            _guard_selector(requirement.selector, request.model_dump())
    if plan.query.selectors and not any(
        _selector_matches(q, request.model_dump()) for q in plan.query.selectors
    ):
        raise ValueError("bound_request_conflicts_with_query")
    return request


class PlanValidation(FinancialModel):
    structurally_valid: bool
    execution_eligible: bool
    disposition: Literal["valid", "invalid", "blocked"]
    errors: list[str] = Field(default_factory=list)
    risks: list[RiskSignal] = Field(default_factory=list)
    triggered_stop_conditions: list[StopCondition] = Field(default_factory=list)
    financial_fact_verified: Literal[False] = False


def validate_plan(
    plan: EvidencePlan | dict, *, catalog: SnapshotCatalog | None = None, executed_steps: int = 0
) -> PlanValidation:
    """Preflight read-only; không gọi M4 tools hoặc thực thi các bước.

    Eligible cho phép bắt đầu, không có nghĩa evidence đã hoàn tất. M5-03 phải
    kiểm lại bindings và luôn dùng gate production M4 khi tính toán.
    """
    try:
        plan = (
            EvidencePlan.model_validate_json(plan.model_dump_json())
            if isinstance(plan, EvidencePlan)
            else EvidencePlan.model_validate(plan)
        )
    except ValidationError as error:
        return PlanValidation(
            structurally_valid=False,
            execution_eligible=False,
            disposition="invalid",
            errors=[e["msg"] for e in error.errors()],
        )
    risks = list(plan.risks)
    stops: list[StopCondition] = []
    selections = {}

    def select(document, snapshot):
        key = document, snapshot
        if key not in selections:
            selections[key] = catalog.select(*key)
        return selections[key]

    def signal(code, reason, stop=None, *, blocking=True, step=None, requirement=None):
        risks.append(
            RiskSignal(
                code=code,
                reason=reason,
                blocking=blocking,
                step_ids=[step] if step else [],
                requirement_ids=[requirement] if requirement else [],
            )
        )
        if stop:
            stops.append(stop)

    def apply_scope(selector, *, required=True, step=None, requirement=None):
        scopes = _query_scope(plan.query, selector)
        if len(scopes) > 1:
            signal(
                "reporting_scope_unresolved",
                "ambiguous_query_scope_constraints",
                "unresolved_ambiguity" if required else None,
                blocking=required,
                step=step,
                requirement=requirement,
            )
        elif scopes:
            selector.reporting_scope = next(iter(scopes))
        return selector

    for risk in plan.risks:
        if risk.blocking:
            stops.append(
                {
                    "missing_evidence": "missing_required_inputs",
                    "conflicting_evidence": "conflicting_evidence",
                    "ambiguous_snapshot": "unresolved_ambiguity",
                    "insufficient_quality": "missing_required_inputs",
                    "reporting_scope_unresolved": "compatibility_gate_blocked",
                    "period_unit_mismatch": "compatibility_gate_blocked",
                    "formula_not_approved": "unsupported_operation",
                    "cross_document_compatibility_unresolved": "compatibility_gate_blocked",
                    "incomplete_lineage": "missing_required_inputs",
                }[risk.code]
            )

    if plan.query.missing_information:
        stops.append("missing_required_inputs")
    if plan.query.ambiguity_flags or plan.query.intent == "ambiguous":
        stops.append("unresolved_ambiguity")
    if plan.query.intent == "unsupported":
        stops.append("unsupported_operation")
    if plan.execution_limit is not None and executed_steps >= plan.execution_limit:
        stops.append("execution_limit_reached")
    documents = {s.selector.document_id or s.arguments.get("document_id") for s in plan.steps} - {
        None
    }
    documents.update(r.selector.document_id for r in plan.requirements if r.selector.document_id)
    documents.update(q.document_id for q in plan.query.selectors if q.document_id)
    if plan.query.cross_document_comparison or len(documents) > 1:
        signal(
            "cross_document_compatibility_unresolved",
            "D03-B10:cross_document_execution_not_approved",
            "compatibility_gate_blocked",
        )
    for requirement in plan.requirements:
        if requirement.resolution in {"missing", "conflicted"}:
            required = requirement.importance == "required"
            signal(
                "missing_evidence"
                if requirement.resolution == "missing"
                else "conflicting_evidence",
                ";".join(requirement.reasons),
                (
                    "missing_required_inputs"
                    if requirement.resolution == "missing"
                    else "conflicting_evidence"
                )
                if required
                else None,
                blocking=required,
                requirement=requirement.requirement_id,
            )
        if catalog is None or requirement.evidence_type != "fact":
            continue
        selector = requirement.selector.model_copy(deep=True)
        selector.canonical_item_id = requirement.canonical_item_id or selector.canonical_item_id
        required = requirement.importance == "required"
        selector = apply_scope(selector, required=required, requirement=requirement.requirement_id)
        if not selector.document_id:
            signal(
                "missing_evidence",
                "fact_document_binding_required",
                "missing_required_inputs" if required else None,
                blocking=required,
                requirement=requirement.requirement_id,
            )
            continue
        selection = select(selector.document_id, selector.snapshot_id)
        if selection.status != "selected":
            signal(
                "ambiguous_snapshot" if selection.status == "ambiguous" else "missing_evidence",
                ";".join(selection.reasons) or selection.status,
                (
                    "unresolved_ambiguity"
                    if selection.status == "ambiguous"
                    else "missing_required_inputs"
                )
                if required
                else None,
                blocking=required,
                requirement=requirement.requirement_id,
            )
            continue
        selector.snapshot_id = selection.candidates[0].descriptor.snapshot_id
        if selector.reporting_scope:
            scope = catalog.get_reporting_scope(selector.document_id, selector.snapshot_id)
            if scope.status != "resolved" or scope.reporting_scope != selector.reporting_scope:
                signal(
                    "reporting_scope_unresolved",
                    "required_scope_unresolved_or_mismatched",
                    "compatibility_gate_blocked" if required else None,
                    blocking=required,
                    requirement=requirement.requirement_id,
                )
        # Scope là source-backed overlay; không filter original context chưa resolve.
        query = EvidenceQuery(**selector.model_dump(exclude={"reporting_scope"}))
        found = catalog.api.find_facts(query)
        usable = []
        for match in found.matches:
            source_review = catalog.api.get_source_review(match.reference.observation)
            if source_review.status == "conflicted":
                signal(
                    "conflicting_evidence",
                    ";".join(source_review.reasons) or "source_review_conflicted",
                    "conflicting_evidence" if required else None,
                    blocking=required,
                    requirement=requirement.requirement_id,
                )
                continue
            decisions = [
                q.decision for q in match.record.quality_context if q.task_type == "direct_qa"
            ]
            if (
                match.display_status != "blocked"
                and decisions
                and all(q in {"usable", "usable_with_caveat"} for q in decisions)
            ):
                usable.append(match)
            if "usable_with_caveat" in decisions:
                signal(
                    "insufficient_quality",
                    "usable_with_caveat_is_not_verified",
                    blocking=False,
                    requirement=requirement.requirement_id,
                )
        if found.status != "found" or not usable:
            signal(
                "conflicting_evidence" if found.status == "conflicted" else "missing_evidence",
                ";".join(found.reasons) or "no_usable_fact",
                (
                    "conflicting_evidence"
                    if found.status == "conflicted"
                    else "missing_required_inputs"
                )
                if required
                else None,
                blocking=required,
                requirement=requirement.requirement_id,
            )
        if requirement.resolution == "resolved" and not all(
            reference in [m.reference for m in usable] for reference in requirement.references
        ):
            signal(
                "missing_evidence",
                "resolved_reference_not_usable_in_selected_catalog",
                "missing_required_inputs" if required else None,
                blocking=required,
                requirement=requirement.requirement_id,
            )
    for step in plan.steps:
        if step.output_evidence_ids and all(
            next(r for r in plan.requirements if r.requirement_id == key).importance == "optional"
            for key in step.output_evidence_ids
        ):
            # Optional work không là điều kiện khởi động toàn plan; M4 vẫn gate
            # từng invocation nếu Supervisor chọn chạy bước này ở task sau.
            continue
        selector = EvidenceSelector(
            **{
                **step.selector.model_dump(),
                **{k: v for k, v in step.arguments.items() if k in EvidenceSelector.model_fields},
            }
        )
        selector = apply_scope(selector, step=step.step_id)
        if catalog is None:
            signal(
                "missing_evidence",
                "catalog_required_for_preflight",
                "missing_required_inputs",
                step=step.step_id,
            )
            continue
        if selector.document_id:
            selection = select(selector.document_id, selector.snapshot_id)
            if selection.status != "selected":
                signal(
                    "ambiguous_snapshot" if selection.status == "ambiguous" else "missing_evidence",
                    ";".join(selection.reasons) or selection.status,
                    "unresolved_ambiguity"
                    if selection.status == "ambiguous"
                    else "missing_required_inputs",
                    step=step.step_id,
                )
                continue
            descriptor = selection.candidates[0].descriptor
            scope = catalog.get_reporting_scope(descriptor.document_id, descriptor.snapshot_id)
            if scope.status != "resolved":
                signal(
                    "reporting_scope_unresolved",
                    ";".join(scope.reasons),
                    "compatibility_gate_blocked" if selector.reporting_scope else None,
                    blocking=selector.reporting_scope is not None,
                    step=step.step_id,
                )
            elif selector.reporting_scope and scope.reporting_scope != selector.reporting_scope:
                signal(
                    "reporting_scope_unresolved",
                    "reporting_scope_mismatch",
                    "compatibility_gate_blocked",
                    step=step.step_id,
                )
        if step.tool == "calculate_financial_metric" or step.step_type == "check_compatibility":
            metric_id = step.arguments.get("metric_id")
            # Không nhận caller approval; policy/operands/closure lấy từ catalog.
            metrics = [
                m
                for m in catalog.metrics
                if (metric_id is None or m.metric_id == metric_id)
                and (selector.document_id is None or m.request.document_id == selector.document_id)
                and (selector.snapshot_id is None or m.request.snapshot_id == selector.snapshot_id)
                and (step.formula_id is None or m.definition.name == step.formula_id)
            ]
            if len(metrics) != 1:
                signal(
                    "formula_not_approved",
                    "metric_binding_missing_or_ambiguous",
                    "unsupported_operation",
                    step=step.step_id,
                )
                continue
            metric = metrics[0]
            selection = select(metric.request.document_id, metric.request.snapshot_id)
            closures = [
                c
                for e in selection.candidates
                for c in e.metrics
                if c.metric_id == metric.metric_id
            ]
            if step.formula_id and step.formula_id != metric.definition.name:
                signal(
                    "formula_not_approved",
                    "metric_formula_mismatch",
                    "unsupported_operation",
                    step=step.step_id,
                )
            if len(closures) != 1 or not closures[0].calculation_eligible:
                readiness = closures[0].readiness or {} if len(closures) == 1 else {}
                blockers = readiness.get("execution_blockers", ["catalog_closure_unavailable"])
                formula = readiness.get("formula_policy", {})
                code = (
                    "formula_not_approved"
                    if not formula.get("execution_approved")
                    else "period_unit_mismatch"
                    if any(
                        token in reason
                        for reason in blockers
                        for token in ("period", "unit", "currency", "scale")
                    )
                    else "incomplete_lineage"
                )
                signal(
                    code,
                    ";".join(blockers) or "catalog_calculation_not_eligible",
                    "compatibility_gate_blocked",
                    step=step.step_id,
                )
    blocked = any(r.blocking for r in risks) or any(
        s != "all_required_evidence_resolved" for s in stops
    )
    if not blocked and all(
        r.resolution == "resolved" for r in plan.requirements if r.importance == "required"
    ):
        stops.append("all_required_evidence_resolved")
    return PlanValidation(
        structurally_valid=True,
        execution_eligible=not blocked,
        disposition="blocked" if blocked else "valid",
        risks=risks,
        triggered_stop_conditions=sorted(set(stops)),
    )
