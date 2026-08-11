from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunHistoryFilters(BaseModel):
    project_id: str | None = None
    run_no: str | None = None
    project_version: str | None = None
    device_type: str | None = None
    vendor: str | None = None
    model: str | None = None
    serial_number: str | None = None
    software_version: str | None = None
    status: Literal["IN_PROGRESS", "COMPLETED"] | None = None
    result: Literal["PASS", "FAIL", "BLOCKED", "UNSET"] | None = None
    started_from: datetime | None = None
    started_to: datetime | None = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class RunDeviceSummary(BaseModel):
    device_type: str | None = None
    vendor: str | None = None
    model: str | None = None
    serial_number: str | None = None
    software_version: str | None = None


class RunResultSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total: int
    pass_: int = Field(alias="pass")
    fail: int
    blocked: int
    unset: int


class RunHistoryItem(BaseModel):
    id: str
    run_no: str
    project_id: str
    project_name: str
    project_version: str
    device: RunDeviceSummary
    status: Literal["IN_PROGRESS", "COMPLETED"]
    summary: RunResultSummary
    started_at: datetime
    finished_at: datetime | None


class RunHistoryPage(BaseModel):
    items: list[RunHistoryItem]
    total: int
    limit: int
    offset: int


class RunComparisonRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def unique_runs(self):
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ValueError("run_ids must be unique")
        return self


class RunComparisonSide(BaseModel):
    run_id: str
    result: Literal["PASS", "FAIL", "BLOCKED"] | None
    evidence_count: int


class RunComparisonTarget(RunComparisonSide):
    change: Literal[
        "UNCHANGED", "IMPROVED", "REGRESSED", "CHANGED", "ADDED", "REMOVED"
    ]


class RunComparisonRow(BaseModel):
    case_code: str
    title: str
    base: RunComparisonSide
    targets: list[RunComparisonTarget]


class RunComparisonRead(BaseModel):
    runs: list[RunHistoryItem]
    rows: list[RunComparisonRow]
