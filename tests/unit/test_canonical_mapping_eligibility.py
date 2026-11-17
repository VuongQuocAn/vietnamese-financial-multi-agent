"""Source-aligned import controls, not a financial accuracy benchmark."""

import json

from vietnamese_financial_multi_agent.accounting.context_resolution import ContextEvidence
from vietnamese_financial_multi_agent.accounting.item_mapping import map_item_label
from vietnamese_financial_multi_agent.evidence.refined_import import import_refined_document

from .test_refined_import import source


def save(root, page):
    (root / "TST/2025/page_0001.json").write_text(
        json.dumps(page, ensure_ascii=False), encoding="utf-8"
    )


def test_ragged_rows_do_not_discard_aligned_values_or_shift_cells(tmp_path):
    page = source(tmp_path)
    rows = page["blocks"][2]["table"]["rows"]
    rows.insert(0, ["section"])
    rows.insert(2, ["Giá vốn hàng bán", "11", "999"])
    rows.append(["Giá vốn hàng bán", "11", "888", "777", "extra"])
    save(tmp_path, page)
    _, facts, evidence, summary = import_refined_document(tmp_path, "TST_2025")
    assert len(facts) == 4
    assert facts[0].value.raw_value == "(1.234)"
    assert facts[0].sources[0].reference.source_pointer == "/blocks/2/table/rows/1/2"
    assert summary["tables"][0]["skipped_row_indices"] == [0, 2, 4]
    assert evidence[2].source_metadata["original_table"]["rows"] == rows
    assert evidence[2].structural_issues == ["ragged_rows"]
    assert all(f.value.raw_value not in {"999", "888", "777"} for f in facts)
    assert facts[1].value.normalized_value is None  # Dash remains missing, not zero.


def test_label_code_statement_binding_distinguishes_receivables_and_ordinals(tmp_path):
    source(tmp_path)
    _, facts, _, _ = import_refined_document(tmp_path, "TST_2025")
    ref = facts[0].sources[0].reference

    def mapped(label, code, statement="B01"):
        return map_item_label(
            ContextEvidence(raw_text=label, provenance=[ref]), statement, source_code=code
        )

    assert mapped("III. Các khoản phải thu ngắn hạn", "130").canonical_item_id == (
        "b01.short_term_receivables"
    )
    assert mapped("1. Phải thu ngắn hạn của khách hàng", "131").canonical_item_id == (
        "b01.short_term_trade_receivables"
    )
    assert mapped("IV. Hàng tồn kho", "140").canonical_item_id == "b01.inventory_total"
    assert mapped("1. Hàng tồn kho", "141").canonical_item_id == "b01.inventory_gross"
    assert mapped("Phải thu ngắn hạn của khách hàng", "130").canonical_item_id is None
    assert mapped("Các khoản phải thu ngắn hạn", "131").canonical_item_id is None
    assert mapped("Phải thu ngắn hạn của khách hàng", None).canonical_item_id is None
    assert mapped("Phải thu ngắn hạn của khách hàng", "131", "B09").canonical_item_id is None
    assert mapped("3. Doanh thu thuần về bán hàng & cc dịch vụ", "10", "B02").canonical_item_id == (
        "b02.net_revenue"
    )
    assert mapped("Doanh thu thuần về bán hàng & cc dịch vụ", "01", "B02").canonical_item_id is None


def test_period_suffixed_statement_restores_context_without_promoting_mentions(tmp_path):
    page = source(tmp_path)
    heading = "BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"
    page["blocks"][0]["text"] = heading + " - Cho năm tài chính kết thúc ngày 31/12/2025"
    table = page["blocks"][2]["table"]
    table["title"] = heading + " - Năm tài chính kết thúc ngày 31/12/2025"
    table["rows"] = [["3. Doanh thu thuần về bán hàng & cc dịch vụ", "10", "123", "100"]]
    save(tmp_path, page)
    _, facts, _, _ = import_refined_document(tmp_path, "TST_2025")
    assert len(facts) == 2
    assert {f.context.period for f in facts} == {"2025", "2024"}
    assert all(f.canonical_item_id == "b02.net_revenue" for f in facts)
    assert all(f.context.scale == 1 and f.value.unit == "VND" for f in facts)
    assert all(f.quality_context[0].decision == "usable_with_caveat" for f in facts)
    page["blocks"][0]["text"] = "Tham khảo " + page["blocks"][0]["text"]
    table["title"] = "Tham khảo " + table["title"]
    save(tmp_path, page)
    _, facts, _, summary = import_refined_document(tmp_path, "TST_2025")
    assert not facts
    assert "statement_unresolved" in summary["tables"][0]["issues"]
