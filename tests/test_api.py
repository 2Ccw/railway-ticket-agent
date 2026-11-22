from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_declares_confirmation_boundary():
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["purchase_mode"] == "official-confirmation-required"


def test_plan_endpoint():
    response = client.post("/api/plan", json={"request": "2026年10月28日从广州南到深圳北，下午二等座"})
    assert response.status_code == 200
    assert response.json()["from_station"] == "广州南"

