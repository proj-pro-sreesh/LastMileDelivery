from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_with_database():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_health_reports_503_when_database_unreachable(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise ConnectionError("db down")

    monkeypatch.setattr("app.routers.health.engine", BrokenEngine())
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
