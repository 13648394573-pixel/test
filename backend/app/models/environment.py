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


class EnvironmentProfile(Base):
    __tablename__ = "environment_profiles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
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
    parameters: Mapped[list[EnvironmentParameter]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="EnvironmentParameter.display_order, EnvironmentParameter.param_key",
    )


class EnvironmentParameter(Base):
    __tablename__ = "environment_parameters"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "param_key",
            name="uq_environment_parameters_profile_key",
        ),
        CheckConstraint(
            "display_order >= 1",
            name="ck_environment_parameters_display_order",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("environment_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    param_key: Mapped[str] = mapped_column(String(100), nullable=False)
    param_value: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
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
    profile: Mapped[EnvironmentProfile] = relationship(back_populates="parameters")


class RunEnvironmentSnapshot(Base):
    __tablename__ = "run_environment_snapshots"
    __table_args__ = (
        CheckConstraint(
            "snapshot_version = 1",
            name="ck_run_environment_snapshots_version",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    test_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    environment_profile_source_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )
    snapshot_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    run: Mapped[TestRun] = relationship(back_populates="environment_snapshot")


def _keep_environment_snapshot_immutable(
    _target: object,
    value: Any,
    old_value: Any,
    _initiator: object,
) -> Any:
    if old_value is not attributes.NO_VALUE and value != old_value:
        raise ValueError("Environment snapshot is immutable")
    return value


for snapshot_attribute in (
    RunEnvironmentSnapshot.profile_snapshot,
    RunEnvironmentSnapshot.snapshot_version,
    RunEnvironmentSnapshot.environment_profile_source_id,
):
    event.listen(
        snapshot_attribute,
        "set",
        _keep_environment_snapshot_immutable,
        retval=True,
        active_history=True,
    )


from app.models.test_execution import TestRun  # noqa: E402
