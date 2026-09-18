from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text


class DatabaseHealthError(RuntimeError):
    """Base error raised when the application database is not safe to use."""


class DatabaseRevisionError(DatabaseHealthError):
    """Raised when the database revision does not match the application."""


class DatabaseIntegrityError(DatabaseHealthError):
    """Raised when SQLite reports structural or foreign-key corruption."""


@dataclass(frozen=True)
class DatabaseHealth:
    revision: str | None
    quick_check: str
    foreign_key_errors: tuple[tuple[object, ...], ...]


def resolve_expected_revision(alembic_ini: Path | None = None) -> str:
    backend_root = Path(__file__).resolve().parents[2]
    ini_path = alembic_ini or backend_root / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise DatabaseRevisionError(
            f"Expected exactly one Alembic head, found {len(heads)}: {heads}"
        )
    return heads[0]


def check_database_health(engine: Engine, expected_revision: str) -> DatabaseHealth:
    del expected_revision  # The expected value is evaluated by require_database_health().
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        revision = None
        if "alembic_version" in tables:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
        quick_check = str(connection.execute(text("PRAGMA quick_check")).scalar_one())
        foreign_key_errors = tuple(
            tuple(row)
            for row in connection.execute(text("PRAGMA foreign_key_check"))
        )
    return DatabaseHealth(revision, quick_check, foreign_key_errors)


def require_database_health(
    engine: Engine,
    expected_revision: str,
) -> DatabaseHealth:
    health = check_database_health(engine, expected_revision)
    if health.revision is None:
        raise DatabaseRevisionError(
            "Database is not initialized: alembic_version is missing. "
            "Run the database migrations before starting Test Workbench."
        )
    if health.revision != expected_revision:
        raise DatabaseRevisionError(
            f"Database revision is {health.revision}; expected {expected_revision}. "
            "Back up the workspace and run the database migrations."
        )
    if health.quick_check.lower() != "ok":
        raise DatabaseIntegrityError(
            f"SQLite quick_check failed: {health.quick_check}"
        )
    if health.foreign_key_errors:
        raise DatabaseIntegrityError(
            "SQLite foreign key check failed: "
            f"{len(health.foreign_key_errors)} violation(s)"
        )
    return health
