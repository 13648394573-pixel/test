import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


DEVICE_PAYLOAD = {
    "device_type": "ONU",
    "vendor": "Huawei",
    "model": "HN8546X6",
    "serial_number": "API-EXEC-ONU-001",
    "mac_address": "00:11:22:33:44:55",
    "hardware_version": "V1",
    "software_version": "V5R020",
}
CASE_PAYLOAD = {
    "case_code": "API-EXEC-WAN-001",
    "title": "Verify IPoE WAN",
    "device_type": "ONU",
    "category": "WAN",
    "priority": "P1",
    "preconditions": "ONU is registered",
    "description": None,
    "enabled": True,
    "steps": [
        {
            "action": "Create an IPoE WAN",
            "expected_result": "WAN obtains an address",
        }
    ],
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


def create_sources(client: TestClient):
    device = client.post("/api/devices", json=DEVICE_PAYLOAD).json()
    test_case = client.post("/api/test-cases", json=CASE_PAYLOAD).json()
    return device, test_case


def test_execution_api_supports_project_run_result_and_history_lifecycle(
    client: TestClient,
) -> None:
    device, test_case = create_sources(client)

    project_response = client.post(
        "/api/test-projects",
        json={
            "name": "Release acceptance",
            "version": "V1",
            "description": "Manual acceptance",
            "case_source_ids": [test_case["id"]],
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()
    assert project["id"]
    assert project["case_selections"] == [
        {"case_source_id": test_case["id"]}
    ]
    assert client.get("/api/test-projects").json() == [project]
    assert client.get(f"/api/test-projects/{project['id']}").json() == project

    update_response = client.put(
        f"/api/test-projects/{project['id']}",
        json={
            "name": "Updated acceptance",
            "version": "V2",
            "description": None,
            "case_source_ids": [test_case["id"]],
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated acceptance"

    run_response = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={"device_source_id": device["id"]},
    )
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["snapshot_version"] == 1
    assert run["device_snapshot"]["software_version"] == "V5R020"
    assert run["status"] == "IN_PROGRESS"
    assert len(run["results"]) == 1
    assert run["results"][0]["snapshot_version"] == 1
    assert run["results"][0]["result"] is None
    assert run["results"][0]["case_snapshot"]["steps"][0]["action"] == (
        "Create an IPoE WAN"
    )
    assert client.get(f"/api/test-runs/{run['id']}").json() == run
    assert client.get(f"/api/test-projects/{project['id']}/runs").json() == [
        run
    ]

    client.put(
        f"/api/devices/{device['id']}",
        json={**DEVICE_PAYLOAD, "software_version": "V5R021"},
    )
    client.put(
        f"/api/test-cases/{test_case['id']}",
        json={**CASE_PAYLOAD, "title": "Changed title"},
    )
    historical = client.get(f"/api/test-runs/{run['id']}").json()
    assert historical["device_snapshot"]["software_version"] == "V5R020"
    assert historical["results"][0]["case_snapshot"]["title"] == (
        "Verify IPoE WAN"
    )

    result_id = run["results"][0]["id"]
    for result_value in ["PASS", "FAIL", "BLOCKED"]:
        result_response = client.put(
            f"/api/test-runs/{run['id']}/results/{result_id}",
            json={"result": result_value},
        )
        assert result_response.status_code == 200
        assert result_response.json()["result"] == result_value
    completed = client.get(f"/api/test-runs/{run['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["finished_at"]

    conflict = client.delete(f"/api/test-projects/{project['id']}")
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Project has run history"}


def test_execution_api_deletes_project_without_history(client: TestClient) -> None:
    _device, test_case = create_sources(client)
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Disposable",
            "version": "V1",
            "description": None,
            "case_source_ids": [test_case["id"]],
        },
    ).json()

    response = client.delete(f"/api/test-projects/{project['id']}")

    assert response.status_code == 204
    assert client.get("/api/test-projects").json() == []


def test_execution_api_reports_missing_resources(client: TestClient) -> None:
    _device, test_case = create_sources(client)
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [test_case["id"]],
        },
    ).json()

    assert client.get("/api/test-projects/missing").status_code == 404
    assert client.get("/api/test-runs/missing").status_code == 404
    missing_device = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={"device_source_id": "missing"},
    )
    assert missing_device.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "",
            "version": "V1",
            "description": None,
            "case_source_ids": ["case-1"],
        },
        {
            "name": "Acceptance",
            "version": "",
            "description": None,
            "case_source_ids": ["case-1"],
        },
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [],
        },
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": ["missing"],
        },
    ],
)
def test_execution_api_rejects_invalid_project_payload(
    client: TestClient,
    payload: dict,
) -> None:
    response = client.post("/api/test-projects", json=payload)

    assert response.status_code == 422


def test_execution_api_rejects_invalid_result_value(client: TestClient) -> None:
    response = client.put(
        "/api/test-runs/missing/results/missing",
        json={"result": "SKIPPED"},
    )

    assert response.status_code == 422
