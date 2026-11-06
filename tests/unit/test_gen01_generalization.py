"""GEN-01 regressions from observed report forms; numeric fixtures are synthetic."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    validate_automated_extraction,
)
from vietnamese_financial_multi_agent.accounting.item_mapping import map_item_label
from vietnamese_financial_multi_agent.accounting.quality import evidence_from_automated_records
from vietnamese_financial_multi_agent.evidence import fact_from_m2

from .test_automated_extraction import sample as sample
from .test_financial_item_mapping import evidence


def test_source_coded_consolidated_aliases_preserve_statement_and_code_gates():
    aliases = [
        ("B01", "270", "TỔNG CỘNG TÀI SẢN (270=100+200)", "b01.total_assets"),
        ("B01", "300", "C. NỢ PHẢI TRẢ", "b01.total_liabilities"),
        ("B02", "10", "3. Doanh thu thuần về bán hàng (10=01)", "b02.net_revenue"),
        ("B02", "20", "5. Lợi nhuận gộp về bán hàng (20=10-11)", "b02.gross_profit"),
        ("B02", "60", "16. (Lỗ) sau thuế thu nhập doanh nghiệp (60=50-51)", "b02.profit_after_tax"),
        ("B03", "70", "Tiền cuối năm (70=50+60+61)", "b03.closing_cash"),
    ]
    for statement, code, label, canonical in aliases:
        assert (
            map_item_label(evidence(label), statement, source_code=code).canonical_item_id
            == canonical
        )
        assert (
            map_item_label(evidence(label), statement, source_code="999").canonical_item_id is None
        )
        assert map_item_label(evidence(label), "B09", source_code=code).canonical_item_id is None
    # BBS subtotal 410 must not become a competing total-equity 400 candidate.
    assert not map_item_label(evidence("I. Vốn chủ sở hữu"), "B01", source_code="410").candidates


def test_relative_annual_columns_use_page_evidence_never_filename_year(sample):
    image, record, payload = sample
    payload["context"].append("Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024")
    table = payload["tables"][0]
    for header, text in zip(table["headers"], ("Năm nay", "Năm trước"), strict=True):
        header["text"] = text
    links = validate_automated_extraction(image, record)["links"]
    assert [link["result"]["context"]["period"] if link["result"] else None for link in links] == [
        "2024",
        "2023",
    ]
    assert [link["raw_header"] for link in links] == ["Năm nay", "Năm trước"]
    # Raw unmapped rows must share the same period resolver as mapped links.
    table["cells"][0]["text"] = "Chỉ tiêu chưa có alias"
    raw_record = dict(record, extraction=validate_automated_extraction(image, record))
    assert [e.extraction.context.period for e in evidence_from_automated_records([raw_record])] == [
        "2024",
        "2023",
    ]
    payload["context"].append("Cho năm tài chính kết thúc ngày 31 tháng 12 năm 2023")
    assert all(
        "period_unresolved" in link["issues"]
        for link in validate_automated_extraction(image, record)["links"]
    )
    payload["context"] = payload["context"][:-2]
    assert all(
        "period_unresolved" in link["issues"]
        for link in validate_automated_extraction(image, record)["links"]
    )


def test_duplicate_ordinal_and_label_position_has_explicit_page_diagnostic(sample):
    image, record, payload = sample
    payload["tables"][0]["cells"].append(dict(text="4.", row=1, column=0, reading="observed"))
    result = validate_automated_extraction(image, record)
    assert "table_0:duplicate_cell_position" in result["issues"]
    assert not any(link["status"] == "accepted_extraction" for link in result["links"])


def test_relative_balance_columns_and_explicit_consolidated_title(sample):
    image, record, payload = sample
    payload["statement_type"] = "B01"
    payload["context"] = [
        "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT (Tiếp theo)",
        "Mẫu số B01-DN/HN",
        "Tại ngày 31 tháng 12 năm 2024",
        "Đơn vị: VND",
    ]
    table = payload["tables"][0]
    table["cells"][0]["text"] = "NỢ PHẢI TRẢ"
    table["cells"][1]["text"] = "300"
    for header, text in zip(table["headers"], ("Số cuối năm", "Số đầu năm"), strict=True):
        header["text"] = text
    links = validate_automated_extraction(image, record)["links"]
    assert [link["result"]["context"]["period"] if link["result"] else None for link in links] == [
        "2024-12-31",
        "2024-01-01",
    ]
    assert all(link["result"]["context"]["reporting_scope"] == "consolidated" for link in links)
    # Missing document scope stays unresolved; never assign separate by default.
    payload["context"][0] = "BẢNG CÂN ĐỐI KẾ TOÁN"
    assert all(
        link["result"]["context"]["reporting_scope"] is None
        for link in validate_automated_extraction(image, record)["links"]
    )


def test_task_attempt_cap_survives_runner_restart(tmp_path):
    bounded = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/run_cross_company_ingestion.py")
    )["BoundedService"]
    (tmp_path / "budget.json").write_text(json.dumps(dict(limit=60, reserved_attempts=59)))
    calls = []

    def generate(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(response=None, guard_result=SimpleNamespace(reason="mock"))

    service = SimpleNamespace(
        pool=SimpleNamespace(ledger=dict(recent=[])), generate=generate, last_attempts=[]
    )
    request = SimpleNamespace(request_id="synthetic-budget-control")
    runner = bounded(service, tmp_path)
    runner.phase("TEST", "recovery", 2)
    runner.generate(request, reservation=SimpleNamespace(token_upper_bound=1))
    runner.generate(request, reservation=SimpleNamespace(token_upper_bound=1))
    restarted = bounded(service, tmp_path)
    restarted.phase("TEST", "recovery", 2)
    restarted.generate(request, reservation=SimpleNamespace(token_upper_bound=1))
    assert len(calls) == 1
    assert json.loads((tmp_path / "budget.json").read_text())["reserved_attempts"] == 60


def test_canonical_adapter_carries_catalog_role_for_existing_m2_mapping(sample):
    image, record, payload = sample
    payload["tables"][0]["cells"][0]["text"] = "Doanh thu thuần về bán hàng và cung cấp dịch vụ"
    payload["tables"][0]["cells"][1]["text"] = "10"
    record["extraction"] = validate_automated_extraction(image, record)
    item = evidence_from_automated_records([record])[0]
    fact = fact_from_m2(item, document_id="document", snapshot_id="snapshot", company_id="company")
    assert fact.canonical_item_id == "b02.net_revenue"
    assert fact.semantic_role == "revenue"
    item.source_item_code = "999"
    assert fact_from_m2(item, document_id="document", snapshot_id="snapshot").semantic_role is None
