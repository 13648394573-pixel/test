from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.session import create_database_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_upgrade_adds_run_numbers_indexes_and_evidence_links(tmp_path) -> None:
    database_path = tmp_path / "history.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260810_0009")
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_projects "
                "(id, name, version, description) "
                "VALUES ('project-1', 'Release', 'V1', NULL)"
            )
        )
        for run_id, started_at in (
            ("run-b", "2026-08-11 10:00:00"),
            ("run-a", "2026-08-11 09:00:00"),
        ):
            connection.execute(
                text(
                    "INSERT INTO test_runs "
                    "(id, project_id, device_source_id, device_snapshot, "
                    "snapshot_version, status, started_at) "
                    "VALUES (:id, 'project-1', 'device-1', '{}', 1, "
                    "'IN_PROGRESS', :started_at)"
                ),
                {"id": run_id, "started_at": started_at},
            )
        connection.execute(
            text(
                "INSERT INTO run_results "
                "(id, run_id, case_source_id, case_snapshot, snapshot_version, "
                "result, integrity_status) VALUES "
                "('result-1', 'run-a', 'case-1', '{}', 1, NULL, 'DRAFT')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evidences "
                "(id, run_result_id, defect_id, category, original_name, "
                "storage_path, media_type, file_size, sha256, description) "
                "VALUES ('evidence-1', 'result-1', NULL, 'LOG', 'before.log', "
                "'run-results/before.log', 'text/plain', 3, :sha256, NULL)"
            ),
            {"sha256": "0" * 64},
        )

    command.upgrade(config, "head")

    inspector = inspect(engine)
    run_columns = {item["name"]: item for item in inspector.get_columns("test_runs")}
    assert run_columns["run_no"]["nullable"] is False
    run_indexes = {
        item["name"]: item for item in inspector.get_indexes("test_runs")
    }
    assert set(run_indexes) >= {
        "ix_test_runs_project_status_started",
        "ix_test_runs_started_at",
        "uq_test_runs_run_no",
    }
    assert run_indexes["uq_test_runs_run_no"]["unique"] == 1
    assert "evidence_run_result_links" in inspector.get_table_names()
    assert {
        item["name"] for item in inspector.get_indexes("evidence_run_result_links")
    } >= {"ix_evidence_run_result_links_result_id"}
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, run_no FROM test_runs ORDER BY started_at, id")
        ).all()
        links = connection.execute(
            text(
                "SELECT evidence_id, run_result_id "
                "FROM evidence_run_result_links"
            )
        ).all()
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
    assert rows == [("run-a", "RUN-000001"), ("run-b", "RUN-000002")]
    assert links == [("evidence-1", "result-1")]
    assert foreign_keys == 1

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO evidence_run_result_links "
                    "(evidence_id, run_result_id) "
                    "VALUES ('evidence-1', 'result-1')"
                )
            )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM run_results WHERE id = 'result-1'"))
        assert connection.execute(
            text("SELECT COUNT(*) FROM evidence_run_result_links")
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT COUNT(*) FROM evidences WHERE id = 'evidence-1'")
        ).scalar_one() == 0


def test_empty_database_upgrade_and_downgrade_preserve_existing_tables(tmp_path) -> None:
    database_path = tmp_path / "empty-history.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")
    command.downgrade(config, "20260810_0009")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert "test_runs" in inspector.get_table_names()
    assert "evidence_run_result_links" not in inspector.get_table_names()
    assert "run_no" not in {
        item["name"] for item in inspector.get_columns("test_runs")
    }


def test_downgrade_rejects_shared_evidence_without_partial_schema_changes(
    tmp_path,
) -> None:
    database_path = tmp_path / "shared-downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_projects "
                "(id, project_code, name, version, description) "
                "VALUES ('project-1', 'LEGACY-TEST-001', 'Release', 'V1', NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO test_runs "
                "(id, run_no, project_id, device_source_id, device_snapshot, "
                "snapshot_version, status) VALUES "
                "('run-1', 'RUN-000001', 'project-1', 'device-1', '{}', 1, "
                "'IN_PROGRESS')"
            )
        )
        for result_id, case_id in (("result-1", "case-1"), ("result-2", "case-2")):
            connection.execute(
                text(
                    "INSERT INTO run_results "
                    "(id, run_id, case_source_id, case_snapshot, snapshot_version, "
                    "result, integrity_status) VALUES "
                    "(:id, 'run-1', :case_id, '{}', 1, NULL, 'DRAFT')"
                ),
                {"id": result_id, "case_id": case_id},
            )
        connection.execute(
            text(
                "INSERT INTO evidences "
                "(id, run_result_id, defect_id, category, original_name, "
                "storage_path, media_type, file_size, sha256, description) "
                "VALUES ('evidence-1', 'result-1', NULL, 'LOG', 'shared.log', "
                "'run-results/shared.log', 'text/plain', 3, :sha256, NULL)"
            ),
            {"sha256": "0" * 64},
        )
        for result_id in ("result-1", "result-2"):
            connection.execute(
                text(
                    "INSERT INTO evidence_run_result_links "
                    "(evidence_id, run_result_id) VALUES ('evidence-1', :result_id)"
                ),
                {"result_id": result_id},
            )

    with pytest.raises(RuntimeError, match="multi-result evidence links"):
        command.downgrade(config, "20260810_0009")

    inspector = inspect(engine)
    assert "evidence_run_result_links" in inspector.get_table_names()
    assert "run_no" in {
        item["name"] for item in inspector.get_columns("test_runs")
    }
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM evidence_run_result_links")
        ).scalar_one() == 2
