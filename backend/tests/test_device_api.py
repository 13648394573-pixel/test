import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


DEVICE_PAYLOAD = {
    "device_type": "ONU",
    "vendor": "Huawei",
    "model": "HN8546X6",
    "serial_number": "ONU-API-001",
    "mac_address": "00:11:22:33:44:55",
    "hardware_version": "V1",
    "software_version": "V5R020",
}


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_device_api_supports_complete_crud_lifecycle(client: TestClient) -> None:
    create_response = client.post("/api/devices", json=DEVICE_PAYLOAD)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["serial_number"] == "ONU-API-001"
    assert created["created_at"]
    assert created["updated_at"]

    assert client.get("/api/devices").json() == [created]
    assert client.get(f"/api/devices/{created['id']}").json() == created

    update_response = client.put(
        f"/api/devices/{created['id']}",
        json={**DEVICE_PAYLOAD, "software_version": "V5R021"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["software_version"] == "V5R021"

    delete_response = client.delete(f"/api/devices/{created['id']}")
    assert delete_response.status_code == 204
    assert client.get("/api/devices").json() == []


def test_device_api_rejects_missing_required_fields(client: TestClient) -> None:
    response = client.post("/api/devices", json={"device_type": "ONU"})

    assert response.status_code == 422


def test_device_api_reports_duplicate_serial_number(client: TestClient) -> None:
    assert client.post("/api/devices", json=DEVICE_PAYLOAD).status_code == 201

    response = client.post(
        "/api/devices",
        json={**DEVICE_PAYLOAD, "model": "Different"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Serial number already exists"}


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_device_api_reports_missing_device(
    client: TestClient,
    method: str,
) -> None:
    if method == "put":
        response = client.put("/api/devices/missing", json=DEVICE_PAYLOAD)
    else:
        response = getattr(client, method)("/api/devices/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}
