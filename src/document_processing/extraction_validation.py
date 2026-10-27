"""Composition validators M1-04a; reports runtime, không thay versioned contracts."""

import re
from dataclasses import asdict, dataclass, replace
from typing import Literal

from .contracts.document_understanding_validation import (
    DocumentUnderstandingStructuralError,
    parse_document_understanding,
    validate_understanding_quality,
)
from .contracts.path_mapping_validation import validate_path_mapping_result
from .contracts.validation import RawOCRStructuralError, parse_raw_ocr, validate_quality
from .crop_audit import CROP_FIELDS, CropError, audit_page, digest, read_image, reference_request
from .extraction_artifacts import (
    check_bbox_ledger,
    parse_recovery_entries,
    verify_alternative,
)
from .ocr_loader import OCRLoadError, load_ocr_page
from .path_resolver import resolve_path


@dataclass(frozen=True)
class ExtractionIssue:
    code: str
    category: Literal["structural", "quality", "artifact"]
    origin: str
    source_token: str
    path: tuple[str | int, ...] = ()
    artifact_token: str | None = None
    status: str = "requires_review"
    message: str = "Review the referenced source field or artifact."


@dataclass(frozen=True)
class CropAvailability:
    path: tuple[str | int, ...]
    artifact_token: str
    availability: Literal["existing_original", "reconstructed_available", "missing_unrecovered"]
    mapping_status: str
    recovery_id: str | None = None
    original_equivalence: str = "unverified"


@dataclass(frozen=True)
class ExtractionReport:
    source_token: str
    structural_status: str
    image_status: str
    source_binding_status: str
    ledger_status: str
    issues: tuple[ExtractionIssue, ...]
    crops: tuple[CropAvailability, ...] = ()

    def export(self):
        return asdict(self)


def _safe_path(path):
    # Unknown fields may themselves contain OCR/private strings. Keep only schema keys.
    from .contracts.document_understanding import UnderstandingModel
    from .contracts.path_mapping import PathMappingModel
    from .contracts.raw_ocr import RawOCRModel

    def fields(base):
        return set(base.model_fields) | set().union(*(fields(c) for c in base.__subclasses__()))

    allowed = fields(RawOCRModel) | fields(UnderstandingModel) | fields(PathMappingModel)
    return tuple(p if type(p) is int or p in allowed else "[field]" for p in path)


def _finish(report, issues, crops=()):
    # Full provenance in equality: same code at different origins/locations stays distinct.
    unique = tuple(sorted(set(issues), key=lambda i: digest(asdict(i))))
    return replace(report, issues=unique, crops=tuple(crops))


def validate_extraction_payload(
    payload, *, source_context: str, understanding=None, raw_binding_verified=False
):
    """Pure in-memory parse/quality composition; caller attests raw source binding."""
    token = digest(source_context)
    report = ExtractionReport(token, "valid", "not_verified", "not_verified", "not_verified", ())
    issues = []

    def forward(values, category, origin):
        issues.extend(
            ExtractionIssue(i.code, category, origin, token, _safe_path(i.path), digest(i.path))
            for i in values
        )

    page = None
    try:
        page = parse_raw_ocr(payload)
        forward(validate_quality(page), "quality", "raw_ocr_v1")
    except RawOCRStructuralError as error:
        report = replace(report, structural_status="invalid")
        forward(error.issues, "structural", "raw_ocr_v1")
    if understanding is not None:
        try:
            result = parse_document_understanding(understanding)
            forward(
                validate_understanding_quality(
                    result, raw_page=page if raw_binding_verified else None
                ),
                "quality",
                "document_understanding_v1",
            )
            # Supplied UnderstandingIssue records are evidence, distinct from
            # issues detected by the quality validator. Never echo free messages.
            supplied = [(("issues", j), item) for j, item in enumerate(result.issues)]
            for collection in ("text_regions", "tables"):
                for i, obj in enumerate(getattr(result, collection)):
                    supplied.extend(
                        ((collection, i, "issues", j), item)
                        for j, item in enumerate(obj.issues or [])
                    )
                    for k, cell in enumerate(getattr(obj, "cells", [])):
                        supplied.extend(
                            ((collection, i, "cells", k, "issues", j), item)
                            for j, item in enumerate(cell.issues or [])
                        )
            for location, item in supplied:
                code = (
                    item.code
                    if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", item.code)
                    else ("unrecognized_issue_code")
                )
                issues.append(
                    ExtractionIssue(
                        code,
                        "quality",
                        "understanding_reported",
                        token,
                        _safe_path(item.path),
                        digest([location, item.model_dump(mode="json")]),
                    )
                )
            if page is None or not raw_binding_verified:
                issues.append(
                    ExtractionIssue(
                        "raw_binding_not_verified",
                        "artifact",
                        "understanding_binding",
                        token,
                        status="not_verified",
                    )
                )
        except DocumentUnderstandingStructuralError as error:
            report = replace(report, structural_status="invalid")
            forward(error.issues, "structural", "document_understanding_v1")
    return _finish(report, issues)


