from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_documentation():
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        assert "/health" in client.get("/openapi.json").json()["paths"]
