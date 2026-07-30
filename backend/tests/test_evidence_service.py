from datetime import datetime
from io import BytesIO

import pytest
from sqlalchemy.orm import Session

from app.defects.repository import DefectRepository
from app.evidence.repository import EvidenceRepository
from app.evidence.service import (
    EvidenceConflictError,
    EvidenceService,
)
from app.evidence.storage import EvidenceStorage
from app.test_execution.repository import TestExecutionRepository


def create_result(db_session: Session, *, locked: bool):
    repository = TestExecutionRepository(db_session)
    project = repository.create_project(
        {"name": "Evidence", "version": "V1", "description": None},
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
        {"result": "FAIL", "actual_result": "No address"},
    )
    if locked:
        result = repository.lock_result(
            result,
            datetime(2026, 7, 30, 10, 0),
            complete_run=True,
        )
    return result


def build_service(db_session: Session, tmp_path) -> EvidenceService:
    return EvidenceService(
        EvidenceRepository(db_session),
        EvidenceStorage(tmp_path, max_bytes=1024),
    )


def upload_for_result(service: EvidenceService, result_id: str):
    return service.create_for_run_result(
        result_id,
        category="LOG",
        original_name="console.log",
        media_type="text/plain",
        description="OLT console",
        stream=BytesIO(b"evidence"),
    )


def test_run_result_evidence_is_mutable_only_while_draft(
    db_session: Session,
    tmp_path,
) -> None:
    result = create_result(db_session, locked=False)
    service = build_service(db_session, tmp_path)

    evidence = upload_for_result(service, result.id)
    assert evidence.run_result_id == result.id
    assert evidence.defect_id is None
    assert len(service.list_for_run_result(result.id)) == 1

    service.delete(evidence.id)
    assert service.list_for_run_result(result.id) == []

    db_session.refresh(result)
    TestExecutionRepository(db_session).lock_result(
        result,
        datetime(2026, 7, 30, 11, 0),
        complete_run=True,
    )
    with pytest.raises(EvidenceConflictError):
        upload_for_result(service, result.id)


def test_defect_evidence_follows_status_lifecycle(
    db_session: Session,
    tmp_path,
) -> None:
    source = create_result(db_session, locked=True)
    defect = DefectRepository(db_session).create_defect(
        {
            "defect_code": "DEF-000001",
            "source_run_result_id": source.id,
            "title": "WAN failure",
            "description": "No address",
            "reproduction_steps": "Create WAN",
            "severity": "S2",
            "status": "OPEN",
        }
    )
    service = build_service(db_session, tmp_path)

    first = service.create_for_defect(
        defect.id,
        category="SCREENSHOT",
        original_name="wan.png",
        media_type="image/png",
        description=None,
        stream=BytesIO(b"png"),
    )
    service.delete(first.id)

    DefectRepository(db_session).update_defect(defect, {"status": "RESOLVED"})
    resolved = service.create_for_defect(
        defect.id,
        category="CONFIG",
        original_name="config.xml",
        media_type="application/xml",
        description=None,
        stream=BytesIO(b"<xml/>"),
    )
    with pytest.raises(EvidenceConflictError):
        service.delete(resolved.id)

    DefectRepository(db_session).update_defect(defect, {"status": "CLOSED"})
    with pytest.raises(EvidenceConflictError):
        service.create_for_defect(
            defect.id,
            category="OTHER",
            original_name="note.txt",
            media_type="text/plain",
            description=None,
            stream=BytesIO(b"closed"),
        )
