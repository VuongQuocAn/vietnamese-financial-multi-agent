"""Fixtures có nhãn synthetic; không đo reconstruction accuracy trên OCR thật."""

import pytest
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    DocumentClassification,
    DocumentUnderstandingResult,
    RawPageIdentity,
    SourceAnchor,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding_validation import (
    validate_understanding_quality,
)
from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import OCRPage
from vietnamese_financial_multi_agent.document_processing.table_reconstruction import (
    SpanEvidence,
    reconstruct_table,
)

from .test_raw_ocr_contracts import payload as payload


def cell(row, col, **changes):
    return dict(
        dict(
            id=f"c{row}{col}",
            row=row,
            col=col,
            bbox=[col * 20, row * 20, col * 20 + 20, row * 20 + 20],
            text="  (1.234,50)\nTiếng Việt!  ",
            line_count=0,
            lines=[],
        ),
        **changes,
    )


@pytest.fixture
def page(payload):
    payload["elements"] = [
        dict(
            id="t",
            type="table",
            name="synthetic",
            crop="source/crop.png",
            bbox=[0, 0, 40, 40],
            cells=[cell(r, c) for r in range(2) for c in range(2)],
        )
    ]
    return OCRPage.model_validate(payload)


def run(page, **kwargs):
    return reconstruct_table(page, "t", source_ref="synthetic-run/page.json", **kwargs)


def evidence(page, rs=1, cs=1, placeholders=()):
    raw = page.elements[0].cells[0]
    return SpanEvidence(
        SourceAnchor(
            page=RawPageIdentity(
                symbol=page.page.symbol,
                year=page.page.year,
                page=page.page.page,
                image=page.page.image,
                source_ref="synthetic-run/page.json",
            ),
            element_id="t",
            table_id="t",
            cell_id=raw.id,
            observed_bbox=list(raw.bbox),
            status="resolved",
        ),
        rs,
        cs,
        placeholders,
    )


def codes(table):
    return {issue.code for issue in table.issues}


def test_regular_grid_order_source_and_no_mutation(page):
    page.elements[0].cells.reverse()
    before = page.export_source()
    result = run(page)
    assert result.status == "resolved"
    assert [(c.row, c.col, c.rowspan, c.colspan) for c in result.cells] == [
        (0, 0, 1, 1),
        (0, 1, 1, 1),
        (1, 0, 1, 1),
        (1, 1, 1, 1),
    ]
    by_id = {c.id: c for c in page.elements[0].cells}
    for output in result.cells:
        raw = by_id[output.id]
        assert output.text == raw.text
        assert output.anchors[0].cell_id == raw.id
        assert output.anchors[0].observed_bbox == raw.bbox
    du = DocumentUnderstandingResult(
        contract_version="document_understanding_v1",
        raw_page=result.anchors[0].page,
        classification=DocumentClassification(label=None, status="unresolved", anchors=[]),
        text_regions=[],
        tables=[result],
        issues=[],
    )
    assert validate_understanding_quality(du, raw_page=page) == []
    result.cells[0].anchors[0].observed_bbox[0] = 99
    assert page.export_source() == before


def test_annotated_colspan_and_placeholder_anchor(page):
    table = page.elements[0]
    table.cells[0].bbox = [0, 0, 40, 20]
    table.cells[1].text = ""
    table.cells[1].bbox = [0, 0, 40, 20]
    result = run(page, spans=(evidence(page, cs=2, placeholders=("c01",)),))
    assert result.status == "resolved"
    assert len(result.cells) == 3
    assert result.cells[0].colspan == 2
    assert [a.cell_id for a in result.cells[0].anchors] == ["c00", "c01"]
    assert result.cells[0].anchors[1].observed_bbox == table.cells[1].bbox


def test_annotated_rowspan_without_placeholder(page):
    table = page.elements[0]
    table.cells[0].bbox = [0, 0, 20, 40]
    del table.cells[2]
    result = run(page, spans=(evidence(page, rs=2),))
    assert result.status == "resolved"
    assert result.cells[0].rowspan == 2
    assert len(result.cells) == 3


def test_observed_empty_is_preserved_and_missing_is_not_filled(page):
    page.elements[0].cells[0].text = ""
    result = run(page)
    assert result.status == "resolved"
    assert result.cells[0].text == ""
    assert codes(result) == {"observed_empty_cell"}
    del page.elements[0].cells[0]
    result = run(page)
    assert result.status == "unresolved"
    assert "missing_grid_positions" in codes(result)
    assert len(result.cells) == 3
    assert all(c.rowspan is None and c.colspan is None for c in result.cells)


def test_wide_bbox_and_empty_duplicate_bbox_do_not_imply_merge(page):
    table = page.elements[0]
    table.cells[0].bbox = [0, 0, 40, 20]
    del table.cells[1]
    result = run(page)
    assert result.status == "unresolved"
    assert "missing_grid_positions" in codes(result)
    table.cells.insert(
        1, type(table.cells[0]).model_validate(cell(0, 1, text="", bbox=[0, 0, 40, 20]))
    )
    result = run(page)
    assert result.status == "unresolved"
    assert "metadata_bbox_conflict" in codes(result)
    assert len(result.cells) == 4


