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


class FocusedRegressionRun(Base):
    __tablename__ = "focused_regression_runs"
    __table_args__ = (
        CheckConstraint(
            "snapshot_version = 1",
            name="ck_focused_regression_runs_snapshot_version",
        ),
        UniqueConstraint(
            "test_run_id",
            name="uq_focused_regression_runs_test_run_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    test_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    defect_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("defects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_run_result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_results.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    defect_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    test_run: Mapped["TestRun"] = relationship(foreign_keys=[test_run_id])
    defect: Mapped["Defect"] = relationship(foreign_keys=[defect_id])
    source_run_result: Mapped["RunResult"] = relationship(
        foreign_keys=[source_run_result_id]
    )


def _keep_defect_snapshot_immutable(
    _target: object,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if old_value is not attributes.NO_VALUE and value != old_value:
        raise ValueError("Focused regression snapshot is immutable")
    return value


def _keep_snapshot_version_one(
    _target: object,
    value: Any,
    _old_value: Any,
    _initiator: object,
) -> Any:
    if value != 1:
        raise ValueError("Focused regression snapshot is immutable")
    return value


event.listen(
    FocusedRegressionRun.defect_snapshot,
    "set",
    _keep_defect_snapshot_immutable,
    retval=True,
    active_history=True,
)
event.listen(
    FocusedRegressionRun.snapshot_version,
    "set",
    _keep_snapshot_version_one,
    retval=True,
    active_history=True,
)


def _reject_mutation(*_args: object, **_kwargs: object) -> None:
    raise ValueError("Focused regression records are immutable")


event.listen(FocusedRegressionRun, "before_update", _reject_mutation)
event.listen(FocusedRegressionRun, "before_delete", _reject_mutation)


from app.models.defect import Defect  # noqa: E402
from app.models.test_execution import RunResult, TestRun  # noqa: E402
