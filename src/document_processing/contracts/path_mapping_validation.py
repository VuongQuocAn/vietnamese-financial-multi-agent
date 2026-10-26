"""Lexical validation thuần bộ nhớ; không resolve, stat, glob hoặc đọc file."""

import re
import unicodedata
from dataclasses import dataclass

from .path_mapping import (
    PATH_MAPPING_CONTRACT_VERSION,
    PathMappingIssue,
    PathMappingRequest,
    PathMappingResult,
    PathMappingStatus,
    PathReference,
    PathStyle,
    PathTarget,
)


@dataclass(frozen=True)
class _LexicalPath:
    anchor: str
    parts: tuple[str, ...]


class _PathPolicyError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _parse(value: str, style: PathStyle) -> _LexicalPath:
    """Không normalize separators, dot segments, case, Unicode hoặc encoding."""
    if not value.strip():
        raise _PathPolicyError("empty_path", "Path is empty or whitespace")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        raise _PathPolicyError(
            "unsafe_segment", "Control, format or surrogate characters forbidden"
        )
    if ".." in re.split(r"[/\\]", value):
        raise _PathPolicyError("path_traversal", "Parent segments forbidden; path was not repaired")
    if "%" in value:
        raise _PathPolicyError(
            "unsupported_path_format", "Encoded path representations unsupported"
        )
    if "://" in value or value.startswith("~"):
        raise _PathPolicyError("unsupported_path_format", "URLs and home expansion unsupported")
    separator = "/" if style == "posix" else "\\"
    other = "\\" if style == "posix" else "/"
    if other in value:
        raise _PathPolicyError("invalid_separators", "Separators do not match explicit path style")
    anchor = ""
    tail = value
    if style == "posix":
        if value.startswith("//"):
            raise _PathPolicyError("absolute_path_injection", "Double-root syntax forbidden")
        if value.startswith("/"):
            anchor, tail = "/", value[1:]
    elif re.match(r"^[a-zA-Z]:\\", value):
        anchor, tail = value[:3], value[3:]
    elif value.startswith("\\\\"):
        unc = value[2:].split("\\")
        if len(unc) < 2 or not all(unc[:2]):
            raise _PathPolicyError("unsupported_path_format", "UNC requires server and share")
        anchor = "\\\\" + "\\".join(unc[:2]) + "\\"
        tail = "\\".join(unc[2:])
        # Server/share cũng phải tuân thủ segment policy.
        for part in unc[:2]:
            _check_segment(part)
    elif value.startswith("\\") or re.match(r"^[a-zA-Z]:", value):
        raise _PathPolicyError(
            "absolute_path_injection", "Drive-relative/root-relative path forbidden"
        )
    parts = tail.split(separator)
    # Cho phép root / hoặc C:\ làm approved root; mapping tới chính root bị từ chối bên dưới.
    if not tail and anchor:
        parts = []
    for part in parts:
        _check_segment(part)
    return _LexicalPath(anchor=anchor, parts=tuple(parts))


def _check_segment(part: str) -> None:
    if not part:
        raise _PathPolicyError("invalid_separators", "Empty segments/repeated separators forbidden")
    if part in {".", ".."} or part.endswith((".", " ")):
        raise _PathPolicyError("unsafe_segment", "Dot segments and trailing dot/space forbidden")
    if any(char in part for char in '<>:"|?*'):
        raise _PathPolicyError(
            "absolute_path_injection", "Drive/stream or nonportable segment syntax"
        )
    stem = part.split(".", 1)[0].rstrip(" ").upper()
    if stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or re.fullmatch(
        r"(?:COM|LPT)[1-9¹²³]", stem
    ):
        raise _PathPolicyError("unsafe_segment", "Windows device names forbidden on every host")


def _contains(root: _LexicalPath, source: _LexicalPath) -> bool:
    return root.anchor == source.anchor and source.parts[: len(root.parts)] == root.parts


def _reference_context_issues(reference: PathReference) -> list[PathMappingIssue]:
    issues = []
    for code, field, message, invalid in (
        (
            "empty_source_context",
            "source_ref",
            "Artifact/run context required",
            not reference.source_ref.strip(),
        ),
        (
            "invalid_source_location",
            "source_location",
            "Expected source key/index",
            not reference.source_location
            or any(
                (isinstance(item, str) and not item.strip()) or (isinstance(item, int) and item < 0)
                for item in reference.source_location
            ),
        ),
        (
            "mismatched_source_category",
            "crop_view",
            "View requires crop category",
            reference.crop_view is not None and reference.category != "ocr_crop",
        ),
    ):
        if invalid:
            issues.append(PathMappingIssue(code=code, path=["reference", field], message=message))
    return issues


