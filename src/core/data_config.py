"""Cấu hình dataset local; không đọc dữ liệu hoặc dựng target của resolver."""

import os
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

DataRootKey = Literal[
    "FINANCIAL_REPORT_DIR", "FINANCIAL_OCR_DIR", "NORMALIZED_DATA_DIR", "CANONICAL_DATA_DIR"
]


class DataConfigError(ValueError):
    """Lỗi cấu hình; thông báo không chứa giá trị environment."""


def _local_path(value: str | Path, key: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise DataConfigError(f"{key}: expected a local path string or native Path")
    text = str(value)
    if not text.strip() or any(ord(char) < 32 for char in text):
        raise DataConfigError(f"{key}: empty path or control characters")
    if "://" in text or text.startswith("~"):
        raise DataConfigError(f"{key}: URLs and home expansion are unsupported")
    windows = PureWindowsPath(text)
    if os.name == "nt":
        if text.startswith(("\\\\?\\", "\\\\.\\")):
            raise DataConfigError(f"{key}: Windows device paths are unsupported")
        if (windows.drive or windows.root) and not windows.is_absolute():
            raise DataConfigError(f"{key}: expected a fully qualified native path")
        parts = windows.parts[1:] if windows.anchor else windows.parts
        if any(char in part for part in parts for char in '<>:"|?*'):
            raise DataConfigError(f"{key}: invalid Windows path syntax")
        if any(PureWindowsPath(part).is_reserved() for part in parts):
            raise DataConfigError(f"{key}: Windows device paths are unsupported")
    elif windows.drive or "\\" in text:
        raise DataConfigError(f"{key}: Windows paths cannot be used on this platform")
    return Path(value)


def default_project_root() -> Path:
    """Chỉ suy ra root từ source checkout; bản cài wheel cần truyền root tường minh."""
    root = Path(__file__).resolve().parents[2]
    if not (root / "pyproject.toml").is_file() or not (root / "src/core/data_config.py").is_file():
        raise DataConfigError("project_root: supply an absolute base outside a source checkout")
    return root


class DataConfig(BaseModel):
    """Các paths tuyệt đối theo platform hiện tại, không chứng minh availability."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, hide_input_in_errors=True)

    ROOT_FIELDS: ClassVar[Mapping[str, str]] = MappingProxyType(
        {
            "FINANCIAL_REPORT_DIR": "financial_report_dir",
            "FINANCIAL_OCR_DIR": "financial_ocr_dir",
            "NORMALIZED_DATA_DIR": "normalized_data_dir",
            "CANONICAL_DATA_DIR": "canonical_data_dir",
        }
    )

    project_root: Path
    financial_report_dir: Path
    financial_ocr_dir: Path
    normalized_data_dir: Path | None = None
    canonical_data_dir: Path | None = None

    @field_validator("*", mode="after")
    @classmethod
    def absolute_native_path(cls, value: Path | None) -> Path | None:
        if value is not None:
            path = _local_path(value, "path")
            if not path.is_absolute():
                raise ValueError("DataConfig requires absolute native paths; use load_data_config")
        return value

    @model_validator(mode="after")
    def separate_outputs(self) -> "DataConfig":
        # Lexical guard cho xung đột cấu hình hiển nhiên, không kiểm tra symlink.
        inputs = [self.financial_report_dir, self.financial_ocr_dir]
        outputs = [self.normalized_data_dir, self.canonical_data_dir]
        for i, output in enumerate(outputs):
            if output is None:
                continue
            output = Path(os.path.normpath(output))
            for other in inputs + outputs[:i]:
                if other is None:
                    continue
                other = Path(os.path.normpath(other))
                if output.is_relative_to(other) or other.is_relative_to(output):
                    raise ValueError(
                        "Output roots must be lexically disjoint from inputs and outputs"
                    )
        return self

    def get_root(self, root_key: str) -> Path:
        """Lookup whitelist; không nối suffix, không fallback, không filesystem I/O."""
        if not isinstance(root_key, str) or root_key not in self.ROOT_FIELDS:
            raise DataConfigError("Unknown data root key")
        root = getattr(self, self.ROOT_FIELDS[root_key])
        if root is None:
            raise DataConfigError(f"{root_key}: root is not configured")
        return root


def load_data_config(
    environment: Mapping[str, str] | None = None, *, project_root: str | Path | None = None
) -> DataConfig:
    """Đọc bốn biến hiện hữu; relative paths tính từ base tuyệt đối, không đọc .env."""
    environment = os.environ if environment is None else environment
    if not isinstance(environment, Mapping):
        raise DataConfigError("environment: expected a mapping")
    base = (
        default_project_root()
        if project_root is None
        else _local_path(project_root, "project_root")
    )
    if not base.is_absolute():
        raise DataConfigError("project_root: expected an absolute native path")
    values: dict[str, Path] = {"project_root": base}
    for key, field in DataConfig.ROOT_FIELDS.items():
        if key not in environment:
            if key in {"FINANCIAL_REPORT_DIR", "FINANCIAL_OCR_DIR"}:
                raise DataConfigError(f"{key}: required configuration is missing")
            continue
        value = environment[key]
        if not isinstance(value, str):
            raise DataConfigError(f"{key}: environment value must be a string")
        path = _local_path(value, key)
        # abspath loại dot segments bằng lexical normalization, không resolve symlink.
        values[field] = path if path.is_absolute() else Path(os.path.abspath(base / path))
    return DataConfig(**values)
