from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def test_upgrade_creates_environment_profile_and_snapshot_contracts(tmp_path) -> None:
    database_path = tmp_path / "environment.db"
    command.upgrade(migration_config(database_path), "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {
        "environment_profiles",
        "environment_parameters",
        "run_environment_snapshots",
    } <= set(inspector.get_table_names())
    assert {item["name"] for item in inspector.get_columns("environment_profiles")} == {
        "id",
        "name",
        "description",
        "enabled",
        "created_at",
        "updated_at",
    }
    assert {item["name"] for item in inspector.get_columns("environment_parameters")} == {
        "id",
        "profile_id",
        "section",
        "param_key",
        "param_value",
        "display_order",
        "created_at",
        "updated_at",
    }
    snapshot_columns = {
        item["name"]: item
        for item in inspector.get_columns("run_environment_snapshots")
    }
    assert set(snapshot_columns) == {
        "id",
        "test_run_id",
        "environment_profile_source_id",
        "snapshot_version",
        "profile_snapshot",
        "created_at",
    }
    assert snapshot_columns["profile_snapshot"]["nullable"] is False

    parameter_fks = inspector.get_foreign_keys("environment_parameters")
    assert parameter_fks[0]["referred_table"] == "environment_profiles"
    assert parameter_fks[0]["options"]["ondelete"] == "CASCADE"
    snapshot_fks = inspector.get_foreign_keys("run_environment_snapshots")
    assert len(snapshot_fks) == 1
    assert snapshot_fks[0]["referred_table"] == "test_runs"
    assert snapshot_fks[0]["options"]["ondelete"] == "CASCADE"
    assert any(
        item["column_names"] == ["test_run_id"]
        for item in inspector.get_unique_constraints("run_environment_snapshots")
    )


def test_downgrade_removes_environment_tables(tmp_path) -> None:
    database_path = tmp_path / "downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")

    command.downgrade(config, "20260730_0005")

    tables = inspect(
        create_engine(f"sqlite:///{database_path.as_posix()}")
    ).get_table_names()
    assert "environment_profiles" not in tables
    assert "environment_parameters" not in tables
    assert "run_environment_snapshots" not in tables
