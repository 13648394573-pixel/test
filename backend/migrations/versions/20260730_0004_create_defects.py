"""create defect and regression tables

Revision ID: 20260730_0004
Revises: 20260729_0003
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0004"
down_revision: str | None = "20260729_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "defects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("defect_code", sa.String(length=30), nullable=False),
        sa.Column("source_run_result_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reproduction_steps", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=2), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
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
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "severity IN ('S1', 'S2', 'S3', 'S4')",
            name="ck_defects_severity",
        ),
        sa.CheckConstraint(
            "status IN "
            "('OPEN', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED')",
            name="ck_defects_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_result_id"],
            ["run_results.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "defect_code",
            name="uq_defects_defect_code",
        ),
        sa.UniqueConstraint(
            "source_run_result_id",
            name="uq_defects_source_run_result_id",
        ),
    )
    op.create_index("ix_defects_status", "defects", ["status"])
    op.create_table(
        "regressions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("defect_id", sa.String(length=36), nullable=False),
        sa.Column(
            "verification_run_result_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "result IN ('PASS', 'FAIL', 'BLOCKED')",
            name="ck_regressions_result",
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"],
            ["defects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["verification_run_result_id"],
            ["run_results.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "defect_id",
            "verification_run_result_id",
            name="uq_regressions_defect_verification_result",
        ),
    )
    op.create_index("ix_regressions_defect_id", "regressions", ["defect_id"])


def downgrade() -> None:
    op.drop_index("ix_regressions_defect_id", table_name="regressions")
    op.drop_table("regressions")
    op.drop_index("ix_defects_status", table_name="defects")
    op.drop_table("defects")
