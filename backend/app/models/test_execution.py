from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
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
)
from sqlalchemy.orm import Mapped, attributes, mapped_column, relationship

from app.db.base import Base


class TestProject(Base):
    __tablename__ = "test_projects"
    __test__ = False

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
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
    case_selections: Mapped[list[ProjectCaseSelection]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectCaseSelection.case_source_id",
    )
    runs: Mapped[list[TestRun]] = relationship(back_populates="project")


class ProjectCaseSelection(Base):
    __tablename__ = "project_case_selections"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    case_source_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project: Mapped[TestProject] = relationship(back_populates="case_selections")


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED')",
            name="ck_test_runs_status",
        ),
        Index("ix_test_runs_started_at", "started_at"),
        Index(
            "ix_test_runs_project_status_started",
            "project_id",
            "status",
            "started_at",
        ),
    )
    __test__ = False

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    run_no: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_projects.id"),
        nullable=False,
        index=True,
    )
    device_source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="IN_PROGRESS",
        server_default="IN_PROGRESS",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    project: Mapped[TestProject] = relationship(back_populates="runs")
    results: Mapped[list[RunResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunResult.case_source_id",
    )
    environment_snapshot: Mapped[RunEnvironmentSnapshot | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        uselist=False,
    )


class RunResult(Base):
    __tablename__ = "run_results"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "case_source_id",
            name="uq_run_results_run_case_source",
        ),
    CheckConstraint(
            "result IS NULL OR result IN ('PASS', 'FAIL', 'BLOCKED')",
            name="ck_run_results_result",
        ),
        CheckConstraint(
            "integrity_status IN ('DRAFT', 'LOCKED')",
            name="ck_run_results_integrity_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    case_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    result: Mapped[str | None] = mapped_column(String(10))
    integrity_status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
    )
    actual_result: Mapped[str | None] = mapped_column(Text)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    test_notes: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    run: Mapped[TestRun] = relationship(back_populates="results")
    evidence_links = relationship(
        "EvidenceRunResultLink",
        back_populates="run_result",
        cascade="all, delete-orphan",
    )


def _keep_snapshot_immutable(
    _target: object,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if old_value is not attributes.NO_VALUE and value != old_value:
        raise ValueError("Snapshots are immutable")
    return value


for snapshot_attribute in (
    TestRun.run_no,
    TestRun.device_snapshot,
    TestRun.snapshot_version,
    RunResult.case_snapshot,
    RunResult.snapshot_version,
):
    event.listen(
        snapshot_attribute,
        "set",
        _keep_snapshot_immutable,
        retval=True,
        active_history=True,
    )


def _keep_locked_result_immutable(
    target: RunResult,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if (
        target.integrity_status == "LOCKED"
        and old_value is not attributes.NO_VALUE
        and value != old_value
    ):
        raise ValueError("Locked results are immutable")
    return value


for result_attribute in (
    RunResult.result,
    RunResult.actual_result,
    RunResult.blocked_reason,
    RunResult.test_notes,
    RunResult.executed_at,
    RunResult.locked_at,
):
    event.listen(
        result_attribute,
        "set",
        _keep_locked_result_immutable,
        retval=True,
        active_history=True,
    )


def _keep_integrity_one_way(
    _target: RunResult,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if old_value == "LOCKED" and value != "LOCKED":
        raise ValueError("Locked results cannot be unlocked")
    return value


event.listen(
    RunResult.integrity_status,
    "set",
    _keep_integrity_one_way,
    retval=True,
    active_history=True,
)


from app.models.environment import RunEnvironmentSnapshot  # noqa: E402
from app.models.evidence_link import EvidenceRunResultLink  # noqa: E402, F401
