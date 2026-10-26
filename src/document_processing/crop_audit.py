"""Audit crop references qua loader/resolver; không ghi artifacts hoặc ảnh."""

import hashlib
import io
import json
import warnings
from collections import Counter
from dataclasses import asdict, dataclass

from PIL import Image, UnidentifiedImageError

from ..core import DataConfig
from .contracts.path_mapping import PathMappingRequest, PathReference, PathRootMapping
from .ocr_loader import OCRLoadError, _read_bytes, load_ocr_page
from .path_resolver import resolve_path

MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
CROP_FIELDS = ("crop", "ink_view_crop", "black_view_crop", "red_view_crop", "blue_view_crop")


class CropError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_image(request: PathMappingRequest, config: DataConfig) -> tuple[Image.Image, str]:
    """Bounded bytes qua read policy loader; decode PNG với pixel limit trước load."""
    result = resolve_path(request, config)
    if result.status != "resolved" or result.confirmed_target is None:
        raise CropError(
            "source_image_missing" if result.status == "missing" else "source_image_unsafe"
        )
    target = result.confirmed_target
    path = config.get_root(target.root_key).joinpath(*target.relative_suffix.split("/"))
    try:
        content = _read_bytes(path, request, config, result, MAX_IMAGE_BYTES)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=["PNG"]) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise CropError("oversized_image")
                if image.mode not in {"RGB", "RGBA", "L", "LA", "1", "P"}:
                    raise CropError("unsupported_image_mode")
                image.load()
                return image.copy(), hashlib.sha256(content).hexdigest()
    except OCRLoadError as error:
        raise CropError(error.code) from None
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise CropError("oversized_image") from None
    except (UnidentifiedImageError, OSError, ValueError) as error:
        if isinstance(error, CropError):
            raise
        raise CropError("image_decode_failed") from None


@dataclass(frozen=True)
class CropAuditRecord:
    page_identity: tuple[str, str, int]
    ocr_source: str
    run_identity: str | None
    element_index: int
    element_id: str
    element_type: str
    field: str
    original_path: str
    source_image: str
    bbox: tuple[int, ...]
    page_dimensions: tuple[int, int]
    mapping_status: str
    eligibility: str
    issues: tuple[str, ...]
    deduplication_key: str
    path_key: str
    source_image_hash: str | None
    verified_local_mapping_id: str | None = None

    def export(self) -> dict:
        return asdict(self)


def reference_request(original_path, category, source_ref, location, mappings):
    return PathMappingRequest(
        contract_version="path_mapping_v1",
        reference=PathReference(
            original_path=original_path,
            category=category,
            source_ref=source_ref,
            source_location=location,
        ),
        mappings=[m.model_copy(deep=True) for m in mappings],
    )


