from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportGenerate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=255)


class ArchiveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    archive_no: str
    report_id: str
    project_id: str
    manifest_version: int
    manifest_snapshot: dict[str, Any]
    archive_storage_path: str
    archive_sha256: str
    archive_file_size: int
    archived_at: datetime
    created_at: datetime


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_no: str
    project_id: str
    test_run_id: str
    report_version: int
    title: str
    snapshot_version: int
    report_snapshot: dict[str, Any]
    html_storage_path: str
    html_sha256: str
    html_file_size: int
    generated_at: datetime
    created_at: datetime
    archive: ArchiveRead | None = None
