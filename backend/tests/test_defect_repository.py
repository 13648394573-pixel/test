from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.defects.repository import DefectRepository
from app.test_execution.repository import TestExecutionRepository


def create_result(
    db_session: Session,
    case_source_id: str,
    result: str,
):
    execution_repository = TestExecutionRepository(db_session)
    project = execution_repository.create_project(
        {
            "name": f"Project {case_source_id}",
            "version": "V1",
            "description": None,
        },
        [case_source_id],
    )
    run = execution_repository.create_run(
        project.id,
        f"device-{case_source_id}",
        {"serial_number": f"ONU-{case_source_id}"},
        [
            {
                "case_source_id": case_source_id,
                "case_snapshot": {
                    "case_code": case_source_id.upper(),
                    "title": f"Case {case_source_id}",
                    "device_type": "ONU",
                    "category": "WAN",
                    "priority": "P1",
                    "preconditions": None,
                    "description": None,
                    "enabled": True,
                    "steps": [],
                },
            }
        ],
    )
    return execution_repository.update_result(
        run.results[0],
        result,
        datetime(2026, 7, 30, 9, 0, 0),
        complete_run=True,
    )


def defect_values(source_id: str, *, severity: str = "S2") -> dict:
    return {
        "defect_code": "DEF-000001",
        "source_run_result_id": source_id,
        "title": "WAN address is missing",
        "description": "ONU does not obtain an address",
        "reproduction_steps": "Create the WAN and inspect its address",
        "severity": severity,
        "status": "OPEN",
    }


def test_repository_creates_lists_filters_and_updates_defects(
    db_session: Session,
) -> None:
    source = create_result(db_session, "case-source", "FAIL")
    repository = DefectRepository(db_session)

    assert repository.next_defect_code() == "DEF-000001"
    defect = repository.create_defect(defect_values(source.id))

    assert defect.source_run_result is source
    assert defect.source_run_result.case_snapshot["case_code"] == "CASE-SOURCE"
    assert repository.get_defect(defect.id) is defect
    assert repository.list_defects(status="OPEN", severity="S2") == [defect]
    assert repository.list_defects(status="CLOSED") == []
    assert repository.source_has_defect(source.id) is True
    assert repository.next_defect_code() == "DEF-000002"

    updated = repository.update_defect(
        defect,
        {
            "title": "Updated WAN failure",
            "severity": "S1",
            "status": "IN_PROGRESS",
        },
    )
    assert updated.title == "Updated WAN failure"
    assert updated.severity == "S1"
    assert updated.status == "IN_PROGRESS"


def test_repository_enforces_one_defect_per_source_result(
    db_session: Session,
) -> None:
    source = create_result(db_session, "duplicate-source", "FAIL")
    repository = DefectRepository(db_session)
    repository.create_defect(defect_values(source.id))

    with pytest.raises(IntegrityError):
        repository.create_defect(
            {
                **defect_values(source.id),
                "defect_code": "DEF-000002",
            }
        )

    assert len(repository.list_defects()) == 1


def test_repository_creates_regression_and_updates_defect_atomically(
    db_session: Session,
) -> None:
    source = create_result(db_session, "same-case", "FAIL")
    verification = create_result(db_session, "same-case", "PASS")
    repository = DefectRepository(db_session)
    defect = repository.create_defect(
        {
            **defect_values(source.id),
            "status": "RESOLVED",
            "resolution_notes": "Fixed WAN provisioning",
        }
    )
    closed_at = datetime(2026, 7, 30, 10, 0, 0)

    regression = repository.create_regression(
        defect,
        {
            "verification_run_result_id": verification.id,
            "result": "PASS",
            "notes": "Verified with release build",
            "executed_at": verification.executed_at,
        },
        {"status": "CLOSED", "closed_at": closed_at},
    )

    assert regression.defect is defect
    assert regression.verification_run_result is verification
    assert defect.status == "CLOSED"
    assert defect.closed_at == closed_at
    assert repository.get_defect(defect.id).regressions == [regression]


def test_repository_keeps_regressions_append_only(db_session: Session) -> None:
    source = create_result(db_session, "append-only", "FAIL")
    verification = create_result(db_session, "append-only", "BLOCKED")
    repository = DefectRepository(db_session)
    defect = repository.create_defect(
        {
            **defect_values(source.id),
            "status": "RESOLVED",
            "resolution_notes": "Candidate fix",
        }
    )
    regression = repository.create_regression(
        defect,
        {
            "verification_run_result_id": verification.id,
            "result": "BLOCKED",
            "notes": None,
            "executed_at": verification.executed_at,
        },
        {},
    )

    regression.notes = "Changed"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    persisted = repository.get_defect(defect.id).regressions[0]
    db_session.delete(persisted)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()
