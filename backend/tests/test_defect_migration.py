from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_creates_defect_and_regression_tables(tmp_path) -> None:
    database_path = tmp_path / "nested" / "migration.db"
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {column["name"] for column in inspector.get_columns("defects")} == {
        "id",
        "defect_code",
        "source_run_result_id",
        "title",
        "description",
        "reproduction_steps",
        "severity",
        "status",
        "resolution_notes",
        "created_at",
        "updated_at",
        "resolved_at",
        "closed_at",
    }
    assert {column["name"] for column in inspector.get_columns("regressions")} == {
        "id",
        "defect_id",
        "verification_run_result_id",
        "result",
        "notes",
        "executed_at",
        "created_at",
    }

    defect_foreign_key = inspector.get_foreign_keys("defects")[0]
    assert defect_foreign_key["constrained_columns"] == ["source_run_result_id"]
    assert defect_foreign_key["referred_table"] == "run_results"
    assert defect_foreign_key["options"].get("ondelete") == "RESTRICT"

    regression_foreign_keys = {
        tuple(item["constrained_columns"]): item
        for item in inspector.get_foreign_keys("regressions")
    }
    assert regression_foreign_keys[("defect_id",)]["referred_table"] == "defects"
    assert regression_foreign_keys[("defect_id",)]["options"].get("ondelete") == (
        "CASCADE"
    )
    assert regression_foreign_keys[("verification_run_result_id",)][
        "referred_table"
    ] == "run_results"
    assert regression_foreign_keys[("verification_run_result_id",)][
        "options"
    ].get("ondelete") == "RESTRICT"

    defect_unique_constraints = inspector.get_unique_constraints("defects")
    assert any(
        item["column_names"] == ["defect_code"]
        for item in defect_unique_constraints
    )
    assert any(
        item["column_names"] == ["source_run_result_id"]
        for item in defect_unique_constraints
    )
    assert any(
        item["column_names"] == ["defect_id", "verification_run_result_id"]
        for item in inspector.get_unique_constraints("regressions")
    )

    defect_checks = " ".join(
        item["sqltext"] for item in inspector.get_check_constraints("defects")
    )
    for value in (
        "S1",
        "S2",
        "S3",
        "S4",
        "OPEN",
        "IN_PROGRESS",
        "RESOLVED",
        "REOPENED",
        "CLOSED",
    ):
        assert value in defect_checks

    regression_checks = " ".join(
        item["sqltext"]
        for item in inspector.get_check_constraints("regressions")
    )
    for value in ("PASS", "FAIL", "BLOCKED"):
        assert value in regression_checks
