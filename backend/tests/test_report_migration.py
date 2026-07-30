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


def test_upgrade_creates_report_and_single_archive_contracts(tmp_path) -> None:
    database_path = tmp_path / "reports.db"
    command.upgrade(migration_config(database_path), "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {"reports", "archives"} <= set(inspector.get_table_names())
    assert {item["name"] for item in inspector.get_columns("reports")} == {
        "id",
        "report_no",
        "project_id",
        "test_run_id",
        "report_version",
        "title",
        "snapshot_version",
        "report_snapshot",
        "html_storage_path",
        "html_sha256",
        "html_file_size",
        "generated_at",
        "created_at",
    }
    assert {item["name"] for item in inspector.get_columns("archives")} == {
        "id",
        "archive_no",
        "report_id",
        "project_id",
        "manifest_version",
        "manifest_snapshot",
        "archive_storage_path",
        "archive_sha256",
        "archive_file_size",
        "archived_at",
        "created_at",
    }
    assert any(
        item["column_names"] == ["test_run_id", "report_version"]
        for item in inspector.get_unique_constraints("reports")
    )
    assert any(
        item["column_names"] == ["report_id"]
        for item in inspector.get_unique_constraints("archives")
    )
    report_fks = {
        tuple(item["constrained_columns"]): item
        for item in inspector.get_foreign_keys("reports")
    }
    archive_fks = {
        tuple(item["constrained_columns"]): item
        for item in inspector.get_foreign_keys("archives")
    }
    assert report_fks[("project_id",)]["referred_table"] == "test_projects"
    assert report_fks[("test_run_id",)]["referred_table"] == "test_runs"
    assert archive_fks[("report_id",)]["referred_table"] == "reports"


def test_downgrade_removes_report_archive_tables(tmp_path) -> None:
    database_path = tmp_path / "downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")

    command.downgrade(config, "20260730_0006")

    tables = inspect(
        create_engine(f"sqlite:///{database_path.as_posix()}")
    ).get_table_names()
    assert "reports" not in tables
    assert "archives" not in tables
