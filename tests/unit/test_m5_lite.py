"""Small offline controls; real BBS evaluation is the opt-in script."""

from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
)
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog

from .test_m4_execution import fixture


def inputs():
    catalog = SnapshotCatalog(**fixture())
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2030",
        mode="deterministic",
    )
    return catalog, context
