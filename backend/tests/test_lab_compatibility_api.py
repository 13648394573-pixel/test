from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.lab_compatibility.contracts import (
    STAGE_CODES,
    CompatibilityCheckView,
    CompatibilityStage,
)
from app.lab_compatibility.service import ActiveCompatibilityCheckExists
from app.main import create_app


FINGERPRINT = "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


class FakeCompatibilityService:
    def __init__(self, *, active_conflict=False):
        self.active_conflict = active_conflict
        self.created = []
        self.executed = []
        now = datetime.now(UTC)
        self.view = CompatibilityCheckView(
            "12345678-1234-4234-8234-123456789abc",
            "PENDING",
            None,
            tuple(CompatibilityStage(code, "NOT_RUN", "尚未执行") for code in STAGE_CODES),
            now,
            now,
        )

    def preview_host_key(self, host, port):
        assert host == "192.168.87.204"
        assert port == 22
        return FINGERPRINT

    def create(self, command):
        if self.active_conflict:
            raise ActiveCompatibilityCheckExists("active")
        self.created.append(command)
        return self.view

    def execute(self, check_id):
        self.executed.append(check_id)
        return self.view

    def get(self, _check_id):
        return self.view

    def list_evidence(self, _check_id):
        return ()


def settings(tmp_path, host="127.0.0.1"):
    return Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
        local_runner_evidence_root=str(tmp_path / "runner"),
        api_bind_host=host,
    )


def payload(**overrides):
    value = {
        "olt_host": "192.168.87.204",
        "olt_port": 22,
        "expected_host_key_fingerprint": FINGERPRINT,
        "olt_username_ref": "olt.lab.username",
        "olt_password_ref": "olt.lab.password",
        "onu_serial_number": "48575443DD91BBBB",
        "frame": 0,
        "slot": 2,
        "pon_port": 10,
        "ont_id": 36,
        "onu_web_url": "http://192.168.1.1",
        "onu_web_username_ref": "onu.lab.username",
        "onu_web_password_ref": "onu.lab.password",
        "onu_adapter_key": "neutral-v1",
        "pc_interface_name": "Ethernet",
        "pc_source_address": "192.168.1.20",
        "pc_ping_target": "192.168.1.1",
    }
    value.update(overrides)
    return value


def test_create_accepts_references_only_and_returns_202(tmp_path) -> None:
    service = FakeCompatibilityService()
    with TestClient(
        create_app(settings(tmp_path), lab_compatibility_service=service)
    ) as client:
        response = client.post("/api/lab-compatibility-checks", json=payload())

    assert response.status_code == 202
    assert response.json()["lifecycle"] == "PENDING"
    assert response.headers["cache-control"] == "no-store"
    assert service.executed == [service.view.check_id]
    assert service.created[0].olt_password_ref == "olt.lab.password"
    assert "local-secret" not in response.text


def test_host_key_preview_and_reads_are_local_only(tmp_path) -> None:
    service = FakeCompatibilityService()
    with TestClient(
        create_app(settings(tmp_path), lab_compatibility_service=service)
    ) as client:
        preview = client.post(
            "/api/lab-compatibility-checks/host-key-preview",
            json={"olt_host": "192.168.87.204", "olt_port": 22},
        )
        read = client.get(f"/api/lab-compatibility-checks/{service.view.check_id}")

    assert preview.json() == {"fingerprint": FINGERPRINT}
    assert read.status_code == 200
    assert read.json()["stages"][0]["code"] == "LOCAL_ENV"


def test_routes_reject_non_loopback_binding(tmp_path) -> None:
    with TestClient(
        create_app(
            settings(tmp_path, "0.0.0.0"),
            lab_compatibility_service=FakeCompatibilityService(),
        )
    ) as client:
        response = client.post("/api/lab-compatibility-checks", json=payload())

    assert response.status_code == 403


def test_payload_rejects_public_hosts_partial_target_and_credentials_in_url(tmp_path) -> None:
    service = FakeCompatibilityService()
    with TestClient(
        create_app(settings(tmp_path), lab_compatibility_service=service)
    ) as client:
        public = client.post(
            "/api/lab-compatibility-checks", json=payload(olt_host="8.8.8.8")
        )
        partial = client.post(
            "/api/lab-compatibility-checks", json=payload(ont_id=None)
        )
        embedded = client.post(
            "/api/lab-compatibility-checks",
            json=payload(onu_web_url="http://user:password@192.168.1.1"),
        )

    assert (public.status_code, partial.status_code, embedded.status_code) == (422, 422, 422)
    assert service.created == []


def test_active_check_conflict_returns_409(tmp_path) -> None:
    with TestClient(
        create_app(
            settings(tmp_path),
            lab_compatibility_service=FakeCompatibilityService(active_conflict=True),
        )
    ) as client:
        response = client.post("/api/lab-compatibility-checks", json=payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "已有现场检查正在运行"