def test_duplicate_position_and_id_preserved_unresolved(page):
    first, second = page.elements[0].cells[:2]
    second.id, second.row, second.col = first.id, first.row, first.col
    result = run(page)
    assert result.status == "unresolved"
    assert {"duplicate_cell_id", "duplicate_cell_position", "grid_collision"} <= codes(result)
    assert len(result.cells) == 4
    assert all(a.status == "unresolved" for c in result.cells for a in c.anchors)


def test_merged_cell_collision_with_data_is_not_silently_removed(page):
    page.elements[0].cells[0].bbox = [0, 0, 40, 20]
    result = run(page, spans=(evidence(page, cs=2),))
    assert result.status == "unresolved"
    assert "grid_collision" in codes(result)
    assert len(result.cells) == 4


def test_invalid_spans_and_bounds(page):
    for span in (0, -1, True, 1.5):
        result = run(page, spans=(evidence(page, rs=span),))
        assert result.status == "unresolved"
        assert "invalid_span" in codes(result)
    result = run(page, spans=(evidence(page, rs=3),))
    assert "span_out_of_bounds" in codes(result)
    for shape in ((0, 2), (True, 2), (1, 1)):
        assert run(page, shape=shape).status == "unresolved"
    page.elements[0].cells[0].row = -1
    assert "negative_cell_position" in codes(run(page))


def test_metadata_geometry_conflict_and_invalid_boxes(page):
    page.elements[0].cells[0].bbox = [21, 0, 40, 20]
    assert "metadata_bbox_conflict" in codes(run(page))
    page.elements[0].cells[0].bbox = [0, 0, 0, 20]
    assert "invalid_cell_bbox" in codes(run(page))
    page.elements[0].cells[0].bbox = [0, 0, 41, 20]
    assert "cell_bbox_out_of_bounds" in codes(run(page))


def test_span_binding_rejects_other_source_bbox_and_duplicate_evidence(page):
    for field, value in (("source_ref", "other-run"), ("image", "other.png")):
        item = evidence(page)
        setattr(item.anchor.page, field, value)
        assert "span_source_mismatch" in codes(run(page, spans=(item,)))
    item = evidence(page)
    item.anchor.observed_bbox = [0, 0, 19, 20]
    assert "span_source_mismatch" in codes(run(page, spans=(item,)))
    assert "invalid_span_reference" in codes(run(page, spans=(evidence(page), evidence(page))))


def test_placeholder_requires_annotation_empty_content_and_valid_position(page):
    table = page.elements[0]
    table.cells[0].bbox = [0, 0, 40, 20]
    # Nonempty text must survive even if caller calls it a placeholder.
    result = run(page, spans=(evidence(page, cs=2, placeholders=("c01",)),))
    assert "invalid_placeholder" in codes(result)
    assert len(result.cells) == 4
    table.cells[1].text = ""
    for ids in (("absent",), ("c01", "c01"), ("c10",), ("c00",)):
        assert "invalid_placeholder" in codes(
            run(page, spans=(evidence(page, cs=2, placeholders=ids),))
        )
    table.cells[1].line_count = 1
    assert "invalid_placeholder" in codes(
        run(page, spans=(evidence(page, cs=2, placeholders=("c01",)),))
    )


def test_empty_or_ambiguous_table_and_unreviewed_metadata(page):
    page.elements[0].cells[0].model_extra["colspan"] = 2
    assert "unreviewed_structure_metadata" in codes(run(page))
    page.elements[0].cells = []
    assert "empty_table" in codes(run(page))
    page.elements.append(page.elements[0].model_copy(deep=True))
    assert codes(run(page)) == {"invalid_table_reference"}
    assert run(page).cells == []
    assert reconstruct_table(page, "absent").status == "unresolved"


def test_annotated_shape_supports_combined_span_without_materializing_grid(page):
    table = page.elements[0]
    table.cells = table.cells[:1]
    table.cells[0].bbox = [0, 0, 40, 40]
    result = run(page, shape=(2, 2), spans=(evidence(page, rs=2, cs=2),))
    assert result.status == "resolved"
    assert (result.cells[0].rowspan, result.cells[0].colspan) == (2, 2)
    result = run(page, shape=(10**9, 10**9))
    assert "missing_grid_positions" in codes(result)


def test_duplicate_placeholder_positions_cannot_hide_raw_conflict(page):
    table = page.elements[0]
    table.cells[0].bbox = [0, 0, 40, 20]
    table.cells[1].text = ""
    duplicate = table.cells[1].model_copy(deep=True)
    duplicate.id = "other-placeholder"
    table.cells.append(duplicate)
    result = run(page, spans=(evidence(page, cs=2, placeholders=("c01", duplicate.id)),))
    assert result.status == "unresolved"
    assert "duplicate_cell_position" in codes(result)
    # Every raw record remains linked even when annotations conflict.
    assert sum(len(c.anchors) for c in result.cells) == 5
