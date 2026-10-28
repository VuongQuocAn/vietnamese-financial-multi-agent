"""W-02 HTTP smoke tests, without providers or financial datasets."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from vietnamese_financial_multi_agent.api.main import create_app


def test_health_without_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("WEB_GEMINI_CONFIG", raising=False)
    app = create_app(storage_root=tmp_path)
    assert isinstance(app, FastAPI)
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "financial-ai-api"}


def test_documents_empty_without_credentials(tmp_path):
    with TestClient(create_app(storage_root=tmp_path)) as client:
        response = client.get("/api/documents")
        assert response.status_code == 200
        assert response.json() == {"items": [], "offset": 0, "limit": 20, "total": 0}
