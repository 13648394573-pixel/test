from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, attributes, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.test_execution import RunResult


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"
    __table_args__ = (
        CheckConstraint("wan_mode IN ('IPOE', 'PPPOE')", name="ck_diagnostic_sessions_wan_mode"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED')",
            name="ck_diagnostic_sessions_status",
        ),
        CheckConstraint("snapshot_version = 1", name="ck_diagnostic_sessions_snapshot_version"),
        Index(
            "uq_diagnostic_sessions_active_result",
            "run_result_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("run_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    retry_of_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("diagnostic_sessions.id", ondelete="RESTRICT")
    )
    adapter_key: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(30), nullable=False)
    wan_mode: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default="PENDING")
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    run_result: Mapped["RunResult"] = relationship()
    retry_of: Mapped["DiagnosticSession | None"] = relationship(remote_side=[id])
    attempts: Mapped[list["DiagnosticAttempt"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="DiagnosticAttempt.sequence"
    )


class DiagnosticAttempt(Base):
    __tablename__ = "diagnostic_attempts"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_diagnostic_attempts_session_sequence"),
        CheckConstraint("sequence > 0", name="ck_diagnostic_attempts_sequence"),
        CheckConstraint("attempt_number > 0", name="ck_diagnostic_attempts_attempt_number"),
        CheckConstraint("layer IN ('GATEWAY', 'PUBLIC_IP', 'DOMAIN')", name="ck_diagnostic_attempts_layer"),
        CheckConstraint("status IN ('PASS', 'FAIL', 'ERROR')", name="ck_diagnostic_attempts_status"),
        CheckConstraint(
            "packets_sent >= 0 AND packets_received >= 0 AND packets_received <= packets_sent",
            name="ck_diagnostic_attempts_packets",
        ),
        CheckConstraint("loss_percent >= 0 AND loss_percent <= 100", name="ck_diagnostic_attempts_loss"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    packets_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    packets_received: Mapped[int] = mapped_column(Integer, nullable=False)
    loss_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    latency_min_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    latency_avg_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    latency_max_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    raw_output: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    session: Mapped[DiagnosticSession] = relationship(back_populates="attempts")
    evidence_links: Mapped[list["DiagnosticAttemptEvidence"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class DiagnosticAttemptEvidence(Base):
    __tablename__ = "diagnostic_attempt_evidences"

    diagnostic_attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnostic_attempts.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evidences.id", ondelete="CASCADE"), primary_key=True
    )
    attempt: Mapped[DiagnosticAttempt] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship()


def _keep_policy_immutable(_target: object, value: Any, old_value: Any, _initiator: object) -> Any:
    if old_value is not attributes.NO_VALUE and value != old_value:
        raise ValueError("Diagnostic policy snapshot is immutable")
    return value


def _reject_attempt_mutation(*_args: object, **_kwargs: object) -> None:
    raise ValueError("Diagnostic attempts are append-only")


event.listen(DiagnosticSession.policy_snapshot, "set", _keep_policy_immutable, retval=True)
event.listen(DiagnosticAttempt, "before_update", _reject_attempt_mutation)
event.listen(DiagnosticAttempt, "before_delete", _reject_attempt_mutation)
