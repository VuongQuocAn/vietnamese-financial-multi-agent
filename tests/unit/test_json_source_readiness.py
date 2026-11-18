"""Source fidelity and negative scope controls; synthetic values are not benchmark evidence."""

import json
from unittest.mock import Mock

import pytest
from vietnamese_financial_multi_agent.agents.lite_orchestrator import (
    FinancialLiteOrchestrator,
)
from vietnamese_financial_multi_agent.agents.planner_contracts import (
    PlannerContext,
    PlannerLLMMetadata,
)
from vietnamese_financial_multi_agent.core.llm_contracts import ModelIdentity
from vietnamese_financial_multi_agent.core.llm_gateway import _failure
from vietnamese_financial_multi_agent.evidence.composition import load_composition
from vietnamese_financial_multi_agent.evidence.graph import build_graph
from vietnamese_financial_multi_agent.evidence.json_catalog import (
    json_document_composition,
    resolve_pointer,
)
from vietnamese_financial_multi_agent.evidence.refined_import import import_refined_document
from vietnamese_financial_multi_agent.evidence.search import SearchDocumentEvidenceRequest
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog, SnapshotDescriptor
from vietnamese_financial_multi_agent.tools.evidence_retrieval import EvidenceRetrievalTools

from .test_refined_import import source


def catalog_fixture(root, scope=""):
    page = source(root)
    page["blocks"].insert(0, dict(type="heading", text="CÔNG TY CỔ PHẦN TEST"))
    if scope:
        page["blocks"].append(dict(type="paragraph", text=scope))
    path = root / "TST/2025/page_0001.json"
    path.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    manifest, facts, evidence, _ = import_refined_document(root, "TST_2025")
    descriptor = SnapshotDescriptor(
        document_id=manifest["document_id"],
        snapshot_id=manifest["snapshot_id"],
        source_kind="json",
        pdf_sha256=None,
        json_sha256=manifest["document_id"].rsplit(":", 1)[1],
        json_pages={p["page"]: p["sha256"] for p in manifest["pages"]},
        origin="normalized_projection",
    )
    return SnapshotCatalog(
        [descriptor],
        facts,
        evidence,
        graph=build_graph(facts, evidence),
        json_sources={manifest["pages"][0]["sha256"]: path.read_bytes()},
    )


def test_scope_exact_selected_option_missing_conflict_and_tampered_source(tmp_path):
    from vietnamese_financial_multi_agent.tools.question_understanding import understand

    assert understand("Các đối tượng có tên riêng trong năm 2030?")[0].reporting_scope is None
    assert (
        understand("Các mục được nêu riêng trên báo cáo hợp nhất năm 2030?")[0].reporting_scope
        == "consolidated"
    )
    assert understand("Doanh thu TEST 2030 riêng")[0].reporting_scope == "separate"
    cases = (
        (
            "[X] BCTC riêng (không có công ty con)\n[ ] BCTC hợp nhất (có công ty con)\n[X] Không",
            "resolved",
            "separate",
        ),
        ("[ ] BCTC riêng\n[ ] BCTC hợp nhất", "unresolved", None),
        ("[?] BCTC riêng", "unresolved", None),
        ("[x] BCTC riêng\n[x] BCTC hợp nhất", "conflicted", None),
    )
    for i, (text, status, scope) in enumerate(cases):
        catalog = catalog_fixture(tmp_path / str(i), text)
        d = catalog.descriptors[0]
        resolved = catalog.get_reporting_scope(d.document_id, d.snapshot_id)
        assert (resolved.status, resolved.reporting_scope) == (status, scope)
        assert resolved.financial_fact_verified is False and resolved.reviews == []
        if scope:
            assert resolved.evidence_status == "json_bound"
            assert (
                resolved.context_resolution.evidence[0]
                .provenance[0]
                .source_pointer.endswith("/text")
            )
            digest = next(iter(d.json_pages.values()))
            catalog.json_source_bytes[digest] = b"{}"
            assert catalog.get_reporting_scope(d.document_id, d.snapshot_id).status == "unresolved"


def test_json_composition_replays_pins_and_search_uses_exact_cell_pointers(tmp_path):
    catalog = catalog_fixture(tmp_path)
    manifest = json_document_composition(catalog)
    assert manifest.financial_snapshot.pdf_sha256 is None
    tools = EvidenceRetrievalTools.from_composition(
        manifest,
        catalog,
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
    )
    try:
        result = tools.search_document_evidence(
            SearchDocumentEvidenceRequest(
                document_id=manifest.logical_document_id,
                composition_id=manifest.composition_id,
                query="Giá vốn hàng bán",
            )
        )
        assert result.status == "found"
        hit = result.matches[0]
        assert hit.pdf_page is None and hit.source_page == 1
        page = next(iter(catalog.json_sources.values()))
        assert all(resolve_pointer(page, c.source_pointer) == c.text for c in hit.cells)
        assert all(c.pdf_page is None for c in hit.evidence.citations)
    finally:
        tools.close_search()
    catalog.evidence[3].structure.cells[0].text = "changed"
    with pytest.raises(ValueError, match="json_composition_evidence_mismatch"):
        load_composition(
            manifest,
            catalog,
            document_id=manifest.logical_document_id,
            composition_id=manifest.composition_id,
        )


def test_m5_receives_readonly_source_context_without_new_numeric_handles(tmp_path):
    catalog = catalog_fixture(tmp_path)
    captured = []

    def generate(request):
        captured.append(request)
        if request.request_id.startswith("m5-evidence-demand"):
            from .test_financial_qa import gateway_for

            prompt = json.loads(request.messages[0].content)
            source = next(
                key
                for key, row in prompt["inventory"].items()
                if row["item"] == "b02.cost_of_sales" and row["period"] == "2025"
            )
            return gateway_for(
                dict(
                    retrieve=[dict(source=source)],
                    document_search=dict(kind="exact_text", query="đơn vị tính"),
                ),
                [],
            ).generate(request)
        return _failure(request, "provider_unavailable")

    d = catalog.descriptors[0]
    context = PlannerContext(
        company_id=catalog.facts[0].company_id,
        document_id=d.document_id,
        snapshot_id=d.snapshot_id,
        model=ModelIdentity(provider="gemini", model="test"),
        mode="gemini",
    )
    from vietnamese_financial_multi_agent.agents.coordinator_plan import adapt_plan

    plan, errors = adapt_plan(
        dict(
            goals=[dict(text="Nhận xét giới hạn của giá vốn hàng bán năm 2025")],
            tasks=[
                dict(
                    role="profitability",
                    objective="Giá vốn hàng bán năm 2025",
                    goal_indexes=[0],
                    after=[],
                )
            ],
        )
    )
    assert not errors
    engine = FinancialLiteOrchestrator(
        catalog,
        Mock(generate=generate),
        supervisor=Mock(plan=Mock(return_value=(plan, PlannerLLMMetadata(), []))),
        composition=json_document_composition(catalog),
        document_repository=catalog,
    )
    result = engine.run(question="Giá vốn hàng bán năm 2025 là bao nhiêu?", context=context)
    prompts = [
        json.loads(r.messages[0].content) for r in captured if r.request_id.startswith("m5-lite-")
    ]
    assert prompts and prompts[0]["document_source_context"], result.errors
    source_context = prompts[0]["document_source_context"]
    assert all(
        c["handle"].startswith("D-")
        and c["text"]
        and all(not citation["financial_fact_verified"] for citation in c["citations"])
        for c in source_context
    )
    assert all(not e["id"].startswith("D") for e in prompts[0]["evidence"])
