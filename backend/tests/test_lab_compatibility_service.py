from app.lab_compatibility.contracts import CreateCompatibilityCheck
from app.lab_compatibility.olt_probe import OLTProbeBlocked, OLTProbeResult
from app.lab_compatibility.service import ActiveCompatibilityCheckExists, LabCompatibilityService
from app.lab_compatibility.store import CompatibilityReportStore
from app.local_runner.contracts import ActionOutcome
from app.local_runner.ma5800.transport import CommandTranscript
from app.local_runner.credentials import CredentialResolver, FakeCredentialStore
from app.local_runner.onu_web.contracts import ONUWebCompatibilityResult
from app.local_runner.pc_probe import PingProbeResult, ProbeObservation


class FakeOLTProbe:
    def __init__(self, *, registration=True, wan=True):
        self.registration = registration
        self.wan = wan

    def preview_host_key(self, _host, _port):
        return "SHA256:approved"

    def run(self, _request, _username, _password):
        return OLTProbeResult((), (), self.registration, self.wan)


class FakeONUAdapter:
    def check_compatibility(self, _context):
        passed = ActionOutcome("PASS", (), ())
        return ONUWebCompatibilityResult(passed, passed)


class UnsupportedOLTProbe(FakeOLTProbe):
    def run(self, _request, _username, _password):
        transcript = CommandTranscript(
            "display_autofind",
            "Password: local-secret\nunsupported",
            "Password: local-secret\nunsupported",
            "MA5800-X7#",
            "hash",
        )
        raise OLTProbeBlocked("ValueError", (transcript,))


class FakePCProbe:
    def run(self, _request):
        ping = PingProbeResult(4, 4, 0, 1, 2, 1, "ok")
        return ProbeObservation("PASS", ping, None, (), None)


def command(**overrides):
    values = {
        "olt_host": "192.168.87.204",
        "olt_port": 22,
        "expected_host_key_fingerprint": "SHA256:approved",
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
    values.update(overrides)
    return CreateCompatibilityCheck(**values)


def build_service(tmp_path, *, olt_probe=None):
    resolver = CredentialResolver(FakeCredentialStore())
    for reference in (
        "olt.lab.username",
        "olt.lab.password",
        "onu.lab.username",
        "onu.lab.password",
    ):
        resolver.enroll(reference, "local-secret")
    return LabCompatibilityService(
        CompatibilityReportStore(tmp_path),
        resolver,
        olt_probe or FakeOLTProbe(),
        FakeONUAdapter(),
        FakePCProbe(),
    )


def test_ready_requires_every_stage_verified(tmp_path) -> None:
    service = build_service(tmp_path)

    view = service.execute(service.create(command()).check_id)

    assert view.lifecycle == "COMPLETED"
    assert view.overall_status == "READY"
    assert {stage.status for stage in view.stages} == {"VERIFIED"}


def test_missing_complete_ont_target_is_partial_not_product_failure(tmp_path) -> None:
    service = build_service(tmp_path, olt_probe=FakeOLTProbe(registration=False, wan=False))
    created = service.create(command(frame=None, slot=None, pon_port=None, ont_id=None))

    view = service.execute(created.check_id)

    current = next(stage for stage in view.stages if stage.code == "OLT_CURRENT_STATE")
    assert current.status == "NEEDS_INPUT"
    assert view.overall_status == "PARTIAL"


def test_second_pending_check_is_rejected(tmp_path) -> None:
    service = build_service(tmp_path)
    service.create(command())

    try:
        service.create(command())
    except ActiveCompatibilityCheckExists:
        pass
    else:
        raise AssertionError("second active check must be rejected")


def test_unsupported_olt_output_keeps_redacted_evidence(tmp_path) -> None:
    service = build_service(tmp_path, olt_probe=UnsupportedOLTProbe())

    view = service.execute(service.create(command()).check_id)

    stage = next(item for item in view.stages if item.code == "OLT_CONNECT")
    assert stage.status == "BLOCKED"
    assert {item.media_type for item in stage.evidence} == {"text/plain", "image/png"}
    text_path = tmp_path / view.check_id / next(
        item.storage_path for item in stage.evidence if item.media_type == "text/plain"
    )
    assert "local-secret" not in text_path.read_text(encoding="utf-8")
