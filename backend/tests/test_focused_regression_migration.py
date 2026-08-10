from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_upgrade_creates_focused_regression_contract(tmp_path) -> None:
    database_path = tmp_path / "focused-regression.db"
    command.upgrade(migration_config(database_path), "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert "focused_regression_runs" in inspector.get_table_names()
    assert {
        column["name"]
        for column in inspector.get_columns("focused_regression_runs")
    } == {
        "id",
        "test_run_id",
        "defect_id",
        "source_run_result_id",
        "defect_snapshot",
        "snapshot_version",
        "created_at",
    }
    assert any(
        constraint["column_names"] == ["test_run_id"]
        for constraint in inspector.get_unique_constraints(
            "focused_regression_runs"
        )
    )
    foreign_keys = {
        tuple(item["constrained_columns"]): (
            item["referred_table"],
            item["options"].get("ondelete"),
        )
        for item in inspector.get_foreign_keys("focused_regression_runs")
    }
    assert foreign_keys == {
        ("test_run_id",): ("test_runs", "RESTRICT"),
        ("defect_id",): ("defects", "RESTRICT"),
        ("source_run_result_id",): ("run_results", "RESTRICT"),
    }
    assert {
        item["name"]
        for item in inspector.get_indexes("focused_regression_runs")
    } >= {
        "ix_focused_regression_runs_defect_id",
        "ix_focused_regression_runs_source_run_result_id",
    }


def test_downgrade_removes_only_focused_regression_table(tmp_path) -> None:
    database_path = tmp_path / "focused-regression-downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")
    command.downgrade(config, "20260808_0008")

    tables = set(
        inspect(
            create_engine(f"sqlite:///{database_path.as_posix()}")
        ).get_table_names()
    )
    assert "focused_regression_runs" not in tables
    assert "test_runs" in tables
    assert "regressions" in tables
