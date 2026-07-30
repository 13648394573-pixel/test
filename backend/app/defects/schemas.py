from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.test_execution.schemas import CaseSnapshotRead


Severity = Literal["S1", "S2", "S3", "S4"]
DefectStatus = Literal[
    "OPEN",
    "IN_PROGRESS",
    "RESOLVED",
    "REOPENED",
    "CLOSED",
]


class DefectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_run_result_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    reproduction_steps: str = Field(min_length=1)
    severity: Severity


class DefectUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    reproduction_steps: str = Field(min_length=1)
    severity: Severity


class DefectStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    target_status: DefectStatus
    resolution_notes: str | None = None


class RegressionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    verification_run_result_id: str = Field(min_length=1)
    notes: str | None = None


class RunResultEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    case_source_id: str
    case_snapshot: CaseSnapshotRead
    snapshot_version: int
    result: Literal["PASS", "FAIL", "BLOCKED"]
    executed_at: datetime


class RegressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    defect_id: str
    verification_run_result_id: str
    result: Literal["PASS", "FAIL", "BLOCKED"]
    notes: str | None
    executed_at: datetime
    created_at: datetime
    verification_run_result: RunResultEvidenceRead


class DefectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    defect_code: str
    source_run_result_id: str
    title: str
    description: str
    reproduction_steps: str
    severity: Severity
    status: DefectStatus
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    source_run_result: RunResultEvidenceRead
    regressions: list[RegressionRead]
