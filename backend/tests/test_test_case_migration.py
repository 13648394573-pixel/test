from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_creates_test_case_aggregate_tables_and_constraints(
    tmp_path,
) -> None:
    database_path = tmp_path / "nested" / "migration.db"
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {column["name"] for column in inspector.get_columns("test_cases")} == {
        "id",
        "case_code",
        "title",
        "device_type",
        "category",
        "priority",
        "preconditions",
        "description",
        "enabled",
        "created_at",
        "updated_at",
    }
    assert {column["name"] for column in inspector.get_columns("case_steps")} == {
        "id",
        "test_case_id",
        "step_number",
        "action",
        "expected_result",
        "created_at",
        "updated_at",
    }
    assert inspector.get_pk_constraint("test_cases")["constrained_columns"] == ["id"]
    assert inspector.get_pk_constraint("case_steps")["constrained_columns"] == ["id"]
    assert any(
        constraint["column_names"] == ["case_code"]
        for constraint in inspector.get_unique_constraints("test_cases")
    )
    assert any(
        constraint["column_names"] == ["test_case_id", "step_number"]
        for constraint in inspector.get_unique_constraints("case_steps")
    )

    foreign_keys = inspector.get_foreign_keys("case_steps")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["constrained_columns"] == ["test_case_id"]
    assert foreign_keys[0]["referred_table"] == "test_cases"
    assert foreign_keys[0]["options"].get("ondelete") == "CASCADE"
