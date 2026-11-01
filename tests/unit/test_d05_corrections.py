"""16 generic controls độc lập BBS; synthetic PASS không là financial accuracy."""

import copy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    ExtractedPage,
    validate_automated_extraction,
)
from vietnamese_financial_multi_agent.accounting.completeness import (
    SourceRow,
    SourceRowInventory,
    assess_row_completeness,
)
from vietnamese_financial_multi_agent.accounting.extraction_semantics import numeric_token_issues
from vietnamese_financial_multi_agent.accounting.quality import evidence_from_automated_records
from vietnamese_financial_multi_agent.accounting.raw_corrections import extraction_payload
from vietnamese_financial_multi_agent.evidence import (
    EvidenceRetrieval,
    evidence_from_persisted_result,
    facts_from_persisted_result,
)
from vietnamese_financial_multi_agent.evidence.snapshots import SnapshotCatalog, SnapshotDescriptor

from .test_arithmetic import evaluate, inputs
from .test_automated_extraction import sample as extraction_sample


@pytest.fixture
def sample():
    return extraction_sample.__wrapped__()


def cell(text, row, column):
    return dict(text=text, row=row, column=column, reading="observed")


def inventory(image):
    return SourceRowInventory(
        document_id=image.identity.source_ref,
        pdf_page=image.identity.page,
        table=0,
        statement_type="B02",
        source_reference="synthetic-independent-source",
        source_image_sha256="independent-image-digest",
        method="controlled_original_pdf_visual_read",
        full_table=True,
        terminal_boundary_observed=True,
        rows=[
            SourceRow(
                label="4. Giá vốn hàng bán",
                code="11",
                selector="source-row-1",
                value_columns=[2, 3],
            ),
            SourceRow(
                label="Lãi cơ bản trên cổ phiếu",
                code="70",
                selector="source-row-2",
                value_columns=[2, 3],
            ),
        ],
    )


def coverage(sample, source):
    image, _, payload = sample
    return assess_row_completeness(ExtractedPage(**payload), image.identity, source)


def project(sample):
    image, record, _ = sample
    record["extraction"] = validate_automated_extraction(image, record)
    return evidence_from_automated_records([record])


def test_missing_terminal_row_and_recovered_coverage(sample):
    source = inventory(sample[0])
    assert coverage(sample, source)["rows"][-1]["status"] == "row_missing"
    table = sample[2]["tables"][0]
    table["rows"] = 3
    table["cells"].extend(
        [
            cell("Lãi cơ bản trên cổ phiếu", 2, 0),
            cell("70", 2, 1),
            cell("17", 2, 2),
            cell("16", 2, 3),
        ]
    )
    assert coverage(sample, source)["status"] == "covered"


def test_missing_middle_row(sample):
    source = inventory(sample[0])
    source.rows.append(
        SourceRow(
            label="Other terminal item", code="90", selector="source-row-3", value_columns=[2, 3]
        )
    )
    table = sample[2]["tables"][0]
    table["rows"] = 4
    table["cells"].extend(
        [cell("Other terminal item", 3, 0), cell("90", 3, 1), cell("9", 3, 2), cell("8", 3, 3)]
    )
    assert [r["status"] for r in coverage(sample, source)["rows"]] == [
        "row_present",
        "row_missing",
        "row_present",
    ]


def test_legitimately_absent_optional_row(sample):
    source = inventory(sample[0])
    source.rows[-1].status = "not_applicable"
    assert coverage(sample, source)["status"] == "covered"


def test_incomplete_inventory_ambiguity_unreadable_and_binding(sample):
    source = inventory(sample[0])
    source.rows = source.rows[:1]
    source.terminal_boundary_observed = False
    assert coverage(sample, source)["status"] == "coverage_uncertain"
    source.rows[0].status = "unreadable"
    assert coverage(sample, source)["rows"][0]["status"] == "source_unreadable"
    source.rows[0].status = "ambiguous"
    assert coverage(sample, source)["rows"][0]["status"] == "row_ambiguous"
    source.document_id = "other-document"
    assert coverage(sample, source)["issues"] == ["source_inventory_binding_mismatch"]
    assert coverage(sample, None)["status"] == "coverage_uncertain"
    source = inventory(sample[0])
    source.rows = source.rows[:1]
    source.rows[0].code = None
    table = sample[2]["tables"][0]
    table["cells"] = [c for c in table["cells"] if c["column"] != table["code_column"]]
    assert coverage(sample, source)["status"] == "covered"


