"""Bounded, in-memory preparation; never changes accepted files or grants approval."""

from .compatibility import OperationCompatibilitySpec, PeriodPair
from .graph import build_graph
from .metrics import FormulaDefinition, MetricRequest, build_metric
from .snapshots import SnapshotCatalog


def prepare_missing_metric(catalog, document_id, snapshot_id, year, formula_id):
    if not formula_id or any(
        m.definition.name == formula_id
        and (m.request.document_id, m.request.snapshot_id) == (document_id, snapshot_id)
        for m in catalog.metrics
    ):
        return catalog
    policies = [p for p in catalog.policies if p.formula_id == formula_id]
    if len(policies) != 1:
        return catalog
    policy = policies[0]
    if not any(
        a.formula_id == policy.formula_id
        and a.version == policy.version
        and a.definition_sha256 == policy.definition_digest()
        for a in catalog.formula_approvals
    ):
        return catalog
    comparative = policy.period_relation == "consecutive_fiscal_years_descending"
    periods = {
        o.role: str(year - int(comparative and i == 1))
        + ("-12-31" if o.statement_type == "B01" else "")
        for i, o in enumerate(policy.operands)
    }
    definition = FormulaDefinition(
        formula_reference=policy.formula_id,
        formula_version=policy.version,
        name=policy.formula_id,
        expression=policy.expression,
        compatibility=OperationCompatibilitySpec(
            operation_id=policy.formula_id,
            rule_reference=policy.formula_id,
            operands=policy.operands,
            document_relation="same",
            period_relation="ordered_pair" if comparative else "same",
            period_pairs=[
                PeriodPair(left=str(year), right=str(year - 1), period_type="fiscal_year")
            ]
            if comparative
            else [],
        ),
    )
    metric = build_metric(
        definition,
        MetricRequest(document_id=document_id, snapshot_id=snapshot_id, operand_periods=periods),
        catalog.facts,
    )
    # Missing/ambiguous operands are explicit capability gaps, not executable metrics.
    if any(o.status != "bound" for o in metric.operands):
        return catalog
    metrics = [*catalog.metrics, metric]
    graph = catalog.graph.model_copy(deep=True) if catalog.graph else None
    if graph is not None:
        addition = build_graph(catalog.facts, catalog.evidence, [metric])
        graph.nodes.extend(
            n for n in addition.nodes if n.node_id not in {x.node_id for x in graph.nodes}
        )
        graph.edges.extend(
            e for e in addition.edges if e.edge_id not in {x.edge_id for x in graph.edges}
        )
    return SnapshotCatalog(
        catalog.descriptors,
        catalog.facts,
        catalog.evidence,
        metrics,
        graph=graph,
        source_reviews=catalog.reviews,
        accounting_bases=catalog.bases,
        approval=catalog.approval,
        formula_policies=catalog.policies,
        formula_approvals=catalog.formula_approvals,
        execution_approval=catalog.execution_approval,
        reporting_scope_reviews=catalog.scope_reviews,
    )
