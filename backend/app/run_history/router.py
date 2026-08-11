from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.run_history.repository import RunHistoryRepository
from app.run_history.schemas import (
    RunComparisonRead,
    RunComparisonRequest,
    RunHistoryFilters,
    RunHistoryPage,
)
from app.run_history.service import RunHistoryService


router = APIRouter(tags=["run-history"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/test-runs/compare", response_model=RunComparisonRead)
def compare_runs(payload: RunComparisonRequest, session: SessionDependency):
    return RunHistoryService(RunHistoryRepository(session)).compare(
        payload.run_ids
    )


@router.get("/test-runs", response_model=RunHistoryPage)
def search_runs(
    session: SessionDependency,
    project_id: str | None = None,
    run_no: str | None = None,
    project_version: str | None = None,
    device_type: str | None = None,
    vendor: str | None = None,
    model: str | None = None,
    serial_number: str | None = None,
    software_version: str | None = None,
    status: Literal["IN_PROGRESS", "COMPLETED"] | None = None,
    result: Literal["PASS", "FAIL", "BLOCKED", "UNSET"] | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = RunHistoryFilters(
        project_id=project_id,
        run_no=run_no,
        project_version=project_version,
        device_type=device_type,
        vendor=vendor,
        model=model,
        serial_number=serial_number,
        software_version=software_version,
        status=status,
        result=result,
        started_from=started_from,
        started_to=started_to,
        limit=limit,
        offset=offset,
    )
    return RunHistoryService(RunHistoryRepository(session)).search(filters)
