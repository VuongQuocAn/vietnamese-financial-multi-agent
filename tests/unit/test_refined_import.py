"""JSON fidelity and provenance controls; synthetic tests are not financial gold."""

import json

import pytest
from vietnamese_financial_multi_agent.evidence.contracts import assess_fact_consistency
from vietnamese_financial_multi_agent.evidence.document_evidence import associate_fact
from vietnamese_financial_multi_agent.evidence.graph import build_graph, validate_graph
from vietnamese_financial_multi_agent.evidence.refined_import import import_refined_document
from vietnamese_financial_multi_agent.evidence.retrieval import EvidenceRetrieval
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog, SnapshotDescriptor


def source(tmp_path):
    folder = tmp_path / "TST" / "2025"
    folder.mkdir(parents=True)
    page = dict(
        document_id="TST_2025",
        page=1,
        status="complete",
        model="synthetic",
        prompt_version="synthetic",
        warnings=["synthetic source caveat"],
        blocks=[
            dict(type="heading", text="BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"),
            dict(type="paragraph", text="Đơn vị tính: VND"),
            dict(
                type="table",
                table=dict(
                    title="BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH",
                    columns=["CHỈ TIÊU", "Mã số", "Năm 2025", "Năm 2024"],
                    rows=[
                        ["Giá vốn hàng bán", "11", "(1.234)", "-"],
                        ["Lợi nhuận sau thuế thu nhập doanh nghiệp", "60", "", "12,5"],
                    ],
                ),
            ),
            dict(
                type="table", table=dict(title="ragged", columns=["A", "B"], rows=[["x", "1", "2"]])
            ),
        ],
    )
    (folder / "page_0001.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    return page


def test_import_preserves_cells_maps_finance_and_keeps_json_provenance(tmp_path):
    page = source(tmp_path)
    manifest, facts, evidence, summary = import_refined_document(tmp_path, "TST_2025")
    assert len(facts) == 4
    assert facts[0].canonical_item_id == "b02.cost_of_sales"
    assert str(facts[0].value.normalized_value) == "-1234"
    assert facts[0].context.period == "2025" and facts[0].value.unit == "VND"
    assert all(f.value.normalized_value is None for f in facts[1:])
    table = evidence[2]
    assert table.source_metadata["original_table"] == page["blocks"][2]["table"]
    assert evidence[3].structural_issues == ["ragged_rows"]
    assert summary["tables"][1]["observations"] == 0
    assert manifest["pdf_verified"] is False
    assert all(
        not f.financial_fact_verified and not f.sources[0].reference.anchor.page.image
        for f in facts
    )
    assert all(f.quality_context[0].decision != "usable" for f in facts)


def test_json_graph_exact_association_and_pdf_boundary(tmp_path):
    source(tmp_path)
    _, facts, evidence, _ = import_refined_document(tmp_path, "TST_2025")
    graph = build_graph(facts, evidence)
    result = validate_graph(graph, facts, evidence)
    assert {a.status for a in result.nodes + result.edges} == {"valid"}
    assert not result.orphan_nodes
    assert associate_fact(facts[0], evidence[2]) is not None
    assert associate_fact(facts[0], evidence[3]) is None
    assert assess_fact_consistency(facts[0]).status != "inconsistent"
    api = EvidenceRetrieval(facts, evidence, graph=graph)
    response = api.get_fact(facts[0].observation_identity())
    assert response.status == "found"
    assert all(
        c.pdf_page is None and "json_source_not_pdf_verified" in c.limitations
        for c in response.matches[0].citations
    )
    changed = facts[0].model_copy(deep=True)
    changed.sources[0].reference.anchor.status = "resolved"
    assert assess_fact_consistency(changed).status == "inconsistent"
    changed = facts[0].model_copy(deep=True)
    changed.sources[0].reference.anchor.page.source_ref = "json:sha256:bad"
    assert assess_fact_consistency(changed).status == "inconsistent"
    # Even a supplied descriptor cannot pass a JSON hash off as a PDF snapshot.
    catalog = SnapshotCatalog(
        [
            SnapshotDescriptor(
                document_id=facts[0].document_id,
                snapshot_id=facts[0].snapshot_id,
                pdf_sha256=facts[0].sources[0].reference.anchor.page.source_ref.rsplit(":", 1)[1],
                origin="normalized_projection",
            )
        ],
        facts=facts,
        evidence=evidence,
        graph=graph,
    )
    assert catalog.select(facts[0].document_id, facts[0].snapshot_id).status == "blocked"


def test_snapshot_changes_with_source_and_does_not_infer_missing_pages(tmp_path):
    source(tmp_path)
    first, *_ = import_refined_document(tmp_path, "TST_2025")
    assert first["completeness_verified"] is False
    path = tmp_path / "TST/2025/page_0001.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["page"] = 3
    (path.parent / "page_0003.json").write_text(json.dumps(value), encoding="utf-8")
    second, *_ = import_refined_document(tmp_path, "TST_2025")
    assert first["snapshot_id"] != second["snapshot_id"]
    assert second["missing_pages"] == [2]
    with pytest.raises(ValueError, match="invalid_document_alias"):
        import_refined_document(tmp_path, "../../outside")
