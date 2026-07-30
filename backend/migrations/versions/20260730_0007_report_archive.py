"""add report and archive workflow

Revision ID: 20260730_0007
Revises: 20260730_0006
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0007"
down_revision: str | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_no", sa.String(length=30), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("test_run_id", sa.String(length=36), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "snapshot_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("report_snapshot", sa.JSON(), nullable=False),
        sa.Column("html_storage_path", sa.String(length=500), nullable=False),
        sa.Column("html_sha256", sa.String(length=64), nullable=False),
        sa.Column("html_file_size", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("report_version >= 1", name="ck_reports_version"),
        sa.CheckConstraint(
            "snapshot_version = 1",
            name="ck_reports_snapshot_version",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["test_projects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"], ["test_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_no", name="uq_reports_report_no"),
        sa.UniqueConstraint(
            "test_run_id",
            "report_version",
            name="uq_reports_run_version",
        ),
    )
    op.create_index("ix_reports_project_id", "reports", ["project_id"])
    op.create_index("ix_reports_test_run_id", "reports", ["test_run_id"])
    op.create_table(
        "archives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("archive_no", sa.String(length=30), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column(
            "manifest_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("manifest_snapshot", sa.JSON(), nullable=False),
        sa.Column("archive_storage_path", sa.String(length=500), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("archive_file_size", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "manifest_version = 1",
            name="ck_archives_manifest_version",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["test_projects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["reports.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("archive_no", name="uq_archives_archive_no"),
        sa.UniqueConstraint("report_id", name="uq_archives_report_id"),
    )
    op.create_index("ix_archives_project_id", "archives", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_archives_project_id", table_name="archives")
    op.drop_table("archives")
    op.drop_index("ix_reports_test_run_id", table_name="reports")
    op.drop_index("ix_reports_project_id", table_name="reports")
    op.drop_table("reports")
