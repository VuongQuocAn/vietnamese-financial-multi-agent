"""W-03 engineering tests; raster-only synthetic PDF, no private data or network."""

import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from google.genai import types
from PIL import Image, ImageDraw
from vietnamese_financial_multi_agent.api.document_store import DocumentError, DocumentStore
from vietnamese_financial_multi_agent.api.main import create_app
from vietnamese_financial_multi_agent.api.metadata_service import compose_metadata_service
from vietnamese_financial_multi_agent.core.fake_llm_transport import FakeLLMTransport
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService
from vietnamese_financial_multi_agent.core.llm_contracts import Usage
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
)
from vietnamese_financial_multi_agent.document_processing.metadata_preflight import (
    DEFAULT_METADATA_MODEL,
    FIELDS,
    METADATA_REF,
    analyze_batch,
    empty_suggestions,
    metadata_schema_registry,
)


def scan_pdf(count=2):
    pages = []
    for number in range(count):
        image = Image.new("RGB", (480, 640), "white")
        ImageDraw.Draw(image).text(
            (30, 40), f"SYNTHETIC TEST ONLY - Page {number + 1}", fill="black"
        )
        pages.append(image)
    buffer = io.BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:])
    for page in pages:
        page.close()
    return buffer.getvalue()


def prediction(page=1, *, complete=True, year=2025):
    result = empty_suggestions()
    values = dict(
        company_name="Synthetic Test Company",
        reporting_year=year,
        stock_ticker="SYN",
        reporting_scope="separate",
        reporting_period=dict(value=f"Năm {year}", type="fiscal_year"),
    )
    for key in FIELDS if complete else ("company_name", "reporting_year"):
        result[key] = dict(
            status="resolved",
            candidates=[dict(value=values[key], raw_text=str(values[key]), pdf_page=page)],
            issues=[],
        )
    return result


def service_for(handler=None, *, tpm=1_000_000, transport_override=None):
    calls = []

    def transport(request):
        calls.append(request)
        if transport_override is not None:
            return transport_override(request)
        if handler:
            payload = handler(request, len(calls))
        else:
            payload = prediction()
        response = FakeLLMTransport(json_text=json.dumps(payload))(request)
        response.usage = Usage(
            status="available",
            source="provider_reported",
            input_tokens=40,
            output_tokens=40,
            total_tokens=80,
        )
        return response

    schemas = metadata_schema_registry()
    gateway = SharedLLMGateway({"gemini": transport}, schema_registry=schemas)
    policy = ProjectPolicy.model_validate_json(
        json.dumps(
            dict(
                account_ref="test-account",
                project_ref="test-project",
                credential_refs=["test-credential"],
                provider="gemini",
                model=DEFAULT_METADATA_MODEL,
                tier="free",
                mapping_confirmed=True,
                verification_source="synthetic-test",
                quota_limits=dict(rpm=100, tpm=tpm, rpd=100),
            )
        )
    )
    guard = QuotaBudgetGuard(
        ProjectRegistry([policy]),
        [
            GatewayBinding(
                policy.account_ref,
                policy.project_ref,
                "test-credential",
                "gemini",
                policy.model,
                gateway,
            )
        ],
    )
    guard.initialize(confirmed_fresh_scope=True)
    service = CachedLLMService(
        guard,
        tenant_ref="test",
        project_ref=policy.project_ref,
        credential_refs=frozenset({"test-credential"}),
        configuration_revision="W-03-test",
        scope_confirmed=True,
        schema_registry=schemas,
    )
    return service, calls


def make_app(tmp_path, handler=None, **kwargs):
    service, calls = service_for(handler)
    return create_app(
        storage_root=tmp_path,
        service=service,
        service_options=dict(credential_ref="test-credential"),
        **kwargs,
    ), calls


def upload(client, content=None, filename="scan.pdf"):
    return client.post(
        "/api/documents", files={"file": (filename, content or scan_pdf(), "application/pdf")}
    )


def settled(client, identifier):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/documents/{identifier}")
        assert response.status_code == 200
        doc = response.json()
        if doc["state"] not in ("queued", "processing"):
            return doc
        time.sleep(0.02)
    pytest.fail("preflight did not settle")


def patch_body(doc, *, confirmed=True):
    return dict(
        metadata_revision=doc["metadata_revision"],
        confirmed=confirmed,
        values=dict(
            company_name="User Edited Company",
            reporting_year=2024,
            stock_ticker=None,
            reporting_period=None,
            reporting_scope=None,
        ),
    )