def _boxes(page):
    for i, element in enumerate(page.elements):
        prefix = ("elements", i)
        yield prefix + ("bbox",), element.bbox
        for name in ("seal_bbox", "signature_bbox"):
            if hasattr(element, name):
                yield prefix + (name,), getattr(element, name)
        for j, cell in enumerate(getattr(element, "cells", [])):
            cp = prefix + ("cells", j)
            yield cp + ("bbox",), cell.bbox
            for k, line in enumerate(cell.lines):
                yield cp + ("lines", k, "bbox"), line.bbox


def validate_extraction(
    request,
    config,
    mappings,
    *,
    expected_identity=None,
    image_bindings=None,
    run_identity=None,
    recovery_entries=None,
    bbox_ledger=None,
    ledger_plan_id=None,
    understanding=None,
    raw_binding_verified=False,
    expected_image_hash=None,
):
    """Read-only single-page validation; no dataset discovery or recovery execution.

    Bindings are caller declarations, never a claim of Drive/run/content equivalence.
    Only matching recovered alternatives are read. No persistent verification cache.
    """
    token = digest([request.reference.source_ref, request.reference.original_path])
    initial = ExtractionReport(
        token, "not_verified", "not_verified", "not_verified", "not_verified", ()
    )
    issues, crops = [], []

    def add(code, origin, path=(), artifact=None, status="requires_review", category="artifact"):
        issues.append(ExtractionIssue(code, category, origin, token, tuple(path), artifact, status))

    def mapping_check(result, path, artifact):
        for issue in (*result.issues, *validate_path_mapping_result(result)):
            add(issue.code, "path_mapping_v1", (*path, *_safe_path(issue.path)), artifact)

    # Ledger/index checks are independent of a page load failure.
    entries, ledger_items = [], []
    index_valid = False
    if recovery_entries is not None:
        try:
            entries = parse_recovery_entries(recovery_entries)
            index_valid = True
        except CropError as error:
            add(error.code, "recovery_index")
    if bbox_ledger is None:
        add("bbox_ledger_not_verified", "human_review", status="not_verified")
    else:
        try:
            ledger_items = check_bbox_ledger(bbox_ledger, entries, plan_id=ledger_plan_id)
            initial = replace(initial, ledger_status="consistent")
        except CropError as error:
            add(error.code, "human_review", status="not_verified")
            # Retain recorded labels even when binding cannot be verified. No
            # guessed source/page linkage: use ledger context and opaque item token.
            raw_items = bbox_ledger.get("issues", []) if isinstance(bbox_ledger, dict) else []
            if isinstance(raw_items, list):
                for index, item in enumerate(raw_items):
                    if isinstance(item, dict) and item.get("issue_code") == (
                        "source_bbox_incomplete_table"
                    ):
                        issues.append(
                            ExtractionIssue(
                                "source_bbox_incomplete_table",
                                "quality",
                                "human_review",
                                digest(["bbox_ledger", ledger_plan_id]),
                                ("issues", index),
                                digest(item),
                                "not_verified",
                            )
                        )
    for item in ledger_items:
        entry = next(e for e in entries if e.recovery_id == item["recovery_id"])
        if entry.ocr_source == request.reference.original_path:
            add(
                "source_bbox_incomplete_table",
                "human_review",
                artifact=digest([entry.original_crop_reference, entry.recovery_id]),
                category="quality",
            )
    try:
        loaded = load_ocr_page(request, config)
    except OCRLoadError as error:
        mapping = error.mapping_result
        if mapping is not None:
            mapping_check(mapping, ("source",), digest(request.reference.original_path))
        if error.issues:
            for issue in error.issues:
                add(
                    issue.code,
                    "raw_ocr_v1",
                    _safe_path(issue.path),
                    category=("structural" if error.code == "structural_failure" else "artifact"),
                )
        add(
            error.code,
            "ocr_loader",
            category=("structural" if error.code == "structural_failure" else "artifact"),
        )
        return _finish(
            replace(
                initial,
                structural_status=(
                    "invalid" if error.code == "structural_failure" else "not_verified"
                ),
            ),
            issues,
        )
    page = loaded.page
    base = validate_extraction_payload(
        page.export_source(),
        source_context=token,
        understanding=understanding,
        raw_binding_verified=raw_binding_verified,
    )
    issues.extend(replace(i, source_token=token) for i in base.issues)
    report = replace(initial, structural_status=base.structural_status)
    mapping_check(loaded.mapping_result, ("source",), digest(request.reference.original_path))
    identity = (page.page.symbol, page.page.year, page.page.page)
    binding_ok = expected_identity is not None and identity == expected_identity
    if not binding_ok:
        add(
            "source_identity_mismatch"
            if expected_identity is not None
            else "source_identity_not_verified",
            "source_binding",
            status="not_verified",
        )
    image_binding = (image_bindings or {}).get(page.page.image)
    if image_binding != identity:
        binding_ok = False
        add("image_binding_not_verified", "source_binding", status="not_verified")
    if run_identity is None:
        add("run_identity_not_verified", "source_binding", status="not_verified")
    report = replace(
        report,
        source_binding_status=(
            "caller_bound_run_unverified"
            if binding_ok and run_identity is None
            else "caller_bound"
            if binding_ok
            else "not_verified"
        ),
    )
    image_request = reference_request(
        page.page.image,
        "raw_page_image",
        request.reference.original_path,
        ["page", "image"],
        mappings,
    )
    mapping_check(resolve_path(image_request, config), ("page", "image"), digest(page.page.image))
    image, image_hash = None, None
    try:
        image, image_hash = read_image(image_request, config)
        report = replace(report, image_status="checked")
        if expected_image_hash is not None and image_hash != expected_image_hash:
            add("source_image_changed", "page_image", ("page", "image"))
            binding_ok = False
            report = replace(report, image_status="invalid", source_binding_status="not_verified")
        if image.size != (page.page.width, page.page.height):
            add("coordinate_dimensions_mismatch", "page_image", ("page",))
            report = replace(report, image_status="invalid")
        for path, box in _boxes(page):
            if (
                min(box[0], box[2]) < 0
                or min(box[1], box[3]) < 0
                or max(box[0], box[2]) > image.width
                or max(box[1], box[3]) > image.height
            ):
                add("bbox_outside_image", "page_image", path)
    except CropError as error:
        add(error.code, "page_image", ("page", "image"))
        report = replace(report, image_status="invalid")
    try:
        records = audit_page(
            request,
            config,
            mappings,
            expected_identity=expected_identity or identity,
            image_bindings=image_bindings,
            run_identity=run_identity,
        )
        # Reload comparison detects source changes between loader/audit snapshots.
        fresh = load_ocr_page(request, config).page
        if fresh.export_source() != page.export_source():
            raise CropError("source_changed")
    except (OCRLoadError, CropError):
        add("source_changed", "crop_audit")
        records = []
        binding_ok = False
        report = replace(report, source_binding_status="not_verified")
    try:
        for i, element in enumerate(page.elements):
            for field in CROP_FIELDS:
                original = element.model_dump(exclude_unset=True).get(field)
                if not isinstance(original, str):
                    continue
                path, artifact = ("elements", i, field), digest(original)
                crop_request = reference_request(
                    original, "ocr_crop", request.reference.original_path, list(path), mappings
                )
                result = resolve_path(crop_request, config)
                mapping_check(result, path, artifact)
                availability, rid = "missing_unrecovered", None
                if result.status == "resolved":
                    try:
                        crop_image, _ = read_image(crop_request, config)
                        crop_image.close()
                        availability = "existing_original"
                    except CropError as error:
                        add(error.code, "original_crop", path, artifact)
                elif result.status == "missing":
                    matches = [
                        e
                        for e in entries
                        if e.ocr_source == request.reference.original_path
                        and e.original_crop_reference == original
                    ]
                    if not matches:
                        add(
                            "recovery_entry_missing" if index_valid else "recovery_not_verified",
                            "recovery_index",
                            path,
                            artifact,
                            "not_verified",
                        )
                    else:
                        record = next(
                            (r for r in records if r.element_index == i and r.field == field), None
                        )
                        try:
                            if not binding_ok or image is None or record is None:
                                raise CropError("recovery_source_unverified")
                            if any(
                                e.id == element.id
                                for e in page.elements[:i] + page.elements[i + 1 :]
                            ):
                                raise CropError("ambiguous_source_binding")
                            verify_alternative(matches[0], record, image, image_hash, config)
                            availability, rid = "reconstructed_available", matches[0].recovery_id
                        except (CropError, OSError) as error:
                            add(
                                error.code if isinstance(error, CropError) else "recovery_io_error",
                                "recovery_index",
                                path,
                                artifact,
                            )
                else:
                    add(
                        "original_reference_not_verified",
                        "original_crop",
                        path,
                        artifact,
                        "not_verified",
                    )
                crops.append(CropAvailability(path, artifact, availability, result.status, rid))
        if image is not None:
            try:
                checked, checked_hash = read_image(image_request, config)
                checked.close()
                if checked_hash != image_hash:
                    raise CropError("source_changed")
            except CropError:
                add("source_changed", "page_image", ("page", "image"))
                report = replace(
                    report, image_status="invalid", source_binding_status="not_verified"
                )
                crops = [
                    replace(c, availability="missing_unrecovered", recovery_id=None)
                    if c.availability == "reconstructed_available"
                    else c
                    for c in crops
                ]
    finally:
        if image is not None:
            image.close()
    return _finish(report, issues, crops)
