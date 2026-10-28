"""HTTP boundary for the local Financial AI Workspace; no business composition yet."""

from fastapi import FastAPI

app = FastAPI(title="Financial AI API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report process availability without loading data, providers or credentials."""
    return {"status": "ok", "service": "financial-ai-api"}
