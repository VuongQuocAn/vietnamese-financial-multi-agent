"""Reconstructed bbox crops; dry-run mặc định, chỉ ghi root riêng, không overwrite."""

import hashlib
import io
import json
import os
import stat
from pathlib import Path

from PIL import Image

from ..core import DataConfig
from .contracts.path_mapping import PathMappingRequest, PathRootMapping
from .crop_audit import (
    CropAuditRecord,
    CropError,
    audit_page,
    digest,
    read_image,
    reference_request,
)
from .ocr_loader import OCRLoadError
from .path_resolver import _is_link

METHOD = "reconstructed_from_page_bbox"
METHOD_VERSION = "1"
PILOT_CAP = 12


def _check_components(path: Path) -> None:
    for part in [*reversed(path.parents), path]:
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            continue
        if _is_link(metadata):
            raise CropError("unsafe_output_link")
        if part != path and not stat.S_ISDIR(metadata.st_mode):
            raise CropError("unsafe_output_parent")


def validate_output_root(root: Path, config: DataConfig) -> Path:
    """Chỉ default root đã được task phê duyệt; không thêm DataConfig whitelist."""
    approved = config.project_root / "data/recovered_crops"
    if not root.is_absolute() or ".." in root.parts or root != approved:
        raise CropError("unapproved_output_root")
    _check_components(root)
    resolved = root.resolve()
    forbidden = [
        config.financial_report_dir,
        config.financial_ocr_dir,
        config.project_root / "data/raw",
        config.project_root / "data/processed",
        config.project_root / "Financial_Report",
        config.project_root / "Financial_Report_OCR",
    ]
    for input_root in forbidden:
        other = input_root.resolve()
        if resolved.is_relative_to(other) or other.is_relative_to(resolved):
            raise CropError("overlapping_output_root")
    if root.exists() and not root.is_dir():
        raise CropError("unsafe_output_root")
    return root


def _validate_png(content: bytes, size: tuple[int, int], mode: str, pixels: bytes) -> None:
    try:
        with Image.open(io.BytesIO(content), formats=["PNG"]) as image:
            image.load()
            if image.size != size or image.mode != mode or image.tobytes() != pixels:
                raise CropError("output_validation_failed")
    except (OSError, ValueError) as error:
        if isinstance(error, CropError):
            raise
        raise CropError("output_validation_failed") from None


