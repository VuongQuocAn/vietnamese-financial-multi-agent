"""Focused component/crop tests; synthetic, no API or financial ground truth."""

import copy
import io
from unittest.mock import Mock

import pytest
from PIL import Image
from vietnamese_financial_multi_agent.core.llm_contracts import parse_json_output
from vietnamese_financial_multi_agent.document_processing import vision_ocr as v
from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import OCRTable

from .test_ocr_correction import harness as correction_harness
from .test_vision_ocr import image as synthetic_image

harness = correction_harness
image = synthetic_image


def text(**changes):
    return dict(text="1.234.560", reading="observed", bbox=None, **changes)


def payload():
    return dict(
        disposition="assessed",
        text_elements=[text()],
        tables=[dict(rows=1, columns=1, cells=[dict(**text(), row=0, column=0)])],
        limitations=[],
    )


def validate(data, image):
    return v.validate_components(data, image, source=v.image_source(image))


def test_bad_geometry_keeps_text_and_never_confirms_or_changes_digits(image):
    raw = payload()
    raw["text_elements"][0]["bbox"] = [0, 0, 9999, 5]
    before = copy.deepcopy(raw)
    result = validate(raw, image)
    assert result["text_elements"][0]["status"] == "accepted"
    assert result["text_elements"][0]["geometry"]["status"] == "unresolved"
    assert result["text_elements"][0]["geometry"]["bounds_valid"] is False
    assert result["text_elements"][0]["text"] == "1.234.560"
    assert raw == before
    assert result["acceptance_scope"] == "structure_only_not_visual_confirmation"


def test_overflow_does_not_drop_cell_text_or_other_tables(image):
    raw = payload()
    raw["tables"].append(dict(rows=1, columns=3, cells=[dict(**text(), row=0, column=3)]))
    result = validate(raw, image)
    assert result["summary"]["tables_accepted"] == 1
    assert result["summary"]["cell_text_accepted"] == 2
    assert result["tables"][1]["status"] == "unresolved"
    assert result["tables"][1]["columns"] == 3
    assert result["tables"][1]["dimensions_inferred"] is False


def test_bad_cell_isolated_and_duplicate_positions_unresolved(image):
    raw = payload()
    raw["tables"][0]["cells"] += [dict(**text(), row=0, column=0), "invalid cell"]
    result = validate(raw, image)
    cells = result["tables"][0]["cells"]
    assert cells[0]["status"] == cells[1]["status"] == "accepted"
    assert cells[2]["status"] == "rejected"
    assert all(c["layout"]["status"] == "unresolved" for c in cells)
    assert result["summary"]["text_accepted"] == 1


def test_source_mismatch_rejects_all_components(image):
    source = v.image_source(image)
    source["image_sha256"] = "wrong"
    result = v.validate_components(payload(), image, source=source)
    assert result["status"] == "rejected" and not result["text_elements"] and not result["tables"]
    assert result["issues"] == ["source_invalid"]


def test_null_unknown_and_inferred_are_preserved_without_acceptance(image):
    raw = payload()
    raw["text_elements"] = [
        dict(text=None, reading="unknown", bbox=None),
        dict(text="inferred", reading="inferred", bbox=None),
    ]
    raw["tables"][0]["columns"] = None
    result = validate(raw, image)
    assert all(t["status"] == "unresolved" for t in result["text_elements"])
    assert result["summary"]["cell_text_accepted"] == 1
    assert result["tables"][0]["status"] == "unresolved"


def test_one_bad_container_does_not_erase_other_components(image):
    raw = payload()
    raw["text_elements"] = "invalid"
    result = validate(raw, image)
    assert result["summary"]["tables_accepted"] == 1
    assert "invalid_text_container" in result["issues"]


def test_schema_failure_can_retain_valid_json_components_and_image_only_prompt(image):
    service = Mock()
    response = service.generate.return_value.response
    response.status, response.finish_reason = "malformed", "stop"
    raw = payload()
    raw["text_elements"].append(dict(text=12, reading="observed", bbox=None))
    response.output = parse_json_output(__import__("json").dumps(raw))
    response.export.return_value = {}
    record = v.extract_structured(
        service, image, credential_ref="test", model="test", component_mode=True
    )
    assert record["output"]["summary"]["text_accepted"] == 1
    assert record["output"]["text_elements"][1]["status"] == "rejected"
    request = service.generate.call_args.args[0]
    assert request.messages[0].images[0].data == image.inline().data
    assert request.output_spec.schema_ref == v.QUALITY_REF
    assert "Báo cá0" not in request.messages[0].content
    response.status = "partial"
    assert (
        v.extract_structured(
            service, image, credential_ref="test", model="test", component_mode=True
        )["output"]
        is None
    )


def test_crop_preserves_source_pixels_and_local_provenance(harness, image):
    harness.page.page.elements.append(
        OCRTable(
            id="table",
            type="table",
            bbox=[10, 20, 190, 80],
            name="synthetic",
            crop="unused.png",
            cells=[],
        )
    )
    before = harness.page.page.export_source()
    crop = v.crop_verified_table(image, harness.page, "table")
    assert crop.parent_sha256 == image.sha256 and crop.crop_bbox == (10, 20, 190, 80)
    assert (crop.width, crop.height) == (180, 60)
    with (
        Image.open(io.BytesIO(crop.content)) as decoded,
        Image.open(io.BytesIO(image.content)) as original,
    ):
        assert decoded.tobytes() == original.crop(crop.crop_bbox).tobytes()
    assert v.image_source(crop)["coordinate_space"] == "crop_local_pixels"
    assert harness.page.page.export_source() == before
    with pytest.raises(ValueError, match="crop_table_ambiguous"):
        v.crop_verified_table(image, harness.page, "missing")
