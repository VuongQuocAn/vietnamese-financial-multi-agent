"""Three offline engineering checks with raster PDFs; not financial accuracy tests."""

import json
from copy import deepcopy
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
from vietnamese_financial_multi_agent.accounting.automated_extraction import (
    EXTRACTION_REF,
    ExtractedPage,
)
from vietnamese_financial_multi_agent.api.document_store import DocumentStore
from vietnamese_financial_multi_agent.api.extraction_sessions import read_result
from vietnamese_financial_multi_agent.api.main import create_app
from vietnamese_financial_multi_agent.api.metadata_service import (
    POOL_CREDENTIAL,
    FreeTierKeyPool,
    MetadataLLMService,
)
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.llm_contracts import GatewayError
from vietnamese_financial_multi_agent.core.llm_quota_budget import QuotaLimits
from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry
from vietnamese_financial_multi_agent.document_processing.financial_discovery import (
    DISCOVERY_REF,
    PagePrediction,
)
from vietnamese_financial_multi_agent.document_processing.metadata_preflight import (
    METADATA_REF,
    metadata_schema_registry,
)

from .test_automated_extraction import sample
from .test_web_documents import prediction, settled, upload


def setup_service(tmp_path, *, fail_page=True):
    schemas = LocalSchemaRegistry(
        [
            (METADATA_REF, metadata_schema_registry().schema_for(METADATA_REF)),
            (DISCOVERY_REF, PagePrediction.model_json_schema()),
            (EXTRACTION_REF, ExtractedPage.model_json_schema()),
        ]
    )
    calls = []
    control = dict(fail=fail_page)
    _, _, payload = sample.__wrapped__()

    def adapter(request):
        kind = request.output_spec.schema_ref.schema_id
        calls.append(kind)
        if kind == METADATA_REF.schema_id:
            body = prediction()
        elif kind == DISCOVERY_REF.schema_id:
            body = dict(
                statement_type="B02",
                classification="statement",
                description="Synthetic",
                has_financial_table=True,
                has_notes_text=False,
                uncertainty=None,
            )
        else:
            body = deepcopy(payload)
            if control["fail"] and calls.count(EXTRACTION_REF.schema_id) == 2:
                body = {}
        return FakeLLMTransport(json_text=json.dumps(body))(request)

    def limited(request):
        response = FakeLLMTransport()(request)
        response.status, response.output, response.finish_reason = "error", None, "error"
        response.error = GatewayError(
            category="rate_limit", code="rate_limit", origin="provider", retryability="unknown"
        )
        return response

    pool = FreeTierKeyPool(
        [limited, adapter],
        DocumentStore(tmp_path),
        schemas=schemas,
        limits=QuotaLimits(rpm=100, tpm=2_000_000, rpd=100),
    )
    return MetadataLLMService(pool, schemas), calls, control


def app_for(tmp_path, service, **options):
    return create_app(
        storage_root=tmp_path,
        service=service,
        service_options=dict(credential_ref=POOL_CREDENTIAL),
        job_options=options,
    )


def process(client, identifier, revision, key=None, operation="extract"):
    return client.post(
        f"/api/documents/{identifier}/process",
        headers={"Idempotency-Key": key or str(uuid4())},
        json=dict(operation=operation, metadata_revision=revision),
    )


