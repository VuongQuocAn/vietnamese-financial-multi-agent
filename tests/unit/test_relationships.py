"""Synthetic engineering cases; real evidence is in docs/accounting-relationships.md."""

import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.accounting import (
    RELATIONSHIP_RULES,
    ContextEvidence,
    RelationshipCheck,
    RelationshipValue,
    TolerancePolicy,
    evaluate_accounting_relationships,
    evaluate_automated_relationships,
    run_automated_pdf,
)
from vietnamese_financial_multi_agent.accounting.automated_extraction import AutomatedLink

from .test_arithmetic import value as financial_value
from .test_automated_extraction import sample as image_record  # noqa: F401

RULE = RELATIONSHIP_RULES[0]
DIGEST = "a" * 64


def sample(statement="B01", number="100"):
    result = financial_value(
        "unused",
        number,
        statement_type=statement,
        mapped_item_code="b01.cash_equivalents" if statement == "B01" else "b03.closing_cash",
        period="2025-12-31" if statement == "B01" else "2025",
        period_type="as_of" if statement == "B01" else "fiscal_year",
    )
    for ref in result.provenance:
        ref.anchor.page.source_ref = f"sha256:{DIGEST}"
        ref.anchor.page.page = 5 if statement == "B01" else 8
        ref.anchor.page.image = f"sha256:{'b' * 64}"
    return RelationshipValue(
        pdf_sha256=DIGEST,
        extraction=result,
        period_end_evidence=ContextEvidence(
            raw_text="Cho năm tài chính kết thúc ngày 31/12/2025",
            provenance=deepcopy(result.provenance),
        ),
    )


def evaluate(rows, **kwargs):
    return evaluate_accounting_relationships(rows, [RULE], **kwargs)


@pytest.mark.parametrize(
    ("number", "status", "difference"),
    [
        ("100", "consistent", "0"),
        ("102", "inconsistent", "2"),
    ],
)
def test_cross_page_immutable_annotations(number, status, difference):
    rows = [sample(), sample("B03", number)]
    before = deepcopy(rows)
    (check,) = evaluate(rows)
    assert check.status == status
    assert check.difference == Decimal(difference)
    assert check.period == "2025-12-31"
    assert check.reporting_scope is None
    assert check.caveats == ["scope_unconfirmed"]
    assert {i.value.extraction.provenance[0].anchor.page.page for i in check.inputs} == {5, 8}
    assert check.inputs[0].value.extraction == rows[0].extraction
    assert not check.financial_fact_verified
    assert RelationshipCheck.model_validate_json(check.model_dump_json()) == check
    assert rows == before  # Failure never changes extraction or downstream QA eligibility.
    check.inputs[0].value.extraction.provenance.clear()
    assert rows == before


@pytest.mark.parametrize(
    "mutation",
    [
        "pdf",
        "date",
        "year",
        "scope",
        "known_unknown_scope",
        "unit",
        "currency",
        "scale",
        "missing_date_evidence",
        "wrong_date_evidence",
        "wrong_doc_evidence",
        "quarter",
        "wrong_anchor",
        "missing_provenance",
        "unresolved",
        "missing_value",
        "unknown_currency",
        "unknown_scale",
        "zero_scale",
        "wrong_balance_type",
        "wrong_flow_type",
    ],
)
def test_contexts_never_cross_join(mutation):
    rows = [sample(), sample("B03")]
    v = rows[1]
    c = v.extraction.context
    if mutation == "pdf":
        v.pdf_sha256 = "c" * 64
    elif mutation == "date":
        rows[0].extraction.context.period = "2025-01-01"
    elif mutation == "year":
        c.period = "2024"
    elif mutation == "scope":
        rows[0].extraction.context.reporting_scope = "separate"
        c.reporting_scope = "consolidated"
    elif mutation == "known_unknown_scope":
        c.reporting_scope = "separate"
    elif mutation == "unit":
        v.extraction.value.unit = "USD"
    elif mutation == "currency":
        c.currency = "USD"
    elif mutation == "scale":
        c.scale = Decimal(1000)
    elif mutation == "missing_date_evidence":
        v.period_end_evidence = None
    elif mutation == "wrong_date_evidence":
        v.period_end_evidence.raw_text = "Cho năm tài chính kết thúc ngày 31/12/2024"
    elif mutation == "wrong_doc_evidence":
        v.period_end_evidence.provenance[0].anchor.page.source_ref = "other"
    elif mutation == "quarter":
        c.period_type = "quarter"
    elif mutation == "wrong_anchor":
        v.extraction.provenance[0].anchor.page.source_ref = "other"
    elif mutation == "missing_provenance":
        v.extraction.provenance = []
    elif mutation == "unresolved":
        v.extraction.value.status = "unresolved"
    elif mutation == "missing_value":
        v.extraction.value.normalized_value = None
    elif mutation == "unknown_currency":
        c.currency = None
    elif mutation == "unknown_scale":
        c.scale = None
    elif mutation == "zero_scale":
        c.scale = Decimal(0)
    elif mutation == "wrong_balance_type":
        rows[0].extraction.context.period_type = "fiscal_year_end"
    elif mutation == "wrong_flow_type":
        c.period_type, c.period = "as_of", "2025-12-31"
    checks = evaluate(rows)
    assert all(check.status == "insufficient_data" for check in checks)
    assert all(check.difference is None for check in checks)


