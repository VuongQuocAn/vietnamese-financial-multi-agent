"""Read-only runtime evidence checks; không phải schema/version contract mới."""

import hashlib
import io
import json
import re
import warnings
from pathlib import Path
from typing import Annotated, Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .crop_audit import MAX_IMAGE_BYTES, CropError, digest
from .crop_expansion import recovery_id
from .crop_recovery import (
    METHOD,
    METHOD_VERSION,
    _read_output,
    _validate_png,
    validate_output_root,
)
from .ocr_loader import _reject_constant, _unique_object

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RecoveryEntry(BaseModel):
    """Projection runtime M1-03f; status strings không phải proof của availability."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    recovery_id: Hash
    original_crop_reference: str
    page_identity: Annotated[list[str | int], Field(min_length=3, max_length=3)]
    ocr_source: str
    source_image_reference: str
    bbox: Annotated[list[int], Field(min_length=4, max_length=4)]
    output_relative_path: str
    method: Literal["reconstructed_from_page_bbox"]
    method_version: Literal["1"]
    status: Literal["recovered", "already_recovered"]
    source_image_hash: Hash
    reconstructed_image_hash: Hash
    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]
    issues: list[str]
    equivalent_to_original_crop: Literal["unverified"]
    element_id: str
    element_type: Literal["table"]
    crop_field: Literal["crop"]
    validation_status: Literal["validated"]
    availability: Literal["reconstructed_available"]


def parse_recovery_entries(values):
    """Reject the complete projection on malformed/duplicate/ambiguous records."""
    if not isinstance(values, list):
        raise CropError("invalid_recovery_index")
    try:
        entries = [RecoveryEntry.model_validate(v) for v in values]
    except ValidationError:
        raise CropError("invalid_recovery_index") from None
    ids, contexts = set(), set()
    for entry in entries:
        if [type(v) for v in entry.page_identity] != [str, str, int]:
            raise CropError("invalid_recovery_index")
        context = (entry.ocr_source, entry.original_crop_reference)
        if entry.recovery_id in ids or context in contexts:
            raise CropError("duplicate_recovery_entry")
        ids.add(entry.recovery_id)
        contexts.add(context)
    return entries


def verify_alternative(entry, record, image, image_hash, config):
    """Bind fresh audit context, canonical ID, source bytes and exact crop pixels.

    Chỉ đọc output được chọn, không execute/re-encode/hash toàn recovery directory.
    """
    expected = dict(
        recovery_id=recovery_id(record),
        original_crop_reference=record.original_path,
        page_identity=list(record.page_identity),
        ocr_source=record.ocr_source,
        source_image_reference=record.source_image,
        bbox=list(record.bbox),
        source_image_hash=image_hash,
        element_id=record.element_id,
        element_type=record.element_type,
        crop_field=record.field,
        issues=list(record.issues),
    )
    if any(getattr(entry, k) != v for k, v in expected.items()):
        raise CropError("recovery_binding_mismatch")
    if record.eligibility != "eligible_candidate" or record.mapping_status != "missing":
        raise CropError("recovery_source_unverified")
    if entry.output_relative_path != entry.recovery_id + ".png":
        raise CropError("unsafe_recovery_target")
    root = validate_output_root(config.project_root / "data/recovered_crops", config)
    content = _read_output(root / entry.output_relative_path, MAX_IMAGE_BYTES)
    sidecar = read_json_bytes(_read_output(root / (entry.recovery_id + ".json"), 8192))
    expected_sidecar = dict(
        recovery_id=entry.recovery_id,
        source_image_hash=image_hash,
        reconstructed_image_hash=entry.reconstructed_image_hash,
        method=METHOD,
        method_version=METHOD_VERSION,
    )
    if sidecar != expected_sidecar:
        raise CropError("invalid_recovery_sidecar")
    if hashlib.sha256(content).hexdigest() != entry.reconstructed_image_hash:
        raise CropError("recovered_output_hash_mismatch")
    with image.crop(record.bbox) as cropped:
        if (entry.width, entry.height) != cropped.size:
            raise CropError("recovered_dimensions_mismatch")
        # The engine's pixel helper normally receives its own encoded bytes.
        # Here index bytes are untrusted: bound header dimensions BEFORE load.
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content), formats=["PNG"]) as header:
                    if header.size != cropped.size or header.mode != cropped.mode:
                        raise CropError("recovered_dimensions_mismatch")
        except (Image.DecompressionBombWarning, Image.DecompressionBombError, OSError, ValueError):
            raise CropError("invalid_recovered_image") from None
        _validate_png(content, cropped.size, cropped.mode, cropped.tobytes())


def read_json_bytes(content):
    try:
        return json.loads(
            content.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise CropError("invalid_evidence_json") from None


def read_local_evidence(path: Path, config, *, jsonl=False):
    """Caller-selected ignored artifacts only, bounded regular files, no discovery."""
    root = config.project_root / "artifacts"
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(root):
        raise CropError("unapproved_evidence_path")
    for source in (config.financial_report_dir, config.financial_ocr_dir):
        if path.resolve().is_relative_to(source.resolve()):
            raise CropError("overlapping_evidence_path")
    content = _read_output(path, 8 * 1024 * 1024)
    if jsonl:
        return [read_json_bytes(line) for line in content.splitlines() if line.strip()]
    return read_json_bytes(content)


def check_bbox_ledger(ledger, entries, *, plan_id):
    """M1-03f ledger attribution on trusted FS; does not close or repair an issue.

    Return caller's records only after consistency checks against the projection.
    This verifies recorded linkage, not authenticity/table completeness.
    """
    try:
        issues = ledger["issues"]
        if (
            not isinstance(issues, list)
            or type(ledger["issue_count"]) is not int
            or ledger["issue_count"] != len(issues)
            or not isinstance(plan_id, str)
            or not re.fullmatch(r"[0-9a-f]{64}", plan_id)
            or ledger["plan_id"] != plan_id
        ):
            raise ValueError
        lookup = {e.recovery_id: e for e in entries}
        seen, sheets = set(), set()
        for item in issues:
            entry = lookup[item["recovery_id"]]
            if (
                item["recovery_id"] in seen
                or type(item["review_sheet_number"]) is not int
                or item["review_sheet_number"] in sheets
                or item["issue_code"] != "source_bbox_incomplete_table"
                or item["status"] != "requires_review"
                or item["follow_up_task"] != "M1-04a"
                or item["bbox_modified"] is not False
                or item["complete_table"] is not False
                or not isinstance(item["reported_by"], str)
                or not item["reported_by"].strip()
                or not isinstance(item["evidence_basis"], str)
                or not item["evidence_basis"].strip()
                or digest(item["original_bbox"]) != digest(entry.bbox)
                or digest(item["page_identity"]) != digest(entry.page_identity)
                or item["element_id"] != entry.element_id
                or item["png_sha256"] != entry.reconstructed_image_hash
            ):
                raise ValueError
            seen.add(item["recovery_id"])
            sheets.add(item["review_sheet_number"])
        return issues
    except (KeyError, TypeError, ValueError):
        raise CropError("bbox_ledger_inconsistent") from None
