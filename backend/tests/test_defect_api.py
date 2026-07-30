import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def create_result(
    client: TestClient,
    *,
    suffix: str,
    result: str,
) -> dict:
    device = client.post(
        "/api/devices",
        json={
            "device_type": "ONU",
            "vendor": "Huawei",
            "model": "HN8546X6",
            "serial_number": f"DEFECT-ONU-{suffix}",
            "mac_address": None,
            "hardware_version": "V1",
            "software_version": "V5R020",
        },
    ).json()
    test_case = client.post(
        "/api/test-cases",
        json={
            "case_code": f"DEFECT-WAN-{suffix}",
            "title": "Verify WAN recovery",
            "device_type": "ONU",
            "category": "WAN",
            "priority": "P1",
            "preconditions": None,
            "description": None,
            "enabled": True,
            "steps": [
                {
                    "action": "Reconnect the WAN",
                    "expected_result": "WAN recovers",
                }
            ],
        },
    ).json()
    project = client.post(
        "/api/test-projects",
        json={
            "name": f"Defect evidence {suffix}",
            "version": "V1",
            "description": None,
            "case_source_ids": [test_case["id"]],
        },
    ).json()
    run = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={"device_source_id": device["id"]},
    ).json()
    run_result = run["results"][0]
    return client.put(
        f"/api/test-runs/{run['id']}/results/{run_result['id']}",
        json={"result": result},
    ).json()


def create_defect(client: TestClient, source_result_id: str) -> dict:
    response = client.post(
        "/api/defects",
        json={
            "source_run_result_id": source_result_id,
            "title": "WAN does not recover",
            "description": "WAN remains disconnected after reconnect",
            "reproduction_steps": "Disconnect and reconnect the uplink",
            "severity": "S2",
        },
    )
    assert response.status_code == 201
    return response.json()


def transition(
    client: TestClient,
    defect_id: str,
    target_status: str,
    resolution_notes: str | None = None,
):
    return client.put(
        f"/api/defects/{defect_id}/status",
        json={
            "target_status": target_status,
            "resolution_notes": resolution_notes,
        },
    )


def test_defect_api_supports_lifecycle_and_pass_regression(
    client: TestClient,
) -> None:
    source = create_result(client, suffix="SOURCE", result="FAIL")
    original_snapshot = source["case_snapshot"]
    defect = create_defect(client, source["id"])

    assert defect["defect_code"] == "DEF-000001"
    assert defect["status"] == "OPEN"
    assert defect["source_run_result"]["result"] == "FAIL"
    assert defect["source_run_result"]["case_snapshot"] == original_snapshot
    assert client.get("/api/defects").json() == [defect]
    assert client.get(f"/api/defects/{defect['id']}").json() == defect

    updated = client.put(
        f"/api/defects/{defect['id']}",
        json={
            "title": "WAN recovery fails",
            "description": "Updated evidence description",
            "reproduction_steps": "Reconnect the uplink twice",
            "severity": "S1",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "WAN recovery fails"

    assert transition(client, defect["id"], "IN_PROGRESS").status_code == 200
    resolved = transition(
        client,
        defect["id"],
        "RESOLVED",
        "Updated WAN recovery handling",
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"

    # Build a second run using the original case through the public API.
    devices = client.get("/api/devices").json()
    projects = client.get("/api/test-projects").json()
    verification_run = client.post(
        f"/api/test-projects/{projects[0]['id']}/runs",
        json={"device_source_id": devices[0]["id"]},
    ).json()
    verification_result = verification_run["results"][0]
    client.put(
        f"/api/test-runs/{verification_run['id']}/results/"
        f"{verification_result['id']}",
        json={"result": "PASS"},
    )

    regression = client.post(
        f"/api/defects/{defect['id']}/regressions",
        json={
            "verification_run_result_id": verification_result["id"],
            "notes": "WAN recovered",
        },
    )
    assert regression.status_code == 201
    assert regression.json()["result"] == "PASS"
    assert client.get(
        f"/api/defects/{defect['id']}/regressions"
    ).json() == [regression.json()]
    assert client.get(f"/api/defects/{defect['id']}").json()["status"] == (
        "CLOSED"
    )
    assert client.delete(f"/api/defects/{defect['id']}").status_code == 405

    source_after = client.get(
        f"/api/test-runs/{source['run_id']}"
    ).json()["results"][0]
    assert source_after["result"] == "FAIL"
    assert source_after["case_snapshot"] == original_snapshot


def test_defect_api_enforces_source_and_transition_rules(
    client: TestClient,
) -> None:
    source = create_result(client, suffix="RULES", result="BLOCKED")
    defect = create_defect(client, source["id"])

    duplicate = client.post(
        "/api/defects",
        json={
            "source_run_result_id": source["id"],
            "title": "Duplicate",
            "description": "Duplicate source",
            "reproduction_steps": "Repeat",
            "severity": "S3",
        },
    )
    assert duplicate.status_code == 409
    assert (
        transition(client, defect["id"], "RESOLVED", "Invalid").status_code
        == 409
    )
    assert client.get("/api/defects/missing").status_code == 404

    passing = create_result(client, suffix="INVALID", result="PASS")
    invalid_source = client.post(
        "/api/defects",
        json={
            "source_run_result_id": passing["id"],
            "title": "Invalid",
            "description": "PASS cannot create a defect",
            "reproduction_steps": "None",
            "severity": "S4",
        },
    )
    assert invalid_source.status_code == 422


@pytest.mark.parametrize(
    "result, expected_status",
    [("FAIL", "REOPENED"), ("BLOCKED", "RESOLVED")],
)
def test_regression_outcome_updates_defect_as_specified(
    client: TestClient,
    result: str,
    expected_status: str,
) -> None:
    source = create_result(client, suffix=f"SRC-{result}", result="FAIL")
    defect = create_defect(client, source["id"])
    transition(client, defect["id"], "IN_PROGRESS")
    transition(client, defect["id"], "RESOLVED", "Candidate fix")

    devices = client.get("/api/devices").json()
    project = client.get("/api/test-projects").json()[0]
    run = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={"device_source_id": devices[0]["id"]},
    ).json()
    verification = run["results"][0]
    client.put(
        f"/api/test-runs/{run['id']}/results/{verification['id']}",
        json={"result": result},
    )

    response = client.post(
        f"/api/defects/{defect['id']}/regressions",
        json={
            "verification_run_result_id": verification["id"],
            "notes": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["result"] == result
    assert client.get(f"/api/defects/{defect['id']}").json()["status"] == (
        expected_status
    )


def test_defect_api_validates_payload(client: TestClient) -> None:
    response = client.post(
        "/api/defects",
        json={
            "source_run_result_id": "",
            "title": "",
            "description": "",
            "reproduction_steps": "",
            "severity": "S5",
        },
    )

    assert response.status_code == 422
