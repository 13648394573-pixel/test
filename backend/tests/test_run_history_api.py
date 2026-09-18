from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.evidence import Evidence
from app.models.evidence_link import EvidenceRunResultLink
from app.models.test_execution import RunResult, TestProject, TestRun
from app.run_history.repository import RunHistoryRepository


def make_client(tmp_path):
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                allow_metadata_create_all=True,
                database_url=f"sqlite:///{(tmp_path / 'history-api.db').as_posix()}",
                log_file=str(tmp_path / "history-api.log"),
            )
        )
    )


def create_run(client: TestClient, *, serial: str, software: str, version: str):
    device = client.post(
        "/api/devices",
        json={
            "device_type": "ONU",
            "vendor": "Huawei",
            "model": "HN8546X6",
            "serial_number": serial,
            "mac_address": None,
            "hardware_version": "V1",
            "software_version": software,
        },
    ).json()
    case = client.post(
        "/api/test-cases",
        json={
            "case_code": f"CASE-{serial}",
            "title": "Connectivity",
            "device_type": "ONU",
            "category": "WAN",
            "priority": "P1",
            "preconditions": None,
            "description": None,
            "enabled": True,
            "steps": [{"action": "Ping", "expected_result": "Reachable"}],
        },
    ).json()
    environment = client.post(
        "/api/environment-profiles",
        json={
            "name": f"Lab-{serial}",
            "description": None,
            "enabled": True,
            "parameters": [],
        },
    ).json()
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Release",
            "version": version,
            "description": None,
            "case_source_ids": [case["id"]],
        },
    ).json()
    response = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={
            "device_source_id": device["id"],
            "environment_profile_id": environment["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_run_creation_assigns_readable_numbers_and_history_filters(tmp_path) -> None:
    with make_client(tmp_path) as client:
        first = create_run(client, serial="ONU-001", software="V1", version="R1")
        second = create_run(client, serial="ONU-002", software="V2", version="R2")

        assert first["run_no"] == "RUN-000001"
        assert second["run_no"] == "RUN-000002"
        response = client.get(
            "/api/test-runs",
            params={
                "serial_number": "onu-002",
                "software_version": "v2",
                "status": "IN_PROGRESS",
                "limit": 1,
                "offset": 0,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert [item["run_no"] for item in payload["items"]] == ["RUN-000002"]
    assert payload["items"][0]["summary"] == {
        "total": 1,
        "pass": 0,
        "fail": 0,
        "blocked": 0,
        "unset": 1,
    }


def test_history_rejects_invalid_pagination(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/api/test-runs", params={"limit": 101})

    assert response.status_code == 422


def create_comparable_runs(client: TestClient):
    device = client.post(
        "/api/devices",
        json={
            "device_type": "ONU",
            "vendor": "Huawei",
            "model": "HN8546X6",
            "serial_number": "COMPARE-ONU",
            "mac_address": None,
            "hardware_version": "V1",
            "software_version": "V1",
        },
    ).json()
    case = client.post(
        "/api/test-cases",
        json={
            "case_code": "COMPARE-WAN-001",
            "title": "Compare WAN",
            "device_type": "ONU",
            "category": "WAN",
            "priority": "P1",
            "preconditions": None,
            "description": None,
            "enabled": True,
            "steps": [{"action": "Ping", "expected_result": "Reachable"}],
        },
    ).json()
    environment = client.post(
        "/api/environment-profiles",
        json={
            "name": "Compare Lab",
            "description": None,
            "enabled": True,
            "parameters": [],
        },
    ).json()
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Compare Release",
            "version": "R1",
            "description": None,
            "case_source_ids": [case["id"]],
        },
    ).json()
    runs = []
    for result_value in ("PASS", "FAIL", "BLOCKED"):
        run = client.post(
            f"/api/test-projects/{project['id']}/runs",
            json={
                "device_source_id": device["id"],
                "environment_profile_id": environment["id"],
            },
        ).json()
        result = run["results"][0]
        payload = {
            "result": result_value,
            "actual_result": "WAN failed" if result_value == "FAIL" else None,
            "blocked_reason": "Lab unavailable" if result_value == "BLOCKED" else None,
            "test_notes": None,
        }
        client.put(
            f"/api/test-runs/{run['id']}/results/{result['id']}",
            json=payload,
        )
        client.post(f"/api/test-runs/{run['id']}/results/{result['id']}/lock")
        runs.append(client.get(f"/api/test-runs/{run['id']}").json())
    return runs


def test_compare_supports_two_to_five_runs_in_request_order(tmp_path) -> None:
    with make_client(tmp_path) as client:
        runs = create_comparable_runs(client)
        response = client.post(
            "/api/test-runs/compare",
            json={"run_ids": [item["id"] for item in runs]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["run_no"] for item in payload["runs"]] == [
        "RUN-000001",
        "RUN-000002",
        "RUN-000003",
    ]
    assert payload["rows"] == [
        {
            "case_code": "COMPARE-WAN-001",
            "title": "Compare WAN",
            "base": {
                "run_id": runs[0]["id"],
                "result": "PASS",
                "evidence_count": 0,
            },
            "targets": [
                {
                    "run_id": runs[1]["id"],
                    "result": "FAIL",
                    "evidence_count": 0,
                    "change": "REGRESSED",
                },
                {
                    "run_id": runs[2]["id"],
                    "result": "BLOCKED",
                    "evidence_count": 0,
                    "change": "REGRESSED",
                },
            ],
        }
    ]


def test_compare_rejects_invalid_run_sets(tmp_path) -> None:
    with make_client(tmp_path) as client:
        one = client.post(
            "/api/test-runs/compare", json={"run_ids": ["run-1"]}
        )
        duplicate = client.post(
            "/api/test-runs/compare",
            json={"run_ids": ["run-1", "run-1"]},
        )
        too_many = client.post(
            "/api/test-runs/compare",
            json={"run_ids": [f"run-{index}" for index in range(6)]},
        )
        missing = client.post(
            "/api/test-runs/compare",
            json={"run_ids": ["run-1", "run-2"]},
        )

    assert one.status_code == 422
    assert duplicate.status_code == 422
    assert too_many.status_code == 422
    assert missing.status_code == 404


def test_compare_evidence_counts_include_shared_result_links(db_session) -> None:
    project = TestProject(name="Shared Evidence", version="V1")
    run = TestRun(
        run_no="RUN-000001",
        project=project,
        device_source_id="device-1",
        device_snapshot={},
    )
    first = RunResult(
        id="result-1",
        run=run,
        case_source_id="case-1",
        case_snapshot={"case_code": "CASE-001", "title": "First"},
    )
    second = RunResult(
        id="result-2",
        run=run,
        case_source_id="case-2",
        case_snapshot={"case_code": "CASE-002", "title": "Second"},
    )
    db_session.add(project)
    db_session.commit()
    evidence = Evidence(
        run_result_id=first.id,
        category="LOG",
        original_name="shared.log",
        storage_path="run-results/shared.log",
        media_type="text/plain",
        file_size=3,
        sha256="0" * 64,
    )
    evidence.result_links = [
        EvidenceRunResultLink(run_result=first),
        EvidenceRunResultLink(run_result=second),
    ]
    db_session.add(evidence)
    db_session.commit()

    counts = RunHistoryRepository(db_session).evidence_counts(
        [first.id, second.id]
    )

    assert counts == {first.id: 1, second.id: 1}
