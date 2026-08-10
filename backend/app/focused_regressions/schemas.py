from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.test_execution.schemas import TestRunRead


class FocusedRegressionCreate(BaseModel):
    device_source_id: str = Field(min_length=1)
    environment_profile_id: str = Field(min_length=1)
    source_run_result_id: str | None = Field(default=None, min_length=1)


class DefectSnapshotRead(BaseModel):
    defect_code: str
    title: str
    severity: str
    status: str
    resolution_notes: str | None
    source_run_result_id: str
    captured_at: datetime


class FocusedRegressionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    test_run_id: str
    defect_id: str
    source_run_result_id: str
    defect_snapshot: DefectSnapshotRead
    snapshot_version: int
    created_at: datetime
    test_run: TestRunRead
