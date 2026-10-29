"""One bounded worker for metadata and extraction, with explicit retry only."""

from copy import deepcopy
from queue import Empty, Queue
from threading import Event, Thread
from uuid import uuid4

from ..document_processing.metadata_preflight import (
    DEFAULT_METADATA_MODEL,
    analyze_batch,
    core_metadata_resolved,
    empty_suggestions,
    merge_suggestions,
)
from .document_store import fail, now
from .extraction_sessions import run_extraction


class PreflightJobs:
    def __init__(
        self,
        store,
        service=None,
        *,
        credential_ref="",
        model=DEFAULT_METADATA_MODEL,
        capacity=4,
        batch_size=4,
        max_pages=200,
        request_limit=50,
        dpi=150,
        reservation_money=None,
    ):
        self.store, self.service = store, service
        self.credential_ref, self.model = credential_ref, model
        self.capacity, self.batch_size, self.max_pages = capacity, batch_size, max_pages
        self.request_limit, self.dpi = request_limit, dpi
        self.reservation_money = reservation_money
        self.queue = Queue(maxsize=capacity)
        self.stopping = Event()
        self.active_count = 0
        # Durable snapshots survive. Never restart a queued/network request implicitly.
        with store.lock:
            for identifier in store.identifiers():
                doc = store.load(identifier)
                if doc["job"] and doc["job"]["state"] in ("queued", "processing"):
                    error = (
                        dict(
                            code="application_interrupted",
                            message="Phiên xử lý đã gián đoạn.",
                            retryable=True,
                        )
                        if doc["job"]["operation"] == "extract"
                        else "server_interrupted"
                    )
                    self._state(doc, "interrupted", error)
        self.worker = Thread(target=self._loop, name="metadata-preflight", daemon=True)
        self.worker.start()

    def close(self):
        self.stopping.set()
        # Finish at most the current bounded provider request before releasing
        # the process writer lock; queued work stays interrupted on restart.
        self.worker.join()

    def _state(self, doc, state, error=None):
        doc["state"] = state
        job = doc["job"]
        job.update(state=state, error=error, updated_at=now(), revision=job["revision"] + 1)
        doc["_attempts"][job["id"]]["job"] = deepcopy(job)
        self.store.save(doc)

    def submit(self, identifier, revision, key, operation="preflight"):
        with self.store.lock:
            doc = self.store.load(identifier)
            # Idempotency is checked before active/revision conflicts, allowing exact replay.
            for attempt in doc["_attempts"].values():
                if attempt["key"] == key:
                    if attempt["revision"] != revision or attempt["job"]["operation"] != operation:
                        fail(409, "idempotency_conflict", "Khóa yêu cầu đã dùng cho revision khác.")
                    job = attempt["job"]
                    return job, 202 if job["state"] in ("queued", "processing") else 200
            if revision != doc["metadata_revision"]:
                fail(409, "metadata_revision_conflict", "Thông tin đã thay đổi. Hãy tải lại.")
            if doc["job"] and doc["job"]["state"] in ("queued", "processing"):
                fail(409, "job_active", "Tài liệu đang được xử lý.")
            if operation == "extract":
                values = doc["metadata"]["values"]
                if (
                    not doc["metadata"]["accepted"]
                    or not (values["company_name"] or "").strip()
                    or not values["reporting_year"]
                ):
                    fail(409, "metadata_required", "Cần tên doanh nghiệp và năm báo cáo hợp lệ.")
            if self.active_count >= self.capacity or self.stopping.is_set():
                fail(429, "queue_full", "Hàng đợi đã đầy. Vui lòng thử lại sau.")
            job = dict(
                id=str(uuid4()),
                operation=operation,
                state="queued",
                phase="preflight" if operation == "preflight" else "discovery",
                metadata_revision=revision,
                progress=dict(preflight=dict(completed_pages=0, total_pages=doc["page_count"])),
                page_errors=[],
                error=None,
                updated_at=now(),
                revision=1,
            )
            if operation == "extract":
                job["progress"] = dict(
                    discovery=dict(completed_pages=0, total_pages=doc["page_count"]),
                    extraction=None,
                )
            doc["job"] = job
            doc["state"] = "queued"
            doc["_attempts"][job["id"]] = dict(key=key, revision=revision, job=deepcopy(job))
            self.store.save(doc)
            self.active_count += 1
            self.queue.put_nowait(identifier)
            return deepcopy(job), 202

    def _loop(self):
        while not self.stopping.is_set():
            try:
                identifier = self.queue.get(timeout=0.2)
            except Empty:
                continue
            try:
                if self.store.load(identifier)["job"]["operation"] == "extract":
                    run_extraction(self, identifier)
                else:
                    self._run(identifier)
            except Exception:
                # No provider content, exception strings, credentials or paths in API/logs.
                with self.store.lock:
                    doc = self.store.load(identifier)
                    operation = doc["job"]["operation"]
                    if operation == "preflight" and doc["metadata"]["preflight"]:
                        doc["metadata"]["preflight"]["stop_reason"] = "internal_error"
                        doc["metadata"]["preflight"]["issues"].append("preflight_failed")
                    self._state(doc, "failed", f"{operation}_failed")
            finally:
                with self.store.lock:
                    self.active_count -= 1
                self.queue.task_done()

    def _run(self, identifier):
        with self.store.lock:
            doc = self.store.load(identifier)
            self._state(doc, "processing")
            metadata = doc["metadata"]
            if metadata.get("acceptance_origin") == "auto":
                metadata["accepted"] = False
                doc["runtime_identity"]["year"] = None
            if metadata["preflight"] is not None:
                doc.setdefault("_preflight_history", []).append(
                    deepcopy(
                        dict(
                            attempt_id=metadata["preflight"]["attempt_id"],
                            suggestions=metadata["suggestions"],
                            preflight=metadata["preflight"],
                        )
                    )
                )
            metadata["suggestions"] = empty_suggestions()
            preflight = dict(
                analyzed_pages=[],
                stop_reason=None,
                issues=[],
                schema_revision="metadata_v2",
                prompt_revision="v1",
                attempt_id=doc["job"]["id"],
                batches=[],
                model=self.model,
            )
            metadata["preflight"] = preflight
            self.store.save(doc)
        if self.service is None:
            preflight.update(stop_reason="configuration_required", issues=["gemini_not_configured"])
            with self.store.lock:
                self._state(
                    doc,
                    "ready" if metadata["accepted"] else "failed",
                    "gemini_not_configured",
                )
            return
        cap = min(doc["page_count"], self.max_pages)
        for index, start in enumerate(range(1, cap + 1, self.batch_size)):
            if self.stopping.is_set():
                preflight["stop_reason"] = "interrupted"
                with self.store.lock:
                    self._state(doc, "interrupted", "server_interrupted")
                return
            if index >= self.request_limit:
                preflight["stop_reason"] = "budget_limit"
                break
            pages = list(range(start, min(start + self.batch_size, cap + 1)))
            # Write intent before a possible provider call. After crash these
            # pages may have unknown usage and must not be sent automatically.
            preflight["pending_pages"] = pages
            with self.store.lock:
                self._state(doc, "processing")
            prediction, stop, error, telemetry = analyze_batch(
                self.service,
                self.store.file(identifier),
                pages,
                credential_ref=self.credential_ref,
                model=self.model,
                dpi=self.dpi,
                reservation_money=self.reservation_money,
            )
            preflight["pending_pages"] = []
            preflight["batches"].append(dict(pages=pages, error=error, **telemetry))
            if stop:
                preflight["issues"].append(error)
                if error not in ("structured_output_invalid", "schema_mismatch"):
                    preflight["stop_reason"] = stop
                    break
                continue  # Inspect next batch under the same page/request caps.
            merge_suggestions(metadata["suggestions"], prediction, doc["content_id"])
            preflight["analyzed_pages"].extend(pages)
            doc["job"]["progress"]["preflight"]["completed_pages"] = len(
                preflight["analyzed_pages"]
            )
            with self.store.lock:
                self._state(doc, "processing")
            if core_metadata_resolved(metadata["suggestions"], doc["content_id"]):
                preflight["stop_reason"] = "sufficient_evidence"
                break
        if preflight["stop_reason"] is None:
            preflight["stop_reason"] = (
                "pages_exhausted" if cap == doc["page_count"] else "page_limit"
            )
        if not core_metadata_resolved(metadata["suggestions"], doc["content_id"]):
            preflight["issues"].append("manual_metadata_needed")
        with self.store.lock:
            if self.store.auto_accept(doc):
                doc["job"]["accepted_metadata_revision"] = doc["metadata_revision"]
            state = "ready" if metadata["accepted"] else "needs_metadata"
            if not metadata["accepted"] and preflight["stop_reason"] in (
                "provider_error",
                "budget_limit",
            ):
                state = "failed"
            self._state(
                doc,
                state,
                preflight["issues"][0]
                if preflight["stop_reason"] in ("provider_error", "budget_limit")
                and preflight["issues"]
                else None,
            )
