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


class RunResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    case_source_id: str
    case_snapshot: CaseSnapshotRead
    snapshot_version: int
    result: Literal["PASS", "FAIL", "BLOCKED"] | None
    executed_at: datetime | None


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


class RunCreate(BaseModel):
    device_source_id: str = Field(min_length=1)


class ResultUpdate(BaseModel):
    result: Literal["PASS", "FAIL", "BLOCKED"]
