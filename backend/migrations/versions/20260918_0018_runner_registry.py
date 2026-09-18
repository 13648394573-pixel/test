"""add controlled Runner Plugin and Action registry

Revision ID: 20260918_0018
Revises: 20260918_0017
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0018"
down_revision: str | None = "20260918_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTION_PHASES = "('PREFLIGHT','SNAPSHOT','EXECUTE','VERIFY','RESTORE','RESTORE_VERIFY')"


def upgrade() -> None:
    op.create_table(
        "runner_plugins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plugin_code", sa.String(120), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DEVELOPMENT"),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("package_sha256", sa.String(64), nullable=False),
        sa.Column("install_path_ref", sa.Text(), nullable=False),
        sa.Column("installed_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("published_at", sa.DateTime()),
        sa.UniqueConstraint("plugin_code", "version", name="uq_runner_plugins_code_version"),
        sa.CheckConstraint("status IN ('DEVELOPMENT','PUBLISHED','RETIRED','INVALID')", name="ck_runner_plugins_status"),
        sa.CheckConstraint("length(package_sha256) = 64", name="ck_runner_plugins_sha256"),
        sa.CheckConstraint("length(install_path_ref) > 0 AND install_path_ref NOT LIKE '/%' AND install_path_ref NOT GLOB '[A-Za-z]:*' AND instr(install_path_ref, '..') = 0", name="ck_runner_plugins_relative_path"),
        sa.CheckConstraint("status NOT IN ('PUBLISHED','RETIRED') OR published_at IS NOT NULL", name="ck_runner_plugins_published_at"),
    )
    op.create_index("ix_runner_plugins_plugin_code", "runner_plugins", ["plugin_code"])
    op.create_index("ix_runner_plugins_status", "runner_plugins", ["status"])
    op.create_table(
        "runner_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plugin_id", sa.String(36), sa.ForeignKey("runner_plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_code", sa.String(120), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("idempotent", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("recovery_capability", sa.String(20), nullable=False, server_default="NONE"),
        sa.Column("adapter_selector", sa.JSON(), nullable=False),
        sa.UniqueConstraint("plugin_id", "action_code", name="uq_runner_actions_code"),
        sa.CheckConstraint(f"phase IN {ACTION_PHASES}", name="ck_runner_actions_phase"),
        sa.CheckConstraint("timeout_seconds > 0", name="ck_runner_actions_timeout"),
        sa.CheckConstraint("recovery_capability IN ('NONE','RESTORE','RESTORE_VERIFY')", name="ck_runner_actions_recovery"),
    )
    op.create_index("ix_runner_actions_plugin_id", "runner_actions", ["plugin_id"])
    op.create_table(
        "skill_runner_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_step_id", sa.String(36), sa.ForeignKey("skill_steps.id", ondelete="RESTRICT")),
        sa.Column("runner_action_id", sa.String(36), sa.ForeignKey("runner_actions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("parameter_mapping", sa.JSON(), nullable=False),
        sa.Column("observation_mapping", sa.JSON(), nullable=False),
        sa.Column("adapter_selector", sa.JSON(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("skill_id", "phase", "display_order", name="uq_skill_runner_bindings_order"),
        sa.CheckConstraint(f"phase IN {ACTION_PHASES}", name="ck_skill_runner_bindings_phase"),
        sa.CheckConstraint("display_order >= 1", name="ck_skill_runner_bindings_order"),
    )
    op.create_index("ix_skill_runner_bindings_skill_id", "skill_runner_bindings", ["skill_id"])
    op.create_index("ix_skill_runner_bindings_runner_action_id", "skill_runner_bindings", ["runner_action_id"])


def downgrade() -> None:
    op.drop_index("ix_skill_runner_bindings_runner_action_id", table_name="skill_runner_bindings")
    op.drop_index("ix_skill_runner_bindings_skill_id", table_name="skill_runner_bindings")
    op.drop_table("skill_runner_bindings")
    op.drop_index("ix_runner_actions_plugin_id", table_name="runner_actions")
    op.drop_table("runner_actions")
    op.drop_index("ix_runner_plugins_status", table_name="runner_plugins")
    op.drop_index("ix_runner_plugins_plugin_code", table_name="runner_plugins")
    op.drop_table("runner_plugins")
