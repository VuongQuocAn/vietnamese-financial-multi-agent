"""Synthetic image integration; no financial accuracy claims or live API."""

import hashlib
import io
from dataclasses import replace
from unittest.mock import Mock

import pytest
from PIL import Image
from pydantic import ValidationError
from vietnamese_financial_multi_agent.core.llm_contracts import Message
from vietnamese_financial_multi_agent.document_processing import vision_ocr as vision
from vietnamese_financial_multi_agent.document_processing.crop_audit import reference_request

from .test_ocr_correction import harness as correction_harness

harness = correction_harness


@pytest.fixture
def image(harness):
    buffer = io.BytesIO()
    Image.new("RGB", (200, 1000), "white").save(buffer, format="PNG")
    content = buffer.getvalue()
    return vision.VerifiedPageImage(
        harness.page.mapping_result.reference.anchor.page.model_copy(deep=True),
        hashlib.sha256(content).hexdigest(),
        200,
        1000,
        content,
    )


def test_actual_sdk_receives_png_and_raw_stays_immutable(harness, image):
    raw = harness.page.page.export_source()
    view = harness.run(image=image, require_vision=True)
    part = harness.client.models.generate_content.call_args.kwargs["contents"][0].parts[1]
    assert part.inline_data.data == image.content and part.inline_data.mime_type == "image/png"
    assert view.grounding == "vision" and view.image_sha256 == image.sha256
    assert view.corrections[0].status == "proposed"
    assert harness.page.page.export_source() == raw
    assert all(t.effective_text == t.original for t in view.texts)


def test_missing_image_does_not_fall_back_to_text(harness):
    assert "verified_image_required" in harness.run(require_vision=True).issues
    harness.client.models.generate_content.assert_not_called()


def test_mismatched_image_identity_or_bytes_stops_before_api(harness, image):
    wrong = image.identity.model_copy(update={"page": 99})
    assert "image_identity_mismatch" in harness.run(image=replace(image, identity=wrong)).issues
    assert "invalid_image_content" in harness.run(image=replace(image, content=b"bad")).issues
    harness.client.models.generate_content.assert_not_called()


@pytest.mark.parametrize("role,data", [("system", None), ("user", "file.png")])
def test_contract_rejects_image_roles_and_paths(image, role, data):
    payload = image.inline().export()
    if data is not None:
        payload["data"] = data
    with pytest.raises(ValidationError):
        Message(role=role, content="test", images=[payload])


def test_uncertain_image_binding_stops_before_read(harness, monkeypatch):
    reader = Mock()
    monkeypatch.setattr(vision, "read_image", reader)
    request = reference_request("p1.png", "raw_page_image", "synthetic-doc/run-A", [], [])
    with pytest.raises(ValueError, match="image_binding_failed"):
        vision.load_verified_image(
            harness.page, request, None, image_bindings={}, expected_sha256="x"
        )
    reader.assert_not_called()


def test_unreadable_image_fails_closed(harness, monkeypatch):
    monkeypatch.setattr(vision, "read_image", Mock(side_effect=ValueError("image_decode_failed")))
    request = reference_request("p1.png", "raw_page_image", "synthetic-doc/run-A", [], [])
    with pytest.raises(ValueError, match="image_decode_failed"):
        vision.load_verified_image(
            harness.page,
            request,
            None,
            image_bindings={"p1.png": ["SYNTHETIC", "2025", 1]},
            expected_sha256="x",
        )


def test_structured_input_has_no_old_ocr_and_unknown_bbox_allowed(harness, image):
    payload = dict(
        disposition="assessed",
        text_elements=[dict(text="visible", reading="observed", bbox=None)],
        tables=[dict(rows=None, columns=None, cells=[])],
        limitations=["unknown geometry"],
    )
    # Fixture service registry contains correction only: capture through a minimal service
    # to test extraction request; Gateway schema validation is exercised by registry below.
    service = Mock()
    service.generate.return_value.response = Mock(status="success", output=Mock(payload=payload))
    service.generate.return_value.response.export.return_value = {}
    record = vision.extract_structured(service, image, credential_ref="synthetic", model="test")
    request = service.generate.call_args.args[0]
    assert "Báo cá0" not in request.messages[0].content
    assert "raw" not in request.messages[0].content
    assert record["output"]["text_elements"][0]["bbox"] is None
    assert record["source"]["image_sha256"] == image.sha256
    assert vision.vision_schema_registry().is_valid(vision.STRUCTURED_REF, payload)
    payload["text_elements"][0]["bbox"] = [0, 0, 201, 10]
    with pytest.raises(ValueError, match="invalid_image_bbox"):
        vision.validate_structured(payload, image)


def test_image_tokens_reserved_without_counting_encoded_bytes(harness, image):
    harness.run(image=image)
    contents = harness.client.models.generate_content.call_args.kwargs["contents"]
    serial, bound = vision.sdk_image_bound(contents)
    assert bound == image.token_bound
    assert serial[0]["parts"][1]["inline_data"] == {"mime_type": "image/png"}
