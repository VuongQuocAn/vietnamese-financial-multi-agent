"""W-02 HTTP smoke tests, without providers or financial datasets."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from vietnamese_financial_multi_agent.api.main import app


def test_health_without_credentials(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert isinstance(app, FastAPI)
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "financial-ai-api"}


def test_future_document_api_is_not_exposed():
    with TestClient(app) as client:
        assert client.get("/api/documents").status_code == 404
