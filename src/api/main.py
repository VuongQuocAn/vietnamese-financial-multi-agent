"""HTTP composition for local PDF upload and metadata review (W-03)."""

import os
import tempfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field
from starlette.datastructures import UploadFile

from ..document_processing.metadata_preflight import MetadataModel, MetadataValues
from .document_store import DocumentError, DocumentStore, fail, safe_path
from .metadata_service import compose_metadata_service
from .preflight_jobs import PreflightJobs


class MetadataPatch(MetadataModel):
    metadata_revision: int = Field(ge=0)
    confirmed: bool
    values: MetadataValues


class ProcessRequest(MetadataModel):
    operation: Literal["preflight"]
    metadata_revision: int = Field(ge=0)


@contextmanager
def exclusive_writer(store):
    """OS lock released on crash; prevents multiple workers writing one local store."""
    with safe_path(store.root, ".writer.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Document storage already has an active API writer") from None
        yield


class BodyLimit:
    """Enforce actual multipart bytes even without Content-Length/chunked requests."""

    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/documents"
        ):
            return await self.app(scope, receive, send)
        count = 0

        async def bounded_receive():
            nonlocal count
            message = await receive()
            count += len(message.get("body", b""))
            if count > self.limit + 64 * 1024:
                fail(413, "upload_limit", "Tệp vượt giới hạn dung lượng upload.")
            return message

        return await self.app(scope, bounded_receive, send)