def test_column_header_in_body_is_not_financial(sample):
    table = sample[2]["tables"][0]
    table["cells"][0]["text"] = "CHỈ TIÊU"
    table["cells"][1]["text"] = "Mã số"
    assert project(sample) == []
    assert sample[1]["extraction"]["structure"][-1]["role"] == "column_header"


def test_numeric_note_reference_remains_in_table_evidence(sample):
    table = sample[2]["tables"][0]
    table["columns"] = 5
    table["headers"].append(cell("Thuyết số", 0, 4))
    table["cells"].append(cell("12", 1, 4))
    assert len(project(sample)) == 2
    evidence = evidence_from_persisted_result(
        dict(document_id="doc", attempt_id="v1", records=[sample[1]])
    )
    assert any(c.text == "12" for e in evidence if e.kind == "table" for c in e.structure.cells)


def test_valid_alphanumeric_codes_are_preserved(sample):
    for code in ("411a", "421b"):
        sample[2]["tables"][0]["cells"][1]["text"] = code
        assert [e.source_item_code for e in project(sample)] == [code, code]


def test_section_and_signature_keep_raw_evidence(sample):
    table = sample[2]["tables"][0]
    table["cells"] = [
        cell("Kế toán trưởng", 1, 0),
        cell(None, 1, 1),
        cell(None, 1, 2),
        cell(None, 1, 3),
    ]
    assert project(sample) == []
    assert sample[1]["extraction"]["structure"][-1]["role"] == "signature_or_footer"
    table["cells"][0]["text"] = "Các khoản mục khác"
    assert project(sample) == []
    assert sample[1]["extraction"]["structure"][-1]["role"] == "section_header"
    table["cells"][0]["text"] = "Chi phí giám đốc"
    table["cells"][2]["text"] = "42"
    table["cells"][3]["text"] = "43"
    assert len(project(sample)) == 2
    assert sample[1]["extraction"]["structure"][-1]["role"] == "financial_item"


def test_suspicious_tokens_are_quality_issues(sample):
    for token in ("-garbled", "12x3", "1.23", "--", "-."):
        assert numeric_token_issues(token)
        sample[2]["tables"][0]["cells"][2]["text"] = token
        assert any("numeric_token" in i for i in project(sample)[0].extraction_issues)


def test_legitimate_nulls_never_become_zero(sample):
    for token in ("-", "–", "—", "", "N/A"):
        assert numeric_token_issues(token) == []
    assert numeric_token_issues("-", Decimal(0)) == ["null_numeric_conflict"]
    sample[2]["tables"][0]["cells"][2]["text"] = "-"
    assert project(sample)[0].extraction.value.normalized_value is None


def test_correction_overlay_preserves_original_and_rejects_wrong_binding(sample):
    image, record, payload = sample
    payload["tables"][0]["cells"][2]["text"] = "-artifact"
    original = copy.deepcopy(record["response"])
    record["raw_corrections"] = [
        dict(
            document_id=image.identity.source_ref,
            pdf_page=image.identity.page,
            request_id=record["response"]["request_id"],
            selector="/tables/0/cells/2",
            original_raw_value="-artifact",
            corrected_raw_value="-",
            review_reference="synthetic-review",
            review_image_sha256="image-hash",
            method="controlled_original_pdf_visual_read",
        )
    ]
    assert project(sample)[0].extraction.value.raw_value == "-"
    assert record["response"] == original
    assert extraction_payload(record)["tables"][0]["cells"][2]["text"] == "-"
    payload["tables"][0]["rows"] = 1
    record["structure_corrections"] = [
        dict(
            record["raw_corrections"][0],
            table=0,
            original_bounds=dict(rows=1, columns=4),
            corrected_bounds=dict(rows=2, columns=4),
        )
    ]
    assert extraction_payload(record)["tables"][0]["rows"] == 2
    assert payload["tables"][0]["rows"] == 1
    record["raw_corrections"][0]["pdf_page"] += 1
    with pytest.raises(ValueError, match="correction_source_binding_mismatch"):
        extraction_payload(record)