def map_path_lexically(request: PathMappingRequest) -> PathMappingResult:
    """Trả logical candidates, luôn not_checked nếu unique; không đọc filesystem.

    Nhiều matching rules cùng category luôn ambiguous, kể cả nested roots.
    Invalid configuration fail closed toàn request để tránh chọn rule theo thứ tự.
    """
    issues = _reference_context_issues(request.reference)

    def add(code: str, path: list[str | int], message: str) -> None:
        issues.append(PathMappingIssue(code=code, path=path, message=message))

    def result(
        status: PathMappingStatus, candidates: list[PathTarget] | None = None
    ) -> PathMappingResult:
        return PathMappingResult(
            contract_version=PATH_MAPPING_CONTRACT_VERSION,
            reference=request.reference.model_copy(deep=True),
            status=status,
            candidate_targets=candidates or [],
            existence_check="not_checked",
            containment_check="not_checked",
            issues=issues,
        )

    reference = request.reference
    roots = []
    seen: set[str] = set()
    for i, mapping in enumerate(request.mappings):
        prefix = ["mappings", i]
        if not mapping.mapping_id.strip() or mapping.mapping_id in seen:
            add(
                "duplicate_mapping_identifier"
                if mapping.mapping_id in seen
                else "empty_mapping_id",
                prefix + ["mapping_id"],
                "Expected unique nonempty mapping identifier",
            )
        seen.add(mapping.mapping_id)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", mapping.destination_root_key):
            add(
                "invalid_root_key", prefix + ["destination_root_key"], "Expected logical config key"
            )
        try:
            root = _parse(mapping.source_root, mapping.path_style)
            roots.append((mapping, root))
        except _PathPolicyError as error:
            add(error.code, prefix + ["source_root"], str(error))
    if issues:
        return result("unsafe")

    # Parse source độc lập với số rules; vẫn phát hiện unknown root khi mappings rỗng.
    sources = {}
    errors = []
    for style in ("posix", "windows"):
        try:
            sources[style] = _parse(reference.original_path, style)
        except _PathPolicyError as error:
            errors.append(error)
    if not sources:
        error = errors[0]
        add(error.code, ["reference", "original_path"], str(error))
        return result("unsafe")
    matches = [
        (mapping, root, sources[mapping.path_style])
        for mapping, root in roots
        if mapping.path_style in sources and _contains(root, sources[mapping.path_style])
    ]
    compatible = [item for item in matches if item[0].category == reference.category]
    if not compatible:
        add(
            "mismatched_source_category" if matches else "unknown_source_root",
            ["reference", "original_path"],
            "No approved mapping for this root and category",
        )
        return result("unmapped")
    candidates = []
    for mapping, root, source in compatible:
        suffix = source.parts[len(root.parts) :]
        if not suffix:
            add("empty_relative_suffix", ["reference", "original_path"], "Resource cannot be root")
            return result("unsafe")
        candidates.append(
            PathTarget(
                mapping_id=mapping.mapping_id,
                root_key=mapping.destination_root_key,
                relative_suffix="/".join(suffix),
            )
        )
    candidates.sort(key=lambda candidate: candidate.mapping_id)
    if len(candidates) > 1:
        add("ambiguous_root_matching", ["mappings"], "Multiple approved rules match; none selected")
        return result("ambiguous", candidates)
    return result("not_checked", candidates)


def validate_path_mapping_result(result: PathMappingResult) -> list[PathMappingIssue]:
    """Quality/status consistency, không chứng minh các khai báo runtime là thật."""
    issues = _reference_context_issues(result.reference)

    def add(code: str, path: list[str | int], message: str) -> None:
        issues.append(PathMappingIssue(code=code, path=path, message=message))

    source_errors = []
    for style in ("posix", "windows"):
        try:
            _parse(result.reference.original_path, style)
            break
        except _PathPolicyError as error:
            source_errors.append(error)
    else:
        error = source_errors[0]
        # Unsafe output được phép giữ source lỗi; các trạng thái khác cần báo xung đột.
        if result.status != "unsafe":
            add(error.code, ["reference", "original_path"], str(error))

    candidates = result.candidate_targets
    confirmed = result.confirmed_target
    seen: set[str] = set()
    for i, target in enumerate(candidates):
        path = ["candidate_targets", i]
        if target.mapping_id in seen:
            add("duplicate_mapping_identifier", path + ["mapping_id"], "Candidate ID repeated")
        seen.add(target.mapping_id)
        try:
            parsed = _parse(target.relative_suffix, "posix")
            if parsed.anchor:
                raise _PathPolicyError("absolute_path_injection", "Suffix must be relative")
        except _PathPolicyError as error:
            add(error.code, path + ["relative_suffix"], str(error))
        if not target.mapping_id.strip():
            add("empty_mapping_id", path + ["mapping_id"], "Expected mapping identifier")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", target.root_key):
            add("invalid_root_key", path + ["root_key"], "Expected logical config key")
    if confirmed is not None and (len(candidates) != 1 or confirmed != candidates[0]):
        add("status_conflict", ["confirmed_target"], "Confirmed target must equal unique candidate")
    expected_checks = {
        "resolved": ("exists", "verified"),
        "missing": ("missing", "verified"),
        "not_checked": ("not_checked", "not_checked"),
        "ambiguous": ("not_checked", "not_checked"),
        "unmapped": ("not_checked", "not_checked"),
    }
    if (
        result.status in expected_checks
        and (result.existence_check, result.containment_check) != expected_checks[result.status]
    ):
        add("status_conflict", ["status"], "Runtime evidence does not agree with status")
    if result.status == "resolved" and confirmed is None:
        add("status_conflict", ["confirmed_target"], "Resolved requires runtime-confirmed target")
    if result.status != "resolved" and confirmed is not None:
        add("status_conflict", ["confirmed_target"], "Only resolved may carry confirmed target")
    if result.status in {"resolved", "missing", "not_checked"} and len(candidates) != 1:
        add("status_conflict", ["candidate_targets"], "Expected unique candidate")
    if result.status == "ambiguous" and len(candidates) < 2:
        add("status_conflict", ["candidate_targets"], "Ambiguous requires multiple candidates")
    if result.status == "unmapped" and candidates:
        add("status_conflict", ["candidate_targets"], "Unmapped cannot have candidates")
    if result.status == "missing" and not any(i.code == "missing_target" for i in result.issues):
        add("missing_target", ["issues"], "Missing status requires missing_target issue")
    if result.status == "unsafe" and not result.issues:
        add("status_conflict", ["issues"], "Unsafe requires an explicit issue")
    return issues
