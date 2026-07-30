import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.evidence.repository import EvidenceRepository
from app.models.evidence import Evidence
from app.test_execution.repository import TestExecutionRepository


def create_result(db_session: Session):
    execution = TestExecutionRepository(db_session)
    project = execution.create_project(
        {"name": "Evidence", "version": "V1", "description": None},
        ["case-1"],
    )
    run = execution.create_run(
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
    return run, run.results[0]


def evidence_values(result_id: str) -> dict:
    return {
        "run_result_id": result_id,
        "defect_id": None,
        "category": "LOG",
        "original_name": "console.log",
        "storage_path": f"run-results/{result_id}/file.log",
        "media_type": "text/plain",
        "file_size": 7,
        "sha256": "a" * 64,
        "description": None,
    }


def test_repository_keeps_metadata_immutable_and_cascades_with_owner(
    db_session: Session,
) -> None:
    run, result = create_result(db_session)
    repository = EvidenceRepository(db_session)
    evidence = repository.create(evidence_values(result.id))
    evidence_id = evidence.id

    evidence.category = "OTHER"
    with pytest.raises(ValueError, match="immutable"):
        db_session.commit()
    db_session.rollback()

    db_session.delete(run)
    db_session.commit()
    assert repository.get(evidence_id) is None


def test_database_rejects_evidence_without_exactly_one_owner(
    db_session: Session,
) -> None:
    _run, result = create_result(db_session)
    db_session.add(
        Evidence(
            **{
                **evidence_values(result.id),
                "run_result_id": None,
            }
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
