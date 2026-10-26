"""Fixtures hoàn toàn synthetic, chỉ kiểm tra contract, không đánh giá OCR tài chính."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from vietnamese_financial_multi_agent.document_processing.contracts import (
    OCRPage,
    OCRPageMetadata,
    RawOCRStructuralError,
    parse_raw_ocr,
    raw_ocr_json_schema,
    validate_quality,
)


@pytest.fixture
def payload():
    return {
        "page": dict(
            symbol="SYNTHETIC",
            year="2025",
            page=1,
            image="source/page.png",
            width=100,
            height=100,
            dpi=300,
        ),
        "elements": [],
        "provenance": {
            "architecture": "synthetic",
            "detection_view": dict(
                width=50, height=50, scale_x_to_original=2.0, scale_y_to_original=2.0
            ),
            "layout_engine": "synthetic",
            "text_detector": "synthetic",
            "text_recognizer": "synthetic",
            "checkbox_detector": "synthetic",
            "checkbox_detector_source": "synthetic",
            "checkbox_detection": dict(
                native_proposals=0,
                magnified_proposals=0,
                accepted=0,
                threshold=0.5,
                proposal_threshold=0.3,
                seconds=0.01,
            ),
            "signature_detector": "synthetic",
            "signature_full_page_threshold": 0.7,
            "signature_context_roi_threshold": 0.28,
            "signature_fallback_detector": None,
            "signature_full_page_proposal_count": 0,
            "signature_final_count": 0,
            "signature_policy": "synthetic",
            "checkbox_policy": "synthetic",
            "seal_policy": "synthetic",
            "notes": ["Synthetic fixture"],
            "page_seconds": 0.1,
        },
    }


def element(kind):
    data = dict(id=kind + "_1", type=kind, bbox=[1, 2, 30, 40])
    if kind == "text":
        data["text"] = "  Mẫu: (1.234,50)\nTiếng Việt!  "
    else:
        data["crop"] = "/synthetic-colab/crops/" + kind + ".png"
    if kind == "table":
        data.update(
            name="synthetic table",
            cells=[
                dict(
                    id="cell_1",
                    row=0,
                    col=0,
                    bbox=[1, 2, 30, 40],
                    text="demo",
                    line_count=1,
                    lines=[
                        dict(
                            id="line_1",
                            type="text",
                            bbox=[2, 3, 20, 30],
                            text="demo",
                            cell_id="cell_1",
                        )
                    ],
                )
            ],
        )
    if kind == "checkbox":
        data.update(
            checked=True,
            choice="yes",
            confidence=0.8,
            group_id="group_1",
            label="demo",
            label_text_ids=[],
        )
    if kind in {"signature", "seal", "seal_signature_region"}:
        data.update(black_view_crop="black.png", red_view_crop="red.png", blue_view_crop="blue.png")
    if kind == "signature":
        data.update(
            role="demo", signer_name="demo", kind="demo", confidence=None, ink_view_crop="ink.png"
        )
    if kind == "seal":
        data["seal_name"] = "demo"
    if kind == "seal_signature_region":
        data.update(
            seal_bbox=[1, 2, 30, 40],
            signature_bbox=[1, 2, 30, 40],
            signature_id="signature_1",
            source="synthetic",
        )
    return data


KINDS = ["text", "table", "checkbox", "signature", "seal", "seal_signature_region", "red_mark"]


def test_page_metadata(payload):
    page = OCRPage.model_validate(payload)
    assert isinstance(page.page, OCRPageMetadata)
    assert page.page.year == "2025"
    assert page.export_source() == payload


@pytest.mark.parametrize("kind", KINDS)
def test_element_round_trip(payload, kind):
    payload["elements"] = [element(kind)]
    before = copy.deepcopy(payload)
    page = OCRPage.model_validate(payload)
    assert page.elements[0].type == kind
    assert page.export_source() == before == payload
    assert OCRPage.model_validate_json(json.dumps(payload)).export_source() == payload


@pytest.mark.parametrize("checked", [True, False])
def test_checkbox_boolean(payload, checked):
    data = element("checkbox")
    data["checked"] = checked
    payload["elements"] = [data]
    assert OCRPage.model_validate(payload).elements[0].checked is checked


def test_nested_and_optional_line_reference(payload):
    table = element("table")
    del table["cells"][0]["lines"][0]["cell_id"]
    payload["elements"] = [table]
    page = OCRPage.model_validate(payload)
    assert page.elements[0].cells[0].lines[0].cell_id is None
    assert page.export_source() == payload


def test_extra_fields_every_level(payload):
    table = element("table")
    payload["elements"] = [table]
    for obj in (
        payload,
        payload["page"],
        payload["provenance"],
        payload["provenance"]["detection_view"],
        payload["provenance"]["checkbox_detection"],
        table,
        table["cells"][0],
        table["cells"][0]["lines"][0],
    ):
        obj["future"] = {"nested": [None, True, 123, "1.000"]}
    assert OCRPage.model_validate(payload).export_source() == payload


def test_geometry_and_sparse_positions_do_not_block_parse(payload):
    table = element("table")
    cell = table["cells"][0]
    cell.update(row=99, col=42, text="", bbox=[30, 2, 1, 2])
    table["cells"].append(copy.deepcopy(cell))
    payload["elements"] = [table]
    assert OCRPage.model_validate(payload).export_source() == payload


@pytest.mark.parametrize("bbox", [[1, 2, 3], [1, 2, 3, 4, 5], [1, 2, "3", 4], None])
def test_bbox_structure(payload, bbox):
    payload["elements"] = [element("text") | {"bbox": bbox}]
    with pytest.raises(ValidationError) as error:
        OCRPage.model_validate(payload)
    assert error.value.errors()[0]["loc"][:3] == ("elements", 0, "text")


@pytest.mark.parametrize("key", ["page", "elements", "provenance"])
def test_missing_root_fields(payload, key):
    del payload[key]
    with pytest.raises(ValidationError) as error:
        OCRPage.model_validate(payload)
    assert error.value.errors()[0]["loc"] == (key,)


@pytest.mark.parametrize("field,value", [("year", 2025), ("page", "1"), ("width", True)])
def test_no_metadata_coercion(payload, field, value):
    payload["page"][field] = value
    with pytest.raises(ValidationError):
        OCRPage.model_validate(payload)


def test_schema_discriminator():
    schema = raw_ocr_json_schema()
    assert schema["title"] == "raw_ocr_v1"
    assert set(schema["properties"]["elements"]["items"]["discriminator"]["mapping"]) == set(KINDS)


def test_unknown_type_preserves_whole_page(payload):
    unknown = {"type": "future_type", "payload": ["nguyên bản", {"new": True}]}
    payload["elements"] = [element("text"), unknown]
    before = copy.deepcopy(payload)
    with pytest.raises(RawOCRStructuralError) as error:
        parse_raw_ocr(payload)
    assert error.value.issues[0].code == "union_tag_invalid"
    assert error.value.issues[0].path == ("elements", 1)
    assert error.value.payload == before == payload
    payload["elements"].clear()
    assert error.value.payload == before
    assert "nguyên bản" not in str(error.value)


@pytest.mark.parametrize("root", [None, [], "text", 5])
def test_invalid_root(root):
    with pytest.raises(RawOCRStructuralError) as error:
        parse_raw_ocr(root)
    assert error.value.issues[0].path == ()
    assert error.value.payload == root


@pytest.mark.parametrize(
    "mutation,path",
    [
        (lambda p: p.update(page=[]), ("page",)),
        (lambda p: p.update(elements={}), ("elements",)),
        (lambda p: p["elements"].append(None), ("elements", 1)),
        (lambda p: p["elements"][0].pop("bbox"), ("elements", 0, "bbox")),
        (
            lambda p: p["elements"][0]["cells"][0].update(row="0"),
            ("elements", 0, "cells", 0, "row"),
        ),
        (
            lambda p: p["elements"][0]["cells"][0].update(col=True),
            ("elements", 0, "cells", 0, "col"),
        ),
        (lambda p: p["elements"][0]["cells"].append("bad"), ("elements", 0, "cells", 1)),
        (
            lambda p: p["elements"][0]["cells"][0]["lines"].append(0),
            ("elements", 0, "cells", 0, "lines", 1),
        ),
        (lambda p: p["provenance"].pop("architecture"), ("provenance", "architecture")),
        (
            lambda p: p["provenance"]["detection_view"].update(width="50"),
            ("provenance", "detection_view", "width"),
        ),
    ],
)
def test_structural_error_source_paths(payload, mutation, path):
    payload["elements"] = [element("table")]
    mutation(payload)
    before = copy.deepcopy(payload)
    with pytest.raises(RawOCRStructuralError) as error:
        parse_raw_ocr(payload)
    assert path in [issue.path for issue in error.value.issues]
    assert error.value.payload == before == payload


def test_quality_reports_without_mutation(payload):
    table = element("table")
    cell = table["cells"][0]
    cell.update(text="", bbox=[30, 2, 1, 2], line_count=5)
    cell["lines"][0]["cell_id"] = "wrong"
    table["cells"].append(copy.deepcopy(cell))
    table["cells"].append(copy.deepcopy(cell) | {"id": "cell_3", "row": 3, "col": 2})
    table["bbox"] = [-1, 2, 101, 40]
    payload["elements"] = [
        table,
        element("signature") | {"confidence": 1.5},
        element("seal_signature_region") | {"signature_id": "missing"},
        element("checkbox") | {"label_text_ids": ["missing", {"new": 1}]},
    ]
    before = copy.deepcopy(payload)
    page = parse_raw_ocr(payload)
    issues = validate_quality(page)
    codes = {issue.code for issue in issues}
    assert {
        "invalid_bbox_geometry",
        "bbox_outside_page",
        "empty_cell_text",
        "duplicate_cell_position",
        "duplicate_id",
        "line_count_mismatch",
        "cell_reference_mismatch",
        "sparse_table",
        "confidence_out_of_range",
        "unresolved_signature_reference",
        "unresolved_text_reference",
        "unresolved_reference_type",
    } <= codes
    assert any(i.path == ("elements", 0, "cells", 0, "bbox") for i in issues)
    assert page.export_source() == before == payload


@pytest.mark.parametrize("box", [[1, 2, 1, 3], [5, 5, 1, 1], [1, 3, 5, 2]])
def test_bad_geometry_is_quality(payload, box):
    payload["elements"] = [element("text") | {"bbox": box}]
    page = parse_raw_ocr(payload)
    assert "invalid_bbox_geometry" in {i.code for i in validate_quality(page)}
    assert page.export_source() == payload


@pytest.mark.parametrize("confidence", [-0.1, 1.1, 0, 1, 0.5, None])
def test_confidence_quality_and_source_types(payload, confidence):
    payload["elements"] = [element("signature") | {"confidence": confidence}]
    page = parse_raw_ocr(payload)
    issues = validate_quality(page)
    assert bool(issues) == (confidence is not None and not 0 <= confidence <= 1)
    exported = page.export_source()["elements"][0]["confidence"]
    assert exported == confidence
    assert type(exported) is type(confidence)


@pytest.mark.parametrize("confidence", [True, "0.5", float("nan"), float("inf")])
def test_confidence_structural(payload, confidence):
    payload["elements"] = [element("signature") | {"confidence": confidence}]
    with pytest.raises(RawOCRStructuralError):
        parse_raw_ocr(payload)


def test_required_nullable_signature_confidence(payload):
    signature = element("signature")
    del signature["confidence"]
    payload["elements"] = [signature]
    with pytest.raises(RawOCRStructuralError):
        parse_raw_ocr(payload)


def test_valid_links_and_all_boxes(payload):
    payload["elements"] = [element(kind) for kind in KINDS]
    payload["elements"][2]["label_text_ids"] = ["text_1"]
    page = parse_raw_ocr(payload)
    assert validate_quality(page) == []
    assert all("confidence" not in page.export_source()["elements"][i] for i in [0, 1, 4, 5, 6])
    payload["elements"][5]["seal_bbox"] = [5, 1, 2, 1]
    payload["elements"][5]["signature_bbox"] = [1, 2, 101, 40]
    issues = validate_quality(parse_raw_ocr(payload))
    assert {i.path for i in issues} == {
        ("elements", 5, "seal_bbox"),
        ("elements", 5, "signature_bbox"),
    }


def test_negative_dimensions_positions_and_duplicate_elements(payload):
    payload["page"]["dpi"] = 0
    table = element("table")
    table["cells"][0]["row"] = -1
    payload["elements"] = [table, copy.deepcopy(table)]
    codes = {i.code for i in validate_quality(parse_raw_ocr(payload))}
    assert {"invalid_page_dimension", "negative_cell_position", "duplicate_id"} <= codes


def test_schema_matches_committed_artifact():
    path = Path(__file__).resolve().parents[2] / "schemas/raw_ocr_v1.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == raw_ocr_json_schema()
