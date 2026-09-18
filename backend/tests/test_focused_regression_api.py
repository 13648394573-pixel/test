import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
        evidence_root=str(tmp_path / "evidence"),
        report_root=str(tmp_path / "reports"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def create_resolved_defect_context(client: TestClient) -> dict:
    device = client.post(
        "/api/devices",
        json={
            "device_type": "ONU",
            "vendor": "Huawei",
            "model": "HN8546X6",
            "serial_number": "FOCUSED-ONU-001",
            "mac_address": None,
            "hardware_version": "V1",
            "software_version": "V2",
        },
    ).json()
    test_case = client.post(
        "/api/test-cases",
        json={
            "case_code": "FOCUSED-WAN-001",
            "title": "Verify WAN recovery",
            "device_type": "ONU",
            "category": "WAN",
            "priority": "P1",
            "preconditions": "ONU is O5",
            "description": None,
            "enabled": True,
            "steps": [
                {
                    "action": "Reconnect WAN",
                    "expected_result": "WAN obtains an address",
                }
            ],
        },
    ).json()
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Focused regression source",
            "version": "1.0",
            "description": None,
            "case_source_ids": [test_case["id"]],
        },
    ).json()
    environment = client.post(
        "/api/environment-profiles",
        json={
            "name": "Focused OLT Lab",
            "description": None,
            "enabled": True,
            "parameters": [],
        },
    ).json()
    run = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={
            "device_source_id": device["id"],
            "environment_profile_id": environment["id"],
        },
    ).json()
    result = run["results"][0]
    client.put(
        f"/api/test-runs/{run['id']}/results/{result['id']}",
        json={"result": "FAIL", "actual_result": "WAN has no address"},
    )
    source = client.post(
        f"/api/test-runs/{run['id']}/results/{result['id']}/lock"
    ).json()
    defect = client.post(
        "/api/defects",
        json={
            "source_run_result_id": source["id"],
            "title": "WAN recovery failed",
            "description": "No address",
            "reproduction_steps": "Reconnect WAN",
            "severity": "S2",
        },
    ).json()
    client.put(
        f"/api/defects/{defect['id']}/status",
        json={"target_status": "IN_PROGRESS", "resolution_notes": None},
    )
    defect = client.put(
        f"/api/defects/{defect['id']}/status",
        json={
            "target_status": "RESOLVED",
            "resolution_notes": "Profile corrected",
        },
    ).json()
    return {
        "device": device,
        "environment": environment,
        "source_run": run,
        "source_result": source,
        "defect": defect,
    }


def test_focused_regression_api_creates_and_tracks_new_run(
    client: TestClient,
) -> None:
    context = create_resolved_defect_context(client)
    defect = context["defect"]
    response = client.post(
        f"/api/defects/{defect['id']}/focused-regression-runs",
        json={
            "device_source_id": context["device"]["id"],
            "environment_profile_id": context["environment"]["id"],
        },
    )

    assert response.status_code == 201
    focused = response.json()
    assert focused["test_run_id"] != context["source_run"]["id"]
    assert focused["source_run_result_id"] == context["source_result"]["id"]
    assert focused["defect_snapshot"]["status"] == "RESOLVED"
    assert focused["snapshot_version"] == 1
    assert len(focused["test_run"]["results"]) == 1
    assert focused["test_run"]["results"][0]["case_snapshot"] == (
        context["source_result"]["case_snapshot"]
    )
    assert client.get(
        f"/api/defects/{defect['id']}/focused-regression-runs"
    ).json() == [focused]
    assert client.get(
        f"/api/focused-regression-runs/{focused['test_run_id']}"
    ).json() == focused


def test_focused_regression_api_maps_not_found_conflict_and_validation(
    client: TestClient,
) -> None:
    context = create_resolved_defect_context(client)
    defect_id = context["defect"]["id"]
    payload = {
        "device_source_id": context["device"]["id"],
        "environment_profile_id": context["environment"]["id"],
    }
    assert client.post(
        f"/api/defects/{defect_id}/focused-regression-runs",
        json=payload,
    ).status_code == 201
    duplicate = client.post(
        f"/api/defects/{defect_id}/focused-regression-runs",
        json=payload,
    )
    assert duplicate.status_code == 409
    assert client.get(
        "/api/focused-regression-runs/missing"
    ).status_code == 404
    assert client.post(
        "/api/defects/missing/focused-regression-runs",
        json=payload,
    ).status_code == 404
    assert client.post(
        f"/api/defects/{defect_id}/focused-regression-runs",
        json={"device_source_id": ""},
    ).status_code == 422


def test_focused_regression_run_supports_report_and_archive_without_source_drift(
    client: TestClient,
) -> None:
    context = create_resolved_defect_context(client)
    source_snapshot = context["source_result"]["case_snapshot"]
    focused = client.post(
        f"/api/defects/{context['defect']['id']}/focused-regression-runs",
        json={
            "device_source_id": context["device"]["id"],
            "environment_profile_id": context["environment"]["id"],
        },
    ).json()
    result = focused["test_run"]["results"][0]
    assert client.put(
        f"/api/test-runs/{focused['test_run_id']}/results/{result['id']}",
        json={"result": "PASS", "actual_result": "WAN recovered"},
    ).status_code == 200
    assert client.post(
        f"/api/test-runs/{focused['test_run_id']}/results/{result['id']}/lock"
    ).status_code == 200

    report_response = client.post(
        f"/api/test-runs/{focused['test_run_id']}/reports",
        json={"title": "Focused WAN Regression"},
    )
    assert report_response.status_code == 201
    report = report_response.json()
    assert report["report_snapshot"]["run"]["id"] == focused["test_run_id"]
    assert report["report_snapshot"]["summary"] == {
        "total": 1,
        "pass": 1,
        "fail": 0,
        "blocked": 0,
        "defects": 0,
    }
    archive_response = client.post(f"/api/reports/{report['id']}/archive")
    assert archive_response.status_code == 201
    assert client.get(
        f"/api/archives/{archive_response.json()['id']}/download"
    ).content.startswith(b"PK")

    source_run = client.get(
        f"/api/test-runs/{context['source_run']['id']}"
    ).json()
    assert source_run["results"][0]["integrity_status"] == "LOCKED"
    assert source_run["results"][0]["result"] == "FAIL"
    assert source_run["results"][0]["case_snapshot"] == source_snapshot
