from collections import deque
from decimal import Decimal

import pytest

from app.diagnostics.contracts import PingObservation
from app.models.test_execution import RunResult, TestProject, TestRun


class SequenceAdapter:
    key = "huawei-ping"
    version = "1"

    def __init__(self, statuses):
        self.statuses = deque(statuses)
        self.requests = []

    def supports(self, snapshot):
        return snapshot.get("vendor") == "Huawei"

    def ping(self, _context, request):
        self.requests.append(request)
        status = self.statuses.popleft()
        received = request.packet_count if status == "PASS" else 0
        return PingObservation(
            status=status,
            packets_sent=request.packet_count,
            packets_received=received,
            loss_percent=Decimal("0" if status == "PASS" else "100"),
            latency_min_ms=None,
            latency_avg_ms=None,
            latency_max_ms=None,
            raw_output=f"{request.layer}:{status}",
        )


def make_result(db_session, *, locked=False) -> RunResult:
    project = TestProject(name="Service", version="1", description=None)
    run = TestRun(
        run_no="RUN-000001",
        project=project,
        device_source_id="device-1",
        device_snapshot={"vendor": "Huawei", "model": "HG8245"},
    )
    result = RunResult(
        run=run,
        case_source_id="case-1",
        case_snapshot={"case_code": "PING"},
        integrity_status="LOCKED" if locked else "DRAFT",
        result="PASS" if locked else None,
    )
    db_session.add(project)
    db_session.commit()
    return result


def make_service(db_session, adapter):
    from app.diagnostics.registry import AdapterRegistry
    from app.diagnostics.repository import DiagnosticRepository
    from app.diagnostics.service import DiagnosticService

    return DiagnosticService(DiagnosticRepository(db_session), AdapterRegistry([adapter]))


def payload(**updates):
    value = {
        "wan_mode": "IPOE",
        "gateway_target": "192.168.1.1",
        "public_ip_target": "1.1.1.1",
        "domain_target": "example.com",
        "packet_count": 3,
        "timeout_seconds": 5,
        "max_attempts_per_layer": 2,
    }
    value.update(updates)
    return value


def test_service_rejects_locked_result(db_session) -> None:
    from app.diagnostics.service import LockedDiagnosticResultError

    result = make_result(db_session, locked=True)
    service = make_service(db_session, SequenceAdapter(["PASS"]))
    with pytest.raises(LockedDiagnosticResultError):
        service.create(result.id, payload())


def test_service_retries_then_runs_all_layers_without_mutating_result(db_session) -> None:
    result = make_result(db_session)
    adapter = SequenceAdapter(["FAIL", "PASS", "PASS", "PASS"])
    service = make_service(db_session, adapter)
    diagnostic = service.create(result.id, payload())

    completed = service.execute(diagnostic.id)

    assert completed.status == "COMPLETED"
    assert [(item.layer, item.attempt_number, item.status) for item in completed.attempts] == [
        ("GATEWAY", 1, "FAIL"),
        ("GATEWAY", 2, "PASS"),
        ("PUBLIC_IP", 1, "PASS"),
        ("DOMAIN", 1, "PASS"),
    ]
    db_session.refresh(result)
    assert result.result is None
    assert result.integrity_status == "DRAFT"


def test_service_stops_after_gateway_exhausts_retries(db_session) -> None:
    result = make_result(db_session)
    adapter = SequenceAdapter(["FAIL", "FAIL"])
    service = make_service(db_session, adapter)

    completed = service.execute(service.create(result.id, payload()).id)

    assert [item.layer for item in completed.attempts] == ["GATEWAY", "GATEWAY"]
    assert completed.status == "COMPLETED"


def test_service_records_log_evidence_for_each_attempt(db_session, tmp_path) -> None:
    from app.diagnostics.registry import AdapterRegistry
    from app.diagnostics.repository import DiagnosticRepository
    from app.diagnostics.service import DiagnosticService
    from app.evidence.repository import EvidenceRepository
    from app.evidence.service import EvidenceService
    from app.evidence.storage import EvidenceStorage

    result = make_result(db_session)
    evidence_repository = EvidenceRepository(db_session)
    evidence_service = EvidenceService(
        evidence_repository,
        EvidenceStorage(tmp_path / "evidence", max_bytes=1024 * 1024),
    )
    service = DiagnosticService(
        DiagnosticRepository(db_session),
        AdapterRegistry([SequenceAdapter(["PASS", "PASS", "PASS"])]),
        evidence_service=evidence_service,
    )

    completed = service.execute(service.create(result.id, payload()).id)

    evidence = evidence_repository.list_for_run_result(result.id)
    assert len(evidence) == 3
    assert all(item.category == "LOG" for item in evidence)
    assert [len(attempt.evidence_links) for attempt in completed.attempts] == [1, 1, 1]


