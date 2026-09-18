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


def test_runner_registry_schema_contains_metadata_not_executable_payloads(tmp_path) -> None:
    database_path = tmp_path / "runner-registry.db"
    command.upgrade(migration_config(database_path), "20260918_0018")
    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))

    assert {"runner_plugins", "runner_actions", "skill_runner_bindings"} <= set(
        inspector.get_table_names()
    )
    forbidden = {"script_body", "command", "password", "token", "selector_source"}
    for table_name in ("runner_plugins", "runner_actions", "skill_runner_bindings"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        assert not columns & forbidden
    assert any(
        constraint["column_names"] == ["plugin_code", "version"]
        for constraint in inspector.get_unique_constraints("runner_plugins")
    )
    assert any(
        constraint["column_names"] == ["plugin_id", "action_code"]
        for constraint in inspector.get_unique_constraints("runner_actions")
    )
