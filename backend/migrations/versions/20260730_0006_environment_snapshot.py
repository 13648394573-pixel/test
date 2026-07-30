"""add environment profiles and run snapshots

Revision ID: 20260730_0006
Revises: 20260730_0005
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "environment_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="1",
            nullable=False,
        ),
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
        sa.UniqueConstraint("name", name="uq_environment_profiles_name"),
    )
    op.create_table(
        "environment_parameters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.Column("param_key", sa.String(length=100), nullable=False),
        sa.Column("param_value", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "display_order >= 1",
            name="ck_environment_parameters_display_order",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["environment_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "param_key",
            name="uq_environment_parameters_profile_key",
        ),
    )
    op.create_index(
        "ix_environment_parameters_profile_id",
        "environment_parameters",
        ["profile_id"],
    )
    op.create_table(
        "run_environment_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("test_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "environment_profile_source_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "snapshot_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("profile_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "snapshot_version = 1",
            name="ck_run_environment_snapshots_version",
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "test_run_id",
            name="uq_run_environment_snapshots_test_run_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("run_environment_snapshots")
    op.drop_index(
        "ix_environment_parameters_profile_id",
        table_name="environment_parameters",
    )
    op.drop_table("environment_parameters")
    op.drop_table("environment_profiles")
