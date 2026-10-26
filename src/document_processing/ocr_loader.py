"""Adapter OCR JSON read-only; runtime wrappers, không tạo contract mới."""

import errno
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..core import DataConfig
from .contracts.path_mapping import PathMappingRequest, PathMappingResult
from .contracts.raw_ocr import OCRPage
from .contracts.validation import (
    QualityIssue,
    RawOCRStructuralError,
    StructuralIssue,
    parse_raw_ocr,
    validate_quality,
)
from .path_resolver import _is_link, resolve_path

DEFAULT_MAX_BYTES = 32 * 1024 * 1024
OCRLoadCode = Literal[
    "invalid_max_bytes",
    "unsupported_category",
    "path_failure",
    "source_changed",
    "missing_file",
    "permission_denied",
    "io_error",
    "unsafe_file",
    "oversized_file",
    "empty_file",
    "invalid_utf8",
    "invalid_json",
    "duplicate_json_key",
    "unsupported_json_root",
    "structural_failure",
    "identity_mismatch",
]


@dataclass(frozen=True)
class LoadedOCRPage:
    page: OCRPage
    mapping_result: PathMappingResult
    quality_issues: tuple[QualityIssue, ...]
    # Không có anchor: không xác minh page identity, source_ref vẫn do caller khai báo.
    identity_checked: bool


class OCRLoadError(ValueError):
    """Lỗi dự kiến; không đưa OCR/local paths vào thông báo mặc định."""

    def __init__(
        self,
        code: OCRLoadCode,
        request: PathMappingRequest,
        mapping_result: PathMappingResult | None = None,
        *,
        issues: tuple[StructuralIssue, ...] = (),
    ):
        self.code = code
        self.reference = request.reference.model_copy(deep=True)
        self.mapping_result = mapping_result
        self.issues = issues
        super().__init__(f"OCR load failed: {code}")


def _fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    # Windows/Python có thể trả ctime khác semantics giữa lstat và fstat.
    # So dev/ino/size/mtime portable; POSIX thêm ctime phát hiện metadata change.
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns if os.name != "nt" else 0,
    )


def _read_bytes(
    target: Path,
    request: PathMappingRequest,
    config: DataConfig,
    result: PathMappingResult,
    max_bytes: int,
) -> bytes:
    def fail(code: OCRLoadCode) -> OCRLoadError:
        return OCRLoadError(code, request, result)

    def revalidate() -> None:
        fresh = resolve_path(request, config)
        if fresh.status != "resolved" or fresh.confirmed_target != result.confirmed_target:
            raise OCRLoadError("source_changed", request, fresh)

    try:
        # Tái sử dụng toàn bộ policy ancestors/root/suffix/containment của resolver.
        revalidate()
        before = target.lstat()
        if _is_link(before) or not stat.S_ISREG(before.st_mode):
            raise fail("unsafe_file")
        if before.st_size > max_bytes:
            raise fail("oversized_file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(target, flags)
        try:
            opened = os.fstat(descriptor)
            if _is_link(opened) or not stat.S_ISREG(opened.st_mode):
                raise fail("unsafe_file")
            if _fingerprint(opened) != _fingerprint(before):
                raise fail("source_changed")
            # fdopen tiếp quản descriptor; unbuffered, đọc tối đa max_bytes + sentinel.
            stream = os.fdopen(descriptor, "rb", buffering=0)
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            chunks = []
            total = 0
            while total <= max_bytes:
                chunk = stream.read(min(64 * 1024, max_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total > max_bytes:
                raise fail("oversized_file")
            if _fingerprint(os.fstat(stream.fileno())) != _fingerprint(opened):
                raise fail("source_changed")
            revalidate()
            if _fingerprint(target.lstat()) != _fingerprint(opened):
                raise fail("source_changed")
        return b"".join(chunks)
    except FileNotFoundError:
        raise fail("missing_file") from None
    except PermissionError:
        raise fail("permission_denied") from None
    except OSError as error:
        code = "unsafe_file" if error.errno == errno.ELOOP else "io_error"
        raise fail(code) from None


class _JSONPolicyError(ValueError):
    def __init__(self, code: OCRLoadCode):
        self.code = code


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _JSONPolicyError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise _JSONPolicyError("invalid_json")


def load_ocr_page(
    request: PathMappingRequest,
    config: DataConfig,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> LoadedOCRPage:
    """Resolve mới, bounded read, parse strict Raw OCR và trả quality issues riêng.

    UTF-8 (có thể có BOM), không fallback encoding, không sửa nguồn. Metadata
    checks/O_NOFOLLOW khi có chỉ giảm TOCTOU; không bảo đảm atomic secure-open.
    """
    if type(max_bytes) is not int or not 0 < max_bytes < sys.maxsize:
        raise OCRLoadError("invalid_max_bytes", request)
    if request.reference.category != "ocr_page_json":
        raise OCRLoadError("unsupported_category", request)
    # Snapshot inputs trong lần gọi; không dùng result cũ hoặc arbitrary local path.
    request = request.model_copy(deep=True)
    result = resolve_path(request, config)
    candidate = result.confirmed_target
    if result.status != "resolved" or candidate is None:
        raise OCRLoadError("path_failure", request, result)
    root = config.get_root(candidate.root_key)
    target = root.joinpath(*candidate.relative_suffix.split("/"))
    content = _read_bytes(target, request, config, result, max_bytes)
    if not content:
        raise OCRLoadError("empty_file", request, result)
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise OCRLoadError("invalid_utf8", request, result) from None
    if not decoded.strip():
        raise OCRLoadError("empty_file", request, result)
    try:
        payload = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except _JSONPolicyError as error:
        raise OCRLoadError(error.code, request, result) from None
    except (ValueError, RecursionError):
        raise OCRLoadError("invalid_json", request, result) from None
    if not isinstance(payload, dict):
        raise OCRLoadError("unsupported_json_root", request, result)
    try:
        page = parse_raw_ocr(payload)
    except RawOCRStructuralError as error:
        raise OCRLoadError(
            "structural_failure",
            request,
            result,
            issues=tuple(error.issues),
        ) from error
    anchor = result.reference.anchor
    if anchor is not None:
        mismatches = tuple(
            StructuralIssue(
                code="page_identity_mismatch",
                path=("page", field),
                message="OCR metadata differs from caller expected page identity",
            )
            for field in ("symbol", "year", "page", "image")
            if getattr(page.page, field) != getattr(anchor.page, field)
        )
        if mismatches:
            raise OCRLoadError("identity_mismatch", request, result, issues=mismatches)
    return LoadedOCRPage(page, result, tuple(validate_quality(page)), anchor is not None)
