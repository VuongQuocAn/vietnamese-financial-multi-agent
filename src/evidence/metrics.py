"""Derived metrics: binding/readiness thuần, không tính toán hoặc sửa facts M2."""

import hashlib
import json
from collections.abc import Iterable
from typing import Literal

from pydantic import Field, model_validator

from ..accounting.contracts import FinancialContext, FinancialModel
from .compatibility import (
    CompatibilityAssessment,
    FinancialOperand,
    OperationCompatibilitySpec,
    assess_compatibility,
)
from .contracts import (
    CanonicalFinancialFact,
    Identity,
    ObservationIdentity,
    TaskQualityContext,
    assess_fact_consistency,
)


def metric_digest(kind, payload):
    wire = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return kind + ":" + hashlib.sha256(wire.encode()).hexdigest()


class FormulaDefinition(FinancialModel):
    formula_reference: Identity
    formula_version: Identity
    name: Identity
    # Biểu thức mô tả bằng roles; không parse/eval hoặc đăng ký executable policy.
    expression: Identity
    policy_status: Literal["reference_example"] = "reference_example"
    compatibility: OperationCompatibilitySpec


class MetricRequest(FinancialModel):
    document_id: Identity
    snapshot_id: Identity
    # Kỳ cụ thể cho từng role, caller chọn từ context thật; không suy từ filename.
    operand_periods: dict[str, Identity]


class MetricOperand(FinancialModel):
    role: Identity
    status: Literal["bound", "missing", "ambiguous", "unresolved_identity"]
    candidates: list[ObservationIdentity]
    candidate_count: int = Field(ge=0)
    observation: ObservationIdentity | None = None
    canonical_item_id: Identity | None = None
    company_id: Identity | None = None
    semantic_role: Identity | None = None
    context: FinancialContext | None = None
    unit: str | None = None
    source_fact_node_id: Identity | None = None


class OperandUsability(FinancialModel):
    role: Identity
    # Giữ annotations gốc, không aggregate/propagate M2 quality.
    quality_context: list[TaskQualityContext]
    resolution_reasons: list[str]
    grounding_levels: list[str]
    grounding_statuses: list[str]
    provenance_reasons: list[str]
    missing_value: bool
    display_status: Literal["display_with_caveat", "blocked", "undetermined"]


class DerivedMetric(FinancialModel):
    version: Literal["derived_metric_v1"] = "derived_metric_v1"
    metric_id: Identity
    definition: FormulaDefinition
    request: MetricRequest
    operands: list[MetricOperand]
    binding_status: Literal[
        "fully_bound", "partially_bound", "missing_operands", "ambiguous_candidates"
    ]
    structural_readiness: Literal["complete", "incomplete", "ambiguous"]
    compatibility: CompatibilityAssessment
    evidence_usability: list[OperandUsability]
    preparation_blockers: list[str]
    # M3-05 không nhận computed: execution/lineage acceptance thuộc M3-06/M4.
    result_status: Literal["not_computed", "unavailable", "invalid_inputs"] = "not_computed"
    result: None = None
    financial_fact_verified: Literal[False] = False

    @model_validator(mode="after")
    def coherent_record(self):
        roles = [r.role for r in self.definition.compatibility.operands]
        if [o.role for o in self.operands] != roles:
            raise ValueError("Duplicate/missing/incorrect operand roles")
        if set(self.request.operand_periods) != set(roles):
            raise ValueError("Explicit period required for every role")
        for operand in self.operands:
            if len(operand.candidates) != len(set(operand.candidates)):
                raise ValueError("Duplicate observation identity")
            if operand.status == "bound":
                if (
                    operand.candidate_count != 1
                    or operand.candidates != [operand.observation]
                    or operand.context is None
                    or operand.source_fact_node_id
                    != metric_digest("source_fact", operand.observation.model_dump())
                ):
                    raise ValueError("Invalid bound operand reference")
            elif operand.observation is not None or operand.source_fact_node_id is not None:
                raise ValueError("Unresolved operand cannot have a bound reference")
            elif (
                (operand.status == "missing" and (operand.candidate_count or operand.candidates))
                or (operand.status == "ambiguous" and operand.candidate_count < 2)
                or (
                    operand.status == "unresolved_identity"
                    and (operand.candidate_count != 1 or operand.candidates)
                )
            ):
                raise ValueError("Candidate count/status mismatch")
        count = sum(o.status == "bound" for o in self.operands)
        ambiguous = any(o.status == "ambiguous" for o in self.operands)
        expected = (
            "ambiguous_candidates"
            if ambiguous
            else "fully_bound"
            if count == len(roles)
            else "partially_bound"
            if count
            else "missing_operands"
        )
        structural = (
            "ambiguous" if ambiguous else "complete" if count == len(roles) else "incomplete"
        )
        if self.binding_status != expected or self.structural_readiness != structural:
            raise ValueError("Binding/structural status mismatch")
        if [(o.role, o.observation) for o in self.operands if o.status == "bound"] != [
            (o.role, o.observation) for o in self.compatibility.operands
        ]:
            raise ValueError("Compatibility references mismatch")
        if [u.role for u in self.evidence_usability] != [
            o.role for o in self.operands if o.status == "bound"
        ]:
            raise ValueError("Evidence usability roles mismatch")
        if self.metric_id != metric_identity(self.definition, self.request, self.operands):
            raise ValueError("Metric identity mismatch")
        return self


