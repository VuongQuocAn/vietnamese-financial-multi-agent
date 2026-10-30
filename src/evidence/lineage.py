"""Lineage xác định và truyền context gốc; không aggregate quality hoặc thực thi."""

from collections.abc import Iterable
from typing import Literal

from pydantic import ValidationError

from ..accounting.contracts import FinancialModel
from .compatibility import CompatibilityAssessment
from .contracts import (
    CanonicalFinancialFact,
    EvidenceAnchor,
    ObservationIdentity,
    assess_fact_consistency,
)
from .document_evidence import FactEvidenceAssociation, associate_fact
from .graph import EvidenceGraph, EvidenceRecord, GraphAssessment, graph_id, validate_graph
from .metrics import (
    DerivedMetric,
    FormulaDefinition,
    MetricOperand,
    MetricRequest,
    OperandUsability,
    build_metric,
)


class OperandLineage(FinancialModel):
    binding: MetricOperand
    # Giữ mọi observation kể cả ambiguous; không copy OCR/table payload.
    observations: list[CanonicalFinancialFact]
    anchors: list[EvidenceAnchor]
    associations: list[FactEvidenceAssociation]
    usability: OperandUsability | None
    context_limitations: list[str]
    unresolved: list[str]


class LineageTaskContext(FinancialModel):
    # Prepared chỉ nói inputs đã trace đủ, không cấp phép arithmetic execution.
    arithmetic_preparation: Literal["prepared", "incomplete"]
    analytical_interpretation: Literal["blocked", "undetermined"]
    claim_verification: Literal["not_verified"] = "not_verified"
    calculation: Literal["blocked"] = "blocked"
    blockers: list[str]


class MetricLineage(FinancialModel):
    version: Literal["metric_lineage_v1"] = "metric_lineage_v1"
    metric_id: str
    request: MetricRequest
    formula: FormulaDefinition
    formula_policy_status: Literal["reference_example"]
    operands: list[OperandLineage]
    structural_validation: list[GraphAssessment]
    compatibility: CompatibilityAssessment
    completeness: Literal["complete", "partial", "ambiguous", "broken"]
    unresolved: list[str]
    # Identity tài liệu không chứng minh legal identity, scope hoặc accounting basis.
    document_scoped_observations: list[ObservationIdentity]
    tasks: LineageTaskContext
    result_status: Literal["not_computed", "unavailable", "invalid_inputs"]
    result: None = None
    financial_fact_verified: Literal[False] = False