def test_per_share_unit_needs_statement_code_label_and_unit(sample):
    table = sample[2]["tables"][0]
    table["cells"][0]["text"] = "Lãi cơ bản trên cổ phiếu"
    table["cells"][1]["text"] = "70"
    assert {e.extraction.value.unit for e in project(sample)} == {"VND/share"}
    table["cells"][1]["text"] = "99"
    assert {e.extraction.value.unit for e in project(sample)} == {None}
    assert "item_unit_uncertain" in project(sample)[0].extraction_issues
    table["cells"][0]["text"] = "Lãi suy giảm trên cổ phiếu"
    table["cells"][1]["text"] = "71"
    assert {e.extraction.value.unit for e in project(sample)} == {None}


def test_same_statement_mixed_units_and_arithmetic_guard(sample):
    table = sample[2]["tables"][0]
    table["rows"] = 3
    table["cells"].extend(
        [
            cell("Lãi cơ bản trên cổ phiếu", 2, 0),
            cell("70", 2, 1),
            cell("19", 2, 2),
            cell("17", 2, 3),
        ]
    )
    assert [e.extraction.value.unit for e in project(sample)] == [
        "VND",
        "VND",
        "VND/share",
        "VND/share",
    ]
    values = inputs()
    values[1].value.unit = "VND/share"
    result = evaluate(values)[0]
    assert result.computed_value is None
    assert "currency_conflict" in result.issues


def test_recovery_snapshot_isolation(sample):
    from vietnamese_financial_multi_agent.accounting.quality import assess_evidence_for_task

    image, record, _ = sample
    document = "sha256:" + "a" * 64
    image.identity.source_ref = document
    record["source"]["page"]["source_ref"] = document
    quality = assess_evidence_for_task(project(sample)).model_dump(mode="json")
    original = dict(document_id=document, attempt_id="original", quality=quality)
    recovery = dict(original, attempt_id="recovery")
    facts = facts_from_persisted_result(original) + facts_from_persisted_result(recovery)
    descriptors = [
        SnapshotDescriptor(
            document_id=document,
            pdf_sha256="a" * 64,
            snapshot_id=s,
            parent_snapshot_id=None if s == "original" else "original",
            origin="original_extraction" if s == "original" else "recovery",
        )
        for s in ("original", "recovery")
    ]
    catalog = SnapshotCatalog(descriptors, facts)
    assert catalog.select(document).status == "ambiguous"
    assert catalog.select(document, "recovery").candidates[0].fact_count == 2
    assert catalog.select(document, "recovery").candidates[0].source_review_bindings == []
    assert (
        EvidenceRetrieval(facts).get_fact(facts[0].observation_identity()).matches[0].record
        == facts[0]
    )


def test_same_runtime_accepts_other_company_and_period(sample):
    original = project(sample)
    sample[0].identity.symbol = "OTHER"
    sample[0].identity.year = "2037"
    sample[0].identity.source_ref = "other-document"
    sample[1]["source"]["page"].update(symbol="OTHER", year="2037", source_ref="other-document")
    for h, period in zip(sample[2]["tables"][0]["headers"], (2037, 2036), strict=True):
        h["text"] = f"Năm {period}"
    new = project(sample)
    assert [e.extraction.context.period for e in new] == ["2037", "2036"]
    assert [e.extraction.value for e in new] == [e.extraction.value for e in original]


def test_existing_monetary_operands_keep_arithmetic_result(sample):
    assert evaluate(inputs())[0].computed_value == Decimal(300)
    projected = project(sample)
    assert [e.canonical_item_id for e in projected] == ["b02.cost_of_sales"] * 2
    assert {e.extraction.value.unit for e in projected} == {"VND"}
