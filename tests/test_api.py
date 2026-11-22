from fastapi.testclient import TestClient

from src.api.main import app


def test_health():
    assert TestClient(app).get("/health").status_code == 200


def test_alert_rejects_extra_fields():
    response = TestClient(app).post("/v1/triage", json={"service": "checkout-api", "summary": "5xx", "extra": True})
    assert response.status_code == 422
