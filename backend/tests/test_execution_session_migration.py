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


def test_execution_and_credential_migrations_create_safe_schema(tmp_path) -> None:
    database_path = tmp_path / "execution.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260918_0019")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    assert {
        "execution_sessions",
        "execution_events",
        "operator_interactions",
        "configuration_snapshots",
        "recovery_tasks",
    } <= set(inspector.get_table_names())
    assert "credential_references" not in inspector.get_table_names()

    command.upgrade(config, "20260918_0020")
    inspector = inspect(engine)
    assert "credential_references" in inspector.get_table_names()
    credential_columns = {
        column["name"] for column in inspector.get_columns("credential_references")
    }
    assert credential_columns == {
        "id",
        "purpose",
        "target_type",
        "credential_target_ref",
        "masked_display_name",
        "created_at",
        "updated_at",
    }
    assert not credential_columns & {"password", "secret", "token", "encrypted_value"}

    run_columns = {column["name"] for column in inspector.get_columns("test_runs")}
    result_columns = {column["name"] for column in inspector.get_columns("run_results")}
    assert "execution_status" in run_columns
    assert {"execution_session_id", "functional_verdict", "recovery_status"} <= result_columns


def test_execution_event_uniqueness_and_active_session_index_are_migrated(
    tmp_path,
) -> None:
    database_path = tmp_path / "execution-indexes.db"
    command.upgrade(migration_config(database_path), "20260918_0020")
    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))

    event_uniques = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("execution_events")
    }
    assert ("session_id", "sequence_no") in event_uniques
    assert ("session_id", "idempotency_key") in event_uniques
    session_indexes = {item["name"] for item in inspector.get_indexes("execution_sessions")}
    assert "uq_execution_sessions_active_result" in session_indexes
