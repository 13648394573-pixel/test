"""add skill rules evidence rules and standard bindings

Revision ID: 20260918_0014
Revises: 20260918_0013
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0014"
down_revision: str | None = "20260918_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_standard_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_requirement_id", sa.String(36), sa.ForeignKey("standard_requirements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("binding_code", sa.String(120), nullable=False),
        sa.Column("fact_key", sa.String(100), nullable=False),
        sa.Column("on_match", sa.String(30), nullable=False, server_default="PASS_CONDITION"),
        sa.Column("on_mismatch", sa.String(20), nullable=False, server_default="FAIL"),
        sa.Column("on_missing", sa.String(20), nullable=False, server_default="BLOCKED"),
        sa.Column("unit_conversion", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_id", "binding_code", name="uq_skill_standard_bindings_code"),
        sa.UniqueConstraint("skill_id", "standard_requirement_id", "fact_key", name="uq_skill_standard_bindings_fact"),
        sa.CheckConstraint("on_match = 'PASS_CONDITION'", name="ck_skill_standard_bindings_match"),
        sa.CheckConstraint("on_mismatch = 'FAIL'", name="ck_skill_standard_bindings_mismatch"),
        sa.CheckConstraint("on_missing IN ('BLOCKED','DRAFT')", name="ck_skill_standard_bindings_missing"),
    )
    op.create_index("ix_skill_standard_bindings_skill_id", "skill_standard_bindings", ["skill_id"])
    op.create_index("ix_skill_standard_bindings_standard_requirement_id", "skill_standard_bindings", ["standard_requirement_id"])
    op.create_table(
        "skill_execution_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_code", sa.String(100), nullable=False),
        sa.Column("result_type", sa.String(20), nullable=False),
        sa.Column("fact_key", sa.String(100), nullable=False),
        sa.Column("operator", sa.String(30), nullable=False),
        sa.Column("expected_value", sa.JSON(none_as_null=True)),
        sa.Column("expected_parameter_key", sa.String(100)),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evaluation_source", sa.String(20), nullable=False),
        sa.Column("standard_binding_id", sa.String(36), sa.ForeignKey("skill_standard_bindings.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_id", "rule_code", name="uq_skill_execution_rules_code"),
        sa.UniqueConstraint("skill_id", "result_type", "priority", name="uq_skill_execution_rules_priority"),
        sa.CheckConstraint("result_type IN ('PASS','FAIL','BLOCKED')", name="ck_skill_execution_rules_result"),
        sa.CheckConstraint("operator IN ('EQ','NE','GT','GTE','LT','LTE','IN','NOT_IN','EXISTS','NOT_EXISTS','MATCHES','CIDR_CONTAINS')", name="ck_skill_execution_rules_operator"),
        sa.CheckConstraint("priority >= 1", name="ck_skill_execution_rules_priority"),
        sa.CheckConstraint("evaluation_source IN ('FIXED','STANDARD')", name="ck_skill_execution_rules_source"),
        sa.CheckConstraint("NOT (expected_value IS NOT NULL AND expected_parameter_key IS NOT NULL)", name="ck_skill_execution_rules_one_expectation"),
        sa.CheckConstraint("operator NOT IN ('EXISTS','NOT_EXISTS') OR (expected_value IS NULL AND expected_parameter_key IS NULL)", name="ck_skill_execution_rules_exists_expectation"),
        sa.CheckConstraint("(evaluation_source = 'STANDARD' AND standard_binding_id IS NOT NULL AND expected_value IS NULL AND expected_parameter_key IS NULL) OR (evaluation_source = 'FIXED' AND standard_binding_id IS NULL)", name="ck_skill_execution_rules_standard_binding"),
    )
    op.create_index("ix_skill_execution_rules_skill_id", "skill_execution_rules", ["skill_id"])
    op.create_table(
        "skill_evidence_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_code", sa.String(100), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("required_for", sa.JSON(), nullable=False),
        sa.Column("min_count", sa.Integer(), nullable=False),
        sa.Column("max_count", sa.Integer()),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sensitive_content", sa.String(20), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_id", "rule_code", name="uq_skill_evidence_rules_code"),
        sa.UniqueConstraint("skill_id", "display_order", name="uq_skill_evidence_rules_order"),
        sa.CheckConstraint("category IN ('SCREENSHOT','LOG','CONFIG','OTHER')", name="ck_skill_evidence_rules_category"),
        sa.CheckConstraint("min_count >= 0", name="ck_skill_evidence_rules_min_count"),
        sa.CheckConstraint("max_count IS NULL OR max_count >= min_count", name="ck_skill_evidence_rules_max_count"),
        sa.CheckConstraint("display_order >= 1", name="ck_skill_evidence_rules_order"),
        sa.CheckConstraint("sensitive_content IN ('NONE','REDACT','PROHIBITED')", name="ck_skill_evidence_rules_sensitive"),
    )
    op.create_index("ix_skill_evidence_rules_skill_id", "skill_evidence_rules", ["skill_id"])


def downgrade() -> None:
    published = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM test_skills WHERE status IN ('PUBLISHED','RETIRED')")).scalar_one()
    if published:
        raise RuntimeError("Cannot downgrade while published Skill history exists")
    op.drop_index("ix_skill_evidence_rules_skill_id", table_name="skill_evidence_rules")
    op.drop_table("skill_evidence_rules")
    op.drop_index("ix_skill_execution_rules_skill_id", table_name="skill_execution_rules")
    op.drop_table("skill_execution_rules")
    op.drop_index("ix_skill_standard_bindings_standard_requirement_id", table_name="skill_standard_bindings")
    op.drop_index("ix_skill_standard_bindings_skill_id", table_name="skill_standard_bindings")
    op.drop_table("skill_standard_bindings")
