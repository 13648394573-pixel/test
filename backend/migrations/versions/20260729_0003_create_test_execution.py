"""create test execution tables

Revision ID: 20260729_0003
Revises: 20260729_0002
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
    )
    op.create_table(
        "project_case_selections",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("case_source_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["test_projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "case_source_id"),
    )
    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("device_source_id", sa.String(length=36), nullable=False),
        sa.Column("device_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "snapshot_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="IN_PROGRESS",
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED')",
            name="ck_test_runs_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["test_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_test_runs_project_id",
        "test_runs",
        ["project_id"],
    )
    op.create_table(
        "run_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("case_source_id", sa.String(length=36), nullable=False),
        sa.Column("case_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "snapshot_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("result", sa.String(length=10), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "result IS NULL OR result IN ('PASS', 'FAIL', 'BLOCKED')",
            name="ck_run_results_result",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["test_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "case_source_id",
            name="uq_run_results_run_case_source",
        ),
    )
    op.create_index("ix_run_results_run_id", "run_results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_results_run_id", table_name="run_results")
    op.drop_table("run_results")
    op.drop_index("ix_test_runs_project_id", table_name="test_runs")
    op.drop_table("test_runs")
    op.drop_table("project_case_selections")
    op.drop_table("test_projects")
