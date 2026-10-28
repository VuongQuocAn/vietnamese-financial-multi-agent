"""Synthetic discovery/selection regressions, independent of local PDFs and Gemini."""

from copy import deepcopy
from types import SimpleNamespace

import pypdfium2 as pdfium
import pytest
from vietnamese_financial_multi_agent.accounting import financial_runtime
from vietnamese_financial_multi_agent.document_processing import financial_discovery as discovery


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "synthetic.pdf"
    with pdfium.PdfDocument.new() as doc:
        for _ in range(3):
            page = doc.new_page(200, 300)
            page.close()
        doc.save(path)
    return path


def service(predictions):
    calls = []

    def generate(request, **kwargs):
        calls.append(request)
        prediction = predictions[len(calls) - 1]
        response = dict(status="success", finish_reason="stop", output=dict(payload=prediction))
        return SimpleNamespace(response=SimpleNamespace(export=lambda: deepcopy(response)))

    return SimpleNamespace(generate=generate, calls=calls)


def prediction(statement, **changes):
    return dict(
        statement_type=statement,
        classification="notes" if statement == "B09" else "statement",
        description="Synthetic continuation",
        has_financial_table=True,
        has_notes_text=statement == "B09",
        uncertainty=None,
        **changes,
    )


def test_multiple_statement_pages_and_notes_are_preserved(pdf):
    gateway = service([prediction("B01"), prediction("B01"), prediction("B09")])
    inventory = discovery.discover_financial_pages(pdf, symbol="TEST", year="2025", service=gateway)
    assert [r["page"] for r in inventory if r["selected"]] == [1, 2]
    assert inventory[2]["reason"] == "notes_inventory"
    assert len(gateway.calls) == 3
    cache = {r["page"]: r for r in inventory}
    replay = discovery.discover_financial_pages(
        pdf, symbol="TEST", year="2025", cached_predictions=cache
    )
    assert replay == inventory
    cache[2]["image_sha256"] = "wrong-image"
    with pytest.raises(ValueError, match="binding_mismatch"):
        discovery.discover_financial_pages(
            pdf, symbol="TEST", year="2025", cached_predictions=cache
        )


def test_unavailable_and_invalid_page_understanding_keeps_uncertain_pages(pdf):
    gateway = service([prediction("B02"), {}, prediction("B03")])
    inventory = discovery.discover_financial_pages(pdf, symbol="TEST", year="2025", service=gateway)
    assert [r["selected"] for r in inventory] == [True, True, True]
    assert inventory[1]["reason"] == "uncertain_fallback"
    no_service = discovery.discover_financial_pages(pdf, symbol="TEST", year="2025")
    assert all(r["selected"] and r["classification"] == "uncertain" for r in no_service)


@pytest.mark.parametrize(
    ("title", "statement"),
    [
        ("BẢNG CÂN ĐỐI KẾ TOÁN (Tiếp theo) Mẫu số B01 - DN", "B01"),
        ("BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH", "B02"),
        ("BÁO CÁO LƯU CHUYỂN TIỀN TỆ", "B03"),
        ("THUYẾT MINH BÁO CÁO TÀI CHÍNH Mẫu số B09 - DN", "B09"),
    ],
)
def test_explicit_text_titles(title, statement):
    assert discovery.classify_text(title).statement_type == statement
    assert discovery.classify_text("B01 B02 B03 B09 table of contents") is None


def test_runtime_automatic_selection_and_partial_response_preserve_good_evidence(monkeypatch):
    from .test_financial_query import sample

    _, record, evidence, _ = sample.__wrapped__()
    invalid = deepcopy(record)
    invalid["extraction"]["issues"] = ["invalid_extraction_response"]
    invalid["source"]["page"]["page"] = 9
    inventory = [
        dict(page=7, selected=True),
        dict(page=9, selected=True),
        dict(page=10, selected=False),
    ]
    monkeypatch.setattr(financial_runtime, "discover_financial_pages", lambda *a, **k: inventory)

    def run(*args, **kwargs):
        assert kwargs["pages"] == [7, 9]
        return [record, invalid]

    monkeypatch.setattr(financial_runtime, "run_automated_pdf", run)
    result = financial_runtime.process_financial_pdf("synthetic.pdf", symbol="TEST", year="2025")
    assert result["evidence"] == evidence
    assert result["inventory"] == inventory
    assert 9 in result["page_issues"]
    assert len(result["records"]) == 2


def test_runtime_empty_selection_does_not_extract(monkeypatch):
    monkeypatch.setattr(financial_runtime, "discover_financial_pages", lambda *a, **k: [])
    result = financial_runtime.process_financial_pdf("synthetic.pdf", symbol="TEST", year="2025")
    assert result["records"] == result["evidence"] == []
