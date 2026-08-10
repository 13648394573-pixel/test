"""add focused regression run workflow

Revision ID: 20260810_0009
Revises: 20260808_0008
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260810_0009"
down_revision: str | None = "20260808_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "focused_regression_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("test_run_id", sa.String(36), nullable=False),
        sa.Column("defect_id", sa.String(36), nullable=False),
        sa.Column("source_run_result_id", sa.String(36), nullable=False),
        sa.Column("defect_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "snapshot_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "snapshot_version = 1",
            name="ck_focused_regression_runs_snapshot_version",
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"],
            ["defects.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_result_id"],
            ["run_results.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "test_run_id",
            name="uq_focused_regression_runs_test_run_id",
        ),
    )
    op.create_index(
        "ix_focused_regression_runs_defect_id",
        "focused_regression_runs",
        ["defect_id"],
    )
    op.create_index(
        "ix_focused_regression_runs_source_run_result_id",
        "focused_regression_runs",
        ["source_run_result_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_focused_regression_runs_source_run_result_id",
        table_name="focused_regression_runs",
    )
    op.drop_index(
        "ix_focused_regression_runs_defect_id",
        table_name="focused_regression_runs",
    )
    op.drop_table("focused_regression_runs")
