from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_upgrade_creates_standard_and_profile_schema(tmp_path) -> None:
    database_path = tmp_path / "standards.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260918_0012")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)

    assert {
        "test_standards",
        "standard_requirements",
        "standard_profiles",
        "standard_profile_items",
        "project_standard_profiles",
    } <= set(inspector.get_table_names())
    assert any(
        constraint["column_names"] == ["standard_code", "version"]
        for constraint in inspector.get_unique_constraints("test_standards")
    )
    assert any(
        constraint["column_names"] == ["profile_id", "display_order"]
        for constraint in inspector.get_unique_constraints("standard_profile_items")
    )

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_standards "
                "(id, standard_code, version, title, source_type, issuer, "
                "language_code, status, source_reference) VALUES "
                "('s1', 'STD', '1.0', 'First', 'INTERNAL', 'UNPON', "
                "'en-US', 'DRAFT', 'REF-1')"
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO test_standards "
                    "(id, standard_code, version, title, source_type, issuer, "
                    "language_code, status, source_reference) VALUES "
                    "('s2', 'STD', '1.0', 'Second', 'INTERNAL', 'UNPON', "
                    "'en-US', 'DRAFT', 'REF-2')"
                )
            )


def test_downgrade_allows_draft_data_but_rejects_published_history(tmp_path) -> None:
    draft_path = tmp_path / "draft.db"
    draft_config = migration_config(draft_path)
    command.upgrade(draft_config, "20260918_0012")
    command.downgrade(draft_config, "20260918_0011")
    assert "test_standards" not in inspect(
        create_engine(f"sqlite:///{draft_path.as_posix()}")
    ).get_table_names()

    published_path = tmp_path / "published.db"
    published_config = migration_config(published_path)
    command.upgrade(published_config, "20260918_0012")
    engine = create_engine(f"sqlite:///{published_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_standards "
                "(id, standard_code, version, title, source_type, issuer, "
                "language_code, status, source_reference, published_at) VALUES "
                "('s1', 'STD', '1.0', 'Published', 'INTERNAL', 'UNPON', "
                "'en-US', 'PUBLISHED', 'REF', CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(RuntimeError, match="published standard history"):
        command.downgrade(published_config, "20260918_0011")
    assert "test_standards" in inspect(engine).get_table_names()
