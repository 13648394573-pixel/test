"""create devices table

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_type", sa.String(length=50), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("hardware_version", sa.String(length=100), nullable=True),
        sa.Column("software_version", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number"),
    )
    op.create_index(
        "ix_devices_serial_number",
        "devices",
        ["serial_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_devices_serial_number", table_name="devices")
    op.drop_table("devices")
