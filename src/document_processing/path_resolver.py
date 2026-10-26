"""Runtime Path Mapping v1, chỉ kiểm tra metadata; không mở nội dung hoặc ghi file."""

import os
import stat

from ..core import DataConfig, DataConfigError
from .contracts.path_mapping import PathMappingIssue, PathMappingRequest, PathMappingResult
from .contracts.path_mapping_validation import map_path_lexically, validate_path_mapping_result


def _validated(result: PathMappingResult) -> PathMappingResult:
    result = PathMappingResult.model_validate(result.export_result())
    issues = validate_path_mapping_result(result)
    if issues:
        # Unsafe source/context phải được giữ nguyên dù quality validator báo lỗi.
        result.status = "unsafe"
        result.confirmed_target = None
        for issue in issues:
            if issue not in result.issues:
                result.issues.append(issue)
    return result


def resolve_path(request: PathMappingRequest, config: DataConfig) -> PathMappingResult:
    """Bind đúng root key, kiểm tra target tại thời điểm gọi, giữ logical result.

    Không follow symlink/reparse point, kể cả bên trong root và ancestors của root.
    Đây không phải secure-open API: filesystem có thể đổi giữa các metadata calls
    hoặc sau khi trả result. Consumer phải kiểm tra lại tại thời điểm sử dụng.
    """
    result = map_path_lexically(request)
    if result.status != "not_checked":
        return _validated(result)
    if len(result.candidate_targets) != 1 or validate_path_mapping_result(result):
        result.issues.append(
            PathMappingIssue(
                code="invalid_lexical_result",
                path=["candidate_targets"],
                message="Expected one validated lexical candidate",
            )
        )
        result.status = "unsafe"
        return _validated(result)
    candidate = result.candidate_targets[0]

    def unsafe(code: str, *, rejected: bool = False) -> PathMappingResult:
        result.status = "unsafe"
        result.containment_check = "rejected" if rejected else result.containment_check
        result.issues.append(
            PathMappingIssue(
                code=code,
                path=["candidate_targets", 0],
                message="Runtime target check failed; see issue code (no fallback attempted)",
            )
        )
        return _validated(result)

    try:
        root = config.get_root(candidate.root_key)
    except DataConfigError:
        return unsafe("root_binding_error")

    # Quality validator đã xác minh suffix portable POSIX, không absolute/drive/UNC/.. .
    target = root.joinpath(*candidate.relative_suffix.split("/"))
    if ".." in root.parts or not target.is_relative_to(root):
        return unsafe("invalid_runtime_root", rejected=True)

    try:
        # Kiểm tra toàn bộ ancestors để root cũng không được đi qua symlink/junction.
        for component in [*reversed(root.parents), root]:
            metadata = component.lstat()
            if _is_link(metadata):
                return unsafe("symlink_or_reparse_point", rejected=True)
            if not stat.S_ISDIR(metadata.st_mode):
                return unsafe("root_not_directory")
        resolved_root = root.resolve(strict=True)
        # Không thay root khi inputs overlap hoặc có cùng filesystem identity.
        for key, field in config.ROOT_FIELDS.items():
            other = getattr(config, field)
            if key == candidate.root_key or other is None:
                continue
            try:
                same = root.samefile(other)
            except OSError:
                # Availability của root khác không phải điều kiện của selected binding.
                continue
            if same:
                result.issues.append(
                    PathMappingIssue(
                        code="shared_root_identity",
                        path=["candidate_targets", 0, "root_key"],
                        message=f"Configured root shares filesystem identity with {key}",
                    )
                )
    except FileNotFoundError:
        return unsafe("root_unavailable")
    except PermissionError:
        return unsafe("permission_denied")
    except (OSError, RuntimeError):
        return unsafe("filesystem_error")

    try:
        current = root
        missing = False
        for part in candidate.relative_suffix.split("/"):
            current = current / part
            try:
                metadata = current.lstat()
            except FileNotFoundError:
                missing = True
                break
            if _is_link(metadata):
                return unsafe("symlink_or_reparse_point", rejected=True)
            if current != target and not stat.S_ISDIR(metadata.st_mode):
                return unsafe("parent_not_directory")

        resolved_target = target.resolve(strict=False)
        if not resolved_target.is_relative_to(resolved_root):
            return unsafe("runtime_containment_failed", rejected=True)
        result.containment_check = "verified"
        if missing:
            result.status = "missing"
            result.existence_check = "missing"
            result.issues.append(
                PathMappingIssue(
                    code="missing_target",
                    path=["candidate_targets", 0],
                    message="Target does not exist under the bound root",
                )
            )
            return _validated(result)
        result.existence_check = "exists"
        if not stat.S_ISREG(metadata.st_mode):
            return unsafe("target_not_regular_file")
        extension = ".json" if result.reference.category == "ocr_page_json" else ".png"
        if target.suffix.lower() != extension:
            return unsafe("resource_extension_mismatch")
        if not os.access(target, os.R_OK):
            return unsafe("target_inaccessible")
        result.status = "resolved"
        result.confirmed_target = candidate.model_copy(deep=True)
        return _validated(result)
    except PermissionError:
        return unsafe("permission_denied")
    except (OSError, RuntimeError):
        return unsafe("filesystem_error")


def _is_link(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )
