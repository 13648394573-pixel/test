from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


DEVICE = {
    "device_type": "ONU",
    "vendor": "Huawei",
    "model": "HN8546X6",
    "serial_number": "EVIDENCE-ONU-001",
    "mac_address": None,
    "hardware_version": None,
    "software_version": None,
}
CASE = {
    "case_code": "EVIDENCE-001",
    "title": "WAN",
    "device_type": "ONU",
    "category": "WAN",
    "priority": "P1",
    "preconditions": None,
    "description": None,
    "enabled": True,
    "steps": [{"action": "Test", "expected_result": "Pass"}],
}


def create_client(tmp_path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                allow_metadata_create_all=True,
                database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
                log_file=str(tmp_path / "api.log"),
                evidence_root=str(tmp_path / "evidence"),
                evidence_max_size_mb=1,
            )
        )
    )


def create_run(client: TestClient):
    device = client.post("/api/devices", json=DEVICE).json()
    case = client.post("/api/test-cases", json=CASE).json()
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Evidence",
            "version": "V1",
            "description": None,
            "case_source_ids": [case["id"]],
        },
    ).json()
    environment = client.post(
        "/api/environment-profiles",
        json={
            "name": "Evidence lab",
            "description": None,
            "enabled": True,
            "parameters": [],
        },
    ).json()
    return client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={
            "device_source_id": device["id"],
            "environment_profile_id": environment["id"],
        },
    ).json()


def test_evidence_api_uploads_lists_downloads_and_deletes(tmp_path) -> None:
    with create_client(tmp_path) as client:
        run = create_run(client)
        result_id = run["results"][0]["id"]

        uploaded = client.post(
            f"/api/run-results/{result_id}/evidences",
            data={"category": "LOG", "description": "Console"},
            files={"file": ("console.log", b"OLT log", "text/plain")},
        )
        assert uploaded.status_code == 201
        evidence = uploaded.json()
        assert evidence["original_name"] == "console.log"
        assert evidence["file_size"] == 7
        assert client.get(
            f"/api/run-results/{result_id}/evidences"
        ).json() == [evidence]

        downloaded = client.get(f"/api/evidences/{evidence['id']}/download")
        assert downloaded.status_code == 200
        assert downloaded.content == b"OLT log"

        deleted = client.delete(f"/api/evidences/{evidence['id']}")
        assert deleted.status_code == 204
        assert client.get(
            f"/api/evidences/{evidence['id']}/download"
        ).status_code == 404


def create_two_result_run(client: TestClient):
    device = client.post(
        "/api/devices", json={**DEVICE, "serial_number": "BATCH-ONU-001"}
    ).json()
    cases = []
    for index in (1, 2):
        cases.append(
            client.post(
                "/api/test-cases",
                json={
                    **CASE,
                    "case_code": f"BATCH-EVIDENCE-{index:03d}",
                    "title": f"WAN {index}",
                },
            ).json()
        )
    project = client.post(
        "/api/test-projects",
        json={
            "name": "Batch Evidence",
            "version": "V1",
            "description": None,
            "case_source_ids": [item["id"] for item in cases],
        },
    ).json()
    environment = client.post(
        "/api/environment-profiles",
        json={
            "name": "Batch Evidence lab",
            "description": None,
            "enabled": True,
            "parameters": [],
        },
    ).json()
    return client.post(
        f"/api/test-projects/{project['id']}/runs",
        json={
            "device_source_id": device["id"],
            "environment_profile_id": environment["id"],
        },
    ).json()


def test_batch_upload_stores_each_file_once_and_links_multiple_results(
    tmp_path,
) -> None:
    with create_client(tmp_path) as client:
        run = create_two_result_run(client)
        result_ids = [item["id"] for item in run["results"]]
        response = client.post(
            "/api/evidences/batch",
            data={
                "run_result_ids": result_ids,
                "category": "SCREENSHOT",
                "description": "Shared WAN evidence",
            },
            files=[
                ("files", ("wan.png", b"image", "image/png")),
                ("files", ("wan.log", b"log", "text/plain")),
            ],
        )

        assert response.status_code == 201
        created = response.json()
        assert len(created) == 2
        assert all(item["run_result_ids"] == result_ids for item in created)
        first_list = client.get(
            f"/api/run-results/{result_ids[0]}/evidences"
        ).json()
        second_list = client.get(
            f"/api/run-results/{result_ids[1]}/evidences"
        ).json()
        assert [item["id"] for item in first_list] == [
            item["id"] for item in second_list
        ]
        files = [path for path in (tmp_path / "evidence").rglob("*") if path.is_file()]
        assert len(files) == 2


def test_batch_upload_rejects_locked_target_without_files(tmp_path) -> None:
    with create_client(tmp_path) as client:
        run = create_two_result_run(client)
        first = run["results"][0]
        client.put(
            f"/api/test-runs/{run['id']}/results/{first['id']}",
            json={"result": "PASS"},
        )
        client.post(
            f"/api/test-runs/{run['id']}/results/{first['id']}/lock"
        )
        response = client.post(
            "/api/evidences/batch",
            data={
                "run_result_ids": [item["id"] for item in run["results"]],
                "category": "LOG",
            },
            files=[("files", ("wan.log", b"log", "text/plain"))],
        )

    assert response.status_code == 409
    assert not list((tmp_path / "evidence").rglob("*.log"))
