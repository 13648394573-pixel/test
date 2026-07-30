from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, attributes, mapped_column, relationship

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint(
            "test_run_id",
            "report_version",
            name="uq_reports_run_version",
        ),
        CheckConstraint("report_version >= 1", name="ck_reports_version"),
        CheckConstraint("snapshot_version = 1", name="ck_reports_snapshot_version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    report_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    test_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    report_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    html_storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    html_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    html_file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    archive: Mapped[Archive | None] = relationship(
        back_populates="report", uselist=False
    )


class Archive(Base):
    __tablename__ = "archives"
    __table_args__ = (
        CheckConstraint(
            "manifest_version = 1",
            name="ck_archives_manifest_version",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    archive_no: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True
    )
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    manifest_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    manifest_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    archive_storage_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    report: Mapped[Report] = relationship(back_populates="archive")


def _keep_value_immutable(
    _target: object,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if old_value is not attributes.NO_VALUE and value != old_value:
        raise ValueError("Report and archive records are immutable")
    return value


for immutable_attribute in (
    Report.report_no,
    Report.project_id,
    Report.test_run_id,
    Report.report_version,
    Report.title,
    Report.snapshot_version,
    Report.report_snapshot,
    Report.html_storage_path,
    Report.html_sha256,
    Report.html_file_size,
    Report.generated_at,
    Archive.archive_no,
    Archive.report_id,
    Archive.project_id,
    Archive.manifest_version,
    Archive.manifest_snapshot,
    Archive.archive_storage_path,
    Archive.archive_sha256,
    Archive.archive_file_size,
    Archive.archived_at,
):
    event.listen(
        immutable_attribute,
        "set",
        _keep_value_immutable,
        retval=True,
        active_history=True,
    )


def _reject_delete(*_args: object, **_kwargs: object) -> None:
    raise ValueError("Report and archive records are immutable")


event.listen(Report, "before_delete", _reject_delete)
event.listen(Archive, "before_delete", _reject_delete)
