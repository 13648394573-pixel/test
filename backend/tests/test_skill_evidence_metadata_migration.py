from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_skill_evidence_metadata_migration_adds_execution_fields(tmp_path) -> None:
    database_path = tmp_path / "skill-evidence.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260918_0020")
    command.upgrade(config, "20260918_0021")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    evidence_columns = {column["name"] for column in inspector.get_columns("evidences")}
    interaction_columns = {
        column["name"] for column in inspector.get_columns("operator_interactions")
    }
    assert {"execution_session_id", "step_ref", "capture_method", "redacted"} <= evidence_columns
    assert {
        "interaction_type",
        "risk_level",
        "options_json",
        "impact_preview",
        "response_json",
    } <= interaction_columns

    indexes = {item["name"] for item in inspector.get_indexes("evidences")}
    assert "ix_evidences_execution_session_id" in indexes
    assert "ix_evidences_execution_session_step" in indexes


def test_skill_evidence_metadata_downgrade_refuses_used_metadata(tmp_path) -> None:
    database_path = tmp_path / "skill-evidence-downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260918_0021")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_projects "
                "(id, project_code, name, version, status) "
                "VALUES ('project-1', 'PRJ-MIGRATION', 'Migration', 'V2', 'DRAFT')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO test_runs "
                "(id, run_no, project_id, device_source_id, device_snapshot, "
                "execution_schema_version, source, snapshot_version, status) "
                "VALUES ('run-1', 'RUN-MIGRATION', 'project-1', 'device-1', '{}', "
                "1, 'MANUAL', 1, 'IN_PROGRESS')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO run_results "
                "(id, run_id, case_source_id, case_snapshot, result_source, "
                "snapshot_version, integrity_status) "
                "VALUES ('result-1', 'run-1', 'case-1', '{}', 'MANUAL', 1, 'DRAFT')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO execution_sessions "
                "(id, test_run_id, run_result_id, mode, status) "
                "VALUES ('session-1', 'run-1', 'result-1', 'FORMAL', 'COMPLETED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evidences "
                "(id, run_result_id, category, original_name, storage_path, media_type, "
                "file_size, sha256, execution_session_id, step_ref, capture_method, redacted) "
                "VALUES ('evidence-1', 'result-1', 'SCREENSHOT', 'one.png', "
                "'runs/one.png', 'image/png', 1, :sha, 'session-1', 'REGISTER', "
                "'OLT_RENDER', 1)"
            ),
            {"sha": "a" * 64},
        )

    with pytest.raises(RuntimeError, match="metadata is in use"):
        command.downgrade(config, "20260918_0020")
