from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.test_execution import RunResult


class Defect(Base):
    __tablename__ = "defects"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('S1', 'S2', 'S3', 'S4')",
            name="ck_defects_severity",
        ),
        CheckConstraint(
            "status IN "
            "('OPEN', 'IN_PROGRESS', 'RESOLVED', 'REOPENED', 'CLOSED')",
            name="ck_defects_status",
        ),
        UniqueConstraint("defect_code", name="uq_defects_defect_code"),
        UniqueConstraint(
            "source_run_result_id",
            name="uq_defects_source_run_result_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    defect_code: Mapped[str] = mapped_column(String(30), nullable=False)
    source_run_result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reproduction_steps: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OPEN",
        server_default="OPEN",
        index=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)

    source_run_result: Mapped[RunResult] = relationship(
        foreign_keys=[source_run_result_id],
    )
    regressions: Mapped[list[Regression]] = relationship(
        back_populates="defect",
        cascade="all, delete-orphan",
        order_by="Regression.created_at",
    )


class Regression(Base):
    __tablename__ = "regressions"
    __table_args__ = (
        CheckConstraint(
            "result IN ('PASS', 'FAIL', 'BLOCKED')",
            name="ck_regressions_result",
        ),
        UniqueConstraint(
            "defect_id",
            "verification_run_result_id",
            name="uq_regressions_defect_verification_result",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    defect_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("defects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_run_result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    defect: Mapped[Defect] = relationship(back_populates="regressions")
    verification_run_result: Mapped[RunResult] = relationship(
        foreign_keys=[verification_run_result_id],
    )


def _reject_regression_mutation(*_args: object, **_kwargs: object) -> None:
    raise ValueError("Regression records are append-only")


event.listen(Regression, "before_update", _reject_regression_mutation)
event.listen(Regression, "before_delete", _reject_regression_mutation)