def _read_output(path: Path, limit: int) -> bytes:
    _check_components(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
        raise CropError("output_conflict")
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise CropError("output_conflict")
    return content


def recover_crop(
    record: CropAuditRecord,
    page_request: PathMappingRequest,
    config: DataConfig,
    mappings: list[PathRootMapping],
    *,
    image_bindings: dict[str, tuple[str, str, int]] | None = None,
    output_root: Path | None = None,
    dry_run: bool = True,
    cap: int = PILOT_CAP,
) -> dict:
    """Re-audit nguồn, so hash, PNG exclusive + sidecar; không tin eligibility cũ.

    Trusted local filesystem, single writer. Checks không atomic với adversarial
    parent/root mutations; không bảo đảm chống hardlinks/mount aliases.
    """
    recovery_id = digest([METHOD, METHOD_VERSION, record.export()])
    relative = recovery_id + ".png"
    result = {
        "recovery_id": recovery_id,
        "original_crop_reference": record.original_path,
        "page_identity": record.page_identity,
        "ocr_source": record.ocr_source,
        "source_image_reference": record.source_image,
        "bbox": record.bbox,
        "output_relative_path": relative,
        "method": METHOD,
        "method_version": METHOD_VERSION,
        "status": "skipped",
        "source_image_hash": record.source_image_hash,
        "reconstructed_image_hash": None,
        "width": None,
        "height": None,
        "issues": list(record.issues),
        "equivalent_to_original_crop": "unverified",
    }
    try:
        if type(cap) is not int or not 1 <= cap <= PILOT_CAP:
            raise CropError("invalid_pilot_cap")
        root = validate_output_root(
            output_root or config.project_root / "data/recovered_crops", config
        )
        if record.eligibility != "eligible_candidate" or record.mapping_status != "missing":
            result["status"] = "ineligible"
            return result
        fresh = audit_page(
            page_request,
            config,
            mappings,
            expected_identity=record.page_identity,
            image_bindings=image_bindings,
            run_identity=record.run_identity,
        )
        if record not in fresh:
            raise CropError("source_changed")
        request = reference_request(
            record.source_image, "raw_page_image", record.ocr_source, ["page", "image"], mappings
        )
        image, source_hash = read_image(request, config)
        with image:
            if source_hash != record.source_image_hash:
                raise CropError("source_changed")
            with image.crop(record.bbox) as cropped:
                size, mode, pixels = cropped.size, cropped.mode, cropped.tobytes()
                buffer = io.BytesIO()
                # PNG encode giữ pixels/mode; không truyền metadata preprocessing nguồn.
                cropped.save(buffer, format="PNG")
                content = buffer.getvalue()
        _validate_png(content, size, mode, pixels)
        output_hash = hashlib.sha256(content).hexdigest()
        result.update(reconstructed_image_hash=output_hash, width=size[0], height=size[1])
        metadata = {
            "recovery_id": recovery_id,
            "source_image_hash": source_hash,
            "reconstructed_image_hash": output_hash,
            "method": METHOD,
            "method_version": METHOD_VERSION,
        }
        metadata_bytes = json.dumps(metadata, sort_keys=True).encode()
        output, sidecar = root / relative, root / (recovery_id + ".json")
        validate_output_root(root, config)
        if output.exists() or sidecar.exists() or output.is_symlink() or sidecar.is_symlink():
            try:
                actual = _read_output(output, len(content))
                saved_metadata = _read_output(sidecar, len(metadata_bytes))
            except (OSError, CropError):
                raise CropError("output_conflict") from None
            if actual != content or saved_metadata != metadata_bytes:
                raise CropError("output_conflict")
            _validate_png(actual, size, mode, pixels)
            result["status"] = "already_recovered"
            return result
        if root.exists() and sum(p.suffix.lower() == ".png" for p in root.iterdir()) >= cap:
            result["status"] = "pilot_cap_reached"
            return result
        if dry_run:
            result["status"] = "dry_run"
            return result
        # Không mkdir trước bước execute; kiểm tra lại sau mkdir và trước mỗi open.
        root.mkdir(parents=True, exist_ok=True)
        validate_output_root(root, config)
        try:
            with output.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            validate_output_root(root, config)
            actual = _read_output(output, len(content))
            if hashlib.sha256(actual).hexdigest() != output_hash:
                raise CropError("output_validation_failed")
            _validate_png(actual, size, mode, pixels)
            with sidecar.open("xb") as stream:
                stream.write(metadata_bytes)
        except FileExistsError:
            raise CropError("output_conflict") from None
        # Một source read cuối so nội dung sau write; không xóa output nếu có lỗi.
        checked_image, checked_hash = read_image(request, config)
        checked_image.close()
        if checked_hash != source_hash:
            raise CropError("source_changed")
        result["status"] = "recovered"
    except CropError as error:
        result["status"] = error.code
    except OCRLoadError as error:
        result["status"] = "source_changed"
        result["issues"].append(error.code)
    except OSError:
        result["status"] = "io_error"
    return result


def select_pilot(records: list[CropAuditRecord], preferred_pages=(), *, cap: int = PILOT_CAP):
    """Deterministic round-robin symbols; ưu tiên manifest representative/pilot."""
    if type(cap) is not int or not 1 <= cap <= PILOT_CAP:
        raise CropError("invalid_pilot_cap")
    preferred = set(preferred_pages)
    unique = {r.deduplication_key: r for r in records if r.eligibility == "eligible_candidate"}
    groups = {}
    for record in sorted(
        unique.values(),
        key=lambda r: (r.page_identity not in preferred, r.page_identity, r.deduplication_key),
    ):
        groups.setdefault(record.page_identity[0], []).append(record)
    selected = []
    while len(selected) < cap and any(groups.values()):
        for symbol in sorted(groups):
            if groups[symbol] and len(selected) < cap:
                selected.append(groups[symbol].pop(0))
    return selected
