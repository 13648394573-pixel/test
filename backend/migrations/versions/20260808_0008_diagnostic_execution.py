"""add diagnostic execution workflow

Revision ID: 20260808_0008
Revises: 20260730_0007
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260808_0008"
down_revision: str | None = "20260730_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_result_id", sa.String(36), nullable=False),
        sa.Column("retry_of_session_id", sa.String(36)),
        sa.Column("adapter_key", sa.String(100), nullable=False),
        sa.Column("adapter_version", sa.String(30), nullable=False),
        sa.Column("wan_mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_code", sa.String(60)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.CheckConstraint("wan_mode IN ('IPOE', 'PPPOE')", name="ck_diagnostic_sessions_wan_mode"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED')",
            name="ck_diagnostic_sessions_status",
        ),
        sa.CheckConstraint("snapshot_version = 1", name="ck_diagnostic_sessions_snapshot_version"),
        sa.ForeignKeyConstraint(["run_result_id"], ["run_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retry_of_session_id"], ["diagnostic_sessions.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_diagnostic_sessions_run_result_id", "diagnostic_sessions", ["run_result_id"])
    op.create_index(
        "uq_diagnostic_sessions_active_result",
        "diagnostic_sessions",
        ["run_result_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )

    op.create_table(
        "diagnostic_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("layer", sa.String(20), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("packets_sent", sa.Integer(), nullable=False),
        sa.Column("packets_received", sa.Integer(), nullable=False),
        sa.Column("loss_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("latency_min_ms", sa.Numeric(10, 3)),
        sa.Column("latency_avg_ms", sa.Numeric(10, 3)),
        sa.Column("latency_max_ms", sa.Numeric(10, 3)),
        sa.Column("raw_output", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_diagnostic_attempts_sequence"),
        sa.CheckConstraint("attempt_number > 0", name="ck_diagnostic_attempts_attempt_number"),
        sa.CheckConstraint("layer IN ('GATEWAY', 'PUBLIC_IP', 'DOMAIN')", name="ck_diagnostic_attempts_layer"),
        sa.CheckConstraint("status IN ('PASS', 'FAIL', 'ERROR')", name="ck_diagnostic_attempts_status"),
        sa.CheckConstraint("packets_sent >= 0 AND packets_received >= 0 AND packets_received <= packets_sent", name="ck_diagnostic_attempts_packets"),
        sa.CheckConstraint("loss_percent >= 0 AND loss_percent <= 100", name="ck_diagnostic_attempts_loss"),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_diagnostic_attempts_session_sequence"),
    )
    op.create_index("ix_diagnostic_attempts_session_id", "diagnostic_attempts", ["session_id"])

    op.create_table(
        "diagnostic_attempt_evidences",
        sa.Column("diagnostic_attempt_id", sa.String(36), primary_key=True),
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.ForeignKeyConstraint(["diagnostic_attempt_id"], ["diagnostic_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("diagnostic_attempt_evidences")
    op.drop_index("ix_diagnostic_attempts_session_id", table_name="diagnostic_attempts")
    op.drop_table("diagnostic_attempts")
    op.drop_index("uq_diagnostic_sessions_active_result", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_sessions_run_result_id", table_name="diagnostic_sessions")
    op.drop_table("diagnostic_sessions")
