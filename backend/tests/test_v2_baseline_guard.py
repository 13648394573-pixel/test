from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.schema_guard import (
    DatabaseIntegrityError,
    DatabaseRevisionError,
    check_database_health,
    require_database_health,
    resolve_expected_revision,
)
from app.db.session import create_database_engine


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_resolve_expected_revision_returns_single_alembic_head() -> None:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))

    assert resolve_expected_revision(BACKEND_ROOT / "alembic.ini") == (
        ScriptDirectory.from_config(config).get_current_head()
    )


def test_require_database_health_accepts_migrated_database(tmp_path) -> None:
    database_path = tmp_path / "healthy.db"
    command.upgrade(migration_config(database_path), "head")
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    expected_revision = resolve_expected_revision(BACKEND_ROOT / "alembic.ini")

    health = require_database_health(engine, expected_revision)

    assert health.revision == expected_revision
    assert health.quick_check == "ok"
    assert health.foreign_key_errors == ()


def test_require_database_health_rejects_missing_revision_table(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'missing.db').as_posix()}")

    with pytest.raises(DatabaseRevisionError, match="alembic_version"):
        require_database_health(engine, "20260918_0011")


def test_require_database_health_rejects_wrong_revision(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'wrong.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('20260811_0010')"))

    with pytest.raises(DatabaseRevisionError, match="expected 20260918_0011"):
        require_database_health(engine, "20260918_0011")


def test_require_database_health_rejects_foreign_key_errors(tmp_path) -> None:
    database_path = tmp_path / "invalid-foreign-key.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('20260918_0011')"))
        connection.execute(text("CREATE TABLE parents (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE children ("
                "id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL, "
                "FOREIGN KEY(parent_id) REFERENCES parents(id))"
            )
        )
        connection.execute(text("PRAGMA foreign_keys=OFF"))
    engine.dispose()

    raw_engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    with raw_engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("INSERT INTO children VALUES (1, 999)")
        connection.commit()
    raw_engine.dispose()

    checked_engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    health = check_database_health(checked_engine, "20260918_0011")
    assert health.foreign_key_errors
    with pytest.raises(DatabaseIntegrityError, match="foreign key"):
        require_database_health(checked_engine, "20260918_0011")
