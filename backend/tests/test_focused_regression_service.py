from copy import deepcopy
from datetime import datetime

import pytest

from app.devices.repository import DeviceRepository
from app.environments.repository import EnvironmentRepository
from app.environments.service import EnvironmentService
from app.models.defect import Defect, Regression
from app.test_execution.repository import TestExecutionRepository


NOW = datetime(2026, 8, 10, 12, 30)


def create_locked_result(db_session, suffix: str, result: str):
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": f"Project {suffix}", "version": "1.0", "description": None},
        ["case-wan"],
    )
    run = repository.create_run(
        project.id,
        f"device-{suffix}",
        {"serial_number": f"OLD-{suffix}"},
        [
            {
                "case_source_id": "case-wan",
                "case_snapshot": {
                    "case_code": "WAN-001",
                    "title": "Verify WAN",
                    "steps": [{"step_number": 1, "action": "Connect"}],
                },
            }
        ],
    )
    values = {
        "result": result,
        "actual_result": "No address" if result == "FAIL" else None,
        "blocked_reason": "Lab blocked" if result == "BLOCKED" else None,
    }
    draft = repository.update_result_draft(run.results[0], values)
    return repository.lock_result(draft, NOW, complete_run=True)


def create_context(db_session):
    source = create_locked_result(db_session, "source", "FAIL")
    defect = Defect(
        defect_code="DEF-000001",
        source_run_result=source,
        title="WAN connection failed",
        description="No address",
        reproduction_steps="Connect WAN",
        severity="S2",
        status="RESOLVED",
        resolution_notes="OLT profile corrected",
        resolved_at=NOW,
    )
    db_session.add(defect)
    db_session.commit()
    device = DeviceRepository(db_session).create(
        {
            "device_type": "ONU",
            "vendor": "Huawei",
            "model": "HN8546X6",
            "serial_number": "NEW-ONU-001",
            "mac_address": "00:11:22:33:44:55",
            "hardware_version": "V1",
            "software_version": "V2",
        }
    )
    environments = EnvironmentService(EnvironmentRepository(db_session))
    profile = environments.create_profile(
        {
            "name": "OLT Lab",
            "description": "MA5800",
            "enabled": True,
            "parameters": [
                {
                    "section": "OLT",
                    "param_key": "pon_port",
                    "param_value": "0/1/0",
                    "display_order": 1,
                }
            ],
        }
    )
    return source, defect, device, profile, environments


def service(db_session, environments):
    from app.defects.repository import DefectRepository
    from app.focused_regressions.repository import FocusedRegressionRepository
    from app.focused_regressions.service import FocusedRegressionService

    return FocusedRegressionService(
        FocusedRegressionRepository(db_session),
        DefectRepository(db_session),
        DeviceRepository(db_session),
        environments,
        clock=lambda: NOW,
    )


def test_service_creates_new_run_with_fresh_and_copied_snapshots(db_session) -> None:
    source, defect, device, profile, environments = create_context(db_session)
    original_case_snapshot = deepcopy(source.case_snapshot)
    original_device_snapshot = deepcopy(source.run.device_snapshot)
    focused_service = service(db_session, environments)

    focused = focused_service.create_run(
        defect.id,
        device.id,
        profile.id,
        source_run_result_id=None,
    )

    assert focused.test_run_id != source.run_id
    assert focused.test_run.project_id == source.run.project_id
    assert focused.test_run.device_snapshot["serial_number"] == "NEW-ONU-001"
    assert focused.test_run.results[0].case_snapshot == original_case_snapshot
    assert focused.test_run.results[0].id != source.id
    assert focused.test_run.results[0].integrity_status == "DRAFT"
    assert focused.test_run.environment_snapshot.profile_snapshot["captured_at"] == (
        "2026-08-10T12:30:00"
    )
    assert focused.defect_snapshot == {
        "defect_code": "DEF-000001",
        "title": "WAN connection failed",
        "severity": "S2",
        "status": "RESOLVED",
        "resolution_notes": "OLT profile corrected",
        "source_run_result_id": source.id,
        "captured_at": "2026-08-10T12:30:00",
    }
    assert source.case_snapshot == original_case_snapshot
    assert source.run.device_snapshot == original_device_snapshot
    with pytest.raises(ValueError, match="Locked results cannot be unlocked"):
        source.integrity_status = "DRAFT"
    with pytest.raises(ValueError, match="Focused regression snapshot is immutable"):
        focused.defect_snapshot = {"status": "CHANGED"}


def test_service_rejects_unresolved_defect_and_active_duplicate(db_session) -> None:
    _source, defect, device, profile, environments = create_context(db_session)
    focused_service = service(db_session, environments)
    defect.status = "IN_PROGRESS"
    db_session.commit()

    from app.focused_regressions.service import (
        ActiveFocusedRegressionExistsError,
        InvalidFocusedRegressionStateError,
    )

    with pytest.raises(InvalidFocusedRegressionStateError):
        focused_service.create_run(defect.id, device.id, profile.id)

    defect.status = "RESOLVED"
    db_session.commit()
    focused_service.create_run(defect.id, device.id, profile.id)
    with pytest.raises(ActiveFocusedRegressionExistsError):
        focused_service.create_run(defect.id, device.id, profile.id)


def test_service_accepts_failed_regression_source_from_same_defect(db_session) -> None:
    _source, defect, device, profile, environments = create_context(db_session)
    failed_regression_result = create_locked_result(db_session, "retry", "BLOCKED")
    regression = Regression(
        defect=defect,
        verification_run_result=failed_regression_result,
        result="BLOCKED",
        notes="Still blocked",
        executed_at=NOW,
    )
    db_session.add(regression)
    db_session.commit()

    focused = service(db_session, environments).create_run(
        defect.id,
        device.id,
        profile.id,
        source_run_result_id=failed_regression_result.id,
    )

    assert focused.source_run_result_id == failed_regression_result.id
    assert focused.test_run.project_id == failed_regression_result.run.project_id


def test_service_rejects_pass_or_cross_defect_source(db_session) -> None:
    _source, defect, device, profile, environments = create_context(db_session)
    pass_result = create_locked_result(db_session, "pass", "PASS")
    failed_other = create_locked_result(db_session, "other", "FAIL")
    defect.regressions.append(
        Regression(
            verification_run_result=pass_result,
            result="PASS",
            executed_at=NOW,
        )
    )
    db_session.commit()

    from app.focused_regressions.service import InvalidFocusedRegressionSourceError

    focused_service = service(db_session, environments)
    with pytest.raises(InvalidFocusedRegressionSourceError):
        focused_service.create_run(
            defect.id,
            device.id,
            profile.id,
            source_run_result_id=pass_result.id,
        )
    with pytest.raises(InvalidFocusedRegressionSourceError):
        focused_service.create_run(
            defect.id,
            device.id,
            profile.id,
            source_run_result_id=failed_other.id,
        )


def test_service_lists_history_and_gets_run(db_session) -> None:
    _source, defect, device, profile, environments = create_context(db_session)
    focused_service = service(db_session, environments)
    focused = focused_service.create_run(defect.id, device.id, profile.id)

    assert focused_service.list_for_defect(defect.id)[0].id == focused.id
    assert focused_service.get_run(focused.test_run_id).id == focused.id

    from app.focused_regressions.service import FocusedRegressionNotFoundError

    with pytest.raises(FocusedRegressionNotFoundError):
        focused_service.get_run("missing")
