from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.devices.repository import DeviceRepository
from app.models.test_execution import (
    ProjectCaseSelection,
    RunResult,
    TestRun as RunModel,
)
from app.test_cases.repository import TestCaseRepository
from app.test_execution.repository import TestExecutionRepository
from app.test_execution.snapshots import (
    build_case_snapshot,
    build_device_snapshot,
)


DEVICE_DATA = {
    "device_type": "ONU",
    "vendor": "Huawei",
    "model": "HN8546X6",
    "serial_number": "EXEC-ONU-001",
    "mac_address": "00:11:22:33:44:55",
    "hardware_version": "V1",
    "software_version": "V5R020",
}
CASE_DATA = {
    "case_code": "EXEC-WAN-001",
    "title": "Verify IPoE WAN",
    "device_type": "ONU",
    "category": "WAN",
    "priority": "P1",
    "preconditions": "ONU is registered",
    "description": "Manual WAN verification",
    "enabled": True,
}
STEPS = [
    {
        "step_number": 1,
        "action": "Create the WAN",
        "expected_result": "WAN obtains an address",
    },
    {
        "step_number": 2,
        "action": "Ping the gateway",
        "expected_result": "Ping succeeds",
    },
]


def create_sources(db_session: Session):
    device_repository = DeviceRepository(db_session)
    case_repository = TestCaseRepository(db_session)
    device = device_repository.create(DEVICE_DATA)
    test_case = case_repository.create(CASE_DATA, STEPS)
    return device_repository, case_repository, device, test_case


def test_snapshot_builders_copy_device_and_ordered_case_steps(
    db_session: Session,
) -> None:
    device_repository, case_repository, device, test_case = create_sources(
        db_session
    )

    device_snapshot = build_device_snapshot(device)
    case_snapshot = build_case_snapshot(test_case)
    device_repository.update(device, {"software_version": "V5R021"})
    case_repository.update(
        test_case,
        {"title": "Changed title"},
        [
            {
                "step_number": 1,
                "action": "Changed action",
                "expected_result": "Changed result",
            }
        ],
    )

    assert device_snapshot == {
        "device_type": "ONU",
        "vendor": "Huawei",
        "model": "HN8546X6",
        "serial_number": "EXEC-ONU-001",
        "mac_address": "00:11:22:33:44:55",
        "hardware_version": "V1",
        "software_version": "V5R020",
    }
    assert case_snapshot["title"] == "Verify IPoE WAN"
    assert case_snapshot["steps"] == [
        {
            "step_number": 1,
            "action": "Create the WAN",
            "expected_result": "WAN obtains an address",
        },
        {
            "step_number": 2,
            "action": "Ping the gateway",
            "expected_result": "Ping succeeds",
        },
    ]


def test_repository_supports_project_crud_and_replaces_case_selections(
    db_session: Session,
) -> None:
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": "Release acceptance", "version": "V1", "description": None},
        ["case-b", "case-a"],
    )

    assert [item.case_source_id for item in project.case_selections] == [
        "case-a",
        "case-b",
    ]
    assert repository.list_projects() == [project]
    assert repository.get_project(project.id) is project

    updated = repository.update_project(
        project,
        {"name": "Updated acceptance", "version": "V2", "description": "Scope"},
        ["case-c"],
    )
    assert updated.name == "Updated acceptance"
    assert [item.case_source_id for item in updated.case_selections] == ["case-c"]

    repository.delete_project(updated)
    assert repository.get_project(project.id) is None
    assert (
        db_session.scalar(
            select(func.count()).select_from(ProjectCaseSelection)
        )
        == 0
    )


def test_repository_creates_run_and_results_in_one_transaction(
    db_session: Session,
) -> None:
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": "Acceptance", "version": "V1", "description": None},
        ["case-1", "case-2"],
    )

    run = repository.create_run(
        project.id,
        "device-1",
        {"serial_number": "ONU-001"},
        [
            {
                "case_source_id": "case-1",
                "case_snapshot": {"case_code": "CASE-1", "steps": []},
            },
            {
                "case_source_id": "case-2",
                "case_snapshot": {"case_code": "CASE-2", "steps": []},
            },
        ],
    )

    assert run.snapshot_version == 1
    assert run.device_snapshot == {"serial_number": "ONU-001"}
    assert len(run.results) == 2
    assert all(item.snapshot_version == 1 for item in run.results)
    assert repository.get_run(run.id) is run
    assert repository.list_runs(project.id) == [run]
    assert repository.project_has_runs(project.id) is True

    with pytest.raises(ValueError):
        run.device_snapshot = {"serial_number": "CHANGED"}
    with pytest.raises(ValueError):
        run.results[0].case_snapshot = {"case_code": "CHANGED"}
    with pytest.raises(ValueError):
        run.results[0].snapshot_version = 2


def test_repository_rolls_back_run_when_result_creation_fails(
    db_session: Session,
) -> None:
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": "Acceptance", "version": "V1", "description": None},
        ["case-1"],
    )
    duplicate_results = [
        {
            "case_source_id": "case-1",
            "case_snapshot": {"case_code": "CASE-1", "steps": []},
        },
        {
            "case_source_id": "case-1",
            "case_snapshot": {"case_code": "CASE-1", "steps": []},
        },
    ]

    with pytest.raises(IntegrityError):
        repository.create_run(
            project.id,
            "device-1",
            {"serial_number": "ONU-001"},
            duplicate_results,
        )

    assert db_session.scalar(select(func.count()).select_from(RunModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(RunResult)) == 0


def test_repository_saves_draft_then_locks_and_completes_run(
    db_session: Session,
) -> None:
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": "Acceptance", "version": "V1", "description": None},
        ["case-1"],
    )
    run = repository.create_run(
        project.id,
        "device-1",
        {"serial_number": "ONU-001"},
        [
            {
                "case_source_id": "case-1",
                "case_snapshot": {"case_code": "CASE-1", "steps": []},
            }
        ],
    )
    executed_at = datetime(2026, 7, 29, 12, 0, 0)

    updated = repository.update_result_draft(
        run.results[0],
        {
            "result": "BLOCKED",
            "actual_result": "WAN did not connect",
            "blocked_reason": "OLT profile unavailable",
            "test_notes": "Retry after provisioning",
        },
    )

    assert updated.result == "BLOCKED"
    assert updated.actual_result == "WAN did not connect"
    assert updated.integrity_status == "DRAFT"
    assert updated.executed_at is None
    assert run.status == "IN_PROGRESS"

    locked = repository.lock_result(
        updated,
        executed_at,
        complete_run=True,
    )

    assert locked.integrity_status == "LOCKED"
    assert locked.executed_at == executed_at
    assert locked.locked_at == executed_at
    assert run.status == "COMPLETED"
    assert run.finished_at == executed_at


def test_repository_rejects_locked_result_and_snapshot_mutation(
    db_session: Session,
) -> None:
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": "Acceptance", "version": "V1", "description": None},
        ["case-1"],
    )
    run = repository.create_run(
        project.id,
        "device-1",
        {"serial_number": "ONU-001"},
        [
            {
                "case_source_id": "case-1",
                "case_snapshot": {"case_code": "CASE-1", "steps": []},
            }
        ],
    )
    result = repository.update_result_draft(
        run.results[0],
        {"result": "PASS", "actual_result": None},
    )
    repository.lock_result(result, datetime(2026, 7, 30), complete_run=True)

    with pytest.raises(ValueError, match="Locked results are immutable"):
        result.actual_result = "changed"
    with pytest.raises(ValueError, match="Snapshots are immutable"):
        result.case_snapshot = {"case_code": "CHANGED"}
