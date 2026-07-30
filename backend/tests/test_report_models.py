import pytest

from app.models.report import Archive, Report


def test_report_is_immutable() -> None:
    report = Report(
        report_no="RPT-000001",
        project_id="project-1",
        test_run_id="run-1",
        report_version=1,
        title="Acceptance",
        report_snapshot={"summary": {"total": 1}},
        html_storage_path="reports/report-1/report.html",
        html_sha256="a" * 64,
        html_file_size=100,
    )

    with pytest.raises(ValueError, match="immutable"):
        report.title = "Changed"


def test_archive_is_immutable() -> None:
    archive = Archive(
        archive_no="ARC-000001",
        report_id="report-1",
        project_id="project-1",
        manifest_snapshot={"files": []},
        archive_storage_path="archives/archive-1.zip",
        archive_sha256="b" * 64,
        archive_file_size=200,
    )

    with pytest.raises(ValueError, match="immutable"):
        archive.archive_sha256 = "c" * 64
