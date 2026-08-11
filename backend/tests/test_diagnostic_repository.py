from datetime import datetime
from decimal import Decimal

from app.models.test_execution import RunResult, TestProject, TestRun


def make_result(db_session) -> RunResult:
    project = TestProject(name="Repo", version="1", description=None)
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
    )
    db_session.add(project)
    db_session.commit()
    return result


def test_repository_creates_and_lists_sessions_newest_first(db_session) -> None:
    from app.diagnostics.repository import DiagnosticRepository

    result = make_result(db_session)
    repository = DiagnosticRepository(db_session)
    first = repository.create_session(
        result.id, "huawei-ping", "1", "IPOE", {"layers": ["GATEWAY"]}
    )
    repository.mark_terminal(first, "COMPLETED", datetime(2026, 8, 8, 10, 0))
    second = repository.create_session(
        result.id, "huawei-ping", "1", "PPPOE", {"layers": ["DOMAIN"]}
    )

    assert [item.id for item in repository.list_for_result(result.id)] == [second.id, first.id]
    assert repository.get_active_for_result(result.id).id == second.id


def test_repository_appends_attempt_and_transitions_session(db_session) -> None:
    from app.diagnostics.repository import DiagnosticRepository

    result = make_result(db_session)
    repository = DiagnosticRepository(db_session)
    diagnostic = repository.create_session(
        result.id, "huawei-ping", "1", "IPOE", {"layers": ["GATEWAY"]}
    )
    repository.mark_running(diagnostic, datetime(2026, 8, 8, 10, 0))
    attempt = repository.append_attempt(
        diagnostic,
        {
            "sequence": 1,
            "layer": "GATEWAY",
            "target": "192.168.1.1",
            "attempt_number": 1,
            "status": "PASS",
            "packets_sent": 3,
            "packets_received": 3,
            "loss_percent": Decimal("0"),
            "latency_min_ms": Decimal("1"),
            "latency_avg_ms": Decimal("2"),
            "latency_max_ms": Decimal("3"),
            "raw_output": "ok",
            "error_code": None,
            "started_at": datetime(2026, 8, 8, 10, 0),
            "finished_at": datetime(2026, 8, 8, 10, 0, 1),
        },
    )
    repository.mark_terminal(diagnostic, "COMPLETED", datetime(2026, 8, 8, 10, 0, 2))

    loaded = repository.get_session(diagnostic.id)
    assert loaded.status == "COMPLETED"
    assert loaded.started_at == datetime(2026, 8, 8, 10, 0)
    assert loaded.attempts[0].id == attempt.id
    assert loaded.attempts[0].packets_received == 3
