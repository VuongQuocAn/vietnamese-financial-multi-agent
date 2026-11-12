"""Small boundary controls; synthetic fixtures are not financial accuracy gold."""

import json
from types import SimpleNamespace

from vietnamese_financial_multi_agent.agents.document_qa_contracts import document_intent
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
    inventory,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import PlannerContext
from vietnamese_financial_multi_agent.api.claim_selection import select_claims
from vietnamese_financial_multi_agent.evidence import SnapshotCatalog
from vietnamese_financial_multi_agent.verification.lite_runtime import LiteVerificationRuntime

from .test_m4_execution import fixture
from .test_m6_lite import semantic_gateway
from .test_multihop_reasoning import reasoning_case
from .test_qa_lite import admitted as admitted


def test_mapped_fact_outside_specialist_labels_reaches_tools_and_candidate():
    data = fixture()
    fact = data["facts"][0]
    fact.canonical_item_id = "b02.revenue_deductions"
    fact.context.raw_item_label = "Các khoản giảm trừ doanh thu"
    data["source_reviews"][0].raw_label = fact.context.raw_item_label
    catalog = SnapshotCatalog(**data)
    context = PlannerContext(
        company_id=fact.company_id,
        document_id=fact.document_id,
        snapshot_id=fact.snapshot_id,
        period=fact.context.period,
        mode="deterministic",
    )
    source = next(
        s for s in inventory(catalog, context).values() if s["item"] == fact.canonical_item_id
    )
    assert source["roles"] == ["profitability"]
    result = FinancialLiteOrchestrator(catalog).run(
        question="Các khoản giảm trừ doanh thu năm 2030?",
        context=context,
    )
    assert any(
        e.canonical_item_id == fact.canonical_item_id
        for c in result.candidates
        for e in c.supporting_evidence
    )
    assert any(t.operation == "get_financial_fact" for t in result.supervisor_result.tool_trace)
    foreign = context.model_copy(update={"company_id": "other"})
    assert not [s for s in inventory(catalog, foreign).values() if s["kind"] == "fact"]


def test_semantic_request_binds_operations_to_source_ids_without_new_calls():
    data, batch = reasoning_case(operator="subtract")
    claim = batch.claims[0]
    claim.reasoning.claim_type = "reasoned_conclusion"
    gateway = semantic_gateway()
    runtime = LiteVerificationRuntime(SnapshotCatalog(**data), gateway)
    runtime.verify(batch)
    assert gateway.generate.call_count == 1
    request = gateway.generate.call_args.args[0]
    row = json.loads(request.messages[-1].content)[0]
    bindings = {b["evidence_id"]: b for b in row["evidence_bindings"]}
    assert bindings.keys() == row["operand_bindings"].keys()
    assert all(b["item"] and b["value"] for b in bindings.values())
    assert "ĐỊNH NGHĨA" in request.messages[0].content
    assert "trạng thái kiểm toán" in request.messages[0].content


def test_confirmed_scope_overlay_and_policy_routing_preserve_boundaries(admitted):
    request, entry = admitted
    request.reporting_scope = "consolidated"
    assert not select_claims(request, [entry])[0]
    resolution = SimpleNamespace(
        document_id=entry.identity.document_id,
        snapshot_id=entry.identity.snapshot_id,
        status="resolved",
        evidence_status="confirmed",
        reporting_scope="consolidated",
    )
    assert select_claims(request, [entry], scope_resolution=resolution)[0] == [entry]
    resolution.snapshot_id = "foreign"
    assert not select_claims(request, [entry], scope_resolution=resolution)[0]
    assert (
        document_intent(
            "Thuyết minh doanh nghiệp quy định giá trị hàng tồn kho theo cơ sở nào và dùng phương pháp nào xác định giá gốc?"
        )[0]
        == "document"
    )
    assert (
        document_intent("Thuyết minh nói gì về hàng tồn kho và tài sản ngắn hạn là bao nhiêu?")[0]
        == "mixed"
    )