def test_api_scan_partial_retry_persistence_and_rotation(tmp_path):
    service, calls, control = setup_service(tmp_path)
    with TestClient(app_for(tmp_path, service)) as client:
        identifier = upload(client).json()["id"]
        doc = settled(client, identifier)
        assert doc["state"] == "ready" and service.pool.keys[0].cooldown_until > 0
        revision = doc["metadata_revision"]
        first = process(client, identifier, revision).json()["job"]["id"]
        doc = settled(client, identifier)
        assert doc["state"] == "partial"
        assert doc["job"]["progress"]["extraction"] == dict(
            completed_pages=2, selected_pages=2, valid_pages=1, invalid_pages=1
        )
        route = f"/api/documents/{identifier}"
        evidence = client.get(f"{route}/evidence?attempt_id={first}").json()
        assert evidence["total"] == 2
        item = evidence["items"][0]
        assert item["value"]["raw_value"] == "1.234"
        assert item["value"]["normalized_value"] == "1234"
        assert item["context"]["period"] == "2025"
        assert {i["context"]["period"] for i in evidence["items"]} == {"2025", "2024"}
        assert not item["financial_fact_verified"] and len(item["sources"]) >= 6
        assert all(s["pdf_page"] == 1 and s["bbox"] is None for s in item["sources"])
        assert client.get(f"{route}/evidence?attempt_id={first}&statement=B09").status_code == 422
        before = len(calls)
        control["fail"] = False
        second = process(client, identifier, revision).json()["job"]["id"]
        assert settled(client, identifier)["state"] == "completed"
        assert len(calls) == before + 1  # Both discovery pages and successful extraction replay.
        assert client.get(f"{route}/evidence?attempt_id={second}").json()["total"] == 4
        assert client.get(f"{route}/evidence?attempt_id={first}").json() == evidence
    with TestClient(app_for(tmp_path, service)) as client:
        assert client.get(f"{route}/evidence?attempt_id={first}").json() == evidence
        assert len(client.get(f"{route}/inventory?attempt_id={second}").json()["pages"]) == 2
        assert client.get(f"{route}/evidence?attempt_id={uuid4()}").status_code == 404
    assert read_result(DocumentStore(tmp_path), identifier, second)["records"]


def test_job_caps_and_operation_idempotency(tmp_path):
    service, calls, _ = setup_service(tmp_path)
    with TestClient(app_for(tmp_path, service, request_limit=1)) as client:
        identifier = upload(client).json()["id"]
        doc = settled(client, identifier)
        entered, release = Event(), Event()
        generate = service.generate

        def blocked(request, **kwargs):
            if request.output_spec.schema_ref == DISCOVERY_REF:
                entered.set()
                assert release.wait(5)
            return generate(request, **kwargs)

        service.generate = blocked
        key = str(uuid4())
        first = process(client, identifier, doc["metadata_revision"], key)
        try:
            assert entered.wait(5)
            assert process(client, identifier, doc["metadata_revision"]).status_code == 409
            assert process(client, identifier, doc["metadata_revision"], key).status_code == 202
        finally:
            release.set()
        final = settled(client, identifier)
        assert final["state"] == "failed" and final["job"]["error"]["code"] == "request_limit"
        assert final["job"]["progress"]["discovery"]["completed_pages"] == 1
        again = process(client, identifier, doc["metadata_revision"], key)
        assert again.status_code == 200 and again.json()["job"]["id"] == first.json()["job"]["id"]
        assert (
            process(client, identifier, doc["metadata_revision"], key, "preflight").status_code
            == 409
        )
        assert process(client, identifier, 999).status_code == 409
        assert len(calls) == 2  # One metadata request and one discovery request.
        values = doc["metadata"]["values"]
        response = client.patch(
            f"/api/documents/{identifier}/metadata",
            json=dict(metadata_revision=doc["metadata_revision"], confirmed=False, values=values),
        )
        assert response.status_code == 200
        assert process(client, identifier, response.json()["metadata_revision"]).status_code == 409


def test_restart_interrupts_without_requests_and_keeps_snapshot(tmp_path):
    service, calls, _ = setup_service(tmp_path, fail_page=False)
    with TestClient(app_for(tmp_path, service)) as client:
        identifier = upload(client).json()["id"]
        doc = settled(client, identifier)
        attempt = process(client, identifier, doc["metadata_revision"]).json()["job"]["id"]
        assert settled(client, identifier)["state"] == "completed"
    store = DocumentStore(tmp_path)
    snapshot = read_result(store, identifier, attempt)
    doc = store.load(identifier)
    doc["job"]["state"] = doc["state"] = "processing"
    store.save(doc)
    before = len(calls)
    with TestClient(app_for(tmp_path, service)) as client:
        status = client.get(f"/api/documents/{identifier}/status").json()
        assert status["job"]["state"] == "interrupted"
        assert status["job"]["error"]["code"] == "application_interrupted"
        assert read_result(store, identifier, attempt) == snapshot
    assert len(calls) == before
