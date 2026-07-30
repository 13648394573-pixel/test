from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.devices.repository import DeviceRepository
from app.test_cases.repository import TestCaseRepository
from app.test_execution.repository import TestExecutionRepository
from app.test_execution.service import (
    InvalidCaseSourceError,
    InvalidDeviceSourceError,
    InvalidResultValueError,
    ProjectHasRunsError,
    RunResultNotFoundError,
    TestExecutionService,
    TestProjectNotFoundError,
    TestRunNotFoundError,
)


DEVICE_DATA = {
    "device_type": "ONU",
    "vendor": "Huawei",
    "model": "HN8546X6",
    "serial_number": "SERVICE-ONU-001",
    "mac_address": None,
    "hardware_version": "V1",
    "software_version": "V5R020",
}
CASE_DATA = {
    "case_code": "SERVICE-WAN-001",
    "title": "Verify WAN",
    "device_type": "ONU",
    "category": "WAN",
    "priority": "P1",
    "preconditions": None,
    "description": None,
    "enabled": True,
}
STEPS = [
    {
        "step_number": 1,
        "action": "Create WAN",
        "expected_result": "WAN is connected",
    }
]
NOW = datetime(2026, 7, 29, 14, 0, 0)


def build_service(db_session: Session):
    device_repository = DeviceRepository(db_session)
    case_repository = TestCaseRepository(db_session)
    service = TestExecutionService(
        TestExecutionRepository(db_session),
        device_repository,
        case_repository,
        clock=lambda: NOW,
    )
    return service, device_repository, case_repository


def test_service_validates_project_case_sources(db_session: Session) -> None:
    service, _device_repository, case_repository = build_service(db_session)
    enabled_case = case_repository.create(CASE_DATA, STEPS)
    disabled_case = case_repository.create(
        {**CASE_DATA, "case_code": "SERVICE-WAN-002", "enabled": False},
        STEPS,
    )

    created = service.create_project(
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [enabled_case.id],
        }
    )
    assert created.name == "Acceptance"

    with pytest.raises(InvalidCaseSourceError):
        service.create_project(
            {
                "name": "Missing",
                "version": "V1",
                "description": None,
                "case_source_ids": ["missing"],
            }
        )
    with pytest.raises(InvalidCaseSourceError):
        service.update_project(
            created.id,
            {
                "name": "Disabled",
                "version": "V1",
                "description": None,
                "case_source_ids": [disabled_case.id],
            },
        )


def test_service_creates_versioned_snapshots_at_run_creation(
    db_session: Session,
) -> None:
    service, device_repository, case_repository = build_service(db_session)
    device = device_repository.create(DEVICE_DATA)
    test_case = case_repository.create(CASE_DATA, STEPS)
    project = service.create_project(
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [test_case.id],
        }
    )

    run = service.create_run(project.id, device.id)
    device_repository.update(device, {"software_version": "V5R021"})
    case_repository.update(
        test_case,
        {"title": "Changed title"},
        [
            {
                "step_number": 1,
                "action": "Changed",
                "expected_result": "Changed",
            }
        ],
    )
    historical = service.get_run(run.id)

    assert historical.snapshot_version == 1
    assert historical.device_snapshot["software_version"] == "V5R020"
    assert historical.results[0].snapshot_version == 1
    assert historical.results[0].case_snapshot["title"] == "Verify WAN"
    assert historical.results[0].case_snapshot["steps"][0]["action"] == "Create WAN"


def test_service_rejects_missing_device_and_missing_selected_case(
    db_session: Session,
) -> None:
    service, device_repository, case_repository = build_service(db_session)
    test_case = case_repository.create(CASE_DATA, STEPS)
    project = service.create_project(
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [test_case.id],
        }
    )

    with pytest.raises(InvalidDeviceSourceError):
        service.create_run(project.id, "missing")

    device = device_repository.create(DEVICE_DATA)
    case_repository.delete(test_case)
    with pytest.raises(InvalidCaseSourceError):
        service.create_run(project.id, device.id)


def test_service_saves_blocked_and_completes_when_all_results_exist(
    db_session: Session,
) -> None:
    service, device_repository, case_repository = build_service(db_session)
    device = device_repository.create(DEVICE_DATA)
    first = case_repository.create(CASE_DATA, STEPS)
    second = case_repository.create(
        {**CASE_DATA, "case_code": "SERVICE-WAN-002"},
        STEPS,
    )
    project = service.create_project(
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [first.id, second.id],
        }
    )
    run = service.create_run(project.id, device.id)

    first_result = service.update_result(run.id, run.results[0].id, "BLOCKED")
    assert first_result.result == "BLOCKED"
    assert run.status == "IN_PROGRESS"
    assert run.finished_at is None

    service.update_result(run.id, run.results[1].id, "PASS")
    assert run.status == "COMPLETED"
    assert run.finished_at == NOW

    with pytest.raises(InvalidResultValueError):
        service.update_result(run.id, run.results[0].id, "SKIPPED")


def test_service_preserves_history_and_reports_missing_resources(
    db_session: Session,
) -> None:
    service, device_repository, case_repository = build_service(db_session)
    device = device_repository.create(DEVICE_DATA)
    test_case = case_repository.create(CASE_DATA, STEPS)
    project = service.create_project(
        {
            "name": "Acceptance",
            "version": "V1",
            "description": None,
            "case_source_ids": [test_case.id],
        }
    )
    run = service.create_run(project.id, device.id)

    with pytest.raises(ProjectHasRunsError):
        service.delete_project(project.id)
    assert service.list_runs(project.id) == [run]

    with pytest.raises(TestProjectNotFoundError):
        service.get_project("missing")
    with pytest.raises(TestRunNotFoundError):
        service.get_run("missing")
    with pytest.raises(RunResultNotFoundError):
        service.update_result(run.id, "missing", "FAIL")