@pytest.mark.integration
def test_scan_upload_vision_review_confirm_ready(tmp_path):
    app, calls = make_app(tmp_path)
    content = scan_pdf()
    with pdfium.PdfDocument(content) as pdf:
        assert pdf[0].get_textpage().get_text_range() == ""
    with TestClient(app) as client:
        response = upload(client, content, filename="../../outside.pdf")
        assert response.status_code == 201
        doc = settled(client, response.json()["id"])
        assert doc["state"] == "needs_metadata"
        assert UUID(doc["id"]).version == 4
        assert doc["content_id"] == "sha256:" + hashlib.sha256(content).hexdigest()
        assert doc["filename"] == "outside.pdf"
        assert doc["metadata"]["values"]["company_name"] is None
        suggestion = doc["metadata"]["suggestions"]["company_name"]
        assert suggestion["candidates"][0]["sources"] == [
            dict(pdf_page=1, content_id=doc["content_id"])
        ]
        assert doc["metadata"]["preflight"]["analyzed_pages"] == [1, 2]
        assert doc["metadata"]["preflight"]["stop_reason"] == "sufficient_evidence"
        assert len(calls) == 1 and sum(len(m.images) for m in calls[0].messages) == 2
        assert "outside.pdf" not in calls[0].messages[0].content
        response = client.patch(f"/api/documents/{doc['id']}/metadata", json=patch_body(doc))
        assert response.status_code == 200
        updated = response.json()
        assert updated["state"] == "ready" and updated["metadata_revision"] == 1
        assert updated["metadata"]["suggestions"] == doc["metadata"]["suggestions"]
        assert updated["metadata"]["values"]["stock_ticker"] is None
        assert updated["runtime_identity"] == dict(symbol=f"document:{doc['id']}", year="2024")
        assert all(edit["origin"] == "user" for edit in updated["metadata"]["edits"])
        assert (
            client.patch(f"/api/documents/{doc['id']}/metadata", json=patch_body(doc)).status_code
            == 409
        )
        listing = client.get("/api/documents").json()
        assert listing["items"][0]["company_name"] == "User Edited Company"
        original = client.get(f"/api/documents/{doc['id']}/file")
        assert original.content == content and original.headers["cache-control"] == "no-store"
        assert (
            client.get(f"/api/documents/{doc['id']}/file", headers={"Range": "bytes=0-9"}).content
            == content[:10]
        )
        assert (
            client.get(
                f"/api/documents/{doc['id']}/file", headers={"Range": "bytes=999999999-"}
            ).status_code
            == 416
        )
        assert "_original_pdf" not in json.dumps(updated) and str(tmp_path) not in json.dumps(
            updated
        )
        assert (tmp_path / "documents" / doc["id"] / "original.pdf").read_bytes() == content
        second = upload(client, content).json()
        assert second["id"] != doc["id"] and second["content_id"] == doc["content_id"]


@pytest.mark.parametrize(
    ("content", "mime", "status"),
    [
        (b"hello", "application/pdf", 415),
        (b"%PDF-invalid", "application/pdf", 422),
        (b"hello", "text/plain", 415),
    ],
)
def test_reject_non_pdf_and_corruption(tmp_path, content, mime, status):
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        assert (
            client.post("/api/documents", files={"file": ("scan.pdf", content, mime)}).status_code
            == status
        )
        assert client.get("/api/documents").json()["total"] == 0


def test_size_page_multipart_and_origin_limits(tmp_path):
    app, _ = make_app(tmp_path, max_upload_bytes=1000)
    with TestClient(app) as client:
        assert upload(client).status_code == 413
        assert upload(client, b"%PDF-" + b"X" * 100_000).status_code == 413
        assert (
            client.post(
                "/api/documents",
                files=[("file", ("a.pdf", scan_pdf())), ("file", ("b.pdf", scan_pdf()))],
            ).status_code
            == 400
        )
        assert (
            client.post("/api/documents", files={"wrong": ("a.pdf", scan_pdf())}).status_code == 422
        )
        assert (
            client.post(
                "/api/documents", headers={"Origin": "https://untrusted.invalid"}
            ).status_code
            == 403
        )
    app, _ = make_app(tmp_path / "page-limit", max_pages=1)
    with TestClient(app) as client:
        assert upload(client).status_code == 413


