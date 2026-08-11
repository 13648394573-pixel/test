from datetime import UTC, datetime
from decimal import Decimal

import pytest


def test_diagnostic_models_expose_expected_tables() -> None:
    from app.models.diagnostic import (
        DiagnosticAttempt,
        DiagnosticAttemptEvidence,
        DiagnosticSession,
    )

    assert DiagnosticSession.__tablename__ == "diagnostic_sessions"
    assert DiagnosticAttempt.__tablename__ == "diagnostic_attempts"
    assert DiagnosticAttemptEvidence.__tablename__ == "diagnostic_attempt_evidences"


def test_policy_snapshot_is_immutable() -> None:
    from app.models.diagnostic import DiagnosticSession

    session = DiagnosticSession(
        run_result_id="result-1",
        adapter_key="huawei-ping",
        adapter_version="1",
        wan_mode="IPOE",
        policy_snapshot={"layers": ["GATEWAY"]},
    )
    with pytest.raises(ValueError, match="Diagnostic policy snapshot is immutable"):
        session.policy_snapshot = {"layers": ["DOMAIN"]}


def test_attempt_rejects_updates_after_persistence(db_session) -> None:
    from app.models.diagnostic import DiagnosticAttempt, DiagnosticSession
    from app.models.test_execution import RunResult, TestProject, TestRun

    project = TestProject(name="P", version="1", description=None)
    run = TestRun(
        run_no="RUN-000001",
        project=project,
        device_source_id="device-1",
        device_snapshot={"vendor": "Huawei", "model": "ONT"},
    )
    result = RunResult(
        run=run,
        case_source_id="case-1",
        case_snapshot={"case_code": "PING"},
    )
    diagnostic = DiagnosticSession(
        run_result_id=result.id,
        adapter_key="huawei-ping",
        adapter_version="1",
        wan_mode="IPOE",
        policy_snapshot={"layers": ["GATEWAY"]},
    )
    diagnostic.run_result = result
    attempt = DiagnosticAttempt(
        session=diagnostic,
        sequence=1,
        layer="GATEWAY",
        target="192.168.1.1",
        attempt_number=1,
        status="PASS",
        packets_sent=3,
        packets_received=3,
        loss_percent=Decimal("0"),
        latency_avg_ms=Decimal("1.2"),
        raw_output="3 packets received",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        finished_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(project)
    db_session.add(attempt)
    db_session.commit()

    attempt.raw_output = "changed"
    with pytest.raises(ValueError, match="Diagnostic attempts are append-only"):
        db_session.commit()