def test_service_records_failure_evidence_before_first_attempt(db_session, tmp_path) -> None:
    from app.diagnostics.adapters.huawei import HuaweiSelectorError
    from app.diagnostics.registry import AdapterRegistry
    from app.diagnostics.repository import DiagnosticRepository
    from app.diagnostics.service import DiagnosticService
    from app.evidence.repository import EvidenceRepository
    from app.evidence.service import EvidenceService
    from app.evidence.storage import EvidenceStorage

    class FailingAdapter:
        key = "huawei-ping"
        version = "1"

        @staticmethod
        def supports(snapshot):
            return snapshot.get("vendor") == "Huawei"

        @staticmethod
        def ping(_context, _request):
            raise HuaweiSelectorError(
                "WAN_INTERFACE",
                ("select[name='wanif']", "select[id*='wan']"),
            )

    result = make_result(db_session)
    evidence_repository = EvidenceRepository(db_session)
    storage = EvidenceStorage(tmp_path / "evidence", max_bytes=1024 * 1024)
    service = DiagnosticService(
        DiagnosticRepository(db_session),
        AdapterRegistry([FailingAdapter()]),
        evidence_service=EvidenceService(evidence_repository, storage),
    )
    diagnostic = service.create(result.id, payload(max_attempts_per_layer=1))

    with pytest.raises(HuaweiSelectorError):
        service.execute(diagnostic.id)

    failed = service.get(diagnostic.id)
    evidence = evidence_repository.list_for_run_result(result.id)
    assert failed.status == "FAILED"
    assert failed.error_code == "HUAWEISELECTORERROR"
    assert failed.attempts == []
    assert len(evidence) == 1
    assert evidence[0].original_name == "diagnostic-failure.txt"
    assert "WAN_INTERFACE" in storage.open_path(evidence[0].storage_path).read_text()


def test_failure_evidence_message_redacts_common_secrets() -> None:
    from app.diagnostics.service import DiagnosticService

    message = (
        "http://alice:url-secret@192.168.1.1 "
        "password=form-secret token=token-secret access_token=access-secret "
        "Authorization: Bearer bearer-secret "
        "Cookie: session=cookie-secret; csrf=second-cookie-secret"
    )

    sanitized = DiagnosticService._sanitize_failure_message(message)

    for secret in (
        "alice",
        "url-secret",
        "form-secret",
        "token-secret",
        "access-secret",
        "bearer-secret",
        "cookie-secret",
        "second-cookie-secret",
    ):
        assert secret not in sanitized


def test_failed_session_error_message_is_sanitized(db_session) -> None:
    from app.diagnostics.registry import AdapterRegistry
    from app.diagnostics.repository import DiagnosticRepository
    from app.diagnostics.service import DiagnosticService

    class SecretFailingAdapter:
        key = "huawei-ping"
        version = "1"

        @staticmethod
        def supports(snapshot):
            return snapshot.get("vendor") == "Huawei"

        @staticmethod
        def ping(_context, _request):
            raise RuntimeError(
                "GET http://192.168.1.1/ping?access_token=db-secret "
                "Authorization: Bearer api-secret"
            )

    result = make_result(db_session)
    service = DiagnosticService(
        DiagnosticRepository(db_session),
        AdapterRegistry([SecretFailingAdapter()]),
    )
    diagnostic = service.create(result.id, payload(max_attempts_per_layer=1))

    with pytest.raises(RuntimeError):
        service.execute(diagnostic.id)

    error_message = service.get(diagnostic.id).error_message
    assert "db-secret" not in error_message
    assert "api-secret" not in error_message
    assert "[REDACTED]" in error_message


def test_failure_evidence_storage_error_is_logged_and_original_error_preserved(
    db_session,
    monkeypatch,
) -> None:
    import app.diagnostics.service as service_module

    from app.diagnostics.adapters.huawei import HuaweiSelectorError
    from app.diagnostics.registry import AdapterRegistry
    from app.diagnostics.repository import DiagnosticRepository
    from app.diagnostics.service import DiagnosticService

    class FailingAdapter:
        key = "huawei-ping"
        version = "1"

        @staticmethod
        def supports(snapshot):
            return snapshot.get("vendor") == "Huawei"

        @staticmethod
        def ping(_context, _request):
            raise HuaweiSelectorError("PING_TARGET", ("input[name='pingAddr']",))

    class BrokenEvidenceService:
        @staticmethod
        def create_for_run_result(*_args, **_kwargs):
            raise OSError("evidence disk unavailable")

    result = make_result(db_session)
    service = DiagnosticService(
        DiagnosticRepository(db_session),
        AdapterRegistry([FailingAdapter()]),
        evidence_service=BrokenEvidenceService(),
    )
    diagnostic = service.create(result.id, payload(max_attempts_per_layer=1))
    messages = []
    monkeypatch.setattr(
        service_module.logger,
        "exception",
        lambda message, **_kwargs: messages.append(message),
    )

    with pytest.raises(HuaweiSelectorError):
        service.execute(diagnostic.id)

    assert messages == ["Failed to record diagnostic failure evidence"]
