from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_all_appointments():
    response = client.get("/api/appointments")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_invalid_appointment():
    response = client.get(
        "/api/appointments/DOES_NOT_EXIST"
    )

    assert response.status_code == 404

    body = response.json()

    assert body["error"] is True
    assert body["code"] == "APPOINTMENT_NOT_FOUND"