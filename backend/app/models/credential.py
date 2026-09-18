from datetime import datetime
import re
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, String, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CredentialReference(Base):
    __tablename__ = "credential_references"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('OLT','ONU','PPPOE','TR069','SERVICE','OTHER')",
            name="ck_credential_references_target_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    credential_target_ref: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    masked_display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


_URI_USERINFO = re.compile(r"^[a-z][a-z0-9+.-]*://[^/@:]+:[^/@]+@", re.IGNORECASE)
_GENERIC_USERINFO = re.compile(r"^[^\s/:]+:[^\s@]+@")


def _validate_credential_reference(_mapper, _connection, target: CredentialReference) -> None:
    value = target.credential_target_ref
    if "\n" in value or "\r" in value or _URI_USERINFO.search(value) or _GENERIC_USERINFO.search(value):
        raise ValueError("credential reference must not contain secret material")


event.listen(CredentialReference, "before_insert", _validate_credential_reference)
event.listen(CredentialReference, "before_update", _validate_credential_reference)