def test_same_confirmed_scope():
    rows = [sample(), sample("B03")]
    for row in rows:
        row.extraction.context.reporting_scope = "consolidated"
    (check,) = evaluate(rows)
    assert check.status == "consistent"
    assert check.caveats == []


def test_missing_is_not_zero_and_not_applicable():
    (check,) = evaluate([sample()])
    assert check.status == "insufficient_data"
    assert check.missing_inputs == ["b03.closing_cash"]
    assert check.computed_value is None
    assert evaluate([])[0].status == "not_applicable"


@pytest.mark.parametrize("conflict", [False, True])
def test_duplicates_block_even_identical(conflict):
    (check,) = evaluate([sample(), sample("B03"), sample("B03", "101" if conflict else "100")])
    assert check.status == "insufficient_data"
    assert "duplicate_or_conflicting_item:b03.closing_cash" in check.issues
    assert len(check.inputs) == 3


@pytest.mark.parametrize("mutation", [None, "code", "label", "statement", "mapped_conflict"])
def test_exact_source_code_label_statement_matching(mutation):
    rows = [sample(), sample("B03")]
    c = rows[1].extraction.context
    c.mapped_item_code = "70"
    c.raw_item_label = "Tiền và tương đương tiền cuối năm"
    if mutation == "code":
        c.mapped_item_code = "60"
    elif mutation == "label":
        c.raw_item_label = "Tiền tương tự"
    elif mutation == "statement":
        c.statement_type = "B02"
    elif mutation == "mapped_conflict":
        c.mapped_item_code = "b03.other"
    (check,) = evaluate(rows)
    if mutation is None:
        assert check.status == "consistent"
        assert check.inputs[1].matching == "source_code"
    else:
        assert check.status == "insufficient_data"


def test_decimal_precision_and_explicit_tolerance():
    number = "1234567890123456789012345678901234567890.01"
    with localcontext() as ctx:
        ctx.prec = 6
        (check,) = evaluate([sample(number=number), sample("B03", number)])
    assert check.difference == Decimal(0)
    assert check.reported_value == Decimal(number)
    (check,) = evaluate(
        [sample(), sample("B03", "101")],
        tolerance_policy=TolerancePolicy(absolute=Decimal(1), basis="test rounding"),
    )
    assert check.status == "consistent"
    assert check.tolerance_basis == "test rounding"


def record(value):
    result = value.extraction
    link = AutomatedLink(
        status="accepted_extraction",
        table=0,
        row=1,
        column=2,
        issues=[],
        result=result,
        canonical_item_id=result.context.mapped_item_code,
    )
    return dict(
        source={"synthetic": True},
        provenance=dict(
            pdf_sha256=DIGEST,
            document_id=f"sha256:{DIGEST}",
            page_number=result.provenance[0].anchor.page.page,
            image_sha256="b" * 64,
        ),
        extraction=dict(
            statement_type=result.context.statement_type,
            links=[link.model_dump(mode="json")],
            model={"model": "mock"},
            request_id="synthetic-request",
        ),
        response=dict(output=dict(payload=dict(context=[value.period_end_evidence.raw_text]))),
    )


