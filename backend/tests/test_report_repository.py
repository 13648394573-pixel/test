from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.report import Report
from app.models.test_execution import TestProject, TestRun
from app.reports.repository import ReportRepository


def create_run(db_session) -> TestRun:
    project = TestProject(name="Release", version="R1")
    run = TestRun(
        run_no="RUN-000001",
        project=project,
        device_source_id="device-1",
        device_snapshot={"serial_number": "ONU-1"},
        status="COMPLETED",
    )
    db_session.add(run)
    db_session.commit()
    return run


def report_values(run: TestRun, version: int) -> dict:
    return {
        "id": f"report-{version}",
        "report_no": f"RPT-{version:06d}",
        "project_id": run.project_id,
        "test_run_id": run.id,
        "report_version": version,
        "title": "Release report",
        "snapshot_version": 1,
        "report_snapshot": {"summary": {"total": 1}},
        "html_storage_path": f"reports/report-{version}/report.html",
        "html_sha256": "a" * 64,
        "html_file_size": 10,
        "generated_at": datetime(2026, 7, 30, 16, 0, 0),
    }


def test_repository_versions_reports_and_lists_by_run_and_project(
    db_session,
) -> None:
    repository = ReportRepository(db_session)
    run = create_run(db_session)
    first = repository.create_report(report_values(run, 1))

    assert repository.next_report_version(run.id) == 2
    assert repository.get_report(first.id).id == first.id
    assert [item.id for item in repository.list_for_run(run.id)] == [first.id]
    assert [item.id for item in repository.list_for_project(run.project_id)] == [
        first.id
    ]


def test_repository_enforces_one_archive_per_report(db_session) -> None:
    repository = ReportRepository(db_session)
    run = create_run(db_session)
    report = repository.create_report(report_values(run, 1))
    values = {
        "archive_no": "ARC-000001",
        "report_id": report.id,
        "project_id": run.project_id,
        "manifest_snapshot": {"files": []},
        "archive_storage_path": "archives/archive-1.zip",
        "archive_sha256": "b" * 64,
        "archive_file_size": 20,
        "archived_at": datetime(2026, 7, 30, 17, 0, 0),
    }
    archive = repository.create_archive(values)

    assert repository.get_archive_for_report(report.id).id == archive.id
    with pytest.raises(IntegrityError):
        repository.create_archive({**values, "archive_no": "ARC-000002"})
