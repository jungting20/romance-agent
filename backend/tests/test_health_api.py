from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_health_returns_contracted_response() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_health_preserves_approved_operation_id() -> None:
    operation = app.openapi()["paths"]["/health"]["get"]

    assert operation["operationId"] == "getHealth"
