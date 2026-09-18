"""add V2 execution snapshots while preserving V1 history

Revision ID: 20260918_0016
Revises: 20260918_0015
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0016"
down_revision: str | None = "20260918_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("test_runs") as batch:
        batch.add_column(sa.Column("template_source_id", sa.String(36)))
        batch.add_column(sa.Column("template_snapshot", sa.JSON()))
        batch.add_column(sa.Column("execution_plan_snapshot", sa.JSON()))
        batch.add_column(sa.Column("execution_schema_version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"))
        batch.add_column(sa.Column("standard_profile_source_id", sa.String(36)))
        batch.add_column(sa.Column("standard_snapshot", sa.JSON()))
        batch.create_foreign_key("fk_test_runs_template_source", "templates", ["template_source_id"], ["id"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_test_runs_standard_profile_source", "standard_profiles", ["standard_profile_source_id"], ["id"], ondelete="RESTRICT")
        batch.create_check_constraint("ck_test_runs_source", "source IN ('MANUAL','LOCAL_RUNNER','HYBRID')")
        batch.create_check_constraint("ck_test_runs_execution_schema_version", "execution_schema_version >= 1")
    with op.batch_alter_table("run_results") as batch:
        batch.add_column(sa.Column("skill_source_id", sa.String(36)))
        batch.add_column(sa.Column("skill_snapshot", sa.JSON()))
        batch.add_column(sa.Column("parameter_snapshot", sa.JSON()))
        batch.add_column(sa.Column("observations", sa.JSON()))
        batch.add_column(sa.Column("matched_rule_codes", sa.JSON()))
        batch.add_column(sa.Column("standard_evaluations", sa.JSON()))
        batch.add_column(sa.Column("evidence_validation", sa.JSON()))
        batch.add_column(sa.Column("result_source", sa.String(20), nullable=False, server_default="MANUAL"))
        batch.create_foreign_key("fk_run_results_skill_source", "test_skills", ["skill_source_id"], ["id"], ondelete="RESTRICT")
        batch.create_check_constraint("ck_run_results_result_source", "result_source IN ('MANUAL','RULE_ENGINE')")
    with op.batch_alter_table("evidences") as batch:
        batch.add_column(sa.Column("evidence_rule_code", sa.String(100)))


def downgrade() -> None:
    connection = op.get_bind()
    v2_rows = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM test_runs WHERE execution_schema_version > 1 "
            "OR template_source_id IS NOT NULL OR standard_profile_source_id IS NOT NULL"
        )
    ).scalar_one()
    if v2_rows:
        raise RuntimeError("Cannot downgrade while V2 Run snapshots exist")
    with op.batch_alter_table("evidences") as batch:
        batch.drop_column("evidence_rule_code")
    with op.batch_alter_table("run_results") as batch:
        batch.drop_constraint("ck_run_results_result_source", type_="check")
        batch.drop_constraint("fk_run_results_skill_source", type_="foreignkey")
        for column in (
            "result_source", "evidence_validation", "standard_evaluations",
            "matched_rule_codes", "observations", "parameter_snapshot",
            "skill_snapshot", "skill_source_id",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_constraint("ck_test_runs_execution_schema_version", type_="check")
        batch.drop_constraint("ck_test_runs_source", type_="check")
        batch.drop_constraint("fk_test_runs_standard_profile_source", type_="foreignkey")
        batch.drop_constraint("fk_test_runs_template_source", type_="foreignkey")
        for column in (
            "standard_snapshot", "standard_profile_source_id", "source",
            "execution_schema_version", "execution_plan_snapshot",
            "template_snapshot", "template_source_id",
        ):
            batch.drop_column(column)
