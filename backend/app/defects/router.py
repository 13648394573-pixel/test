from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.defects.repository import DefectRepository
from app.defects.schemas import (
    DefectCreate,
    DefectRead,
    DefectStatus,
    DefectStatusUpdate,
    DefectUpdate,
    RegressionCreate,
    RegressionRead,
    Severity,
)
from app.defects.service import DefectService


router = APIRouter(prefix="/defects", tags=["defects"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> DefectService:
    return DefectService(DefectRepository(session))


ServiceDependency = Annotated[DefectService, Depends(get_service)]


@router.get("", response_model=list[DefectRead])
def list_defects(
    service: ServiceDependency,
    status_filter: Annotated[
        DefectStatus | None,
        Query(alias="status"),
    ] = None,
    severity: Severity | None = None,
):
    return service.list_defects(status=status_filter, severity=severity)


@router.post(
    "",
    response_model=DefectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_defect(payload: DefectCreate, service: ServiceDependency):
    return service.create_defect(payload.model_dump())


@router.get("/{defect_id}", response_model=DefectRead)
def get_defect(defect_id: str, service: ServiceDependency):
    return service.get_defect(defect_id)


@router.put("/{defect_id}", response_model=DefectRead)
def update_defect(
    defect_id: str,
    payload: DefectUpdate,
    service: ServiceDependency,
):
    return service.update_defect(defect_id, payload.model_dump())


@router.put("/{defect_id}/status", response_model=DefectRead)
def transition_defect(
    defect_id: str,
    payload: DefectStatusUpdate,
    service: ServiceDependency,
):
    return service.transition(
        defect_id,
        payload.target_status,
        payload.resolution_notes,
    )


@router.get("/{defect_id}/regressions", response_model=list[RegressionRead])
def list_regressions(defect_id: str, service: ServiceDependency):
    return service.list_regressions(defect_id)


@router.post(
    "/{defect_id}/regressions",
    response_model=RegressionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_regression(
    defect_id: str,
    payload: RegressionCreate,
    service: ServiceDependency,
):
    return service.create_regression(
        defect_id,
        payload.verification_run_result_id,
        payload.notes,
    )