def create_app(
    *,
    storage_root=None,
    service=None,
    service_options=None,
    max_upload_bytes=None,
    max_pages=None,
    job_options=None,
):
    upload_limit = max_upload_bytes or int(os.environ.get("WEB_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))
    page_limit = max_pages or int(os.environ.get("WEB_MAX_PAGES", 200))
    root = Path(storage_root or os.environ.get("WEB_STORAGE_ROOT", "artifacts/web-demo-v1"))
    if upload_limit < 1 or page_limit < 1:
        raise ValueError("Invalid document limits")
    limits = dict(
        capacity=int(os.environ.get("WEB_PREFLIGHT_CAPACITY", 4)),
        batch_size=int(os.environ.get("WEB_PREFLIGHT_BATCH_SIZE", 4)),
        max_pages=int(os.environ.get("WEB_PREFLIGHT_MAX_PAGES", page_limit)),
        request_limit=int(os.environ.get("WEB_PREFLIGHT_REQUEST_LIMIT", 50)),
        dpi=int(os.environ.get("WEB_PREFLIGHT_DPI", 150)),
    )
    limits.update(job_options or {})
    if (
        not 1 <= limits["capacity"] <= 8
        or not 1 <= limits["batch_size"] <= 8
        or not 1 <= limits["max_pages"] <= page_limit
        or not 1 <= limits["request_limit"] <= 200
        or not 72 <= limits["dpi"] <= 200
    ):
        raise ValueError("Invalid preflight limits")

    @asynccontextmanager
    async def lifespan(app):
        store = DocumentStore(root, max_upload_bytes=upload_limit, max_pages=page_limit)
        with exclusive_writer(store):
            adapter = None
            actual_service, options = service, service_options or {}
            if actual_service is None:
                actual_service, adapter, options = compose_metadata_service(store)
            jobs = PreflightJobs(store, actual_service, **options, **limits)
            app.state.store, app.state.jobs = store, jobs
            try:
                yield
            finally:
                jobs.close()
                if adapter and not jobs.worker.is_alive():
                    adapter.close()

    app = FastAPI(title="Financial AI API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BodyLimit, limit=upload_limit)

    @app.exception_handler(DocumentError)
    async def document_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "retryable": error.status == 429,
                },
                "request_id": str(uuid4()),
            },
            headers={"Retry-After": "2"} if error.status == 429 else {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Dữ liệu yêu cầu không hợp lệ.",
                    "retryable": False,
                },
                "request_id": str(uuid4()),
            },
        )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method in ("POST", "PATCH", "DELETE"):
            origins = os.environ.get(
                "WEB_ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"
            ).split(",")
            if (
                request.headers.get("origin")
                and request.headers["origin"] not in origins
                or request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "origin_rejected",
                            "message": "Origin không được phép.",
                            "retryable": False,
                        }
                    },
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "financial-ai-api"}

    @app.post("/api/documents", status_code=201)
    async def upload(request: Request):
        store, jobs = request.app.state.store, request.app.state.jobs
        form = None
        try:
            form = await request.form(max_files=1, max_fields=0)
            items = list(form.multi_items())
            if len(items) != 1 or items[0][0] != "file" or not isinstance(items[0][1], UploadFile):
                fail(422, "invalid_upload", "Gửi đúng một tệp PDF trong field file.")
            file = items[0][1]
            if file.content_type not in ("application/pdf", "application/octet-stream"):
                fail(415, "not_pdf", "Chỉ chấp nhận tệp PDF.")
            descriptor, name = tempfile.mkstemp(prefix=".upload-", dir=safe_path(store.root))
            temporary = Path(name)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    size = 0
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > store.max_upload_bytes:
                            fail(413, "upload_limit", "Tệp vượt giới hạn dung lượng upload.")
                        output.write(chunk)
                doc = store.ingest(temporary, file.filename or "document.pdf")
            finally:
                temporary.unlink(missing_ok=True)
            try:
                jobs.submit(doc["id"], 0, str(uuid4()))
            except DocumentError as error:
                if error.status != 429:
                    raise
            doc = store.load(doc["id"])
            return JSONResponse(
                status_code=201,
                content=store.public(doc),
                headers={"Location": f"/api/documents/{doc['id']}"},
            )
        finally:
            if form is not None:
                await form.close()

    @app.get("/api/documents")
    def documents(
        request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
    ):
        store = request.app.state.store
        with store.lock:
            docs = [store.load(identifier) for identifier in store.identifiers()]
        docs.sort(key=lambda doc: (doc["created_at"], doc["id"]), reverse=True)
        items = []
        for doc in docs[offset : offset + limit]:
            item = {
                key: doc[key]
                for key in (
                    "id",
                    "filename",
                    "created_at",
                    "state",
                    "metadata_revision",
                    "latest_result",
                )
            }
            item.update(
                {
                    key: doc["metadata"]["values"][key] if doc["metadata"]["confirmed"] else None
                    for key in ("company_name", "stock_ticker", "reporting_year")
                }
            )
            items.append(item)
        return dict(items=items, total=len(docs), offset=offset, limit=limit)

    @app.get("/api/documents/{identifier}")
    def detail(identifier: str, request: Request):
        store = request.app.state.store
        return store.public(store.load(identifier))

    @app.get("/api/documents/{identifier}/file")
    def original(identifier: str, request: Request):
        return FileResponse(
            request.app.state.store.file(identifier),
            media_type="application/pdf",
            filename="document.pdf",
            content_disposition_type="inline",
        )

    @app.get("/api/documents/{identifier}/status")
    def status(identifier: str, request: Request):
        doc = request.app.state.store.load(identifier)
        return {key: doc[key] for key in ("metadata_revision", "state", "job")} | {
            "document_id": identifier
        }

    @app.patch("/api/documents/{identifier}/metadata")
    def patch_metadata(identifier: str, payload: MetadataPatch, request: Request):
        store = request.app.state.store
        return store.public(
            store.patch(identifier, payload.metadata_revision, payload.confirmed, payload.values)
        )

    @app.post("/api/documents/{identifier}/process")
    def process(
        identifier: str,
        payload: ProcessRequest,
        request: Request,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        try:
            if UUID(idempotency_key).version != 4:
                raise ValueError
        except ValueError:
            fail(422, "invalid_idempotency_key", "Idempotency-Key phải là UUIDv4.")
        job, status_code = request.app.state.jobs.submit(
            identifier, payload.metadata_revision, idempotency_key
        )
        return JSONResponse(
            status_code=status_code,
            content=dict(document_id=identifier, job=job),
            headers={"Location": f"/api/documents/{identifier}/status"},
        )

    return app


app = create_app()
