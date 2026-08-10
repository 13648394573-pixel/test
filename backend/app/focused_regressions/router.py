from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.defects.repository import DefectRepository
from app.devices.repository import DeviceRepository
from app.environments.repository import EnvironmentRepository
from app.environments.service import EnvironmentService
from app.focused_regressions.repository import FocusedRegressionRepository
from app.focused_regressions.schemas import (
    FocusedRegressionCreate,
    FocusedRegressionRead,
)
from app.focused_regressions.service import FocusedRegressionService


router = APIRouter(tags=["focused-regressions"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> FocusedRegressionService:
    return FocusedRegressionService(
        FocusedRegressionRepository(session),
        DefectRepository(session),
        DeviceRepository(session),
        EnvironmentService(EnvironmentRepository(session)),
    )


ServiceDependency = Annotated[FocusedRegressionService, Depends(get_service)]


@router.post(
    "/defects/{defect_id}/focused-regression-runs",
    response_model=FocusedRegressionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_focused_regression_run(
    defect_id: str,
    payload: FocusedRegressionCreate,
    service: ServiceDependency,
):
    return service.create_run(
        defect_id,
        payload.device_source_id,
        payload.environment_profile_id,
        payload.source_run_result_id,
    )


@router.get(
    "/defects/{defect_id}/focused-regression-runs",
    response_model=list[FocusedRegressionRead],
)
def list_focused_regression_runs(
    defect_id: str,
    service: ServiceDependency,
):
    return service.list_for_defect(defect_id)


@router.get(
    "/focused-regression-runs/{run_id}",
    response_model=FocusedRegressionRead,
)
def get_focused_regression_run(
    run_id: str,
    service: ServiceDependency,
):
    return service.get_run(run_id)
