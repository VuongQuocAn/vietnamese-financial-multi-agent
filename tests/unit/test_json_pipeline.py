"""Focused JSON-source calculation/M5 controls; fixtures are synthetic."""

import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    SupervisorLite,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
from vietnamese_financial_multi_agent.evidence.graph import build_graph
from vietnamese_financial_multi_agent.evidence.json_catalog import json_fact_bound
from vietnamese_financial_multi_agent.evidence.refined_import import import_refined_document
from vietnamese_financial_multi_agent.evidence.retrieval import RetrievalReference
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog, SnapshotDescriptor
from vietnamese_financial_multi_agent.tools.financial_calculator import (
    DynamicOperation,
    FinancialCalculator,
)
from vietnamese_financial_multi_agent.tools.financial_retrieval import (
    FinancialRetrievalTools,
    GetFinancialFactRequest,
)

from .test_refined_import import source


def fixture(tmp_path):
    page = source(tmp_path)
    page["blocks"].insert(0, dict(type="heading", text="CÔNG TY CỔ PHẦN TEST"))
    page["blocks"][3]["table"]["rows"][0][3] = "2.000"
    path = tmp_path / "TST/2025/page_0001.json"
    path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    manifest, facts, evidence, _ = import_refined_document(tmp_path, "TST_2025")
    descriptor = SnapshotDescriptor(
        document_id=manifest["document_id"],
        snapshot_id=manifest["snapshot_id"],
        source_kind="json",
        pdf_sha256=None,
        json_sha256=manifest["document_id"].rsplit(":", 1)[1],
        json_pages={p["page"]: p["sha256"] for p in manifest["pages"]},
        origin="normalized_projection",
    )
    catalog = SnapshotCatalog(
        [descriptor],
        facts=facts,
        evidence=evidence,
        graph=build_graph(facts, evidence),
        json_sources={manifest["pages"][0]["sha256"]: path.read_bytes()},
    )
    return catalog


def test_json_tools_calculate_from_bound_sources_and_preserve_pdf_payload(tmp_path):
    catalog = fixture(tmp_path)
    facts = catalog.facts[:2]
    assert all(json_fact_bound(catalog, f) for f in facts)
    match = (
        FinancialRetrievalTools(catalog)
        .get_financial_fact(
            GetFinancialFactRequest(
                document_id=facts[0].document_id,
                snapshot_id=facts[0].snapshot_id,
                local_observation_id=facts[0].local_observation_id,
            )
        )
        .matches[0]
    )
    assert match.json_source_bound and match.citations[0].pdf_page is None
    refs = {
        k: RetrievalReference(kind="fact", observation=f.observation_identity())
        for k, f in zip(["cur", "prev"], facts, strict=True)
    }
    result = FinancialCalculator(catalog).calculate_dynamic(
        refs,
        [
            DynamicOperation(
                operation_id="change",
                operator="subtract",
                inputs=list(refs),
                period_relation="across_periods",
            )
        ],
    )
    assert result.steps[0].result == "-3234" and not result.standard_metric
    pdf = SnapshotDescriptor(
        document_id="sha256:abc", pdf_sha256="abc", snapshot_id="old", origin="original_extraction"
    )
    assert set(pdf.model_dump()) == {
        "document_id",
        "pdf_sha256",
        "snapshot_id",
        "parent_snapshot_id",
        "origin",
    }


def test_json_missing_or_tampered_sources_and_context_cannot_calculate(tmp_path):
    catalog = fixture(tmp_path)
    fact = catalog.facts[0]
    changed = fact.model_copy(deep=True)
    changed.value.raw_value = "123456"
    assert not json_fact_bound(catalog, changed)
    changed = fact.model_copy(deep=True)
    changed.context.period = None
    assert not json_fact_bound(catalog, changed)
    changed = fact.model_copy(deep=True)
    changed.context.scale = Decimal("1000")
    assert not json_fact_bound(catalog, changed)
    catalog.json_sources = {}
    assert catalog.select(fact.document_id, fact.snapshot_id).status == "blocked"
    with pytest.raises(ValueError, match="unavailable_or_conflicting"):
        FinancialCalculator(catalog).calculate_dynamic(
            {"x": RetrievalReference(kind="fact", observation=fact.observation_identity())},
            [DynamicOperation(operation_id="sum", operator="add", inputs=["x", "x"])],
        )
    path = tmp_path / "TST/2025/page_0001.json"
    page = json.loads(path.read_bytes())
    page["blocks"][3]["table"]["columns"][2] = "Năm 2025 (triệu đồng)"
    path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    _, facts, _, _ = import_refined_document(tmp_path, "TST_2025")
    assert facts[0].context.scale is None
    assert facts[0].quality_context[0].decision == "insufficient"


def test_m5_uses_json_facts_and_graph_without_gateway(tmp_path):
    catalog = fixture(tmp_path)
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2025",
        mode="deterministic",
    )
    supervisor = Mock()

    def plan(question, context, sources):
        result, metadata, gaps = SupervisorLite().plan(question, context, sources)
        for task in result.tasks:
            task.use_graph = True
        return result, metadata, gaps

    supervisor.plan.side_effect = plan
    result = FinancialLiteOrchestrator(catalog, supervisor=supervisor).run(
        question="Giá vốn hàng bán năm 2025 là bao nhiêu?", context=context
    )
    assert result.candidates, result.model_dump_json()
    assert all(not c.financial_fact_verified for c in result.candidates)
    assert any(t.operation == "get_graph_context" for t in result.supervisor_result.tool_trace)
