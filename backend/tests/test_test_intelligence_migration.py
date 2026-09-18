from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_stepwise_skill_migrations_create_controlled_schema(tmp_path) -> None:
    database_path = tmp_path / "skills.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260918_0013")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    assert {"test_skills", "skill_parameters", "skill_steps"} <= set(
        inspector.get_table_names()
    )
    assert "skill_execution_rules" not in inspector.get_table_names()

    command.upgrade(config, "20260918_0014")
    inspector = inspect(engine)
    assert {
        "skill_execution_rules",
        "skill_evidence_rules",
        "skill_standard_bindings",
    } <= set(inspector.get_table_names())
    rule_columns = {column["name"] for column in inspector.get_columns("skill_execution_rules")}
    assert "script_body" not in rule_columns
    assert "command" not in rule_columns
    assert any(
        constraint["column_names"] == ["skill_id", "rule_code"]
        for constraint in inspector.get_unique_constraints("skill_execution_rules")
    )


def test_skill_downgrade_rejects_published_skill(tmp_path) -> None:
    database_path = tmp_path / "published-skill.db"
    config = migration_config(database_path)
    command.upgrade(config, "20260918_0014")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO test_skills "
                "(id, skill_code, version, spec_version, name, objective, status, "
                "applicable_devices, preconditions, environment_requirements, "
                "validation_methods, outputs, tags, published_at) VALUES "
                "('skill-1', 'ONU-VLAN', '1.0.0', '1.0', 'VLAN', 'Verify VLAN', "
                "'PUBLISHED', '[]', '[]', '[]', '[]', '[]', '[]', CURRENT_TIMESTAMP)"
            )
        )

    with pytest.raises(RuntimeError, match="published Skill history"):
        command.downgrade(config, "20260918_0012")
    assert "test_skills" in inspect(engine).get_table_names()
