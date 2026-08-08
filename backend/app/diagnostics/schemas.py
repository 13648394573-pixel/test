from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticCreate(BaseModel):
    wan_mode: Literal["IPOE", "PPPOE"]
    adapter_key: str | None = None
    gateway_target: str = Field(min_length=1, max_length=255)
    public_ip_target: str = Field(min_length=1, max_length=255)
    domain_target: str = Field(min_length=1, max_length=253)
    packet_count: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    max_attempts_per_layer: int = Field(default=3, ge=1, le=3)


class AttemptEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evidence_id: str


class DiagnosticAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence: int
    layer: Literal["GATEWAY", "PUBLIC_IP", "DOMAIN"]
    target: str
    attempt_number: int
    status: Literal["PASS", "FAIL", "ERROR"]
    packets_sent: int
    packets_received: int
    loss_percent: Decimal
    latency_min_ms: Decimal | None
    latency_avg_ms: Decimal | None
    latency_max_ms: Decimal | None
    raw_output: str
    error_code: str | None
    started_at: datetime
    finished_at: datetime
    evidence_links: list[AttemptEvidenceRead] = []


class DiagnosticSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_result_id: str
    retry_of_session_id: str | None
    adapter_key: str
    adapter_version: str
    wan_mode: Literal["IPOE", "PPPOE"]
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "INTERRUPTED"]
    policy_snapshot: dict
    snapshot_version: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    attempts: list[DiagnosticAttemptRead] = []