@pytest.mark.parametrize(
    "bad",
    [
        dict(reporting_year=0),
        dict(reporting_year=10000),
        dict(reporting_year="2025"),
        dict(company_name="  "),
        dict(company_name=None),
        dict(unknown="x"),
    ],
)
def test_metadata_validation(tmp_path, bad):
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        body = patch_body(doc)
        body["values"].update(bad)
        assert client.patch(f"/api/documents/{doc['id']}/metadata", json=body).status_code == 422


def test_expand_pages_keep_conflicting_candidates(tmp_path):
    def handler(request, index):
        return prediction(
            page=1 if index == 1 else 5, complete=False, year=2025 if index == 1 else 2024
        )

    app, calls = make_app(tmp_path, handler)
    with TestClient(app) as client:
        doc = settled(client, upload(client, scan_pdf(6)).json()["id"])
        field = doc["metadata"]["suggestions"]["reporting_year"]
        assert field["status"] == "uncertain"
        assert [c["value"] for c in field["candidates"]] == [2025, 2024]
        assert doc["metadata"]["preflight"]["analyzed_pages"] == list(range(1, 7))
        assert doc["metadata"]["preflight"]["stop_reason"] == "pages_exhausted"
        assert doc["metadata"]["suggestions"]["stock_ticker"]["status"] == "unresolved"
        assert len(calls) == 2


@pytest.mark.parametrize(
    "kind", ["bad_page", "bad_year", "bad_status", "bad_schema", "timeout", "provider"]
)
def test_invalid_provider_results_never_publish_suggestions(tmp_path, kind):
    def handler(request, index):
        if kind == "timeout":
            raise TimeoutError("sensitive provider message")
        if kind == "provider":
            raise RuntimeError("secret provider response")
        output = prediction()
        if kind == "bad_page":
            output["company_name"]["candidates"][0]["pdf_page"] = 9
        if kind == "bad_year":
            output["reporting_year"]["candidates"][0]["value"] = 0
        if kind == "bad_status":
            output["company_name"]["status"] = "unresolved"
        if kind == "bad_schema":
            output.pop("reporting_scope")
        return output

    app, calls = make_app(tmp_path, handler)
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        assert doc["state"] == "needs_metadata"
        assert doc["metadata"]["preflight"]["stop_reason"] == "provider_error"
        assert doc["metadata"]["suggestions"] == empty_suggestions()
        assert "secret" not in json.dumps(doc) and "sensitive" not in json.dumps(doc)
        assert len(calls) == 1


def test_quota_rejects_before_transport(tmp_path):
    service, calls = service_for(tpm=10_000)
    app = create_app(
        storage_root=tmp_path,
        service=service,
        service_options=dict(credential_ref="test-credential"),
    )
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        assert doc["metadata"]["preflight"]["stop_reason"] == "budget_limit"
        assert doc["metadata"]["preflight"]["analyzed_pages"] == []
        assert calls == []


def test_semantically_invalid_response_not_replayed_on_retry(tmp_path):
    def handler(request, index):
        return prediction(page=9 if index == 1 else 1)

    app, calls = make_app(tmp_path, handler)
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        assert doc["metadata"]["preflight"]["stop_reason"] == "provider_error"
        client.post(
            f"/api/documents/{doc['id']}/process",
            json=dict(operation="preflight", metadata_revision=0),
            headers={"Idempotency-Key": str(uuid4())},
        )
        retried = settled(client, doc["id"])
        assert retried["metadata"]["preflight"]["stop_reason"] == "sufficient_evidence"
        assert len(calls) == 2


