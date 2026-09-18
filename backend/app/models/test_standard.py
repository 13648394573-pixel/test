from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


PUBLICATION_STATUS_CHECK = (
    "(status = 'DRAFT' AND published_at IS NULL) OR "
    "(status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)"
)


class TestStandard(Base):
    __tablename__ = "test_standards"
    __table_args__ = (
        UniqueConstraint(
            "standard_code", "version", name="uq_test_standards_code_version"
        ),
        CheckConstraint(
            "source_type IN "
            "('INTERNAL','CUSTOMER','OPERATOR','COUNTRY','REGION','INDUSTRY')",
            name="ck_test_standards_source_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_test_standards_status",
        ),
        CheckConstraint(PUBLICATION_STATUS_CHECK, name="ck_test_standards_published_at"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_test_standards_effective_dates",
        ),
    )
    __test__ = False

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    standard_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    issuer: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    region_code: Mapped[str | None] = mapped_column(String(30))
    language_code: Mapped[str] = mapped_column(String(35), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", server_default="DRAFT", index=True
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    requirements: Mapped[list[StandardRequirement]] = relationship(
        back_populates="standard",
        cascade="all, delete-orphan",
        order_by="StandardRequirement.display_order",
    )
    profile_items: Mapped[list[StandardProfileItem]] = relationship(
        back_populates="standard", passive_deletes=True
    )


class StandardRequirement(Base):
    __tablename__ = "standard_requirements"
    __table_args__ = (
        UniqueConstraint(
            "standard_id", "requirement_code", name="uq_standard_requirements_code"
        ),
        UniqueConstraint(
            "standard_id", "display_order", name="uq_standard_requirements_order"
        ),
        CheckConstraint(
            "requirement_level IN ('MANDATORY','RECOMMENDED','INFORMATIVE')",
            name="ck_standard_requirements_level",
        ),
        CheckConstraint("display_order >= 1", name="ck_standard_requirements_order"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    standard_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_standards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_code: Mapped[str] = mapped_column(String(120), nullable=False)
    clause_reference: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_level: Mapped[str] = mapped_column(String(20), nullable=False)
    applicability: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)
    operator: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_value: Mapped[Any | None] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(30))
    source_text_reference: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    standard: Mapped[TestStandard] = relationship(back_populates="requirements")


class StandardProfile(Base):
    __tablename__ = "standard_profiles"
    __table_args__ = (
        UniqueConstraint(
            "profile_code", "version", name="uq_standard_profiles_code_version"
        ),
        CheckConstraint("version >= 1", name="ck_standard_profiles_version"),
        CheckConstraint(
            "merge_policy = 'ALL_MANDATORY_MUST_PASS'",
            name="ck_standard_profiles_merge_policy",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_standard_profiles_status",
        ),
        CheckConstraint(PUBLICATION_STATUS_CHECK, name="ck_standard_profiles_published_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    region_code: Mapped[str | None] = mapped_column(String(30))
    customer_name: Mapped[str | None] = mapped_column(String(200))
    operator_name: Mapped[str | None] = mapped_column(String(200))
    merge_policy: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="ALL_MANDATORY_MUST_PASS",
        server_default="ALL_MANDATORY_MUST_PASS",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", server_default="DRAFT", index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    items: Mapped[list[StandardProfileItem]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="StandardProfileItem.display_order",
    )


class StandardProfileItem(Base):
    __tablename__ = "standard_profile_items"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "display_order", name="uq_standard_profile_items_order"
        ),
        CheckConstraint("display_order >= 1", name="ck_standard_profile_items_order"),
    )

    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("standard_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    standard_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_standards.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    profile: Mapped[StandardProfile] = relationship(back_populates="items")
    standard: Mapped[TestStandard] = relationship(back_populates="profile_items")


class ProjectStandardProfile(Base):
    __tablename__ = "project_standard_profiles"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    standard_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("standard_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    project = relationship("TestProject")
    standard_profile: Mapped[StandardProfile] = relationship()
