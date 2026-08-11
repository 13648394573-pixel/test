from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvidenceRunResultLink(Base):
    __tablename__ = "evidence_run_result_links"

    evidence_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        primary_key=True,
    )
    run_result_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("run_results.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    evidence = relationship("Evidence", back_populates="result_links")
    run_result = relationship("RunResult", back_populates="evidence_links")
