from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_creates_devices_table_with_required_constraints(tmp_path) -> None:
    database_path = tmp_path / "nested" / "migration.db"
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    columns = {column["name"] for column in inspector.get_columns("devices")}
    unique_constraints = inspector.get_unique_constraints("devices")

    assert columns == {
        "id",
        "device_type",
        "vendor",
        "model",
        "serial_number",
        "mac_address",
        "hardware_version",
        "software_version",
        "created_at",
        "updated_at",
    }
    assert inspector.get_pk_constraint("devices")["constrained_columns"] == ["id"]
    assert any(
        constraint["column_names"] == ["serial_number"]
        for constraint in unique_constraints
    )
