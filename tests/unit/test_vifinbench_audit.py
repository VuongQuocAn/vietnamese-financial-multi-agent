"""Engineering checks cho audit helper, không phải financial accuracy evaluation."""

from decimal import Decimal

from scripts.audit_vifinbench_neutral import arithmetic_probes, integer_value, markdown_table


def test_integer_parser_preserves_sign_and_rejects_unknowns():
    assert integer_value("(1.234.567)") == Decimal(-1234567)
    assert integer_value("-1,234,567") == Decimal(-1234567)
    assert integer_value("0") == Decimal(0)
    for value in ("", "-", "–", "16,50", "1.23", "1.234,56"):
        assert integer_value(value) is None


def test_arithmetic_uses_actual_code_column_and_keeps_mismatch():
    record = {
        "table_id": "SAMPLE_2025_p001_t001",
        "page": 1,
        "table": {
            "title": "Báo cáo kết quả hoạt động kinh doanh",
            "columns": ["STT", "Chỉ tiêu", "Mã số", "Năm 2025", "Năm 2024"],
            "rows": [
                ["1", "Doanh thu thuần", "10", "1.000", "-"],
                ["2", "Giá vốn", "11", "700", "100"],
                ["3", "Lợi nhuận gộp", "20", "301", "900"],
            ],
        },
    }
    checks = arithmetic_probes(record)
    assert len(checks) == 1  # Không tự biến dấu '-' kỳ trước thành 0.
    assert checks[0]["header"] == "Năm 2025"
    assert checks[0]["difference"] == "1"
    assert checks[0]["matches"] is False


def test_markdown_retains_extra_cell_without_claiming_header_alignment():
    table = {"columns": ["Chỉ tiêu", "Kỳ"], "rows": [["A|B", "1", "2"]]}
    rendered = markdown_table(table)
    assert "| Chỉ tiêu | Kỳ |  |" in rendered
    assert "| A\\|B | 1 | 2 |" in rendered
