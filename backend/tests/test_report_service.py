from datetime import datetime
from io import BytesIO

import pytest

from app.evidence.storage import EvidenceStorage
from app.models.evidence import Evidence
from app.models.test_execution import RunResult, TestProject, TestRun
from app.reports.repository import ReportRepository
from app.reports.service import (
    ArchiveAlreadyExistsError,
    ReportArtifactConflictError,
    ReportNotReadyError,
    ReportService,
)
from app.reports.storage import ReportStorage


NOW = datetime(2026, 7, 30, 18, 0, 0)


def create_completed_run(db_session, tmp_path):
    project = TestProject(name="ONU Release", version="R1")
    run = TestRun(
        run_no="RUN-000001",
        project=project,
        device_source_id="device-1",
        device_snapshot={
            "vendor": "Example",
            "model": "X1",
            "serial_number": "ONU-001",
        },
        status="COMPLETED",
        finished_at=NOW,
    )
    result = RunResult(
        run=run,
        case_source_id="case-1",
        case_snapshot={
            "case_code": "WAN-001",
            "title": "Verify WAN",
            "steps": [],
        },
        result="FAIL",
        integrity_status="LOCKED",
        actual_result="No address",
        executed_at=NOW,
        locked_at=NOW,
    )
    db_session.add(run)
    db_session.commit()
    evidence_storage = EvidenceStorage(
        tmp_path / "evidence",
        max_bytes=1024,
    )
    stored = evidence_storage.store(
        "run_result",
        result.id,
        "wan.log",
        BytesIO(b"stable log"),
    )
    evidence = Evidence(
        run_result_id=result.id,
        category="LOG",
        original_name="wan.log",
        storage_path=stored.storage_path,
        media_type="text/plain",
        file_size=stored.file_size,
        sha256=stored.sha256,
    )
    db_session.add(evidence)
    db_session.commit()
    return project, run, evidence


def build_service(db_session, tmp_path) -> ReportService:
    return ReportService(
        ReportRepository(db_session),
        ReportStorage(tmp_path / "reports", tmp_path / "evidence"),
        clock=lambda: NOW,
    )


def test_service_generates_versioned_immutable_report_snapshot(
    db_session,
    tmp_path,
) -> None:
    project, run, _evidence = create_completed_run(db_session, tmp_path)
    service = build_service(db_session, tmp_path)

    first = service.generate_report(run.id)
    project.name = "Changed source"
    db_session.commit()
    second = service.generate_report(run.id)

    assert first.report_version == 1
    assert second.report_version == 2
    assert first.report_snapshot["project"]["name"] == "ONU Release"
    assert first.report_snapshot["summary"]["fail"] == 1
    assert service.download_report(first.id).read_text("utf-8").startswith(
        "<!doctype html>"
    )


def test_service_rejects_unfinished_or_unlocked_run(db_session, tmp_path) -> None:
    project = TestProject(name="Draft", version="R1")
    run = TestRun(
        run_no="RUN-000001",
        project=project,
        device_source_id="device-1",
        device_snapshot={},
        status="IN_PROGRESS",
    )
    run.results = [
        RunResult(
            case_source_id="case-1",
            case_snapshot={"case_code": "C1", "title": "Draft", "steps": []},
            integrity_status="DRAFT",
        )
    ]
    db_session.add(run)
    db_session.commit()

    with pytest.raises(ReportNotReadyError):
        build_service(db_session, tmp_path).generate_report(run.id)


def test_service_creates_one_archive_and_rejects_duplicate(
    db_session,
    tmp_path,
) -> None:
    _project, run, _evidence = create_completed_run(db_session, tmp_path)
    service = build_service(db_session, tmp_path)
    report = service.generate_report(run.id)

    archive = service.create_archive(report.id)

    assert service.download_archive(archive.id).is_file()
    assert archive.manifest_snapshot["report"]["report_id"] == report.id
    with pytest.raises(ArchiveAlreadyExistsError):
        service.create_archive(report.id)


def test_service_detects_report_and_evidence_tampering(
    db_session,
    tmp_path,
) -> None:
    _project, run, evidence = create_completed_run(db_session, tmp_path)
    service = build_service(db_session, tmp_path)
    report = service.generate_report(run.id)
    service.storage.resolve(report.html_storage_path).write_text("tampered")

    with pytest.raises(ReportArtifactConflictError):
        service.download_report(report.id)

    report = service.generate_report(run.id)
    evidence_path = (
        service.storage.evidence_root / evidence.storage_path
    ).resolve()
    evidence_path.write_bytes(b"tampered evidence")
    with pytest.raises(ReportArtifactConflictError):
        service.create_archive(report.id)


def test_archive_snapshot_deduplicates_shared_evidence() -> None:
    evidence = {
        "id": "evidence-1",
        "original_name": "shared.log",
        "storage_path": "run_result/result-1/shared.log",
        "sha256": "a" * 64,
        "file_size": 4,
    }
    snapshot = {
        "results": [
            {"evidences": [evidence]},
            {"evidences": [dict(evidence)]},
        ],
        "defects": [],
    }

    assert ReportService._snapshot_evidences(snapshot) == [evidence]


def test_service_inlines_screenshot_evidence_and_customer_code(
    db_session,
    tmp_path,
) -> None:
    from PIL import Image

    project, run, _evidence = create_completed_run(db_session, tmp_path)
    result = run.results[0]

    evidence_storage = EvidenceStorage(tmp_path / "evidence", max_bytes=65536)
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(200, 30, 30)).save(buffer, format="PNG")
    buffer.seek(0)
    stored = evidence_storage.store(
        "run_result", result.id, "wan.png", buffer
    )
    screenshot = Evidence(
        run_result_id=result.id,
        category="SCREENSHOT",
        original_name="wan.png",
        storage_path=stored.storage_path,
        media_type="image/png",
        file_size=stored.file_size,
        sha256=stored.sha256,
    )
    db_session.add(screenshot)
    db_session.commit()

    service = build_service(db_session, tmp_path)
    report = service.generate_report(
        run.id, mode="formal", customer_code="CUST-2026-001"
    )

    assert report.report_snapshot["customer_code"] == "CUST-2026-001"
    inlined = [
        item
        for item in report.report_snapshot["results"][0]["evidences"]
        if item.get("data_uri")
    ]
    assert len(inlined) == 1
    assert inlined[0]["data_uri"].startswith("data:image/png;base64,")
    html = service.download_report(report.id).read_text("utf-8")
    assert "<img" in html
    assert "CUST-2026-001" in html