def trace_metric_lineage(
    metric: DerivedMetric,
    graph: EvidenceGraph,
    facts: Iterable[CanonicalFinancialFact],
    evidence: Iterable[EvidenceRecord] = (),
    *,
    expected_formula: FormulaDefinition | None = None,
) -> MetricLineage:
    """Resolve trong closure của metric; không để lỗi metric khác thành global gate.

    expected_formula kiểm tra catalog/version do caller chọn, không tự lookup policy.
    Các refs thiếu luôn hiện rõ, không dựng lại graph để che missing edge/node.
    """
    facts, evidence = list(facts), list(evidence)
    fresh = build_metric(metric.definition, metric.request, facts)
    unresolved, broken = [], False
    try:
        DerivedMetric.model_validate_json(metric.model_dump_json())
    except ValidationError:
        unresolved.append("invalid_metric_record")
        broken = True
    if expected_formula is not None and metric.definition != expected_formula:
        unresolved.append("formula_reference_version_mismatch")
        broken = True

    # Closure gồm cả dangling/wrong used_in edges nhắm vào metric đang xét.
    selected = {metric.metric_id}
    selected.update(o.source_fact_node_id for o in metric.operands if o.source_fact_node_id)
    selected.update(
        graph_id("source_fact", i.model_dump()) for o in metric.operands for i in o.candidates
    )
    selected.update(
        e.source for e in graph.edges if e.relation == "used_in" and e.target == metric.metric_id
    )
    while True:
        targets = {
            e.target for e in graph.edges if e.source in selected and e.relation != "used_in"
        }
        if targets <= selected:
            break
        selected.update(targets)
    local = EvidenceGraph(
        nodes=[n for n in graph.nodes if n.node_id in selected],
        edges=[
            e
            for e in graph.edges
            if (e.relation == "used_in" and e.target == metric.metric_id)
            or (e.relation != "used_in" and e.source in selected)
        ],
        input_issues=[
            i for i in graph.input_issues if i.reference.split("/sources/")[0] in selected
        ],
    )
    validation = validate_graph(local, facts, evidence, [metric])
    assessments = [*validation.nodes, *validation.edges, *validation.inputs]
    node_ids = {n.node_id for n in local.nodes}
    if metric.metric_id not in node_ids:
        unresolved.append("missing_metric_node")
        broken = True
    # metric_record_mismatch phát hiện record stale so với catalog hiện tại.
    if any(a.status == "invalid" for a in assessments):
        broken = True
    for a in assessments:
        if a.status != "valid":
            unresolved.extend(a.reasons)

    rows, scoped = [], []
    for operand in metric.operands:
        missing = []
        requirement = next(
            (r for r in metric.definition.compatibility.operands if r.role == operand.role), None
        )
        if requirement is None:
            missing.append("operand_role_mismatch")
            broken = True
        observations = sorted(
            [
                f
                for f in facts
                if f.observation_identity() in operand.candidates
                or (
                    operand.status == "unresolved_identity"
                    and requirement is not None
                    and f.observation_identity() is None
                    and (
                        f.document_id,
                        f.snapshot_id,
                        f.canonical_item_id,
                        f.context.statement_type,
                        f.context.period,
                    )
                    == (
                        metric.request.document_id,
                        metric.request.snapshot_id,
                        requirement.canonical_item_id,
                        requirement.statement_type,
                        metric.request.operand_periods.get(operand.role),
                    )
                )
            ],
            key=lambda f: f.model_dump_json(),
        )
        if operand.status != "bound":
            missing.append(operand.status)
        if operand.status == "bound" and len(observations) != 1:
            missing.append("missing_or_ambiguous_source_fact")
            broken = True
        anchors, associations = [], []
        for fact in observations:
            if fact.observation_identity() is None:
                missing.append("unresolved_observation_identity")
                continue
            fid = graph_id("source_fact", fact.observation_identity().model_dump())
            if fid not in node_ids:
                missing.append("missing_source_fact_node")
                broken = True
            if not fact.sources:
                missing.append("missing_evidence_anchor")
            for source in fact.sources:
                key = source.source_key()
                aid = graph_id("anchor", key) if key is not None else None
                if aid not in node_ids or not any(
                    e.relation == "from_source" and e.source == fid and e.target == aid
                    for e in local.edges
                ):
                    missing.append("missing_evidence_anchor_or_edge")
                    broken |= key is not None
                else:
                    anchors.append(source.model_copy(deep=True))
            for record in sorted(evidence, key=lambda e: e.model_dump_json()):
                association = associate_fact(fact, record)
                if association is not None and any(
                    e.relation == "associated_with"
                    and e.source == fid
                    and e.target == graph_id(record.kind, association.evidence.model_dump())
                    for e in local.edges
                ):
                    associations.append(association)
            identity = fact.observation_identity()
            if (identity.document_id, identity.snapshot_id) == (
                metric.request.document_id,
                metric.request.snapshot_id,
            ):
                scoped.append(identity)
        usability = next((u for u in fresh.evidence_usability if u.role == operand.role), None)
        rows.append(
            OperandLineage(
                binding=operand.model_copy(deep=True),
                observations=[f.model_copy(deep=True) for f in observations],
                anchors=anchors,
                associations=associations,
                usability=usability,
                context_limitations=sorted(
                    {
                        code
                        for fact in observations
                        for code in [
                            *[i.code for i in assess_fact_consistency(fact).issues],
                            *(["missing_company_id"] if not fact.company_id else []),
                            *(
                                ["missing_reporting_scope"]
                                if not fact.context.reporting_scope
                                else []
                            ),
                            *(["missing_semantic_role"] if not fact.semantic_role else []),
                        ]
                    }
                ),
                unresolved=sorted(set(missing)),
            )
        )
        unresolved.extend(missing)
    completeness = (
        "broken"
        if broken
        else "ambiguous"
        if any(o.status == "ambiguous" for o in metric.operands)
        else "partial"
        if unresolved or metric.structural_readiness != "complete"
        else "complete"
    )
    blockers = sorted(
        set(
            [
                *fresh.preparation_blockers,
                *unresolved,
                *(f"{row.binding.role}:{code}" for row in rows for code in row.context_limitations),
            ]
        )
    )
    return MetricLineage(
        metric_id=metric.metric_id,
        request=metric.request.model_copy(deep=True),
        formula=metric.definition.model_copy(deep=True),
        formula_policy_status=metric.definition.policy_status,
        operands=rows,
        structural_validation=assessments,
        compatibility=fresh.compatibility,
        completeness=completeness,
        unresolved=sorted(set(unresolved)),
        document_scoped_observations=sorted(
            set(scoped), key=lambda i: (i.document_id, i.snapshot_id, i.local_id)
        ),
        tasks=LineageTaskContext(
            arithmetic_preparation="prepared" if completeness == "complete" else "incomplete",
            analytical_interpretation="blocked"
            if (
                completeness != "complete"
                or fresh.compatibility.status == "incompatible"
                or any(u.display_status == "blocked" for u in fresh.evidence_usability)
            )
            else "undetermined",
            blockers=blockers,
        ),
        result_status=metric.result_status,
    )
