"""Synthetic engineering tests; these fixtures are not financial quality evidence."""

import copy
import hashlib
import io
from decimal import Decimal
from types import SimpleNamespace

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    EXTRACTION_REF,
    extract_financial_page,
    extraction_schema_registry,
    parse_vietnamese_number,
    run_automated_pdf,
    validate_automated_extraction,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    RawPageIdentity,
)
from vietnamese_financial_multi_agent.document_processing.gemini_ingestion import IngestionPage
from vietnamese_financial_multi_agent.document_processing.vision_ocr import (
    VerifiedPageImage,
    image_source,
)


@pytest.fixture
def sample():
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    content = buffer.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    identity = RawPageIdentity(
        symbol="TEST", year="2025", page=7, image=f"sha256:{digest}", source_ref="synthetic-test"
    )
    image = VerifiedPageImage(identity, digest, 100, 100, content)

    def cell(text, row, column):
        return dict(text=text, row=row, column=column, reading="observed")

    payload = dict(
        statement_type="B02",
        context=["BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", "Mẫu số B02 - DN", "Đơn vị tính: VND"],
        limitations=[],
        tables=[
            dict(
                rows=2,
                columns=4,
                label_column=0,
                code_column=1,
                headers=[cell("Năm 2025", 0, 2), cell("Năm 2024", 0, 3)],
                cells=[
                    cell("4. Giá vốn hàng bán", 1, 0),
                    cell("11", 1, 1),
                    cell("1.234", 1, 2),
                    cell("(2.345)", 1, 3),
                ],
            )
        ],
    )
    record = dict(
        source=image_source(image),
        response=dict(
            status="success",
            finish_reason="stop",
            request_id="synthetic-request",
            provenance=dict(requested_model=dict(provider="gemini", model="mock")),
            output=dict(format="json", payload=payload),
        ),
    )
    return image, record, payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("417.992.011.559", "417992011559"),
        ("319.074.961.905", "319074961905"),
        ("0", "0"),
        ("-1.250.000", "-1250000"),
        ("(1.250.000)", "-1250000"),
        (" 123 ", "123"),
        ("-", None),
        ("", None),
        ("1.25", None),
        ("1,250", None),
        ("1.234,56", None),
        ("(-123)", None),
        ("1 250", None),
    ],
)
def test_decimal_parser(raw, expected):
    result = parse_vietnamese_number(raw)
    assert result == (Decimal(expected) if expected is not None else None)
    assert result is None or isinstance(result, Decimal)


def test_automatic_association_and_provenance_without_review(sample):
    image, record, _ = sample
    before = copy.deepcopy(record)
    result = validate_automated_extraction(image, record)
    assert record == before
    assert len(result["links"]) == 2
    for link, year, raw, normalized in zip(
        result["links"], ("2025", "2024"), ("1.234", "(2.345)"), ("1234", "-2345"), strict=True
    ):
        assert link["status"] == "accepted_extraction"
        assert link["canonical_item_id"] == "b02.cost_of_sales"
        assert link["result"]["value"]["normalized_value"] == normalized
        assert link["result"]["value"]["raw_value"] == raw
        assert link["result"]["context"]["period"] == year
        assert link["result"]["context"]["scale"] == "1"
        assert link["result"]["financial_fact_verified"] is False
        assert all(
            r["anchor"]["page"] == image.identity.model_dump(mode="json")
            for r in link["result"]["provenance"]
        )
        assert all(r["anchor"]["cell_id"] is None for r in link["result"]["provenance"])
        assert "manual_review" not in link


def test_d01_liabilities_mapping_preserves_columns_and_rejects_wrong_source_code(sample):
    image, record, payload = sample
    payload["statement_type"] = "B01"
    payload["context"] = ["BẢNG CÂN ĐỐI KẾ TOÁN", "Mẫu số B01 - DN", "Đơn vị tính: VND"]
    table = payload["tables"][0]
    table["headers"][0]["text"] = "31/12/2025"
    table["headers"][1]["text"] = "01/01/2025"
    table["cells"][0]["text"] = "C - NỢ PHẢI TRẢ"
    table["cells"][1]["text"] = "300"
    links = validate_automated_extraction(image, record)["links"]
    assert [link["canonical_item_id"] for link in links] == ["b01.total_liabilities"] * 2
    assert [link["result"]["context"]["period"] for link in links] == ["2025-12-31", "2025-01-01"]
    assert [link["result"]["value"]["normalized_value"] for link in links] == ["1234", "-2345"]
    table["cells"][1]["text"] = "310"
    links = validate_automated_extraction(image, record)["links"]
    assert all("source_code_conflict" in link["issues"] for link in links)
    assert all(link["status"] != "accepted_extraction" for link in links)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "header_conflict",
        "code_conflict",
        "statement_conflict",
        "unit_conflict",
        "unknown_position",
        "inferred",
        "empty",
        "out_of_bounds",
        "duplicate_table",
        "duplicate_period",
    ],
)
def test_conflicts_never_accept_affected_links(sample, mutation):
    image, record, payload = sample
    table = payload["tables"][0]
    if mutation == "missing":
        table["cells"].pop()
    elif mutation == "duplicate":
        table["cells"].append(copy.deepcopy(table["cells"][-1]))
    elif mutation == "header_conflict":
        table["headers"][1]["column"] = 2
    elif mutation == "code_conflict":
        table["cells"][1]["text"] = "12"
    elif mutation == "statement_conflict":
        payload["context"].append("BẢNG CÂN ĐỐI KẾ TOÁN")
    elif mutation == "unit_conflict":
        payload["context"].append("Đơn vị tính: triệu đồng")
    elif mutation == "unknown_position":
        table["cells"][-1]["column"] = None
    elif mutation == "inferred":
        table["cells"][-1]["reading"] = "inferred"
    elif mutation == "empty":
        table["cells"][-1]["text"] = "-"
    elif mutation == "out_of_bounds":
        table["cells"][-1]["row"] = 100
    elif mutation == "duplicate_table":
        payload["tables"].append(copy.deepcopy(table))
    elif mutation == "duplicate_period":
        table["headers"][1]["text"] = "Năm 2025"
    links = validate_automated_extraction(image, record)["links"]
    assert links
    affected = links if mutation not in {"missing", "duplicate", "inferred", "empty"} else links[1:]
    assert all(
        link["status"] != "accepted_extraction" and link["result"] is None for link in affected
    )


