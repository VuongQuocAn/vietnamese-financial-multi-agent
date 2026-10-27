"""Checkpoint nội bộ trên trusted local filesystem; không xác minh nghiệp vụ."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.data_config import DataConfig
from .contracts.document_understanding import RawPageIdentity

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1, pattern=r"\S")]
CheckpointStatus = Literal["MISS", "HIT", "STALE", "INVALID"]


def _json_bytes(value: Any) -> bytes:
    # Không cho JSON coercion keys/tuples làm mất hoặc đổi representation nguồn.
    def check(item: Any) -> None:
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError("JSON object keys must be strings")
                check(child)
        elif type(item) is list:
            for child in item:
                check(child)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise ValueError("Expected JSON-compatible values")

    check(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def fingerprint_json(value: Any) -> str:
    """SHA-256 của JSON ổn định; caller truyền đủ content/provenance/config liên quan."""
    return hashlib.sha256(_json_bytes(value)).hexdigest()


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, hide_input_in_errors=True)


class ProcessingUnit(_Model):
    """source_ref bắt buộc bind tài liệu/run; page=None là document-level."""

    source_ref: NonEmpty
    page: RawPageIdentity | None = None

    @model_validator(mode="after")
    def page_identity(self) -> "ProcessingUnit":
        if self.page is not None:
            if not all(
                value.strip() for value in (self.page.symbol, self.page.year, self.page.image)
            ) or not (self.page.source_ref and self.page.source_ref.strip()):
                raise ValueError("Page identity requires source_ref and nonempty source fields")
            if self.page.page < 1:
                raise ValueError("Page index must be positive")
        return self


class CheckpointRequest(_Model):
    unit: ProcessingUnit
    stage: NonEmpty
    input_fingerprint: Digest
    config_fingerprint: Digest
    processing_version: NonEmpty


class _Artifact(_Model):
    format_version: Literal["document_checkpoint_v1"]
    request: CheckpointRequest
    verified: bool
    result: Any
    result_digest: Digest
    artifact_digest: Digest


@dataclass(frozen=True)
class CheckpointLookup:
    status: CheckpointStatus
    # HIT có thể chứa JSON null; phải kiểm tra status, không kiểm tra truthiness.
    result: Any = None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate checkpoint key")
        result[key] = value
    return result


class CheckpointStore:
    """Một writer/process. I/O errors được raise; dữ liệu hỏng trả INVALID."""

    def __init__(self, output_root: Path, *, data_config: DataConfig):
        self.output_root = Path(output_root).resolve()
        protected = [
            data_config.financial_report_dir,
            data_config.financial_ocr_dir,
            data_config.project_root / "data" / "raw",
            data_config.project_root / "data" / "processed",
            data_config.project_root / "data" / "recovered_crops",
        ]
        protected += [
            root
            for root in (data_config.normalized_data_dir, data_config.canonical_data_dir)
            if root is not None
        ]
        for root in protected:
            root = root.resolve()
            if self.output_root.is_relative_to(root) or root.is_relative_to(self.output_root):
                raise ValueError("Checkpoint root must be separate from data roots")

    @staticmethod
    def _request(request: CheckpointRequest) -> dict[str, Any]:
        # Revalidate nested mutable RawPageIdentity; snapshot trước I/O.
        return CheckpointRequest.model_validate(request.model_dump(exclude_unset=True)).model_dump(
            mode="json", exclude_unset=True
        )

    def _path(self, request: dict[str, Any]) -> Path:
        # Một slot cho unit/stage; thay revision sẽ STALE thay vì silently HIT.
        key = fingerprint_json({"unit": request["unit"], "stage": request["stage"]})
        return self.output_root / f"{key}.json"

    def lookup(self, request: CheckpointRequest) -> CheckpointLookup:
        expected = self._request(request)
        try:
            content = self._path(expected).read_bytes()
        except FileNotFoundError:
            return CheckpointLookup("MISS")
        try:
            body = json.loads(content, object_pairs_hook=_unique_object)
            artifact = _Artifact.model_validate(body)
            integrity = body.pop("artifact_digest")
            if (
                artifact.verified is not True
                or fingerprint_json(body) != integrity
                or fingerprint_json(artifact.result) != artifact.result_digest
            ):
                return CheckpointLookup("INVALID")
            if body["request"] != expected:
                return CheckpointLookup("STALE")
            return CheckpointLookup("HIT", artifact.result)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return CheckpointLookup("INVALID")

    def save_verified(self, request: CheckpointRequest, result: Any, *, verified: bool) -> None:
        """Caller xác nhận semantic validation đã hoàn tất; strict True bắt buộc.

        ValueError cho JSON/attestation sai, OSError cho I/O; không publish khi lỗi.
        """
        if verified is not True:
            raise ValueError("Caller must explicitly confirm a completed, verified result")
        expected = self._request(request)
        body = {
            "format_version": "document_checkpoint_v1",
            "request": expected,
            "verified": True,
            "result": result,
            "result_digest": fingerprint_json(result),
        }
        body["artifact_digest"] = fingerprint_json(body)
        content = _json_bytes(body)
        self.output_root.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.output_root, prefix=".checkpoint-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path(expected))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
