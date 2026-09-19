from __future__ import annotations

from datetime import datetime
from ipaddress import ip_address
import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.lab_compatibility.contracts import CreateCompatibilityCheck


REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
FINGERPRINT = re.compile(r"^SHA256:[A-Za-z0-9+/]{20,100}$")
SERIAL = re.compile(r"^[0-9A-F]{16}$")


def _private_address(value: str, field: str) -> str:
    try:
        address = ip_address(value)
    except ValueError as exception:
        raise ValueError(f"{field} must be an IP address") from exception
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError(f"{field} must be local or private")
    return str(address)


class HostKeyPreviewCreate(BaseModel):
    olt_host: str
    olt_port: int = Field(default=22, ge=1, le=65535)

    @field_validator("olt_host")
    @classmethod
    def private_olt(cls, value: str) -> str:
        return _private_address(value, "olt_host")


class HostKeyPreviewRead(BaseModel):
    fingerprint: str


class CompatibilityCheckCreate(BaseModel):
    olt_host: str
    olt_port: int = Field(default=22, ge=1, le=65535)
    expected_host_key_fingerprint: str
    olt_username_ref: str
    olt_password_ref: str
    onu_serial_number: str | None = None
    frame: int | None = Field(default=None, ge=0, le=15)
    slot: int | None = Field(default=None, ge=0, le=31)
    pon_port: int | None = Field(default=None, ge=0, le=255)
    ont_id: int | None = Field(default=None, ge=0, le=127)
    onu_web_url: str
    onu_web_username_ref: str
    onu_web_password_ref: str
    onu_adapter_key: Literal["neutral-v1"] = "neutral-v1"
    pc_interface_name: str = Field(min_length=1, max_length=100)
    pc_source_address: str
    pc_ping_target: str = Field(min_length=1, max_length=253)

    @field_validator("olt_host")
    @classmethod
    def private_olt(cls, value: str) -> str:
        return _private_address(value, "olt_host")

    @field_validator("pc_source_address")
    @classmethod
    def private_source(cls, value: str) -> str:
        return _private_address(value, "pc_source_address")

    @field_validator("expected_host_key_fingerprint")
    @classmethod
    def fingerprint(cls, value: str) -> str:
        if not FINGERPRINT.fullmatch(value):
            raise ValueError("invalid SHA256 host-key fingerprint")
        return value

    @field_validator(
        "olt_username_ref",
        "olt_password_ref",
        "onu_web_username_ref",
        "onu_web_password_ref",
    )
    @classmethod
    def credential_reference(cls, value: str) -> str:
        if not REFERENCE.fullmatch(value):
            raise ValueError("invalid credential reference")
        return value

    @field_validator("onu_serial_number")
    @classmethod
    def serial(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if not SERIAL.fullmatch(normalized):
            raise ValueError("ONU serial number must be 16 hexadecimal characters")
        return normalized

    @field_validator("onu_web_url")
    @classmethod
    def local_onu_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("invalid ONU Web URL")
        if parsed.username or parsed.password:
            raise ValueError("ONU Web URL must not contain credentials")
        _private_address(parsed.hostname, "onu_web_url host")
        return value

    @field_validator("pc_interface_name")
    @classmethod
    def interface_name(cls, value: str) -> str:
        if not re.fullmatch(r"[\w .()_-]{1,100}", value):
            raise ValueError("unsafe interface name")
        return value

    @field_validator("pc_ping_target")
    @classmethod
    def ping_target(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", value):
            raise ValueError("unsafe Ping target")
        return value

    @model_validator(mode="after")
    def complete_ont_target(self):
        values = (self.frame, self.slot, self.pon_port, self.ont_id)
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError("frame, slot, pon_port, and ont_id must be provided together")
        return self

    def to_command(self) -> CreateCompatibilityCheck:
        return CreateCompatibilityCheck(**self.model_dump())


class CompatibilityEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    original_name: str
    media_type: str
    storage_path: str | None
    file_size: int | None
    sha256: str | None
    redacted: bool


class CompatibilityStageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    status: Literal["VERIFIED", "NEEDS_INPUT", "BLOCKED", "NOT_RUN"]
    message: str
    evidence: list[CompatibilityEvidenceRead]


class CompatibilityCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    check_id: str
    lifecycle: Literal["PENDING", "RUNNING", "COMPLETED"]
    overall_status: Literal["READY", "PARTIAL", "BLOCKED"] | None
    stages: list[CompatibilityStageRead]
    created_at: datetime
    updated_at: datetime