def test_automated_records_integration():
    records = [record(sample()), record(sample("B03"))]
    for r in records:
        for ref in r["extraction"]["links"][0]["result"]["provenance"]:
            ref["source_pointer"] = "/context/0"
    before = deepcopy(records)
    (check,) = evaluate_automated_relationships(records, [RULE])
    assert check.status == "consistent"
    assert records == before
    assert check.inputs[1].value.source_metadata["request_id"] == "synthetic-request"
    assert check.inputs[1].value.automated_link.status == "accepted_extraction"
    records[1]["provenance"]["page_number"] = 99
    with pytest.raises(ValueError, match="page_metadata_conflict"):
        evaluate_automated_relationships(records, [RULE])


def test_unavailable_never_evaluates_fake_equality():
    rule = replace(RULE, unavailable_reason="adjustments_missing")
    (check,) = evaluate_accounting_relationships([sample(), sample("B03")], [rule])
    assert check.status == "insufficient_data"
    assert check.difference is None
    assert len(RELATIONSHIP_RULES) == 4
    assert sum(r.unavailable_reason is None for r in RELATIONSHIP_RULES) == 1


def test_statement_present_without_accepted_links_is_insufficient():
    r = record(sample("B03"))
    r["extraction"]["links"] = []
    (check,) = evaluate_automated_relationships([r], [RULE])
    assert check.status == "insufficient_data"
    assert check.pdf_sha256 == DIGEST
    assert check.issues == ["no_accepted_extractions_for_relationship"]
    assert check.missing_inputs == ["b01.cash_equivalents", "b03.closing_cash"]


def test_link_conflict_preserved_and_blocked():
    row = sample("B03")
    r = record(row)
    row.automated_link = AutomatedLink.model_validate_json(json.dumps(r["extraction"]["links"][0]))
    row.automated_link.canonical_item_id = "b03.other"
    (check,) = evaluate([sample(), row])
    assert check.status == "insufficient_data"
    assert "link_conflict:b03.closing_cash" in check.issues


def test_pdf_cache_to_relationships_with_unmapped_qa_data(request, monkeypatch):
    base_image, base_record, _ = request.getfixturevalue("image_record")
    pages, cache = [], {}
    for statement, page_number, title, label, code, header in [
        (
            "B01",
            5,
            "BẢNG CÂN ĐỐI KẾ TOÁN",
            "I. Tiền và các khoản tương đương tiền",
            "110",
            "31/12/2025",
        ),
        (
            "B03",
            8,
            "BÁO CÁO LƯU CHUYỂN TIỀN TỆ",
            "Tiền và tương đương tiền cuối năm",
            "70",
            "Năm 2025",
        ),
    ]:
        identity = base_image.identity.model_copy(
            update={
                "source_ref": f"sha256:{DIGEST}",
                "page": page_number,
            }
        )
        image = replace(base_image, identity=identity)
        r = deepcopy(base_record)
        from vietnamese_financial_multi_agent.document_processing.vision_ocr import image_source

        r["source"] = image_source(image)
        r["provenance"] = dict(
            pdf_sha256=DIGEST,
            document_id=f"sha256:{DIGEST}",
            page_number=page_number,
            image_sha256=image.sha256,
        )
        p = r["response"]["output"]["payload"]
        p["statement_type"] = statement
        p["context"] = [
            title,
            f"Mẫu số {statement} - DN",
            "Đơn vị tính: VND",
            "Cho năm tài chính kết thúc ngày 31/12/2025",
        ]
        table = p["tables"][0]
        table["headers"] = [dict(text=header, row=0, column=2, reading="observed")]
        table["rows"] = 3
        table["cells"] = [
            dict(text=text, row=row, column=column, reading="observed")
            for row, labels in [(1, (label, code, "100")), (2, ("Ngoài catalog", "999", "55"))]
            for column, text in enumerate(labels)
        ]
        cache[page_number] = r
        pages.append(SimpleNamespace(image=image, source=r["provenance"]))
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.accounting.automated_extraction.load_pages",
        lambda *a, **kw: pages,
    )
    records = run_automated_pdf(
        Path("synthetic.pdf"), symbol="TEST", year="2025", pages=[5, 8], cached_records=cache
    )
    before = deepcopy(records)
    (check,) = evaluate_automated_relationships(records, [RULE])
    assert check.status == "consistent"
    assert len(check.inputs) == 2
    assert records == before
    assert all(
        any(
            link["raw_label"] == "Ngoài catalog" and link["raw_value"] == "55"
            for link in r["extraction"]["links"]
        )
        for r in records
    )
