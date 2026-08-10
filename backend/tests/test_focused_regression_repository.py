from datetime import datetime
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.defect import Defect
from app.models.environment import RunEnvironmentSnapshot
from app.models.test_execution import RunResult, TestProject, TestRun


def make_source(db_session):
    project = TestProject(name="Focused", version="1.0", description=None)
    source_run = TestRun(
        project=project,
        device_source_id="device-old",
        device_snapshot={"serial_number": "OLD-ONU"},
        status="COMPLETED",
        finished_at=datetime(2026, 8, 9, 10, 0),
    )
    source_result = RunResult(
        run=source_run,
        case_source_id="case-1",
        case_snapshot={"case_code": "WAN-001", "steps": []},
        result="FAIL",
        integrity_status="LOCKED",
        executed_at=datetime(2026, 8, 9, 10, 0),
        locked_at=datetime(2026, 8, 9, 10, 0),
    )
    defect = Defect(
        defect_code="DEF-000001",
        source_run_result=source_result,
        title="WAN connection failed",
        description="No address",
        reproduction_steps="Create WAN",
        severity="S2",
        status="RESOLVED",
        resolution_notes="Profile corrected",
        resolved_at=datetime(2026, 8, 9, 11, 0),
    )
    db_session.add(defect)
    db_session.commit()
    return project, source_result, defect


def create_values(project, source_result, defect):
    return {
        "project_id": project.id,
        "device_source_id": "device-new",
        "device_snapshot": {"serial_number": "NEW-ONU"},
        "environment_profile_source_id": "environment-1",
        "environment_snapshot": {
            "name": "OLT Lab",
            "captured_at": "2026-08-10T10:00:00",
            "parameters": [],
        },
        "case_source_id": source_result.case_source_id,
        "case_snapshot": dict(source_result.case_snapshot),
        "defect_id": defect.id,
        "source_run_result_id": source_result.id,
        "defect_snapshot": {
            "defect_code": defect.defect_code,
            "status": defect.status,
            "captured_at": "2026-08-10T10:00:00",
        },
    }


def test_model_rejects_focused_regression_snapshot_mutation() -> None:
    from app.models.focused_regression import FocusedRegressionRun

    focused = FocusedRegressionRun(
        test_run_id="run-1",
        defect_id="defect-1",
        source_run_result_id="result-1",
        defect_snapshot={"defect_code": "DEF-000001"},
    )

    with pytest.raises(ValueError, match="Focused regression snapshot is immutable"):
        focused.defect_snapshot = {"defect_code": "CHANGED"}
    with pytest.raises(ValueError, match="Focused regression snapshot is immutable"):
        focused.snapshot_version = 2


def test_repository_creates_run_result_and_association_atomically(db_session) -> None:
    from app.focused_regressions.repository import FocusedRegressionRepository

    project, source_result, defect = make_source(db_session)
    repository = FocusedRegressionRepository(db_session)

    focused = repository.create_run(**create_values(project, source_result, defect))

    assert focused.defect_id == defect.id
    assert focused.source_run_result_id == source_result.id
    assert focused.snapshot_version == 1
    assert focused.test_run.status == "IN_PROGRESS"
    assert focused.test_run.device_snapshot == {"serial_number": "NEW-ONU"}
    assert len(focused.test_run.results) == 1
    assert focused.test_run.results[0].case_snapshot == source_result.case_snapshot
    assert focused.test_run.results[0].integrity_status == "DRAFT"
    assert focused.test_run.environment_snapshot.profile_snapshot["name"] == "OLT Lab"
    assert repository.get_by_run_id(focused.test_run_id).id == focused.id


def test_repository_lists_newest_first_and_finds_active_run(db_session) -> None:
    from app.focused_regressions.repository import FocusedRegressionRepository

    project, source_result, defect = make_source(db_session)
    repository = FocusedRegressionRepository(db_session)
    first = repository.create_run(**create_values(project, source_result, defect))
    first.test_run.status = "COMPLETED"
    db_session.commit()
    time.sleep(1.1)
    second = repository.create_run(**create_values(project, source_result, defect))

    assert [item.id for item in repository.list_for_defect(defect.id)] == [
        second.id,
        first.id,
    ]
    assert repository.get_active_for_defect(defect.id).id == second.id


def test_repository_rolls_back_all_records_on_association_failure(db_session) -> None:
    from app.focused_regressions.repository import FocusedRegressionRepository
    from app.models.focused_regression import FocusedRegressionRun

    project, source_result, defect = make_source(db_session)
    repository = FocusedRegressionRepository(db_session)
    values = create_values(project, source_result, defect)
    first = repository.create_run(**values)
    run_count = db_session.scalar(select(func.count()).select_from(TestRun))
    result_count = db_session.scalar(select(func.count()).select_from(RunResult))
    focused_count = db_session.scalar(
        select(func.count()).select_from(FocusedRegressionRun)
    )

    invalid_values = {**values, "defect_id": "missing-defect"}
    with pytest.raises(IntegrityError):
        repository.create_run(**invalid_values)

    assert db_session.scalar(select(func.count()).select_from(TestRun)) == run_count
    assert db_session.scalar(select(func.count()).select_from(RunResult)) == result_count
    assert (
        db_session.scalar(select(func.count()).select_from(FocusedRegressionRun))
        == focused_count
    )
    assert db_session.scalar(select(func.count()).select_from(RunEnvironmentSnapshot)) == 1
