"""Local document snapshots, one writer per API process; no dataset mutations."""

import hashlib
import json
import os
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

import pypdfium2 as pdfium

from ..document_processing.metadata_preflight import (
    PDF_LOCK,
    MetadataValues,
    core_metadata_resolved,
    empty_suggestions,
)


def now():
    return datetime.now(UTC).isoformat()


class DocumentError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def fail(status, code, message):
    raise DocumentError(status, code, message)


def safe_path(root: Path, *parts):
    """Reject symlinks/junctions including ancestors and enforce resolved containment."""
    path = root.joinpath(*parts).absolute()
    for entry in (path, *path.parents):
        if entry.exists() or entry.is_symlink():
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                fail(500, "unsafe_storage", "Vị trí lưu trữ không an toàn.")
    if not path.resolve().is_relative_to(root.resolve()):
        fail(500, "unsafe_storage", "Vị trí lưu trữ không an toàn.")
    return path


def atomic_json(path, payload):
    """Flush content before same-directory replace; callers hold store lock."""
    descriptor, name = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class DocumentStore:
    def __init__(self, root: Path, *, max_upload_bytes=50 * 1024 * 1024, max_pages=200):
        self.root = root.absolute()
        self.lock = RLock()
        self.max_upload_bytes, self.max_pages = max_upload_bytes, max_pages
        safe_path(self.root).mkdir(parents=True, exist_ok=True)
        safe_path(self.root, "documents").mkdir(exist_ok=True)

    def directory(self, identifier):
        try:
            parsed = UUID(str(identifier))
            if parsed.version != 4 or str(parsed) != str(identifier):
                raise ValueError
        except ValueError:
            fail(404, "document_not_found", "Không tìm thấy tài liệu.")
        return safe_path(self.root, "documents", str(parsed))

    def load(self, identifier):
        with self.lock:
            directory = self.directory(identifier)
            path = safe_path(self.root, "documents", directory.name, "document.json")
            if not path.is_file():
                fail(404, "document_not_found", "Không tìm thấy tài liệu.")
            doc = json.loads(path.read_text(encoding="utf-8"))
            metadata = doc["metadata"]
            metadata.setdefault("accepted", metadata["confirmed"])
            metadata.setdefault(
                "acceptance_origin", "user" if metadata["confirmed"] or metadata["edits"] else None
            )
            metadata.setdefault("acceptance_history", [])
            return doc

    def save(self, document):
        with self.lock:
            document["updated_at"] = now()
            path = safe_path(self.root, "documents", document["id"], "document.json")
            atomic_json(path, document)

    def identifiers(self):
        for path in safe_path(self.root, "documents").iterdir():
            try:
                if UUID(path.name).version == 4 and path.is_dir():
                    yield path.name
            except ValueError:
                continue

    def public(self, document):
        return {key: value for key, value in document.items() if not key.startswith("_")}

    def file(self, identifier):
        self.load(identifier)
        return safe_path(self.root, "documents", identifier, "original.pdf")

    def ingest(self, temporary, filename):
        """The temporary file has already passed streaming byte limits."""
        with temporary.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                fail(415, "not_pdf", "Chỉ chấp nhận tệp PDF có header hợp lệ.")
        try:
            with PDF_LOCK, pdfium.PdfDocument(temporary) as pdf:
                count = len(pdf)
                if count < 1:
                    raise ValueError
                # Reject encrypted PDFs even if an empty password happens to open.
                if pdfium.raw.FPDF_GetSecurityHandlerRevision(pdf.raw) != -1:
                    raise ValueError
        except Exception:
            fail(422, "invalid_pdf", "PDF hỏng hoặc có mã hóa/mật khẩu.")
        if count > self.max_pages:
            fail(413, "page_limit", "PDF vượt giới hạn số trang.")
        with temporary.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        identifier = str(uuid4())
        directory = self.directory(identifier)
        directory.mkdir(exist_ok=False)
        target = safe_path(self.root, "documents", identifier, "original.pdf")
        # New UUID directory only; never use client filename as a path.
        with temporary.open("rb") as source, target.open("xb") as output:
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        filename = filename.replace("\\", "/").split("/")[-1]
        filename = "".join(c for c in filename if c.isprintable())[:240] or "document.pdf"
        document = dict(
            id=identifier,
            filename=filename,
            size_bytes=target.stat().st_size,
            content_id=f"sha256:{digest}",
            page_count=count,
            created_at=now(),
            updated_at=now(),
            state="uploaded",
            metadata_revision=0,
            runtime_identity=dict(symbol=f"document:{identifier}", year=None),
            metadata=dict(
                suggestions=empty_suggestions(),
                values={key: None for key in MetadataValues.model_fields},
                confirmed=False,
                accepted=False,
                acceptance_origin=None,
                acceptance_history=[],
                edits=[],
                preflight=None,
            ),
            job=None,
            latest_result=None,
            limits=dict(max_upload_bytes=self.max_upload_bytes, max_pages=self.max_pages),
            _original_pdf=f"documents/{identifier}/original.pdf",
            _attempts={},
        )
        self.save(document)
        return document

    def patch(self, identifier, revision, confirmed, values):
        with self.lock:
            doc = self.load(identifier)
            if revision != doc["metadata_revision"]:
                fail(409, "metadata_revision_conflict", "Thông tin đã thay đổi. Hãy tải lại.")
            if doc["job"] and doc["job"]["state"] in ("queued", "processing"):
                fail(409, "job_active", "Đợi nhận diện metadata hoàn tất trước khi sửa.")
            if confirmed and (
                not values.company_name
                or not values.company_name.strip()
                or values.reporting_year is None
            ):
                fail(422, "metadata_required", "Xác nhận cần tên công ty và năm hợp lệ.")
            metadata = doc["metadata"]
            updated = values.model_dump(mode="json")
            for field, value in updated.items():
                if value != metadata["values"][field]:
                    metadata["edits"].append(
                        dict(
                            field=field,
                            previous=metadata["values"][field],
                            value=value,
                            origin="user",
                            metadata_revision=revision + 1,
                            updated_at=now(),
                        )
                    )
            metadata.update(
                values=updated, confirmed=confirmed, accepted=confirmed, acceptance_origin="user"
            )
            doc["metadata_revision"] += 1
            doc["state"] = "ready" if confirmed else "needs_metadata"
            doc["runtime_identity"]["year"] = str(values.reporting_year) if confirmed else None
            doc["latest_result"] = None
            self.save(doc)
            return doc

    def auto_accept(self, doc):
        """Worker holds writer lock; never replace user-entered values."""
        metadata = doc["metadata"]
        if (
            metadata["confirmed"]
            or metadata["edits"]
            or metadata.get("acceptance_origin") == "user"
            or not core_metadata_resolved(metadata["suggestions"], doc["content_id"])
        ):
            return False
        values = {
            key: field["candidates"][0]["value"] if field["status"] == "resolved" else None
            for key, field in metadata["suggestions"].items()
        }
        validated = MetadataValues.model_validate(values).model_dump(mode="json")
        previous = metadata["values"]
        doc["metadata_revision"] += 1
        metadata.update(values=validated, accepted=True, confirmed=False, acceptance_origin="auto")
        metadata["acceptance_history"].append(
            dict(
                origin="auto",
                previous=previous,
                values=validated,
                metadata_revision=doc["metadata_revision"],
                attempt_id=doc["job"]["id"],
                updated_at=now(),
            )
        )
        doc["runtime_identity"]["year"] = str(validated["reporting_year"])
        doc["latest_result"] = None
        return True
