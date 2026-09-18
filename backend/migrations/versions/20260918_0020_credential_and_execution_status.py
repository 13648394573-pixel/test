"""add credential references and execution status links

Revision ID: 20260918_0020
Revises: 20260918_0019
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0020"
down_revision: str | None = "20260918_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credential_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purpose", sa.String(200), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("credential_target_ref", sa.String(300), nullable=False, unique=True),
        sa.Column("masked_display_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("target_type IN ('OLT','ONU','PPPOE','TR069','SERVICE','OTHER')", name="ck_credential_references_target_type"),
    )
    with op.batch_alter_table("test_runs") as batch:
        batch.add_column(sa.Column("execution_status", sa.String(30)))
        batch.create_check_constraint("ck_test_runs_execution_status", "execution_status IS NULL OR execution_status IN ('CREATED','PREFLIGHT','RUNNING','WAITING_OPERATOR','EVALUATING','RESTORING','COMPLETED','BLOCKED','ERROR','CANCELLED','RECOVERY_REQUIRED')")
    with op.batch_alter_table("run_results") as batch:
        batch.add_column(sa.Column("execution_session_id", sa.String(36)))
        batch.add_column(sa.Column("functional_verdict", sa.String(20)))
        batch.add_column(sa.Column("recovery_status", sa.String(30)))
        batch.create_foreign_key("fk_run_results_execution_session", "execution_sessions", ["execution_session_id"], ["id"], ondelete="SET NULL")
        batch.create_unique_constraint("uq_run_results_execution_session_id", ["execution_session_id"])
        batch.create_check_constraint("ck_run_results_functional_verdict", "functional_verdict IS NULL OR functional_verdict IN ('PASS','FAIL','BLOCKED','NOT_EVALUATED')")
        batch.create_check_constraint("ck_run_results_recovery_status", "recovery_status IS NULL OR recovery_status IN ('NOT_REQUIRED','PENDING','VERIFIED','FAILED','MANUAL_REQUIRED')")


def downgrade() -> None:
    connection = op.get_bind()
    unfinished = connection.execute(sa.text("SELECT COUNT(*) FROM execution_sessions WHERE status NOT IN ('COMPLETED','BLOCKED','ERROR','CANCELLED')")).scalar_one()
    unsafe_recovery = connection.execute(sa.text("SELECT COUNT(*) FROM recovery_tasks WHERE required = 1 AND status != 'VERIFIED'")).scalar_one()
    if unfinished or unsafe_recovery:
        raise RuntimeError("Cannot downgrade while execution or recovery work is unfinished")
    with op.batch_alter_table("run_results") as batch:
        batch.drop_constraint("ck_run_results_recovery_status", type_="check")
        batch.drop_constraint("ck_run_results_functional_verdict", type_="check")
        batch.drop_constraint("uq_run_results_execution_session_id", type_="unique")
        batch.drop_constraint("fk_run_results_execution_session", type_="foreignkey")
        batch.drop_column("recovery_status")
        batch.drop_column("functional_verdict")
        batch.drop_column("execution_session_id")
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_constraint("ck_test_runs_execution_status", type_="check")
        batch.drop_column("execution_status")
    op.drop_table("credential_references")