@pytest.mark.parametrize("mutation", ["schema", "binding", "failure", "truncated", "model"])
def test_invalid_response(sample, mutation):
    image, record, payload = sample
    if mutation == "schema":
        payload["tables"][0]["cells"][0]["unexpected"] = True
    elif mutation == "binding":
        record["source"]["image_sha256"] = "wrong"
    elif mutation == "failure":
        record["response"]["status"] = "error"
    elif mutation == "truncated":
        record["response"]["finish_reason"] = "length"
    elif mutation == "model":
        record["response"]["provenance"] = {}
    result = validate_automated_extraction(image, record)
    assert result["issues"] and not result["links"]


def test_structured_gateway_request(sample):
    image, record, payload = sample
    assert extraction_schema_registry().is_valid(EXTRACTION_REF, payload)
    calls = []

    def generate(request, **kwargs):
        calls.append((request.export(), kwargs))
        return SimpleNamespace(response=SimpleNamespace(export=lambda: record["response"]))

    result = extract_financial_page(
        SimpleNamespace(generate=generate),
        IngestionPage(image, {"page_number": 7}),
        credential_ref="mock",
    )
    assert result["extraction"]["links"][0]["status"] == "accepted_extraction"
    assert len(calls) == 1
    assert calls[0][0]["output_spec"]["schema_ref"] == EXTRACTION_REF.export()
    assert calls[0][0]["messages"][0]["images"][0]["mime_type"] == "image/png"


def test_descriptive_headers_and_as_of_period(sample):
    image, record, payload = sample
    payload["statement_type"] = "B01"
    payload["context"] = ["BẢNG CÂN ĐỐI KẾ TOÁN", "Đơn vị tính: triệu đồng"]
    table = payload["tables"][0]
    table["cells"][0]["text"] = "TỔNG CỘNG TÀI SẢN"
    table["cells"][1]["text"] = "270"
    table["headers"][0]["text"] = "31/12/2025"
    table["headers"][1]["text"] = "01/01/2025"
    table["headers"].append(dict(text="CHỈ TIÊU", reading="observed", row=0, column=0))
    links = validate_automated_extraction(image, record)["links"]
    assert len(links) == 2
    assert all(link["status"] == "accepted_extraction" for link in links)
    assert links[0]["result"]["context"]["period"] == "2025-12-31"
    assert links[1]["result"]["context"]["period"] == "2025-01-01"
    assert links[0]["result"]["context"]["scale"] == "1000000"
    assert links[0]["result"]["value"]["normalized_value"] == "1234"


def test_conflicting_duplicate_blocks_valid_row_too(sample):
    image, record, payload = sample
    duplicate = copy.deepcopy(payload["tables"][0])
    duplicate["cells"][1]["text"] = "12"
    payload["tables"].append(duplicate)
    links = validate_automated_extraction(image, record)["links"]
    assert all(link["status"] != "accepted_extraction" for link in links)


def test_missing_headers_are_reported(sample):
    image, record, payload = sample
    payload["tables"][0]["headers"] = []
    result = validate_automated_extraction(image, record)
    assert not result["links"]
    assert "table_0:headers_missing" in result["issues"]


def test_pdf_entrypoint_bound_cache_and_no_source_writes(sample, monkeypatch, tmp_path):
    image, record, _ = sample
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"synthetic entrypoint selection test, renderer mocked")
    original = pdf.read_bytes()
    selections = []

    def load(path, **kwargs):
        selections.append((path, kwargs))
        return [IngestionPage(image, {"page_number": 7})]

    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.accounting.automated_extraction.load_pages", load
    )
    results = run_automated_pdf(
        pdf, symbol="TEST", year="2025", pages=[7], cached_records={7: record}
    )
    assert results[0]["extraction"]["links"][0]["status"] == "accepted_extraction"
    assert selections[0][1]["pages"] == [7]
    assert pdf.read_bytes() == original
    record["source"]["image_sha256"] = "wrong"
    with pytest.raises(ValueError, match="cached_image_binding_mismatch"):
        run_automated_pdf(pdf, symbol="TEST", year="2025", pages=[7], cached_records={7: record})
