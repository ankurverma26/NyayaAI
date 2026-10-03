"""
tests/test_health.py
────────────────────
Smoke-test for the /health endpoint.
Run with: pytest tests/test_health.py -v
"""
import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Synchronous test client — no running server needed."""
    return TestClient(app)


def test_health_status_ok(client: TestClient) -> None:
    """Health endpoint must return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_payload_shape(client: TestClient) -> None:
    """Health response must include required keys."""
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "use_llm" in data
    assert "embed_model" in data


def test_health_use_llm_default(client: TestClient) -> None:
    """Default USE_LLM should be False (no LLM required for core pipeline)."""
    data = client.get("/health").json()
    assert data["use_llm"] == get_settings().use_llm