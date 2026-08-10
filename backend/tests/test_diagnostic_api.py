from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def create_result(client: TestClient) -> str:
    device = client.post("/api/devices", json={
        "device_type": "ONU", "vendor": "Huawei", "model": "HG8245",
        "serial_number": "DIAG-001", "mac_address": None,
        "hardware_version": None, "software_version": "V1",
    }).json()
    case = client.post("/api/test-cases", json={
        "case_code": "DIAG-PING", "title": "Ping", "device_type": "ONU",
        "category": "WAN", "priority": "P1", "preconditions": None,
        "description": None, "enabled": True,
        "steps": [{"action": "Ping", "expected_result": "Reachable"}],
    }).json()
    environment = client.post("/api/environment-profiles", json={
        "name": "Diagnostic lab", "description": None, "enabled": True,
        "parameters": [{
            "section": "ONU", "param_key": "onu_management_url",
            "param_value": "http://192.168.1.1", "display_order": 1,
        }],
    }).json()
    project = client.post("/api/test-projects", json={
        "name": "Diagnostic", "version": "1", "description": None,
        "case_source_ids": [case["id"]],
    }).json()
    run = client.post(f"/api/test-projects/{project['id']}/runs", json={
        "device_source_id": device["id"],
        "environment_profile_id": environment["id"],
    }).json()
    return run["results"][0]["id"]


def test_diagnostic_api_creates_executes_and_lists_session(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
        evidence_root=str(tmp_path / "evidence"),
    )
    app = create_app(settings)
    app.state.huawei_ping_executor = lambda _context, _request: (
        "sent=3 received=3 loss=0% min=1ms avg=2ms max=3ms"
    )
    with TestClient(app) as client:
        result_id = create_result(client)
        response = client.post(f"/api/run-results/{result_id}/diagnostics", json={
            "wan_mode": "IPOE",
            "gateway_target": "192.168.1.1",
            "public_ip_target": "1.1.1.1",
            "domain_target": "example.com",
            "packet_count": 3,
            "timeout_seconds": 5,
            "max_attempts_per_layer": 2,
        })
        assert response.status_code == 202
        session_id = response.json()["id"]

        detail = client.get(f"/api/diagnostics/{session_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "COMPLETED"
        assert [item["layer"] for item in detail.json()["attempts"]] == [
            "GATEWAY", "PUBLIC_IP", "DOMAIN"
        ]
        history = client.get(f"/api/run-results/{result_id}/diagnostics").json()
        assert [item["id"] for item in history] == [session_id]


def test_diagnostic_api_rejects_invalid_policy(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'invalid.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
    )
    app = create_app(settings)
    app.state.huawei_ping_executor = lambda _context, _request: ""
    with TestClient(app) as client:
        result_id = create_result(client)
        response = client.post(f"/api/run-results/{result_id}/diagnostics", json={
            "wan_mode": "IPOE", "gateway_target": "bad",
            "public_ip_target": "1.1.1.1", "domain_target": "example.com",
            "packet_count": 3, "timeout_seconds": 5, "max_attempts_per_layer": 2,
        })
        assert response.status_code == 422


def test_application_restart_interrupts_running_diagnostic(tmp_path) -> None:
    from app.diagnostics.repository import DiagnosticRepository

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'recovery.db').as_posix()}",
        log_file=str(tmp_path / "recovery.log"),
        evidence_root=str(tmp_path / "evidence"),
    )
    first_app = create_app(settings)
    with TestClient(first_app) as client:
        result_id = create_result(client)
        with first_app.state.session_factory() as session:
            repository = DiagnosticRepository(session)
            diagnostic = repository.create_session(
                result_id,
                "huawei-ping",
                "1",
                "IPOE",
                {"layers": ["GATEWAY", "PUBLIC_IP", "DOMAIN"]},
            )
            repository.mark_running(diagnostic, datetime(2026, 8, 10, 9, 0))
            session_id = diagnostic.id

    restarted_app = create_app(settings)
    with TestClient(restarted_app) as client:
        response = client.get(f"/api/diagnostics/{session_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "INTERRUPTED"
    assert response.json()["error_code"] == "PROCESS_RESTARTED"
    assert response.json()["completed_at"] is not None
