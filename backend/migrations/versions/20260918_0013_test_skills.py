"""add test skills parameters and steps

Revision ID: 20260918_0013
Revises: 20260918_0012
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0013"
down_revision: str | None = "20260918_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_code", sa.String(100), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("spec_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("applicable_devices", sa.JSON(), nullable=False),
        sa.Column("preconditions", sa.JSON(), nullable=False),
        sa.Column("environment_requirements", sa.JSON(), nullable=False),
        sa.Column("validation_methods", sa.JSON(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("retired_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_code", "version", name="uq_test_skills_code_version"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_test_skills_status"),
        sa.CheckConstraint("(status = 'DRAFT' AND published_at IS NULL) OR (status IN ('PUBLISHED','RETIRED') AND published_at IS NOT NULL)", name="ck_test_skills_published_at"),
    )
    op.create_index("ix_test_skills_skill_code", "test_skills", ["skill_code"])
    op.create_index("ix_test_skills_status", "test_skills", ["status"])
    op.create_table(
        "skill_parameters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("param_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("default_value", sa.JSON(none_as_null=True)),
        sa.Column("constraints_json", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(30)),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text()),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_id", "param_key", name="uq_skill_parameters_key"),
        sa.UniqueConstraint("skill_id", "display_order", name="uq_skill_parameters_order"),
        sa.CheckConstraint("source IN ('CASE','RUN','ENVIRONMENT','DEVICE')", name="ck_skill_parameters_source"),
        sa.CheckConstraint("display_order >= 1", name="ck_skill_parameters_order"),
        sa.CheckConstraint("sensitive = 0 OR default_value IS NULL", name="ck_skill_parameters_sensitive_default"),
    )
    op.create_index("ix_skill_parameters_skill_id", "skill_parameters", ["skill_id"])
    op.create_table(
        "skill_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("expected_observation", sa.Text(), nullable=False),
        sa.Column("execution_mode", sa.String(20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("evidence_rule_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_id", "step_no", name="uq_skill_steps_number"),
        sa.CheckConstraint("step_no >= 1", name="ck_skill_steps_number"),
        sa.CheckConstraint("execution_mode IN ('RUNNER','OPERATOR','HYBRID')", name="ck_skill_steps_execution_mode"),
    )
    op.create_index("ix_skill_steps_skill_id", "skill_steps", ["skill_id"])


def downgrade() -> None:
    published = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM test_skills WHERE status IN ('PUBLISHED','RETIRED')")).scalar_one()
    if published:
        raise RuntimeError("Cannot downgrade while published Skill history exists")
    op.drop_index("ix_skill_steps_skill_id", table_name="skill_steps")
    op.drop_table("skill_steps")
    op.drop_index("ix_skill_parameters_skill_id", table_name="skill_parameters")
    op.drop_table("skill_parameters")
    op.drop_index("ix_test_skills_status", table_name="test_skills")
    op.drop_index("ix_test_skills_skill_code", table_name="test_skills")
    op.drop_table("test_skills")
