from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def create_client(tmp_path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                allow_metadata_create_all=True,
                database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
                log_file=str(tmp_path / "api.log"),
                evidence_root=str(tmp_path / "evidence"),
                report_root=str(tmp_path / "reports"),
            )
        )
    )


def create_run(client: TestClient) -> tuple[dict, dict]:
    device = client.post(
        "/api/devices",
        json={
            "device_type": "ONU",
            "vendor": "Example",
            "model": "X1",
            "serial_number": "REPORT-ONU-001",
            "mac_address": None,
            "hardware_version": "A1",
            "software_version": "R1",
        },
    ).json()
    case = client.post(
        "/api/test-cases",
        json={
            "case_code": "REPORT-WAN-001",
            "title": "Verify WAN",
            "device_type": "ONU",
            "category": "WAN",
            "priority": "P1",
            "preconditions": None,
            "description": None,
            "enabled": True,
            "steps": [{"action": "Connect", "expected_result": "Online"}],
        },
    ).json()
    environment = client.post(
        "/api/environment-profiles",
        json={
            "name": "Report lab",
            "description": None,
            "enabled": True,
            "parameters": [],
        },
    ).json()
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Release report",
            "version": "R1",
            "description": None,
            "case_source_ids": [case["id"]],
        },
    ).json()
    run = client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={
            "device_source_id": device["id"],
            "environment_profile_id": environment["id"],
        },
    ).json()
    return project, run


def lock_run(client: TestClient, run: dict) -> dict:
    result_id = run["results"][0]["id"]
    client.put(
        f"/api/test-runs/{run['id']}/results/{result_id}",
        json={"result": "PASS", "actual_result": "Online"},
    )
    return client.post(
        f"/api/test-runs/{run['id']}/results/{result_id}/lock"
    ).json()


def test_report_api_generates_downloads_and_archives_once(tmp_path) -> None:
    with create_client(tmp_path) as client:
        project, run = create_run(client)
        lock_run(client, run)

        created_response = client.post(
            f"/api/test-runs/{run['id']}/reports",
            json={"title": "ONU Acceptance"},
        )
        assert created_response.status_code == 201
        report = created_response.json()
        assert report["report_version"] == 1
        assert report["report_snapshot"]["summary"]["pass"] == 1
        assert client.get(
            f"/api/test-runs/{run['id']}/reports"
        ).json() == [report]
        assert client.get(
            f"/api/test-projects/{project['id']}/reports"
        ).json() == [report]
        assert client.get(f"/api/reports/{report['id']}").json() == report

        html = client.get(f"/api/reports/{report['id']}/download")
        assert html.status_code == 200
        assert html.headers["content-type"].startswith("text/html")
        assert b"ONU Acceptance" in html.content
        assert b"Release report" in html.content

        archive_response = client.post(
            f"/api/reports/{report['id']}/archive"
        )
        assert archive_response.status_code == 201
        archive = archive_response.json()
        assert client.get(
            f"/api/reports/{report['id']}/archive"
        ).json() == archive
        assert client.get(f"/api/archives/{archive['id']}").json() == archive
        downloaded = client.get(f"/api/archives/{archive['id']}/download")
        assert downloaded.status_code == 200
        assert downloaded.content.startswith(b"PK")
        assert client.post(
            f"/api/reports/{report['id']}/archive"
        ).status_code == 409


def test_report_api_rejects_not_ready_and_missing_sources(tmp_path) -> None:
    with create_client(tmp_path) as client:
        _project, run = create_run(client)

        assert client.post(
            f"/api/test-runs/{run['id']}/reports",
            json={},
        ).status_code == 409
        assert client.post(
            "/api/test-runs/missing/reports",
            json={},
        ).status_code == 404
        assert client.get("/api/reports/missing").status_code == 404
