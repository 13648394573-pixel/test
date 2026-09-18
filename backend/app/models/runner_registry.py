from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, attributes, mapped_column, relationship

from app.db.base import Base


ACTION_PHASES = "('PREFLIGHT','SNAPSHOT','EXECUTE','VERIFY','RESTORE','RESTORE_VERIFY')"


class RunnerPlugin(Base):
    __tablename__ = "runner_plugins"
    __table_args__ = (
        UniqueConstraint("plugin_code", "version", name="uq_runner_plugins_code_version"),
        CheckConstraint(
            "status IN ('DEVELOPMENT','PUBLISHED','RETIRED','INVALID')",
            name="ck_runner_plugins_status",
        ),
        CheckConstraint("length(package_sha256) = 64", name="ck_runner_plugins_sha256"),
        CheckConstraint(
            "length(install_path_ref) > 0 AND install_path_ref NOT LIKE '/%' "
            "AND install_path_ref NOT GLOB '[A-Za-z]:*' "
            "AND instr(install_path_ref, '..') = 0",
            name="ck_runner_plugins_relative_path",
        ),
        CheckConstraint(
            "status NOT IN ('PUBLISHED','RETIRED') OR published_at IS NOT NULL",
            name="ck_runner_plugins_published_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plugin_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DEVELOPMENT", server_default="DEVELOPMENT", index=True
    )
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    install_path_ref: Mapped[str] = mapped_column(Text, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    actions: Mapped[list[RunnerAction]] = relationship(
        back_populates="plugin", cascade="all, delete-orphan", order_by="RunnerAction.action_code"
    )


class RunnerAction(Base):
    __tablename__ = "runner_actions"
    __table_args__ = (
        UniqueConstraint("plugin_id", "action_code", name="uq_runner_actions_code"),
        CheckConstraint(f"phase IN {ACTION_PHASES}", name="ck_runner_actions_phase"),
        CheckConstraint("timeout_seconds > 0", name="ck_runner_actions_timeout"),
        CheckConstraint(
            "recovery_capability IN ('NONE','RESTORE','RESTORE_VERIFY')",
            name="ck_runner_actions_recovery",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plugin_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runner_plugins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_code: Mapped[str] = mapped_column(String(120), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    recovery_capability: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE", server_default="NONE")
    adapter_selector: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    plugin: Mapped[RunnerPlugin] = relationship(back_populates="actions")


class SkillRunnerBinding(Base):
    __tablename__ = "skill_runner_bindings"
    __table_args__ = (
        UniqueConstraint(
            "skill_id", "phase", "display_order", name="uq_skill_runner_bindings_order"
        ),
        CheckConstraint(f"phase IN {ACTION_PHASES}", name="ck_skill_runner_bindings_phase"),
        CheckConstraint("display_order >= 1", name="ck_skill_runner_bindings_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_step_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skill_steps.id", ondelete="RESTRICT")
    )
    runner_action_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runner_actions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    parameter_mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    observation_mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    adapter_selector: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    skill = relationship("TestSkill")
    skill_step = relationship("SkillStep")
    runner_action: Mapped[RunnerAction] = relationship()


def _keep_published_plugin_immutable(
    target: RunnerPlugin,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if (
        target.status in {"PUBLISHED", "RETIRED"}
        and old_value is not attributes.NO_VALUE
        and value != old_value
    ):
        raise ValueError("Published Runner Plugin package identity is immutable")
    return value


for immutable_attribute in (
    RunnerPlugin.plugin_code,
    RunnerPlugin.version,
    RunnerPlugin.manifest_json,
    RunnerPlugin.package_sha256,
    RunnerPlugin.install_path_ref,
):
    event.listen(
        immutable_attribute,
        "set",
        _keep_published_plugin_immutable,
        retval=True,
        active_history=True,
    )
