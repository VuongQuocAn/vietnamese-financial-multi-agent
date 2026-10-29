"""Thin durable sessions around the existing M1–M2 PDF runtime."""

import json
from collections import Counter
from datetime import datetime, timedelta

from ..accounting.financial_runtime import process_financial_pdf
from ..accounting.quality import assess_evidence_for_task, evidence_from_automated_records
from ..document_processing.financial_discovery import discover_financial_pages
from .document_store import atomic_json, fail, now, safe_path

CONFIG = "w04-v1:discovery100:extraction200"


class SessionStopped(Exception):
    pass


class SessionService:
    """Keep the existing key-pool service and cap calls across both phases."""

    def __init__(self, jobs):
        self.jobs, self.calls = jobs, 0

    def generate(self, *args, **kwargs):
        if self.jobs.stopping.is_set():
            raise SessionStopped("application_interrupted")
        if self.calls >= self.jobs.request_limit:
            raise SessionStopped("request_limit")
        if self.jobs.service is None:
            raise SessionStopped("service_not_configured")
        self.calls += 1
        return self.jobs.service.generate(*args, **kwargs)


def snapshot_path(store, doc, attempt_id):
    if attempt_id not in doc["_attempts"]:
        fail(404, "attempt_not_found", "Không tìm thấy phiên xử lý của tài liệu.")
    return safe_path(store.root, "documents", doc["id"], "attempts", attempt_id, "result.json")


def read_result(store, identifier, attempt_id):
    with store.lock:
        doc = store.load(identifier)
        path = snapshot_path(store, doc, attempt_id)
        if not path.is_file():
            fail(409, "snapshot_unavailable", "Phiên chưa có kết quả được lưu.")
        return json.loads(path.read_text(encoding="utf-8"))


def inventory_response(result):
    fields = (
        "statement_type",
        "classification",
        "description",
        "has_financial_table",
        "has_notes_text",
        "uncertainty",
        "selected",
        "reason",
        "method",
    )
    return dict(
        document_id=result["document_id"],
        attempt_id=result["attempt_id"],
        metadata_revision=result["metadata_revision"],
        pages=[
            dict(
                pdf_page=p["page"],
                **{k: p[k] for k in fields},
                extraction_status=p["extraction_status"],
            )
            for p in result["inventory"]
        ],
    )


def evidence_response(result, statement, offset, limit):
    items = result["items"]
    if statement:
        items = [i for i in items if i["context"]["statement_type"] == statement]
    return dict(
        document_id=result["document_id"],
        attempt_id=result["attempt_id"],
        metadata_revision=result["metadata_revision"],
        snapshot_revision=result["snapshot_revision"],
        items=items[offset : offset + limit],
        invalid_pages=result["invalid_pages"],
        annotations=dict(arithmetic=[], relationships=[]),
        offset=offset,
        limit=limit,
        total=len(items),
    )


def project_items(quality, records, content_id):
    by_page = {r["source"]["page"]["page"]: r for r in records}
    items = []
    for assessment in quality.items:
        e = assessment.evidence
        page = e.extraction.provenance[0].anchor.page.page
        index = int(e.evidence_id.rsplit("/", 1)[1])
        link = by_page[page]["extraction"]["links"][index]
        binding = {k: link[k] for k in ("table", "row", "column")}
        items.append(
            dict(
                evidence_id=e.evidence_id,
                source_item_code=e.source_item_code,
                canonical_item_id=e.canonical_item_id,
                raw_label=link["raw_label"],
                raw_header=e.raw_header,
                value=e.extraction.value.model_dump(mode="json"),
                context=e.extraction.context.model_dump(mode="json"),
                extraction_issues=e.extraction_issues,
                quality=dict(
                    decision=assessment.decision,
                    issues=[i.model_dump(mode="json") for i in assessment.issues],
                    caveats=assessment.caveats,
                ),
                sources=[
                    dict(
                        content_id=content_id,
                        pdf_page=ref.anchor.page.page,
                        source_pointer=ref.source_pointer,
                        provenance_level=ref.provenance_level,
                        bbox=None,
                    )
                    for ref in e.extraction.provenance
                ],
                binding=binding if all(v is not None for v in binding.values()) else None,
                financial_fact_verified=False,
            )
        )
    items.sort(
        key=lambda i: (
            i["sources"][0]["pdf_page"],
            *[(i["binding"] or {}).get(k, -1) for k in ("table", "row", "column")],
            i["evidence_id"],
        )
    )
    return items


