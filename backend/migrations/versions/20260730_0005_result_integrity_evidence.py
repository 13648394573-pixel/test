"""add result integrity and evidence

Revision ID: 20260730_0005
Revises: 20260730_0004
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0005"
down_revision: str | None = "20260730_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_results") as batch:
        batch.add_column(
            sa.Column(
                "integrity_status",
                sa.String(length=10),
                server_default="DRAFT",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("actual_result", sa.Text(), nullable=True))
        batch.add_column(sa.Column("blocked_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("test_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("locked_at", sa.DateTime(), nullable=True))
        batch.create_check_constraint(
            "ck_run_results_integrity_status",
            "integrity_status IN ('DRAFT', 'LOCKED')",
        )

    op.execute(
        "UPDATE run_results "
        "SET integrity_status = CASE "
        "WHEN result IS NULL THEN 'DRAFT' ELSE 'LOCKED' END, "
        "locked_at = CASE WHEN result IS NULL THEN NULL ELSE executed_at END"
    )

    op.create_table(
        "evidences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_result_id", sa.String(length=36), nullable=True),
        sa.Column("defect_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "((run_result_id IS NOT NULL AND defect_id IS NULL) OR "
            "(run_result_id IS NULL AND defect_id IS NOT NULL))",
            name="ck_evidences_exactly_one_owner",
        ),
        sa.CheckConstraint(
            "category IN ('SCREENSHOT', 'LOG', 'CONFIG', 'OTHER')",
            name="ck_evidences_category",
        ),
        sa.ForeignKeyConstraint(
            ["run_result_id"],
            ["run_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"],
            ["defects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_path",
            name="uq_evidences_storage_path",
        ),
    )
    op.create_index(
        "ix_evidences_run_result_id",
        "evidences",
        ["run_result_id"],
    )
    op.create_index("ix_evidences_defect_id", "evidences", ["defect_id"])


def downgrade() -> None:
    op.drop_index("ix_evidences_defect_id", table_name="evidences")
    op.drop_index("ix_evidences_run_result_id", table_name="evidences")
    op.drop_table("evidences")
    with op.batch_alter_table("run_results") as batch:
        batch.drop_constraint(
            "ck_run_results_integrity_status",
            type_="check",
        )
        batch.drop_column("locked_at")
        batch.drop_column("test_notes")
        batch.drop_column("blocked_reason")
        batch.drop_column("actual_result")
        batch.drop_column("integrity_status")
