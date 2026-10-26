"""Fixtures synthetic: kiểm tra contracts, không phải ground truth tài chính."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.document_processing.contracts import (
    DocumentUnderstandingStructuralError,
    OCRPage,
    document_understanding_json_schema,
    parse_document_understanding,
    validate_understanding_quality,
)
from vietnamese_financial_multi_agent.document_processing.contracts.document_understanding import (
    DocumentUnderstandingResult,
    SourceAnchor,
    UnderstoodCell,
    UnderstoodTable,
    UnderstoodTextRegion,
)


@pytest.fixture
def identity():
    return dict(symbol="SYNTHETIC", year="2025", page=1, image="source/page.png")


@pytest.fixture
def result_payload(identity):
    return dict(
        contract_version="document_understanding_v1",
        raw_page=identity,
        classification=dict(label=None, status="unresolved", anchors=[]),
        text_regions=[],
        tables=[],
        issues=[],
    )


def test_core_round_trip(result_payload):
    result = DocumentUnderstandingResult.model_validate(result_payload)
    assert result.export_result() == result_payload
    assert (
        DocumentUnderstandingResult.model_validate_json(json.dumps(result_payload)).export_result()
        == result_payload
    )


@pytest.mark.parametrize("field", ["contract_version", "raw_page", "classification", "issues"])
def test_required_core_fields(result_payload, field):
    del result_payload[field]
    with pytest.raises(ValidationError) as error:
        DocumentUnderstandingResult.model_validate(result_payload)
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("value", ["1", True, 1.0, None])
def test_strict_page_number(identity, value):
    identity["page"] = value
    with pytest.raises(ValidationError):
        SourceAnchor(page=identity, status="unresolved")


def test_image_only_anchor_and_null(identity):
    payload = dict(page=identity, observed_bbox=[0, 0, 10, 20], status="unresolved")
    anchor = SourceAnchor.model_validate(payload)
    assert "element_id" not in anchor.export_result()
    payload["element_id"] = None
    assert SourceAnchor.model_validate(payload).export_result() == payload


def test_contextual_anchor(identity):
    payload = dict(
        page={**identity, "source_ref": "synthetic-run-A/page-1"},
        element_id="t1",
        table_id="t1",
        cell_id="c1",
        line_id="l1",
        observed_bbox=[1, 2, 3, 4],
        proposed_bbox=[0, 1, 4, 5],
        status="uncertain",
    )
    assert SourceAnchor.model_validate(payload).export_result() == payload


@pytest.mark.parametrize(
    "change",
    [
        {"contract_version": "v2"},
        {"future": 1},
        {"classification": {"label": None, "status": "unknown", "anchors": []}},
    ],
)
def test_invalid_core_values(result_payload, change):
    result_payload.update(change)
    with pytest.raises(ValidationError):
        DocumentUnderstandingResult.model_validate(result_payload)


@pytest.mark.parametrize("bbox", [[1, 2, 3], [1, 2, 3, 4, 5], [1, True, 3, 4]])
def test_bbox_shape(identity, bbox):
    with pytest.raises(ValidationError):
        SourceAnchor(page=identity, status="unresolved", observed_bbox=bbox)


@pytest.mark.parametrize("count", [1, 3])
def test_text_regions_multi_source(identity, count):
    payload = dict(
        id="region",
        text="  Tổng cộng: 1.234.567\nTiếng Việt  ",
        status="uncertain",
        anchors=[
            dict(page=identity, element_id=f"text-{i}", status="resolved") for i in range(count)
        ],
        reading_order=None,
    )
    assert UnderstoodTextRegion.model_validate(payload).export_result() == payload


@pytest.mark.parametrize("origin", ["ocr_table", "inferred_from_text"])
def test_structured_tables_round_trip(result_payload, identity, origin):
    anchors = [dict(page=identity, element_id="t1", table_id="t1", status="resolved")]
    if origin == "inferred_from_text":
        anchors = [
            dict(page=identity, element_id="text1", status="uncertain"),
            dict(page=identity, observed_bbox=[0, 0, 20, 20], status="unresolved"),
        ]
    cell = dict(id="cell1", row=0, col=0, text="1.234.567", anchors=anchors, status="uncertain")
    table = dict(id="table1", origin=origin, anchors=anchors, cells=[cell], status="uncertain")
    result_payload["tables"] = [table]
    result = DocumentUnderstandingResult.model_validate(result_payload)
    assert result.export_result() == result_payload
    assert isinstance(result.tables[0], UnderstoodTable)
    assert isinstance(result.tables[0].cells[0], UnderstoodCell)
    assert result.tables[0].cells[0].rowspan is None
    assert "rowspan" not in result.export_result()["tables"][0]["cells"][0]
    cell["rowspan"] = None
    cell["colspan"] = 2
    assert (
        DocumentUnderstandingResult.model_validate(result_payload).export_result() == result_payload
    )


def test_sparse_duplicate_empty_unresolved_preserved(identity):
    payload = dict(
        id="t",
        origin="inferred_from_text",
        anchors=[],
        status="unresolved",
        cells=[
            dict(id="a", row=0, col=0, text="", anchors=[], status="unresolved"),
            dict(id="b", row=9, col=7, text="demo", anchors=[], status="unresolved"),
            dict(id="c", row=9, col=7, text="demo2", anchors=[], status="uncertain"),
        ],
    )
    assert UnderstoodTable.model_validate(payload).export_result() == payload


@pytest.mark.parametrize(
    "field,value", [("row", True), ("col", "0"), ("rowspan", 1.5), ("colspan", "2"), ("text", 123)]
)
def test_cell_strict_types(field, value):
    payload = dict(id="c", row=0, col=0, text="", anchors=[], status="unresolved")
    payload[field] = value
    with pytest.raises(ValidationError) as error:
        UnderstoodCell.model_validate(payload)
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.fixture
def raw_payload(identity):
    return dict(
        page={**identity, "width": 100, "height": 100, "dpi": 300},
        elements=[
            dict(id="text1", type="text", bbox=[1, 2, 30, 40], text="1.234.567"),
            dict(
                id="table1",
                type="table",
                name="Synthetic",
                bbox=[1, 2, 30, 40],
                crop="source/crop.png",
                cells=[
                    dict(
                        id="cell1",
                        row=0,
                        col=0,
                        text="",
                        bbox=[2, 3, 20, 30],
                        line_count=1,
                        lines=[
                            dict(
                                id="line1",
                                type="text",
                                text="",
                                bbox=[3, 4, 10, 20],
                                cell_id="cell1",
                            )
                        ],
                    )
                ],
            ),
        ],
        provenance=dict(
            architecture="synthetic",
            layout_engine="synthetic",
            text_detector="synthetic",
            text_recognizer="synthetic",
            checkbox_detector="synthetic",
            checkbox_detector_source="synthetic",
            signature_detector="synthetic",
            detection_view=dict(
                width=100, height=100, scale_x_to_original=1, scale_y_to_original=1
            ),
            checkbox_detection=dict(
                native_proposals=0,
                magnified_proposals=0,
                accepted=0,
                threshold=0.5,
                proposal_threshold=0.3,
                seconds=0,
            ),
            signature_full_page_threshold=0.7,
            signature_context_roi_threshold=0.28,
            signature_fallback_detector=None,
            signature_full_page_proposal_count=0,
            signature_final_count=0,
            signature_policy="synthetic",
            checkbox_policy="synthetic",
            seal_policy="synthetic",
            notes=[],
            page_seconds=0,
        ),
    )


@pytest.fixture
def linked_payload(result_payload, identity):
    anchor = dict(page=identity, element_id="text1", status="resolved")
    result_payload["classification"] = dict(label="B01", status="resolved", anchors=[anchor])
    result_payload["text_regions"] = [
        dict(id="r1", text="1.234.567", status="resolved", anchors=[copy.deepcopy(anchor)])
    ]
    return result_payload


def codes(result_payload, raw_payload=None):
    result = parse_document_understanding(result_payload)
    raw = None if raw_payload is None else OCRPage.model_validate(raw_payload)
    before = result.export_result()
    raw_before = None if raw is None else raw.export_source()
    issues = validate_understanding_quality(result, raw_page=raw)
    assert result.export_result() == before
    if raw is not None:
        assert raw.export_source() == raw_before
    return {i.code for i in issues}


def test_valid_standalone_and_explicit_raw(linked_payload, raw_payload):
    assert codes(linked_payload) == codes(linked_payload, raw_payload) == set()
    linked_payload["raw_page"]["source_ref"] = "synthetic-run-A"
    linked_payload["text_regions"][0]["anchors"][0]["page"]["source_ref"] = "synthetic-run-A"
    assert codes(linked_payload, raw_payload) == set()


@pytest.mark.parametrize("level", ["table", "cell", "line"])
def test_scoped_table_references(linked_payload, identity, raw_payload, level):
    anchor = dict(page=identity, table_id="table1", status="resolved")
    if level in ("cell", "line"):
        anchor["cell_id"] = "cell1"
    if level == "line":
        anchor["line_id"] = "line1"
    linked_payload["text_regions"][0]["anchors"] = [anchor]
    assert codes(linked_payload, raw_payload) == set()


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"element_id": "missing"}, "unresolved_source_reference"),
        ({"element_id": None, "cell_id": "cell1"}, "ambiguous_cell_reference"),
        ({"line_id": "line1"}, "ambiguous_line_reference"),
        ({"table_id": "table1"}, "source_context_mismatch"),
        ({"table_id": "text1"}, "reference_type_mismatch"),
        ({"observed_bbox": [1, 2, 30, 41]}, "observed_bbox_mismatch"),
        ({"proposed_bbox": [9, 4, 1, 4]}, "invalid_bbox_geometry"),
        ({"element_id": " "}, "empty_source_reference"),
    ],
)
def test_bad_anchor_links(linked_payload, raw_payload, change, expected):
    linked_payload["text_regions"][0]["anchors"][0].update(change)
    assert expected in codes(linked_payload, raw_payload)
    assert "status_conflict" in codes(linked_payload, raw_payload)


@pytest.mark.parametrize("level", ["element", "cell", "line"])
@pytest.mark.parametrize("failure", ["missing", "duplicate"])
def test_resolution_requires_unique_source(linked_payload, identity, raw_payload, level, failure):
    anchor = dict(
        page=identity, table_id="table1", cell_id="cell1", line_id="line1", status="uncertain"
    )
    linked_payload["text_regions"][0].update(status="uncertain", anchors=[anchor])
    if level == "element":
        collection = raw_payload["elements"]
        if failure == "missing":
            collection.pop(1)
        else:
            collection.append(copy.deepcopy(collection[1]))
    else:
        collection = raw_payload["elements"][1]["cells"]
        if level == "line":
            collection = collection[0]["lines"]
        if failure == "missing":
            collection.clear()
        else:
            collection.append(copy.deepcopy(collection[0]))
    expected = (
        "unresolved_source_reference" if failure == "missing" else "ambiguous_source_reference"
    )
    assert expected in codes(linked_payload, raw_payload)


def test_reused_ids_in_other_table_are_not_ambiguous(linked_payload, identity, raw_payload):
    other = copy.deepcopy(raw_payload["elements"][1])
    other["id"] = "table2"
    raw_payload["elements"].append(other)
    linked_payload["text_regions"][0]["anchors"] = [
        dict(
            page=identity,
            element_id="table1",
            table_id="table1",
            cell_id="cell1",
            line_id="line1",
            status="resolved",
            observed_bbox=[3, 4, 10, 20],
        )
    ]
    assert codes(linked_payload, raw_payload) == set()


@pytest.mark.parametrize(
    "field,value", [("page", 2), ("image", "other.png"), ("source_ref", "other-run")]
)
def test_wrong_anchor_page_context(linked_payload, raw_payload, field, value):
    anchor = linked_payload["text_regions"][0]["anchors"][0]
    anchor["page"] = {**anchor["page"], field: value}
    assert "anchor_page_mismatch" in codes(linked_payload, raw_payload)


def test_raw_comparison_is_explicit(linked_payload, raw_payload):
    raw_payload["elements"].clear()
    assert codes(linked_payload) == set()
    assert "unresolved_source_reference" in codes(linked_payload, raw_payload)
    raw_payload["page"]["page"] = 2
    assert "raw_page_mismatch" in codes(linked_payload, raw_payload)


@pytest.mark.parametrize("status", ["uncertain", "unresolved", "resolved"])
def test_image_only_unverified(linked_payload, identity, raw_payload, status):
    linked_payload["text_regions"][0].update(
        status=status,
        anchors=[
            dict(
                page=identity,
                observed_bbox=[2, 3, 10, 20],
                proposed_bbox=[1, 1, 20, 30],
                status=status,
            )
        ],
    )
    found = codes(linked_payload, raw_payload)
    assert ("status_conflict" in found) == (status == "resolved")
    assert "missing_provenance" not in found


def test_proposed_bbox_alone_is_not_observed_evidence(linked_payload, identity):
    linked_payload["text_regions"][0].update(
        status="unresolved",
        anchors=[dict(page=identity, proposed_bbox=[1, 1, 2, 2], status="unresolved")],
    )
    assert "missing_provenance" in codes(linked_payload)


def test_quality_preserves_abnormal_content(result_payload, identity):
    anchor = dict(page=identity, observed_bbox=[20, 10, 1, 1], status="uncertain")
    cell = dict(
        id="c", row=-1, col=2, text="", anchors=[anchor], status="uncertain", rowspan=0, colspan=-1
    )
    result_payload["tables"] = [
        dict(
            id="t",
            origin="ocr_table",
            anchors=[anchor],
            status="uncertain",
            cells=[cell, copy.deepcopy(cell)],
        )
    ]
    assert {
        "invalid_bbox_geometry",
        "negative_cell_position",
        "duplicate_cell_position",
        "empty_text",
        "duplicate_id",
        "invalid_span",
        "missing_ocr_table_reference",
    } <= codes(result_payload)


def test_sparse_table_is_not_a_quality_error(result_payload, identity):
    anchor = dict(page=identity, element_id="text1", status="resolved")
    cells = [
        dict(id=f"c{i}", row=i * 3, col=i * 5, text="1.234", anchors=[anchor], status="resolved")
        for i in range(2)
    ]
    result_payload["tables"] = [
        dict(id="t", origin="inferred_from_text", anchors=[anchor], cells=cells, status="resolved")
    ]
    assert codes(result_payload) == set()


@pytest.mark.parametrize(
    "label,status,expected",
    [
        (None, "unresolved", None),
        (None, "resolved", "status_conflict"),
        ("unknown", "uncertain", "invalid_classification_label"),
        ("", "uncertain", "invalid_classification_label"),
        ("custom-unapproved-taxonomy", "uncertain", "missing_provenance"),
    ],
)
def test_classification_semantics(result_payload, label, status, expected):
    result_payload["classification"].update(label=label, status=status)
    found = codes(result_payload)
    assert found == set() if expected is None else expected in found


@pytest.mark.parametrize("value", [True, "0.5", float("inf"), float("nan")])
def test_confidence_strict(result_payload, value):
    result_payload["classification"]["confidence"] = value
    with pytest.raises(DocumentUnderstandingStructuralError):
        parse_document_understanding(result_payload)


def test_confidence_quality(result_payload):
    result_payload["classification"]["confidence"] = 2
    assert codes(result_payload) == {"confidence_out_of_range"}


def test_nested_structural_paths_and_payload_snapshot(linked_payload):
    linked_payload["text_regions"][0]["anchors"][0]["page"]["page"] = "1"
    before = copy.deepcopy(linked_payload)
    with pytest.raises(DocumentUnderstandingStructuralError) as error:
        parse_document_understanding(linked_payload)
    assert ("text_regions", 0, "anchors", 0, "page", "page") in [i.path for i in error.value.issues]
    assert error.value.payload == before == linked_payload
    linked_payload.clear()
    assert error.value.payload == before
    assert "1.234.567" not in str(error.value)


@pytest.mark.parametrize("root", [None, [], "text", 5])
def test_invalid_result_root(root):
    with pytest.raises(DocumentUnderstandingStructuralError) as error:
        parse_document_understanding(root)
    assert error.value.issues[0].path == ()


def test_json_parsing_error():
    with pytest.raises(ValidationError) as error:
        DocumentUnderstandingResult.model_validate_json('{"contract_version":')
    assert error.value.errors()[0]["loc"] == ()
    assert error.value.errors()[0]["type"] == "json_invalid"


def test_schema_sync():
    path = Path(__file__).resolve().parents[2] / "schemas/document_understanding_v1.schema.json"
    schema = document_understanding_json_schema()
    assert json.loads(path.read_text(encoding="utf-8")) == schema
    assert schema["properties"]["contract_version"]["const"] == "document_understanding_v1"
    assert schema["additionalProperties"] is False


def test_nested_unknown_field_rejected(linked_payload):
    linked_payload["text_regions"][0]["anchors"][0]["future"] = "preserve via error"
    with pytest.raises(DocumentUnderstandingStructuralError) as error:
        parse_document_understanding(linked_payload)
    assert error.value.issues[0].path[-1] == "future"
    assert error.value.payload == linked_payload


def test_duplicate_output_ids_are_scoped(linked_payload, identity):
    linked_payload["text_regions"].append(copy.deepcopy(linked_payload["text_regions"][0]))
    linked_payload["text_regions"][1]["reading_order"] = -1
    anchor = dict(page=identity, table_id="table1", status="resolved")
    cell = dict(id="c1", row=0, col=0, text="demo", anchors=[anchor], status="resolved")
    table = dict(id="t", origin="ocr_table", anchors=[anchor], cells=[cell], status="resolved")
    linked_payload["tables"] = [table, copy.deepcopy(table)]
    result = parse_document_understanding(linked_payload)
    issues = validate_understanding_quality(result)
    duplicates = [i.path for i in issues if i.code == "duplicate_id"]
    assert duplicates == [["text_regions", 1, "id"], ["tables", 1, "id"]]
    assert "negative_reading_order" in {i.code for i in issues}
    # c1 ở bảng khác không trùng ID trong cùng container.


def test_missing_provenance_and_status_contradictions(linked_payload):
    linked_payload["text_regions"][0]["anchors"] = []
    assert codes(linked_payload) == {"missing_provenance", "status_conflict"}
    linked_payload["text_regions"][0]["status"] = "unresolved"
    assert codes(linked_payload) == {"missing_provenance"}


def test_valid_multi_anchor_and_optional_content_issues(linked_payload, raw_payload, identity):
    region = linked_payload["text_regions"][0]
    region["anchors"].append(
        dict(page=identity, table_id="table1", cell_id="cell1", status="resolved")
    )
    region["issues"] = [
        dict(code="review_requested", path=["text_regions", 0], message="Cần review")
    ]
    linked_payload["issues"] = [dict(code="note", path=[], message="Synthetic fixture")]
    assert codes(linked_payload, raw_payload) == set()
    assert (
        DocumentUnderstandingResult.model_validate_json(
            json.dumps(linked_payload, ensure_ascii=False)
        ).export_result()
        == linked_payload
    )


def test_unknown_spans_differ_from_recognized_one():
    base = dict(id="c", row=0, col=0, text="demo", anchors=[], status="unresolved")
    for extra in ({}, {"rowspan": None}, {"rowspan": 1}):
        payload = {**base, **extra}
        assert UnderstoodCell.model_validate_json(json.dumps(payload)).export_result() == payload


def test_raw_anomalies_do_not_prevent_linkage(linked_payload, identity, raw_payload):
    raw_cell = raw_payload["elements"][1]["cells"][0]
    raw_cell.update(bbox=[20, 10, 1, 1], row=-1)
    raw_payload["elements"][1]["cells"].append({**copy.deepcopy(raw_cell), "id": "cell2"})
    linked_payload["text_regions"][0].update(
        text="",
        status="uncertain",
        anchors=[
            dict(
                page=identity,
                table_id="table1",
                cell_id="cell1",
                observed_bbox=[20, 10, 1, 1],
                status="uncertain",
            )
        ],
    )
    assert codes(linked_payload, raw_payload) == {"invalid_bbox_geometry", "empty_text"}