def metric_identity(definition, request, operands):
    # Definition content, scope và candidate/binding identities phân biệt instances.
    return metric_digest(
        "derived_metric",
        dict(
            definition=definition.model_dump(mode="json"),
            request=request.model_dump(mode="json"),
            bindings=[
                dict(
                    role=o.role,
                    status=o.status,
                    count=o.candidate_count,
                    candidates=[i.model_dump() for i in o.candidates],
                )
                for o in operands
            ],
        ),
    )


def build_metric(
    definition: FormulaDefinition,
    request: MetricRequest,
    facts: Iterable[CanonicalFinancialFact],
) -> DerivedMetric:
    """Chọn canonical ID + statement + explicit period trong đúng một attempt.

    Không chọn latest, raw label hoặc semantic role thiếu. Mọi candidate ambiguity
    được giữ; không ghép operands giữa documents/snapshots. Không nested metrics v1.
    """
    requirements = definition.compatibility.operands
    if set(request.operand_periods) != {r.role for r in requirements}:
        raise ValueError("Explicit period required for every role")
    facts = list(facts)
    bindings, supplied, usability = [], [], []
    for requirement in requirements:
        matches = [
            f
            for f in facts
            if (
                f.document_id,
                f.snapshot_id,
                f.canonical_item_id,
                f.context.statement_type,
                f.context.period,
            )
            == (
                request.document_id,
                request.snapshot_id,
                requirement.canonical_item_id,
                requirement.statement_type,
                request.operand_periods[requirement.role],
            )
        ]
        identities = sorted(
            {f.observation_identity() for f in matches if f.observation_identity() is not None},
            key=lambda i: (i.document_id, i.snapshot_id, i.local_id),
        )
        status = (
            "missing"
            if not matches
            else "ambiguous"
            if len(matches) > 1
            else "bound"
            if identities
            else "unresolved_identity"
        )
        binding = MetricOperand(
            role=requirement.role,
            status=status,
            candidates=identities,
            candidate_count=len(matches),
        )
        if status == "bound":
            fact = matches[0]
            binding.observation = identities[0]
            binding.canonical_item_id = fact.canonical_item_id
            binding.company_id = fact.company_id
            binding.semantic_role = fact.semantic_role
            binding.context = fact.context.model_copy(deep=True)
            binding.unit = fact.value.unit
            binding.source_fact_node_id = metric_digest("source_fact", identities[0].model_dump())
            supplied.append(FinancialOperand(role=requirement.role, fact=fact))
            decisions = [q.decision for q in fact.quality_context if q.task_type == "direct_qa"]
            missing_value = fact.value.normalized_value is None or not fact.value.raw_value.strip()
            consistency = assess_fact_consistency(fact)
            has_source_page = any(
                s.reference is not None
                and s.reference.anchor.page.page > 0
                and s.reference.anchor.page.image.strip()
                and (s.document_id, s.snapshot_id) == (fact.document_id, fact.snapshot_id)
                for s in fact.sources
            )
            usability.append(
                OperandUsability(
                    role=requirement.role,
                    quality_context=[q.model_copy(deep=True) for q in fact.quality_context],
                    resolution_reasons=[q.code for q in fact.resolution_issues],
                    grounding_levels=sorted(
                        {s.reference.provenance_level for s in fact.sources if s.reference}
                    ),
                    grounding_statuses=sorted(
                        {s.reference.anchor.status for s in fact.sources if s.reference}
                    ),
                    provenance_reasons=[
                        i.code for i in consistency.issues if not i.path or i.path[0] == "sources"
                    ],
                    missing_value=missing_value,
                    display_status="blocked"
                    if missing_value
                    or consistency.status == "inconsistent"
                    or any(d in {"insufficient", "conflicted"} for d in decisions)
                    else "display_with_caveat"
                    if len(decisions) == 1 and has_source_page
                    else "undetermined",
                )
            )
        bindings.append(binding)
    assessment = assess_compatibility(definition.compatibility, supplied)
    ambiguous = any(o.status == "ambiguous" for o in bindings)
    count = len(supplied)
    binding_status = (
        "ambiguous_candidates"
        if ambiguous
        else "fully_bound"
        if count == len(requirements)
        else "partially_bound"
        if count
        else "missing_operands"
    )
    blockers = ["formula_policy_not_approved"]
    if binding_status != "fully_bound":
        blockers.append(binding_status)
    blockers.extend(dict.fromkeys(r.code for r in assessment.reasons))
    if any(u.display_status != "display_with_caveat" for u in usability):
        blockers.append("operand_evidence_not_displayable")
    if any(u.missing_value for u in usability):
        blockers.append("missing_operand_value")
    return DerivedMetric(
        metric_id=metric_identity(definition, request, bindings),
        definition=definition.model_copy(deep=True),
        request=request.model_copy(deep=True),
        operands=bindings,
        binding_status=binding_status,
        structural_readiness="ambiguous"
        if ambiguous
        else "complete"
        if binding_status == "fully_bound"
        else "incomplete",
        compatibility=assessment,
        evidence_usability=usability,
        preparation_blockers=blockers,
    )
