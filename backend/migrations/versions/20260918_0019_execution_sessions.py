"""add execution sessions events operator interactions and recovery

Revision ID: 20260918_0019
Revises: 20260918_0018
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0019"
down_revision: str | None = "20260918_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXECUTION_STATUSES = "('CREATED','PREFLIGHT','RUNNING','WAITING_OPERATOR','EVALUATING','RESTORING','COMPLETED','BLOCKED','ERROR','CANCELLED','RECOVERY_REQUIRED')"
ACTIVE_STATUSES = "'CREATED','PREFLIGHT','RUNNING','WAITING_OPERATOR','EVALUATING','RESTORING','RECOVERY_REQUIRED'"


def upgrade() -> None:
    op.create_table(
        "execution_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("test_run_id", sa.String(36), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_result_id", sa.String(36), sa.ForeignKey("run_results.id", ondelete="CASCADE")),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="CREATED"),
        sa.Column("runner_instance_id", sa.String(100)),
        sa.Column("plugin_snapshot", sa.JSON()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("heartbeat_at", sa.DateTime()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("mode IN ('MANUAL','DEVELOPMENT','FORMAL')", name="ck_execution_sessions_mode"),
        sa.CheckConstraint(f"status IN {EXECUTION_STATUSES}", name="ck_execution_sessions_status"),
    )
    op.create_index("ix_execution_sessions_test_run_id", "execution_sessions", ["test_run_id"])
    op.create_index("ix_execution_sessions_run_result_id", "execution_sessions", ["run_result_id"])
    op.create_index(
        "uq_execution_sessions_active_result",
        "execution_sessions",
        ["run_result_id"],
        unique=True,
        sqlite_where=sa.text(f"run_result_id IS NOT NULL AND status IN ({ACTIVE_STATUSES})"),
    )
    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("step_ref", sa.String(100)),
        sa.Column("action_ref", sa.String(120)),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_execution_events_sequence"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_execution_events_idempotency"),
        sa.CheckConstraint("sequence_no >= 1", name="ck_execution_events_sequence"),
    )
    op.create_index("ix_execution_events_session_id", "execution_events", ["session_id"])
    op.create_table(
        "operator_interactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interaction_ref", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("completion_condition", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("responder_name", sa.String(200)),
        sa.Column("responded_at", sa.DateTime()),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidences.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("session_id", "interaction_ref", name="uq_operator_interactions_ref"),
        sa.CheckConstraint("status IN ('PENDING','COMPLETED','UNABLE','CANCELLED')", name="ck_operator_interactions_status"),
    )
    op.create_index("ix_operator_interactions_session_id", "operator_interactions", ["session_id"])
    op.create_table(
        "configuration_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_ref", sa.String(100), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("capture_action_ref", sa.String(120), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidences.id", ondelete="SET NULL")),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("length(sha256) = 64", name="ck_configuration_snapshots_sha256"),
    )
    op.create_index("ix_configuration_snapshots_session_id", "configuration_snapshots", ["session_id"])
    op.create_table(
        "recovery_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration_snapshot_id", sa.String(36), sa.ForeignKey("configuration_snapshots.id", ondelete="RESTRICT")),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("restore_action_ref", sa.String(120)),
        sa.Column("verify_action_ref", sa.String(120)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("manual_resolution", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("status IN ('PENDING','RUNNING','VERIFIED','FAILED','MANUAL_REQUIRED')", name="ck_recovery_tasks_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_recovery_tasks_attempt_count"),
    )
    op.create_index("ix_recovery_tasks_session_id", "recovery_tasks", ["session_id"])


def downgrade() -> None:
    connection = op.get_bind()
    unfinished = connection.execute(sa.text("SELECT COUNT(*) FROM execution_sessions WHERE status NOT IN ('COMPLETED','BLOCKED','ERROR','CANCELLED')")).scalar_one()
    unsafe_recovery = connection.execute(sa.text("SELECT COUNT(*) FROM recovery_tasks WHERE required = 1 AND status != 'VERIFIED'")).scalar_one()
    if unfinished or unsafe_recovery:
        raise RuntimeError("Cannot downgrade while execution or recovery work is unfinished")
    op.drop_index("ix_recovery_tasks_session_id", table_name="recovery_tasks")
    op.drop_table("recovery_tasks")
    op.drop_index("ix_configuration_snapshots_session_id", table_name="configuration_snapshots")
    op.drop_table("configuration_snapshots")
    op.drop_index("ix_operator_interactions_session_id", table_name="operator_interactions")
    op.drop_table("operator_interactions")
    op.drop_index("ix_execution_events_session_id", table_name="execution_events")
    op.drop_table("execution_events")
    op.drop_index("uq_execution_sessions_active_result", table_name="execution_sessions")
    op.drop_index("ix_execution_sessions_run_result_id", table_name="execution_sessions")
    op.drop_index("ix_execution_sessions_test_run_id", table_name="execution_sessions")
    op.drop_table("execution_sessions")
