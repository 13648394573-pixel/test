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


def test_upgrade_creates_diagnostic_execution_contract(tmp_path) -> None:
    database_path = tmp_path / "diagnostics.db"
    command.upgrade(migration_config(database_path), "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {
        "diagnostic_sessions",
        "diagnostic_attempts",
        "diagnostic_attempt_evidences",
    } <= set(inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("diagnostic_sessions")} == {
        "id", "run_result_id", "retry_of_session_id", "adapter_key",
        "adapter_version", "wan_mode", "status", "policy_snapshot",
        "snapshot_version", "error_code", "error_message", "created_at",
        "started_at", "completed_at",
    }
    assert {column["name"] for column in inspector.get_columns("diagnostic_attempts")} == {
        "id", "session_id", "sequence", "layer", "target", "attempt_number",
        "status", "packets_sent", "packets_received", "loss_percent",
        "latency_min_ms", "latency_avg_ms", "latency_max_ms", "raw_output",
        "error_code", "started_at", "finished_at",
    }
    assert any(
        constraint["column_names"] == ["session_id", "sequence"]
        for constraint in inspector.get_unique_constraints("diagnostic_attempts")
    )
    index = next(
        item for item in inspector.get_indexes("diagnostic_sessions")
        if item["name"] == "uq_diagnostic_sessions_active_result"
    )
    assert index["unique"] == 1


def test_downgrade_removes_diagnostic_execution_tables(tmp_path) -> None:
    database_path = tmp_path / "diagnostics-downgrade.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")
    command.downgrade(config, "20260730_0007")

    tables = set(inspect(create_engine(f"sqlite:///{database_path.as_posix()}")) .get_table_names())
    assert "diagnostic_sessions" not in tables
    assert "diagnostic_attempts" not in tables
    assert "diagnostic_attempt_evidences" not in tables