def test_job_bound_and_active_idempotency(tmp_path):
    started, release = Event(), Event()

    def handler(request, index):
        started.set()
        assert release.wait(5)
        return prediction()

    app, calls = make_app(tmp_path, handler, job_options=dict(capacity=1))
    with TestClient(app) as client:
        try:
            first = upload(client).json()
            assert started.wait(3)
            path = f"/api/documents/{first['id']}"
            assert client.patch(path + "/metadata", json=patch_body(first)).status_code == 409
            assert (
                client.post(
                    path + "/process",
                    json=dict(operation="preflight", metadata_revision=0),
                    headers={"Idempotency-Key": str(uuid4())},
                ).status_code
                == 409
            )
            second = upload(client).json()
            assert second["state"] == "uploaded" and second["job"] is None
            body = dict(operation="preflight", metadata_revision=0)
            assert (
                client.post(
                    f"/api/documents/{second['id']}/process",
                    json=body,
                    headers={"Idempotency-Key": str(uuid4())},
                ).status_code
                == 429
            )
        finally:
            release.set()
        settled(client, first["id"])
        deadline = time.monotonic() + 3
        while app.state.jobs.active_count and time.monotonic() < deadline:
            time.sleep(0.02)
        key = str(uuid4())
        second_path = f"/api/documents/{second['id']}/process"
        response = client.post(second_path, json=body, headers={"Idempotency-Key": key})
        assert response.status_code == 202
        job_id = response.json()["job"]["id"]
        terminal = settled(client, second["id"])
        replay = client.post(second_path, json=body, headers={"Idempotency-Key": key})
        assert replay.status_code == 200 and replay.json()["job"]["id"] == job_id
        assert (
            client.post(
                second_path,
                json=dict(operation="preflight", metadata_revision=1),
                headers={"Idempotency-Key": key},
            ).status_code
            == 409
        )
        assert terminal["state"] == "needs_metadata"
        assert len(calls) <= 2  # Same bytes can safely hit scoped response cache.


def test_simultaneous_submissions_only_one_attempt(tmp_path):
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        key = str(uuid4())
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: app.state.jobs.submit(doc["id"], 0, key), range(4)))
        assert len({r[0]["id"] for r in responses}) == 1


@pytest.mark.parametrize("state", ["queued", "processing"])
def test_restart_interrupts_without_auto_calls_and_preserves_confirmed(tmp_path, state):
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        client.patch(f"/api/documents/{doc['id']}/metadata", json=patch_body(doc))
    store = DocumentStore(tmp_path)
    snapshot = store.load(doc["id"])
    snapshot["job"]["state"] = state
    snapshot["state"] = state
    store.save(snapshot)
    app, calls = make_app(tmp_path)
    with TestClient(app) as client:
        restarted = client.get(f"/api/documents/{doc['id']}").json()
        assert restarted["state"] == "interrupted" and restarted["job"]["state"] == "interrupted"
        assert restarted["metadata"]["confirmed"] and restarted["metadata_revision"] == 1
        assert restarted["metadata"]["suggestions"] == doc["metadata"]["suggestions"]
        assert calls == []