def run_extraction(jobs, identifier):
    store = jobs.store
    with store.lock:
        doc = store.load(identifier)
        job = doc["job"]
        jobs._state(doc, "processing")
    result = dict(
        document_id=identifier,
        attempt_id=job["id"],
        metadata_revision=job["metadata_revision"],
        metadata=doc["metadata"]["values"],
        config=CONFIG,
        model=jobs.model,
        created_at=now(),
        snapshot_revision=0,
        inventory=[],
        records=[],
        items=[],
        invalid_pages=[],
        quality=None,
    )
    path = snapshot_path(store, doc, job["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    service = SessionService(jobs)
    identity = doc["runtime_identity"]
    options = dict(
        symbol=identity["symbol"],
        year=identity["year"],
        service=service,
        credential_ref=jobs.credential_ref,
        model=jobs.model,
    )
    cache, discovery_cache = {}, {}
    # Explicit retry may replay only same-revision/config/model, recently persisted successes.
    for attempt_id, attempt in reversed(list(doc["_attempts"].items())):
        if attempt_id == job["id"] or attempt["revision"] != job["metadata_revision"]:
            continue
        old_path = snapshot_path(store, doc, attempt_id)
        if not old_path.is_file():
            continue
        old = json.loads(old_path.read_text(encoding="utf-8"))
        if (
            old["config"] != CONFIG
            or old["model"] != jobs.model
            or datetime.fromisoformat(old["created_at"])
            < datetime.fromisoformat(now()) - timedelta(days=1)
        ):
            continue
        for record in old["records"]:
            if "invalid_extraction_response" not in record["extraction"]["issues"]:
                cache.setdefault(record["source"]["page"]["page"], record)
        for page in old["inventory"]:
            if page["classification"] != "uncertain" and not page["uncertainty"]:
                discovery_cache.setdefault(page["page"], page)

    def persist():
        valid = [
            r
            for r in result["records"]
            if "invalid_extraction_response" not in r["extraction"]["issues"]
        ]
        quality = assess_evidence_for_task(evidence_from_automated_records(valid))
        result["quality"] = quality.model_dump(mode="json")
        result["items"] = project_items(quality, valid, doc["content_id"])
        result["invalid_pages"] = [
            dict(pdf_page=e["pdf_page"], issues=[e["code"]]) for e in job["page_errors"]
        ]
        result["snapshot_revision"] += 1
        counts = Counter(p["statement_type"] for p in result["inventory"])
        job["summary"] = dict(
            statement_pages={k: counts[k] for k in ("B01", "B02", "B03", "B09")},
            evidence_items=len(result["items"]),
        )
        with store.lock:
            atomic_json(path, result)
            doc["latest_result"] = dict(
                attempt_id=job["id"], metadata_revision=job["metadata_revision"]
            )
            jobs._state(doc, job["state"], job["error"])

    def discovery_page(record):
        # W-04 keeps notes in inventory even when their classification has caveats.
        if record["statement_type"] == "B09":
            record.update(selected=False, reason="notes_inventory")
        record["extraction_status"] = "pending" if record["selected"] else "not_selected"
        result["inventory"].append(record)
        job["progress"]["discovery"]["completed_pages"] = len(result["inventory"])
        persist()
        if jobs.stopping.is_set():
            raise SessionStopped("application_interrupted")

    stop = None
    try:
        persist()
        discover_financial_pages(
            store.file(identifier),
            **options,
            cached_predictions=discovery_cache,
            on_page=discovery_page,
        )
        selected = [p for p in result["inventory"] if p["selected"]]
        job["phase"] = "extraction"
        progress = dict(
            completed_pages=0, selected_pages=len(selected), valid_pages=0, invalid_pages=0
        )
        job["progress"]["extraction"] = progress
        persist()
        for page in selected:
            number = page["page"]
            if jobs.stopping.is_set():
                raise SessionStopped("application_interrupted")
            try:
                part = process_financial_pdf(
                    store.file(identifier), **options, pages=[number], cached_records=cache
                )
                result["records"].extend(part["records"])
                invalid = any(
                    "invalid_extraction_response" in r["extraction"]["issues"]
                    for r in part["records"]
                )
                page["extraction_status"] = "invalid" if invalid else "valid"
                if invalid:
                    job["page_errors"].append(
                        dict(
                            pdf_page=number,
                            phase="extraction",
                            code="invalid_extraction_response",
                            retryable=True,
                        )
                    )
            except SessionStopped:
                raise
            except Exception:
                page["extraction_status"] = "error"
                job["page_errors"].append(
                    dict(
                        pdf_page=number,
                        phase="extraction",
                        code="page_extraction_failed",
                        retryable=True,
                    )
                )
            progress["completed_pages"] += 1
            progress[
                "valid_pages" if page["extraction_status"] == "valid" else "invalid_pages"
            ] += 1
            persist()
    except SessionStopped as error:
        stop = str(error)
    except Exception:
        stop = "extraction_session_failed"
    usable = any(
        i["value"]["normalized_value"] is not None
        and i["quality"]["decision"] in ("usable", "usable_with_caveat")
        for i in result["items"]
    )
    incomplete = (
        stop
        or job["page_errors"]
        or any(p["uncertainty"] or p["classification"] == "uncertain" for p in result["inventory"])
        or not job["progress"].get("extraction")
        or not job["progress"]["extraction"]["selected_pages"]
    )
    state = "partial" if usable and incomplete else "completed" if usable else "failed"
    if (
        not usable
        and not stop
        and any(p["statement_type"] == "B09" for p in result["inventory"])
        and not any(p["selected"] for p in result["inventory"])
    ):
        state = "partial"
    if stop == "application_interrupted":
        state = "interrupted"
    job["phase"] = "finalizing" if not stop else job["phase"]
    job["state"] = state
    job["error"] = (
        dict(
            code=stop or "no_usable_evidence",
            message="Chưa hoàn tất phân tích. Kết quả đã lưu được giữ lại.",
            retryable=True,
        )
        if stop or state == "failed"
        else None
    )
    persist()
