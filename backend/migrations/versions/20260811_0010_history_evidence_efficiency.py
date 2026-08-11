"""add run history and evidence association foundations

Revision ID: 20260811_0010
Revises: 20260810_0009
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_0010"
down_revision: str | None = "20260810_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_runs",
        sa.Column("run_no", sa.String(20), nullable=True),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id FROM test_runs ORDER BY started_at, id")
    ).all()
    for sequence, row in enumerate(rows, start=1):
        connection.execute(
            sa.text("UPDATE test_runs SET run_no = :run_no WHERE id = :id"),
            {"run_no": f"RUN-{sequence:06d}", "id": row.id},
        )
    with op.batch_alter_table("test_runs") as batch:
        batch.alter_column(
            "run_no",
            existing_type=sa.String(20),
            nullable=False,
        )
    op.create_index(
        "uq_test_runs_run_no",
        "test_runs",
        ["run_no"],
        unique=True,
    )
    op.create_index(
        "ix_test_runs_started_at",
        "test_runs",
        ["started_at"],
    )
    op.create_index(
        "ix_test_runs_project_status_started",
        "test_runs",
        ["project_id", "status", "started_at"],
    )
    op.create_table(
        "evidence_run_result_links",
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("run_result_id", sa.String(36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["evidences.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_result_id"], ["run_results.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("evidence_id", "run_result_id"),
    )
    op.create_index(
        "ix_evidence_run_result_links_result_id",
        "evidence_run_result_links",
        ["run_result_id"],
    )
    connection.execute(
        sa.text(
            "INSERT INTO evidence_run_result_links "
            "(evidence_id, run_result_id, created_at) "
            "SELECT id, run_result_id, created_at FROM evidences "
            "WHERE run_result_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    extra_links = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM evidence_run_result_links links "
            "JOIN evidences evidence ON evidence.id = links.evidence_id "
            "WHERE evidence.run_result_id != links.run_result_id"
        )
    ).scalar_one()
    if extra_links:
        raise RuntimeError(
            "Cannot downgrade while multi-result evidence links exist"
        )
    op.drop_index(
        "ix_evidence_run_result_links_result_id",
        table_name="evidence_run_result_links",
    )
    op.drop_table("evidence_run_result_links")
    op.drop_index("ix_test_runs_project_status_started", table_name="test_runs")
    op.drop_index("ix_test_runs_started_at", table_name="test_runs")
    op.drop_index("uq_test_runs_run_no", table_name="test_runs")
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_column("run_no")
