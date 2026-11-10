from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.skill_execution.service import CreateSkillExecutionCommand
from app.local_runner.ma5800.service_port_contracts import ServicePortMapping, PortOperation


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ReconciliationRead(BaseModel):
    status: Literal['FOUND', 'ABSENT', 'UNCONFIRMED']
    evidence_ids: list[str]
    automatic_write_authorized: Literal[False]
    captured_at: datetime


class ServicePortResourceRead(BaseModel):
    port_id: int
    mapping: ServicePortMapping
    origin: Literal['REUSED', 'CREATED']
    state: Literal['REUSED', 'CREATE_PENDING', 'ACTIVE', 'CREATE_UNCERTAIN', 'DELETE_PENDING',
                   'DELETE_UNCERTAIN', 'DELETED', 'RETAINED']
    consumers: list[Literal['IPOE', 'PPPOE']]
    creation_event_id: str | None
    operation_id: str
    last_event_id: str
    evidence_ids: list[str]
    before_evidence_ids: list[str]
    baseline_hash: str
    reconciliation: ReconciliationRead | None = None


class ExecutionCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    device_id: UUID
    environment_id: UUID
    skill_id: UUID
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=50)

    def to_command(self):
        return CreateSkillExecutionCommand(str(self.project_id), str(self.device_id),
            str(self.environment_id), str(self.skill_id), self.parameters)


class InteractionResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    choice: str = Field(min_length=1, max_length=30)
    approved: StrictBool = False
    preview_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


class EventRead(BaseModel):
    sequence_no: int
    type: str
    step_ref: str | None
    occurred_at: datetime


class ObservationRead(BaseModel):
    fact_key: str
    value: StrictBool | float
    source: Literal['MA5800', 'ONU_WEB', 'PC_PROBE']


class ServicePortApprovalRead(BaseModel):
    operations: list[PortOperation]
    evidence_ids: list[str]
    retained_consumers: list[Literal['IPOE', 'PPPOE']]


class CleanupApproval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approved: StrictBool
    preview_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


class CleanupPreviewRead(ServicePortApprovalRead):
    preview_hash: str


class CleanupItemRead(BaseModel):
    port_id: int
    status: Literal['DELETED', 'UNCERTAIN', 'BLOCKED', 'NOT_PROCESSED']


class CleanupOutcomeRead(BaseModel):
    status: Literal['PASS', 'BLOCKED']
    items: list[CleanupItemRead]


class InteractionRead(BaseModel):
    id: str
    ref: str
    type: str
    risk_level: str
    title: str
    instructions: str
    completion_condition: str
    options: list[str]
    preview_hash: str
    target: dict[str, str | int]
    action_code: str | None
    affected_service_ports: list[int]
    service_port_preview: ServicePortApprovalRead | None = None


class RecoveryRead(BaseModel):
    id: str
    status: str
    instructions: str


class ExecutionRead(BaseModel):
    session_id: str
    test_run_id: str
    run_result_id: str
    skill_code: str
    skill_version: str
    wan_mode: Literal['SEQUENTIAL_ISOLATED', 'CONCURRENT_DUAL_WAN']
    status: str
    mode: Literal['DEVELOPMENT']
    integrity_status: Literal['DRAFT', 'LOCKED']
    result: str | None
    functional_verdict: str | None
    evidence_complete: bool | None
    runner_configured: bool
    events: list[EventRead]
    observations: list[ObservationRead]
    pending_interaction: InteractionRead | None
    recovery_tasks: list[RecoveryRead]
    service_port_resources: list[ServicePortResourceRead] = Field(default_factory=list)
    cleanup_available: bool = False
    cleanup_preview: CleanupPreviewRead | None = None
    cleanup_outcome: CleanupOutcomeRead | None = None


class ExecutionEvidenceRead(BaseModel):
    id: str
    category: str
    media_type: str
    file_size: int
    sha256: str
    created_at: datetime
    step_ref: str | None
    rule_code: str | None
    capture_method: str | None
    redacted: bool
    download_url: str
