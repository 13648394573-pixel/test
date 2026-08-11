from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_creates_test_execution_tables_and_constraints(tmp_path) -> None:
    database_path = tmp_path / "nested" / "migration.db"
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {column["name"] for column in inspector.get_columns("test_projects")} == {
        "id",
        "name",
        "version",
        "description",
        "created_at",
        "updated_at",
    }
    assert {
        column["name"]
        for column in inspector.get_columns("project_case_selections")
    } == {"project_id", "case_source_id"}
    assert {column["name"] for column in inspector.get_columns("test_runs")} == {
        "id",
        "run_no",
        "project_id",
        "device_source_id",
        "device_snapshot",
        "snapshot_version",
        "status",
        "started_at",
        "finished_at",
    }
    assert {column["name"] for column in inspector.get_columns("run_results")} == {
        "id",
        "run_id",
        "case_source_id",
        "case_snapshot",
        "snapshot_version",
            "result",
            "integrity_status",
            "actual_result",
            "blocked_reason",
            "test_notes",
            "executed_at",
            "locked_at",
        }

    assert inspector.get_pk_constraint("test_projects")["constrained_columns"] == [
        "id"
    ]
    assert inspector.get_pk_constraint("project_case_selections")[
        "constrained_columns"
    ] == ["project_id", "case_source_id"]
    assert inspector.get_pk_constraint("test_runs")["constrained_columns"] == [
        "id"
    ]
    assert inspector.get_pk_constraint("run_results")["constrained_columns"] == [
        "id"
    ]

    selection_foreign_key = inspector.get_foreign_keys(
        "project_case_selections"
    )[0]
    assert selection_foreign_key["referred_table"] == "test_projects"
    assert selection_foreign_key["options"].get("ondelete") == "CASCADE"

    result_foreign_key = inspector.get_foreign_keys("run_results")[0]
    assert result_foreign_key["referred_table"] == "test_runs"
    assert result_foreign_key["options"].get("ondelete") == "CASCADE"

    assert any(
        constraint["column_names"] == ["run_id", "case_source_id"]
        for constraint in inspector.get_unique_constraints("run_results")
    )
    check_sql = " ".join(
        constraint["sqltext"]
        for constraint in inspector.get_check_constraints("run_results")
    )
    assert "PASS" in check_sql
    assert "FAIL" in check_sql
    assert "BLOCKED" in check_sql

    run_columns = {
        column["name"]: column for column in inspector.get_columns("test_runs")
    }
    result_columns = {
        column["name"]: column for column in inspector.get_columns("run_results")
    }
    assert str(run_columns["snapshot_version"]["default"]).strip("'\"()") == "1"
    assert str(result_columns["snapshot_version"]["default"]).strip("'\"()") == "1"
