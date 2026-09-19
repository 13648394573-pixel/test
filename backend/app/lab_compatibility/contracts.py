from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from app.local_runner.contracts import ArtifactPayload


StageStatus = Literal["VERIFIED", "NEEDS_INPUT", "BLOCKED", "NOT_RUN"]
OverallStatus = Literal["READY", "PARTIAL", "BLOCKED"]
Lifecycle = Literal["PENDING", "RUNNING", "COMPLETED"]
StageCode = Literal[
    "LOCAL_ENV",
    "OLT_CONNECT",
    "OLT_AUTOFIND",
    "OLT_CURRENT_STATE",
    "ONU_WEB_WAN",
    "ONU_WEB_PING_PAGE",
    "PC_INTERFACE",
    "PC_PING",
]

STAGE_CODES: tuple[StageCode, ...] = (
    "LOCAL_ENV",
    "OLT_CONNECT",
    "OLT_AUTOFIND",
    "OLT_CURRENT_STATE",
    "ONU_WEB_WAN",
    "ONU_WEB_PING_PAGE",
    "PC_INTERFACE",
    "PC_PING",
)


@dataclass(frozen=True)
class CreateCompatibilityCheck:
    olt_host: str
    olt_port: int
    expected_host_key_fingerprint: str
    olt_username_ref: str
    olt_password_ref: str
    onu_serial_number: str | None
    frame: int | None
    slot: int | None
    pon_port: int | None
    ont_id: int | None
    onu_web_url: str
    onu_web_username_ref: str
    onu_web_password_ref: str
    onu_adapter_key: str
    pc_interface_name: str
    pc_source_address: str
    pc_ping_target: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "CreateCompatibilityCheck":
        return cls(**value)


@dataclass(frozen=True)
class CompatibilityStage:
    code: StageCode
    status: StageStatus
    message: str
    evidence: tuple[ArtifactPayload, ...] = ()

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "status": self.status,
            "message": self.message,
            "evidence": [
                {
                    "original_name": item.original_name,
                    "media_type": item.media_type,
                    "storage_path": item.storage_path,
                    "file_size": item.file_size,
                    "sha256": item.sha256,
                    "redacted": item.redacted,
                }
                for item in self.evidence
            ],
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CompatibilityStage":
        return cls(
            code=value["code"],
            status=value["status"],
            message=value["message"],
            evidence=tuple(ArtifactPayload(**item) for item in value["evidence"]),
        )


@dataclass(frozen=True)
class CompatibilityCheckView:
    check_id: str
    lifecycle: Lifecycle
    overall_status: OverallStatus | None
    stages: tuple[CompatibilityStage, ...]
    created_at: datetime
    updated_at: datetime

    def stage(self, code: StageCode) -> CompatibilityStage:
        return next(item for item in self.stages if item.code == code)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "lifecycle": self.lifecycle,
            "overall_status": self.overall_status,
            "stages": [item.to_dict() for item in self.stages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CompatibilityCheckView":
        return cls(
            check_id=value["check_id"],
            lifecycle=value["lifecycle"],
            overall_status=value["overall_status"],
            stages=tuple(CompatibilityStage.from_dict(item) for item in value["stages"]),
            created_at=datetime.fromisoformat(value["created_at"]),
            updated_at=datetime.fromisoformat(value["updated_at"]),
        )