def audit_page(
    request: PathMappingRequest,
    config: DataConfig,
    mappings: list[PathRootMapping],
    *,
    expected_identity: tuple[str, str, int],
    image_bindings: dict[str, tuple[str, str, int]] | None = None,
    run_identity: str | None = None,
) -> list[CropAuditRecord]:
    """image_bindings là xác nhận caller, không suy ra từ basename/detection_view."""
    loaded = load_ocr_page(request, config)
    page = loaded.page
    identity = (page.page.symbol, page.page.year, page.page.page)
    source_ref = request.reference.original_path
    image_request = reference_request(
        page.page.image, "raw_page_image", source_ref, ["page", "image"], mappings
    )
    image_result = resolve_path(image_request, config)
    image_error = None
    image_size = None
    image_hash = None
    # Chỉ decode ảnh khi có missing reference; không quét/decode crops hiện hữu.
    records = []
    for index, element in enumerate(page.elements):
        values = element.model_dump(exclude_unset=True)
        for field in CROP_FIELDS:
            if field not in values:
                continue
            original = values[field]
            if not isinstance(original, str):
                continue
            crop_request = reference_request(
                original, "ocr_crop", source_ref, ["elements", index, field], mappings
            )
            result = resolve_path(crop_request, config)
            status = "existing" if result.status == "resolved" else result.status
            issues = [issue.code for issue in result.issues]
            if run_identity is None:
                issues.append("run_identity_unverified")
            eligibility = "not_needed" if status == "existing" else "requires_review"
            if identity != expected_identity:
                issues.append("source_identity_mismatch")
            if status != "existing" and field != "crop":
                eligibility = "unsupported_view"
                issues.append("unverified_color_transformation")
            bbox = tuple(element.bbox)
            if status == "missing":
                if field != "crop":
                    eligibility = "unsupported_view"
                    issues.append("unverified_color_transformation")
                elif element.type != "table":
                    issues.append("unverified_crop_region")
                elif identity != expected_identity:
                    issues.append("source_identity_mismatch")
                elif image_result.status != "resolved":
                    eligibility = (
                        "source_image_missing"
                        if image_result.status == "missing"
                        else "requires_review"
                    )
                    issues.extend([eligibility, *[i.code for i in image_result.issues]])
                elif (image_bindings or {}).get(page.page.image) != identity:
                    issues.append("source_identity_unverified")
                else:
                    if image_size is None and image_error is None:
                        try:
                            image, image_hash = read_image(image_request, config)
                            image_size = image.size
                            image.close()
                        except CropError as error:
                            image_error = error.code
                    if image_error:
                        issues.append(image_error)
                    elif image_size != (page.page.width, page.page.height):
                        issues.append("coordinate_dimensions_mismatch")
                    elif (
                        len(bbox) != 4
                        or any(type(v) is not int for v in bbox)
                        or not (0 <= bbox[0] < bbox[2] <= image_size[0])
                        or not (0 <= bbox[1] < bbox[3] <= image_size[1])
                    ):
                        eligibility = "invalid_bbox"
                        issues.append("invalid_bbox")
                    else:
                        eligibility = "eligible_candidate"
            # Context bao gồm artifact + run khi biết; không gộp basename/runs.
            context = [run_identity, source_ref, identity, original]
            records.append(
                CropAuditRecord(
                    identity,
                    source_ref,
                    run_identity,
                    index,
                    element.id,
                    element.type,
                    field,
                    original,
                    page.page.image,
                    bbox,
                    (page.page.width, page.page.height),
                    status,
                    eligibility,
                    tuple(issues),
                    digest([context, index, element.id, element.type, field]),
                    digest([run_identity, source_ref, original]),
                    image_hash,
                    result.candidate_targets[0].mapping_id
                    if len(result.candidate_targets) == 1
                    else None,
                )
            )
    return records


def summarize(records: list[CropAuditRecord]) -> dict:
    missing = [r for r in records if r.mapping_status == "missing"]
    eligible = [r for r in records if r.eligibility == "eligible_candidate"]
    return {
        "references_audited": len(records),
        "missing_references": len(missing),
        "unique_source_paths": len({r.original_path for r in records}),
        "unique_missing_paths": len({r.original_path for r in missing}),
        "contextual_missing_paths": len({r.path_key for r in missing}),
        "eligible_candidates": len({r.deduplication_key for r in eligible}),
        "requires_review": sum(r.eligibility == "requires_review" for r in records),
        "mapping_status": dict(Counter(r.mapping_status for r in records)),
        "eligibility": dict(Counter(r.eligibility for r in records)),
        "reference_types": dict(Counter(f"{r.element_type}.{r.field}" for r in records)),
        "missing_types": dict(Counter(f"{r.element_type}.{r.field}" for r in missing)),
        "run_identity_unverified": any(r.run_identity is None for r in records),
    }


def select_inventory_pages(pages: list[dict], warnings: list[dict]) -> list[dict]:
    """Chọn đúng pages đã có cảnh báo thiếu trong M1-01, không scan filesystem."""
    warned = {
        w["source"]
        for w in warnings
        if w.get("code") == "crop_reference_colab_suffix_missing" and w.get("count", 0) > 0
    }
    selected = []
    seen = set()
    for page in pages:
        source = page["source"]
        if source in seen:
            raise CropError("duplicate_inventory_page")
        seen.add(source)
        if page.get("references", {}).get("crop:colab_suffix_missing", 0) > 0:
            if source not in warned:
                raise CropError("inventory_warning_mismatch")
            selected.append(page)
    if not selected or len(selected) > 193 or {p["source"] for p in selected} != warned:
        raise CropError("inventory_coverage_mismatch")
    return sorted(selected, key=lambda p: (p["symbol"], p["year"], p["page"], p["source"]))