def test_manual_retry_preserves_user_values_and_ai_history(tmp_path):
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        confirmed = client.patch(
            f"/api/documents/{doc['id']}/metadata", json=patch_body(doc)
        ).json()
        response = client.post(
            f"/api/documents/{doc['id']}/process",
            json=dict(operation="preflight", metadata_revision=1),
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 202
        retried = settled(client, doc["id"])
        assert retried["state"] == "ready"
        assert retried["metadata"]["values"] == confirmed["metadata"]["values"]
        assert app.state.store.load(doc["id"])["_preflight_history"]


def test_storage_traversal_and_symlink(tmp_path):
    store = DocumentStore(tmp_path / "store")
    with pytest.raises(DocumentError):
        store.load("../../outside")
    target = tmp_path / "outside"
    target.mkdir()
    identifier = str(uuid4())
    try:
        (store.root / "documents" / identifier).symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    with pytest.raises(DocumentError) as error:
        store.load(identifier)
    assert error.value.code == "unsafe_storage"


def test_process_excludes_financial_extraction_and_invalid_ids(tmp_path):
    app, _ = make_app(tmp_path)
    with TestClient(app) as client:
        doc = upload(client).json()
        assert (
            client.post(
                f"/api/documents/{doc['id']}/process",
                json=dict(operation="extract", metadata_revision=0),
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 422
        )
        assert client.get("/api/documents/invalid").status_code == 404
        assert client.get("/api/documents?limit=101").status_code == 422


def test_live_composition_binding_and_restart_scope(tmp_path, monkeypatch):
    key = "AIza" + "x" * 35  # Synthetic credential, no network.
    policy = dict(
        account_ref="test-account",
        project_ref="test-project",
        credential_refs=["test-key"],
        provider="gemini",
        model=DEFAULT_METADATA_MODEL,
        tier="free",
        mapping_confirmed=True,
        verification_source="synthetic",
        quota_limits=dict(rpm=15, tpm=250000, rpd=20),
        budget=dict(amount="0", currency="USD"),
    )
    settings = dict(
        project_policy=policy,
        accounting_scope="synthetic-scope",
        fresh_exclusive_scope_confirmed=True,
        data_export_approved=True,
        pricing_confirmed=True,
        key_index=0,
        credential_sha256=hashlib.sha256(key.encode()).hexdigest(),
        request_spending_upper_bound="0",
    )
    config = tmp_path / "policy.json"
    config.write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setenv("WEB_GEMINI_CONFIG", str(config))
    monkeypatch.setenv("GEMINI_API_KEY", key)
    monkeypatch.delenv("GEMINI_API_KEY_FILE", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    clients = []

    def client(**kwargs):
        clients.append(kwargs)
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.api.metadata_service.genai.Client", client
    )
    store = DocumentStore(tmp_path / "store")
    assert compose_metadata_service(store)[0] is not None
    assert compose_metadata_service(store)[0] is None  # Same consumed scope cannot reset guard.
    assert "AIza" not in next((store.root / "accounting-scopes").glob("*.json")).read_text()
    changed = deepcopy(settings)
    changed["accounting_scope"] = "another-scope"
    changed["credential_sha256"] = "0" * 64
    config.write_text(json.dumps(changed), encoding="utf-8")
    assert compose_metadata_service(store)[0] is None
    assert len(clients) == 2


def test_unconfigured_gemini_manual_confirmation_still_works(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_GEMINI_CONFIG", raising=False)
    with TestClient(create_app(storage_root=tmp_path)) as client:
        doc = settled(client, upload(client).json()["id"])
        assert doc["state"] == "needs_metadata"
        assert doc["metadata"]["suggestions"] == empty_suggestions()
        assert doc["metadata"]["preflight"]["stop_reason"] == "configuration_required"
        assert (
            client.patch(f"/api/documents/{doc['id']}/metadata", json=patch_body(doc)).json()[
                "state"
            ]
            == "ready"
        )


@pytest.mark.parametrize(
    ("options", "reason", "expected_pages"),
    [
        (dict(batch_size=1, request_limit=1), "budget_limit", [1]),
        (dict(max_pages=1), "page_limit", [1]),
    ],
)
def test_preflight_request_and_page_caps(tmp_path, options, reason, expected_pages):
    app, calls = make_app(
        tmp_path, lambda request, index: prediction(complete=False), job_options=options
    )
    with TestClient(app) as client:
        doc = settled(client, upload(client).json()["id"])
        assert doc["metadata"]["preflight"]["analyzed_pages"] == expected_pages
        assert doc["metadata"]["preflight"]["stop_reason"] == reason
        assert len(calls) == 1


def test_single_process_storage_writer(tmp_path):
    app, _ = make_app(tmp_path)
    other, _ = make_app(tmp_path)
    with TestClient(app), pytest.raises(RuntimeError, match="active API writer"), TestClient(other):
        pass


def test_encrypted_pdf_rejected(tmp_path, monkeypatch):
    app, _ = make_app(tmp_path)
    monkeypatch.setattr(pdfium.raw, "FPDF_GetSecurityHandlerRevision", lambda _: 6)
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_pdf"


def test_metadata_schema_through_real_adapter_with_stub_sdk(tmp_path):
    """Validate SDK-bound structured schema/image shape without calling Gemini."""
    captured = []

    def generate_content(**kwargs):
        captured.append(kwargs)
        return types.GenerateContentResponse(
            model_version=DEFAULT_METADATA_MODEL,
            candidates=[
                types.Candidate(
                    content=types.Content(parts=[types.Part(text=json.dumps(prediction()))]),
                    finish_reason=types.FinishReason.STOP,
                )
            ],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=40, candidates_token_count=40, total_token_count=80
            ),
        )

    schemas = metadata_schema_registry()
    adapter = GeminiAdapter(
        SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)),
        schema_registry=schemas,
    )
    service, _ = service_for(transport_override=adapter)
    path = tmp_path / "scan.pdf"
    path.write_bytes(scan_pdf())
    output, stop, error, telemetry = analyze_batch(
        service, path, [1, 2], credential_ref="test-credential", model=DEFAULT_METADATA_MODEL
    )
    assert output["company_name"]["status"] == "resolved" and stop is None and error is None
    assert telemetry["usage"]["total_tokens"] == 80
    assert captured[0]["config"].response_mime_type == "application/json"
    assert captured[0]["config"].response_json_schema == schemas.schema_for(METADATA_REF)
    assert (
        sum(
            part.inline_data is not None
            for content in captured[0]["contents"]
            for part in content.parts
        )
        == 2
    )
