from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def test_upgrade_adds_result_integrity_and_evidence_contracts(tmp_path) -> None:
    database_path = tmp_path / "migration.db"
    config = migration_config(database_path)

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    result_columns = {
        item["name"]: item for item in inspector.get_columns("run_results")
    }
    assert {
        "integrity_status",
        "actual_result",
        "blocked_reason",
        "test_notes",
        "locked_at",
    } <= result_columns.keys()
    assert result_columns["integrity_status"]["nullable"] is False

    evidence_columns = {
        item["name"] for item in inspector.get_columns("evidences")
    }
    assert evidence_columns == {
        "id",
        "run_result_id",
        "defect_id",
        "category",
        "original_name",
        "storage_path",
        "media_type",
        "file_size",
        "sha256",
        "description",
        "created_at",
    }
    foreign_keys = {
        tuple(item["constrained_columns"]): item
        for item in inspector.get_foreign_keys("evidences")
    }
    assert foreign_keys[("run_result_id",)]["referred_table"] == "run_results"
    assert foreign_keys[("run_result_id",)]["options"]["ondelete"] == "CASCADE"
    assert foreign_keys[("defect_id",)]["referred_table"] == "defects"
    assert foreign_keys[("defect_id",)]["options"]["ondelete"] == "CASCADE"
    checks = " ".join(
        item["sqltext"] for item in inspector.get_check_constraints("evidences")
    )
    assert "run_result_id IS NOT NULL AND defect_id IS NULL" in checks
    assert "run_result_id IS NULL AND defect_id IS NOT NULL" in checks
    assert all(
        value in checks for value in ("SCREENSHOT", "LOG", "CONFIG", "OTHER")
    )
    assert any(
        item["column_names"] == ["storage_path"]
        for item in inspector.get_unique_constraints("evidences")
    )


def test_upgrade_backfills_existing_results_by_execution_state(tmp_path) -> None:
    database_path = tmp_path / "backfill.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260730_0004")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_projects "
                "(id, name, version) VALUES ('p1', 'P', 'V1')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO test_runs "
                "(id, project_id, device_source_id, device_snapshot) "
                "VALUES ('run1', 'p1', 'd1', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO run_results "
                "(id, run_id, case_source_id, case_snapshot, result, executed_at) "
                "VALUES "
                "('draft', 'run1', 'c1', '{}', NULL, NULL), "
                "('done', 'run1', 'c2', '{}', 'FAIL', '2026-07-30 10:00:00')"
            )
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, integrity_status, locked_at "
                "FROM run_results ORDER BY id"
            )
        ).mappings().all()
    assert rows[0]["id"] == "done"
    assert rows[0]["integrity_status"] == "LOCKED"
    assert str(rows[0]["locked_at"]).startswith("2026-07-30 10:00:00")
    assert rows[1] == {
        "id": "draft",
        "integrity_status": "DRAFT",
        "locked_at": None,
    }


def test_downgrade_removes_evidence_and_integrity_columns(tmp_path) -> None:
    database_path = tmp_path / "downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")

    command.downgrade(config, "20260730_0004")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert "evidences" not in inspector.get_table_names()
    assert {
        item["name"] for item in inspector.get_columns("run_results")
    }.isdisjoint(
        {
            "integrity_status",
            "actual_result",
            "blocked_reason",
            "test_notes",
            "locked_at",
        }
    )
