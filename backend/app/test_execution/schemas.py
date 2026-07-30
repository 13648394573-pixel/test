from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    description: str | None = None
    case_source_ids: list[str] = Field(min_length=1)


class ProjectCaseSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_source_id: str


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    case_selections: list[ProjectCaseSelectionRead]


class DeviceSnapshotRead(BaseModel):
    device_type: str
    vendor: str
    model: str
    serial_number: str
    mac_address: str | None
    hardware_version: str | None
    software_version: str | None


class CaseStepSnapshotRead(BaseModel):
    step_number: int
    action: str
    expected_result: str


class CaseSnapshotRead(BaseModel):
    case_code: str
    title: str
    device_type: str | None
    category: str
    priority: str
    preconditions: str | None
    description: str | None
    enabled: bool
    steps: list[CaseStepSnapshotRead]


class EnvironmentParameterSnapshotRead(BaseModel):
    section: str
    param_key: str
    param_value: str
    display_order: int


class EnvironmentProfileSnapshotRead(BaseModel):
    profile_name: str
    description: str | None
    profile_updated_at: datetime
    captured_at: datetime
    parameters: list[EnvironmentParameterSnapshotRead]


class RunEnvironmentSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    test_run_id: str
    environment_profile_source_id: str
    snapshot_version: int
    profile_snapshot: EnvironmentProfileSnapshotRead
    created_at: datetime


class RunResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    case_source_id: str
    case_snapshot: CaseSnapshotRead
    snapshot_version: int
    result: Literal["PASS", "FAIL", "BLOCKED"] | None
    integrity_status: Literal["DRAFT", "LOCKED"]
    actual_result: str | None
    blocked_reason: str | None
    test_notes: str | None
    executed_at: datetime | None
    locked_at: datetime | None


class TestRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    device_source_id: str
    device_snapshot: DeviceSnapshotRead
    snapshot_version: int
    status: Literal["IN_PROGRESS", "COMPLETED"]
    started_at: datetime
    finished_at: datetime | None
    results: list[RunResultRead]
    environment_snapshot: RunEnvironmentSnapshotRead | None = None


class RunCreate(BaseModel):
    device_source_id: str = Field(min_length=1)
    environment_profile_id: str = Field(min_length=1)


class ResultUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    result: Literal["PASS", "FAIL", "BLOCKED"] | None = None
    actual_result: str | None = None
    blocked_reason: str | None = None
    test_notes: str | None = None
