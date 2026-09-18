"""add Skill Case bindings and execution Templates

Revision ID: 20260918_0015
Revises: 20260918_0014
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0015"
down_revision: str | None = "20260918_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("test_case_id", sa.String(36), sa.ForeignKey("test_cases.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("parameter_values", sa.JSON(), nullable=False),
        sa.Column("binding_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("binding_version >= 1", name="ck_skill_cases_binding_version"),
    )
    op.create_index("ix_skill_cases_skill_id", "skill_cases", ["skill_id"])
    op.create_table(
        "templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("template_code", "version", name="uq_templates_code_version"),
        sa.CheckConstraint("status IN ('DRAFT','ACTIVE','RETIRED')", name="ck_templates_status"),
        sa.CheckConstraint("version >= 1", name="ck_templates_version"),
    )
    op.create_index("ix_templates_template_code", "templates", ["template_code"])
    op.create_index("ix_templates_status", "templates", ["status"])
    op.create_table(
        "template_cases",
        sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("test_case_id", sa.String(36), sa.ForeignKey("test_cases.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("template_id", "display_order", name="uq_template_cases_order"),
        sa.CheckConstraint("display_order >= 1", name="ck_template_cases_order"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    active = connection.execute(
        sa.text("SELECT COUNT(*) FROM templates WHERE status IN ('ACTIVE','RETIRED')")
    ).scalar_one()
    if active:
        raise RuntimeError("Cannot downgrade while active Template history exists")
    inspector = sa.inspect(connection)
    run_columns = {column["name"] for column in inspector.get_columns("test_runs")}
    if "template_source_id" in run_columns:
        referenced = connection.execute(
            sa.text("SELECT COUNT(*) FROM test_runs WHERE template_source_id IS NOT NULL")
        ).scalar_one()
        if referenced:
            raise RuntimeError("Cannot downgrade while V2 Runs reference Templates")
    op.drop_table("template_cases")
    op.drop_index("ix_templates_status", table_name="templates")
    op.drop_index("ix_templates_template_code", table_name="templates")
    op.drop_table("templates")
    op.drop_index("ix_skill_cases_skill_id", table_name="skill_cases")
    op.drop_table("skill_cases")
