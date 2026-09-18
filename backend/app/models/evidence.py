from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidences"
    __table_args__ = (
        CheckConstraint(
            "((run_result_id IS NOT NULL AND defect_id IS NULL) OR "
            "(run_result_id IS NULL AND defect_id IS NOT NULL))",
            name="ck_evidences_exactly_one_owner",
        ),
        CheckConstraint(
            "category IN ('SCREENSHOT', 'LOG', 'CONFIG', 'OTHER')",
            name="ck_evidences_category",
        ),
        UniqueConstraint(
            "storage_path",
            name="uq_evidences_storage_path",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    run_result_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("run_results.id", ondelete="CASCADE"),
        index=True,
    )
    defect_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("defects.id", ondelete="CASCADE"),
        index=True,
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_rule_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    result_links = relationship(
        "EvidenceRunResultLink",
        back_populates="evidence",
        cascade="all, delete-orphan",
        order_by="EvidenceRunResultLink.created_at, EvidenceRunResultLink.run_result_id",
    )

    @property
    def run_result_ids(self) -> list[str]:
        linked = [item.run_result_id for item in self.result_links]
        if linked:
            return linked
        return [self.run_result_id] if self.run_result_id else []


def _reject_metadata_mutation(_mapper, _connection, target: Evidence) -> None:
    state = inspect(target)
    metadata_fields = (
        "run_result_id",
        "defect_id",
        "category",
        "original_name",
        "storage_path",
        "media_type",
        "file_size",
        "sha256",
        "description",
        "evidence_rule_code",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in metadata_fields):
        raise ValueError("Evidence metadata is immutable")


event.listen(Evidence, "before_update", _reject_metadata_mutation)
