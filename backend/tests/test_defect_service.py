from copy import deepcopy
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.defects.repository import DefectRepository
from app.defects.service import (
    ClosedDefectError,
    DefectService,
    DuplicateDefectSourceError,
    DuplicateRegressionError,
    InvalidDefectSourceError,
    InvalidDefectTransitionError,
    InvalidRegressionEvidenceError,
)
from app.test_execution.repository import TestExecutionRepository


NOW = datetime(2026, 7, 30, 12, 0, 0)


def create_result(
    db_session: Session,
    suffix: str,
    case_source_id: str,
    result: str | None,
):
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": f"Project {suffix}", "version": "V1", "description": None},
        [case_source_id],
    )
    run = repository.create_run(
        project.id,
        f"device-{suffix}",
        {"serial_number": f"ONU-{suffix}"},
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
    if result is None:
        return run.results[0]
    draft = repository.update_result_draft(
        run.results[0],
        {
            "result": result,
            "actual_result": "Observed failure" if result == "FAIL" else None,
            "blocked_reason": "Lab unavailable" if result == "BLOCKED" else None,
        },
    )
    return repository.lock_result(
        draft,
        datetime(2026, 7, 30, 9, 0, 0),
        complete_run=True,
    )


def create_payload(source_id: str) -> dict:
    return {
        "source_run_result_id": source_id,
        "title": "WAN address is missing",
        "description": "ONU does not obtain an address",
        "reproduction_steps": "Create the WAN and inspect its address",
        "severity": "S2",
    }


def service(db_session: Session) -> DefectService:
    return DefectService(DefectRepository(db_session), clock=lambda: NOW)


@pytest.mark.parametrize("result", ["FAIL", "BLOCKED"])
def test_service_creates_defect_only_from_failure_evidence(
    db_session: Session,
    result: str,
) -> None:
    source = create_result(db_session, result.lower(), "case-wan", result)
    original_snapshot = deepcopy(source.case_snapshot)
    original_result = source.result
    defects = service(db_session)

    defect = defects.create_defect(create_payload(source.id))

    assert defect.defect_code == "DEF-000001"
    assert defect.status == "OPEN"
    assert defect.source_run_result_id == source.id
    assert source.result == original_result
    assert source.case_snapshot == original_snapshot

    with pytest.raises(DuplicateDefectSourceError):
        defects.create_defect(create_payload(source.id))


@pytest.mark.parametrize("result", [None, "PASS"])
def test_service_rejects_non_failure_source(
    db_session: Session,
    result: str | None,
) -> None:
    source = create_result(db_session, str(result), "case-wan", result)

    with pytest.raises(InvalidDefectSourceError):
        service(db_session).create_defect(create_payload(source.id))


def test_service_rejects_unlocked_failure_source(db_session: Session) -> None:
    source = create_result(db_session, "draft", "case-wan", None)
    source = TestExecutionRepository(db_session).update_result_draft(
        source,
        {"result": "FAIL", "actual_result": "No address"},
    )

    with pytest.raises(InvalidDefectSourceError):
        service(db_session).create_defect(create_payload(source.id))


def test_service_updates_open_defect_but_keeps_closed_defect_read_only(
    db_session: Session,
) -> None:
    source = create_result(db_session, "update", "case-wan", "FAIL")
    defects = service(db_session)
    defect = defects.create_defect(create_payload(source.id))

    updated = defects.update_defect(
        defect.id,
        {
            "title": "Updated WAN issue",
            "description": "Updated description",
            "reproduction_steps": "Updated steps",
            "severity": "S1",
        },
    )
    assert updated.title == "Updated WAN issue"
    defects.transition(defect.id, "IN_PROGRESS")
    defects.transition(defect.id, "RESOLVED", "Fixed in candidate")
    verification = create_result(db_session, "close", "case-wan", "PASS")
    defects.create_regression(defect.id, verification.id, "Verified")

    with pytest.raises(ClosedDefectError):
        defects.update_defect(defect.id, {"title": "Forbidden"})


def test_service_enforces_manual_state_machine(db_session: Session) -> None:
    source = create_result(db_session, "states", "case-wan", "FAIL")
    defects = service(db_session)
    defect = defects.create_defect(create_payload(source.id))

    with pytest.raises(InvalidDefectTransitionError):
        defects.transition(defect.id, "RESOLVED", "Skipped work")

    assert defects.transition(defect.id, "IN_PROGRESS").status == "IN_PROGRESS"
    with pytest.raises(InvalidDefectTransitionError):
        defects.transition(defect.id, "RESOLVED", " ")

    resolved = defects.transition(defect.id, "RESOLVED", "Fixed provisioning")
    assert resolved.status == "RESOLVED"
    assert resolved.resolution_notes == "Fixed provisioning"
    assert resolved.resolved_at == NOW


@pytest.mark.parametrize(
    ("regression_result", "expected_status"),
    [
        ("PASS", "CLOSED"),
        ("FAIL", "REOPENED"),
        ("BLOCKED", "RESOLVED"),
    ],
)
def test_service_applies_regression_outcomes(
    db_session: Session,
    regression_result: str,
    expected_status: str,
) -> None:
    source = create_result(
        db_session,
        f"source-{regression_result}",
        "case-wan",
        "FAIL",
    )
    verification = create_result(
        db_session,
        f"verify-{regression_result}",
        "case-wan",
        regression_result,
    )
    defects = service(db_session)
    defect = defects.create_defect(create_payload(source.id))
    defects.transition(defect.id, "IN_PROGRESS")
    defects.transition(defect.id, "RESOLVED", "Fixed")
    original_snapshot = deepcopy(verification.case_snapshot)

    regression = defects.create_regression(
        defect.id,
        verification.id,
        "Manual verification",
    )
    refreshed = defects.get_defect(defect.id)

    assert regression.result == regression_result
    assert refreshed.status == expected_status
    assert len(refreshed.regressions) == 1
    assert verification.result == regression_result
    assert verification.case_snapshot == original_snapshot
    if regression_result == "PASS":
        assert refreshed.closed_at == NOW
    else:
        assert refreshed.closed_at is None


def test_service_rejects_invalid_or_duplicate_regression_evidence(
    db_session: Session,
) -> None:
    source = create_result(db_session, "source", "case-wan", "FAIL")
    wrong_case = create_result(db_session, "wrong", "case-voip", "PASS")
    pending = create_result(db_session, "pending", "case-wan", None)
    valid = create_result(db_session, "valid", "case-wan", "BLOCKED")
    defects = service(db_session)
    defect = defects.create_defect(create_payload(source.id))

    with pytest.raises(InvalidDefectTransitionError):
        defects.create_regression(defect.id, valid.id, None)

    defects.transition(defect.id, "IN_PROGRESS")
    defects.transition(defect.id, "RESOLVED", "Fixed")
    with pytest.raises(InvalidRegressionEvidenceError):
        defects.create_regression(defect.id, wrong_case.id, None)
    with pytest.raises(InvalidRegressionEvidenceError):
        defects.create_regression(defect.id, pending.id, None)

    defects.create_regression(defect.id, valid.id, None)
    with pytest.raises(DuplicateRegressionError):
        defects.create_regression(defect.id, valid.id, None)
