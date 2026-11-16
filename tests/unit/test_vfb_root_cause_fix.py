"""Targeted controls for observed VFB-E2E-03 failures; no benchmark data/API."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

from vietnamese_financial_multi_agent.accounting.context_resolution import ContextEvidence
from vietnamese_financial_multi_agent.accounting.item_mapping import map_item_label
from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.agents.integration_workspace import IntegrationRequirement
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    LitePlan,
    LiteTask,
    SupervisorLite,
    inventory,
    resolve_requirements,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.api.financial_qa_pipeline import FinancialQAPipeline
from vietnamese_financial_multi_agent.api.qa_pipeline_contracts import FinancialQARequest
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.tools import QADocument
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_financial_qa import gateway_for
from .test_financial_validators import batch_for
from .test_json_pipeline import fixture as json_fixture
from .test_m4_execution import fixture


def test_supervisor_keeps_graph_guidance_and_composite_retrieval_is_executed():
    catalog = SnapshotCatalog(**fixture())
    fact = catalog.facts[0]
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period="2030",
        mode="auto",
    )
    sources = inventory(catalog, context)
    handles = [h for h, s in sources.items() if s["kind"] == "fact"][:2]
    payload = dict(
        requirements=[
            dict(
                requirement_id="R1",
                text="Tính tỷ trọng từ hai nguồn",
                kind="metric",
                interpretation=True,
                interpretation_topic="dynamic_calculation",
                required_indicators=handles,
                period="2030",
            )
        ],
        tasks=[
            dict(
                task_id="T1",
                specialist="profitability",
                objective="Tính tỷ trọng",
                requirement_ids=["R1"],
                sources=handles,
            )
        ],
    )
    seen = []
    plan, metadata, errors = SupervisorLite(gateway_for(payload, seen), integration_v2=True).plan(
        "Tính tỷ trọng từ hai nguồn", context, sources
    )
    assert not errors and metadata.calls == 1
    prompt = json.loads(seen[0].messages[0].content)
    assert "use_graph=true" in prompt["instruction"]
    assert "answer_goal CHỈ" in prompt["instruction"]
    assert "requirement_schema" in prompt and "response_example" in prompt
    context.mode = "deterministic"
    supervisor = Mock(plan=Mock(return_value=(plan, PlannerLLMMetadata(), [])))
    result = FinancialLiteOrchestrator(catalog, supervisor=supervisor, integration_v2=True).run(
        question="Tính tỷ trọng từ hai nguồn", context=context
    )
    assert plan.tasks[0].use_graph
    operations = [t.operation for t in result.supervisor_result.tool_trace]
    assert "get_financial_fact" in operations and "get_graph_context" in operations


def test_source_alias_gates_cash_routing_and_json_scope(tmp_path):
    catalog = json_fixture(tmp_path)
    reference = catalog.facts[0].sources[0].reference
    for label, statement, code, expected in [
        ("Lợi nhuận sau thuế TNDN", "B02", "60", "b02.profit_after_tax"),
        ("D. VỐN CHỦ SỞ HỮU", "B01", "400", "b01.total_equity"),
    ]:
        evidence = ContextEvidence(raw_text=label, provenance=[reference])
        assert map_item_label(evidence, statement, source_code=code).canonical_item_id == expected
        assert map_item_label(evidence, statement, source_code="999").canonical_item_id is None
    assert document_intent("Hệ số thanh toán bằng tiền năm 2031 đạt bao nhiêu?")[0] == "other"
    assert document_intent("Có phải tất cả nhà cửa tăng đều mua mới bằng tiền không?")[0] == "other"
    assert document_intent("Nêu các khoản mục trong bảng tiền")[0] == "document"
    fact = catalog.facts[0]
    scope = SimpleNamespace(
        status="resolved", evidence_status="json_bound", reporting_scope="consolidated"
    )
    catalog.get_reporting_scope = Mock(return_value=scope)
    pipeline = FinancialQAPipeline(
        catalog=catalog,
        repository=Mock(),
        documents=[
            QADocument(
                document_id=fact.document_id,
                company_id=fact.company_id,
                company_aliases=["TST"],
                reporting_year=2025,
            )
        ],
    )
    request = FinancialQARequest(
        question="Doanh thu hợp nhất năm 2025?",
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        company_id=fact.company_id,
        integration_v2=True,
    )
    assert pipeline._lite_context(request)[1] is None
    scope.evidence_status = "insufficient"
    assert pipeline._lite_context(request)[1] == "clarification_required"


def test_true_fact_cannot_bind_unrelated_model_goal_without_semantic_support():
    data = fixture()
    batch = batch_for(data)
    claim = batch.claims[0]
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), integration_v2=True)
    context = dict(
        requirements=[
            dict(
                requirement_id="R1",
                text="Khoản nợ riêng của khách hàng là bao nhiêu?",
                kind="fact",
                target_id=claim.supporting_evidence[0].canonical_item_id,
                answer_goal="value",
            )
        ],
        candidate_requirements={claim.candidate_id: ["R1"]},
    )
    histories = runtime.verify(batch, integration_context=context)
    assert histories[0].outcome.final.decision == "ACCEPT"  # true source-bound fact remains true
    assert runtime.summary["supported_requirements"][claim.candidate_id] == []
    assert runtime.summary["semantic_candidate_count"] == 1
    source = claim.supporting_evidence[0]
    context["requirements"][0]["text"] = f"Nêu {source.label} kỳ {source.period}"
    runtime.verify(batch, integration_context=context)
    assert runtime.summary["semantic_candidate_count"] == 0
    assert runtime.summary["supported_requirements"][claim.candidate_id] == ["R1"]
    plan = LitePlan(
        requirements=[
            IntegrationRequirement(
                requirement_id="R1",
                text=f"{source.label} năm {source.period} là bao nhiêu?",
                kind="fact",
                target_id=source.canonical_item_id,
                period=source.period,
                interpretation=True,
            )
        ],
        tasks=[
            LiteTask(
                task_id="T1", specialist="profitability", objective="Tra số", requirement_ids=["R1"]
            )
        ],
    )
    sources = inventory(
        SnapshotCatalog(**data),
        PlannerContext(
            document_id=source.document_id,
            snapshot_id=source.snapshot_id,
            company_id=source.company_id,
            period=source.period,
        ),
    )
    resolve_requirements(plan, sources)
    assert not plan.requirements[0].interpretation
