from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


EXECUTION_STATUSES = (
    "('CREATED','PREFLIGHT','RUNNING','WAITING_OPERATOR','EVALUATING',"
    "'RESTORING','COMPLETED','BLOCKED','ERROR','CANCELLED','RECOVERY_REQUIRED')"
)
ACTIVE_SESSION_STATUSES = (
    "'CREATED','PREFLIGHT','RUNNING','WAITING_OPERATOR','EVALUATING',"
    "'RESTORING','RECOVERY_REQUIRED'"
)


class ExecutionSession(Base):
    __tablename__ = "execution_sessions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('MANUAL','DEVELOPMENT','FORMAL')",
            name="ck_execution_sessions_mode",
        ),
        CheckConstraint(
            f"status IN {EXECUTION_STATUSES}",
            name="ck_execution_sessions_status",
        ),
        Index(
            "uq_execution_sessions_active_result",
            "run_result_id",
            unique=True,
            sqlite_where=text(
                f"run_result_id IS NOT NULL AND status IN ({ACTIVE_SESSION_STATUSES})"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    test_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_result_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("run_results.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED", server_default="CREATED")
    runner_instance_id: Mapped[str | None] = mapped_column(String(100))
    plugin_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    events: Mapped[list[ExecutionEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ExecutionEvent.sequence_no"
    )
    operator_interactions: Mapped[list[OperatorInteraction]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    configuration_snapshots: Mapped[list[ConfigurationSnapshot]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    recovery_tasks: Mapped[list[RecoveryTask]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ExecutionEvent(Base):
    __tablename__ = "execution_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no", name="uq_execution_events_sequence"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_execution_events_idempotency"),
        CheckConstraint("sequence_no >= 1", name="ck_execution_events_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    step_ref: Mapped[str | None] = mapped_column(String(100))
    action_ref: Mapped[str | None] = mapped_column(String(120))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    session: Mapped[ExecutionSession] = relationship(back_populates="events")


class OperatorInteraction(Base):
    __tablename__ = "operator_interactions"
    __table_args__ = (
        UniqueConstraint("session_id", "interaction_ref", name="uq_operator_interactions_ref"),
        CheckConstraint(
            "status IN ('PENDING','COMPLETED','UNABLE','CANCELLED')",
            name="ck_operator_interactions_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interaction_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    completion_condition: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default="PENDING")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    responder_name: Mapped[str | None] = mapped_column(String(200))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evidences.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    session: Mapped[ExecutionSession] = relationship(back_populates="operator_interactions")


class ConfigurationSnapshot(Base):
    __tablename__ = "configuration_snapshots"
    __table_args__ = (
        CheckConstraint("length(sha256) = 64", name="ck_configuration_snapshots_sha256"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    capture_action_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evidences.id", ondelete="SET NULL"))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    session: Mapped[ExecutionSession] = relationship(back_populates="configuration_snapshots")


class RecoveryTask(Base):
    __tablename__ = "recovery_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','VERIFIED','FAILED','MANUAL_REQUIRED')",
            name="ck_recovery_tasks_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_recovery_tasks_attempt_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("execution_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    configuration_snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("configuration_snapshots.id", ondelete="RESTRICT")
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", server_default="PENDING")
    restore_action_ref: Mapped[str | None] = mapped_column(String(120))
    verify_action_ref: Mapped[str | None] = mapped_column(String(120))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    manual_resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    session: Mapped[ExecutionSession] = relationship(back_populates="recovery_tasks")
    configuration_snapshot: Mapped[ConfigurationSnapshot | None] = relationship()


def _reject_event_update(_mapper, _connection, _target: ExecutionEvent) -> None:
    raise ValueError("Execution events are append-only")


event.listen(ExecutionEvent, "before_update", _reject_event_update)
event.listen(ExecutionEvent, "before_delete", _reject_event_update)
