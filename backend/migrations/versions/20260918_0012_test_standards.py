"""add versioned test standards and profiles

Revision ID: 20260918_0012
Revises: 20260918_0011
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_0012"
down_revision: str | None = "20260918_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_standards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("standard_code", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("issuer", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("region_code", sa.String(30)),
        sa.Column("language_code", sa.String(35), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("standard_code", "version", name="uq_test_standards_code_version"),
        sa.CheckConstraint("source_type IN ('INTERNAL','CUSTOMER','OPERATOR','COUNTRY','REGION','INDUSTRY')", name="ck_test_standards_source_type"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_test_standards_status"),
        sa.CheckConstraint("(status = 'DRAFT' AND published_at IS NULL) OR (status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)", name="ck_test_standards_published_at"),
        sa.CheckConstraint("effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from", name="ck_test_standards_effective_dates"),
    )
    op.create_index("ix_test_standards_standard_code", "test_standards", ["standard_code"])
    op.create_index("ix_test_standards_status", "test_standards", ["status"])
    op.create_table(
        "standard_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("standard_id", sa.String(36), sa.ForeignKey("test_standards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_code", sa.String(120), nullable=False),
        sa.Column("clause_reference", sa.String(120)),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirement_level", sa.String(20), nullable=False),
        sa.Column("applicability", sa.JSON(), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("operator", sa.String(30), nullable=False),
        sa.Column("expected_value", sa.JSON()),
        sa.Column("unit", sa.String(30)),
        sa.Column("source_text_reference", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("standard_id", "requirement_code", name="uq_standard_requirements_code"),
        sa.UniqueConstraint("standard_id", "display_order", name="uq_standard_requirements_order"),
        sa.CheckConstraint("requirement_level IN ('MANDATORY','RECOMMENDED','INFORMATIVE')", name="ck_standard_requirements_level"),
        sa.CheckConstraint("display_order >= 1", name="ck_standard_requirements_order"),
    )
    op.create_index("ix_standard_requirements_standard_id", "standard_requirements", ["standard_id"])
    op.create_table(
        "standard_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_code", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("country_code", sa.String(2)),
        sa.Column("region_code", sa.String(30)),
        sa.Column("customer_name", sa.String(200)),
        sa.Column("operator_name", sa.String(200)),
        sa.Column("merge_policy", sa.String(40), nullable=False, server_default="ALL_MANDATORY_MUST_PASS"),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("profile_code", "version", name="uq_standard_profiles_code_version"),
        sa.CheckConstraint("version >= 1", name="ck_standard_profiles_version"),
        sa.CheckConstraint("merge_policy = 'ALL_MANDATORY_MUST_PASS'", name="ck_standard_profiles_merge_policy"),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_standard_profiles_status"),
        sa.CheckConstraint("(status = 'DRAFT' AND published_at IS NULL) OR (status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)", name="ck_standard_profiles_published_at"),
    )
    op.create_index("ix_standard_profiles_profile_code", "standard_profiles", ["profile_code"])
    op.create_index("ix_standard_profiles_status", "standard_profiles", ["status"])
    op.create_table(
        "standard_profile_items",
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("standard_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("standard_id", sa.String(36), sa.ForeignKey("test_standards.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("profile_id", "display_order", name="uq_standard_profile_items_order"),
        sa.CheckConstraint("display_order >= 1", name="ck_standard_profile_items_order"),
    )
    op.create_table(
        "project_standard_profiles",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("test_projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("standard_profile_id", sa.String(36), sa.ForeignKey("standard_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("selected_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_project_standard_profiles_standard_profile_id", "project_standard_profiles", ["standard_profile_id"])


def downgrade() -> None:
    connection = op.get_bind()
    published_standards = connection.execute(
        sa.text("SELECT COUNT(*) FROM test_standards WHERE status IN ('PUBLISHED','RETIRED')")
    ).scalar_one()
    published_profiles = connection.execute(
        sa.text("SELECT COUNT(*) FROM standard_profiles WHERE status IN ('PUBLISHED','RETIRED')")
    ).scalar_one()
    if published_standards or published_profiles:
        raise RuntimeError("Cannot downgrade while published standard history exists")
    op.drop_index("ix_project_standard_profiles_standard_profile_id", table_name="project_standard_profiles")
    op.drop_table("project_standard_profiles")
    op.drop_table("standard_profile_items")
    op.drop_index("ix_standard_profiles_status", table_name="standard_profiles")
    op.drop_index("ix_standard_profiles_profile_code", table_name="standard_profiles")
    op.drop_table("standard_profiles")
    op.drop_index("ix_standard_requirements_standard_id", table_name="standard_requirements")
    op.drop_table("standard_requirements")
    op.drop_index("ix_test_standards_status", table_name="test_standards")
    op.drop_index("ix_test_standards_standard_code", table_name="test_standards")
    op.drop_table("test_standards")
