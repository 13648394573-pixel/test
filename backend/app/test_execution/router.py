from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.devices.repository import DeviceRepository
from app.test_cases.repository import TestCaseRepository
from app.test_execution.repository import TestExecutionRepository
from app.test_execution.schemas import (
    ProjectRead,
    ProjectWrite,
    ResultUpdate,
    RunCreate,
    RunResultRead,
    TestRunRead,
)
from app.test_execution.service import TestExecutionService


router = APIRouter(tags=["test-execution"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> TestExecutionService:
    return TestExecutionService(
        TestExecutionRepository(session),
        DeviceRepository(session),
        TestCaseRepository(session),
    )


ServiceDependency = Annotated[TestExecutionService, Depends(get_service)]


@router.get("/test-projects", response_model=list[ProjectRead])
def list_projects(service: ServiceDependency):
    return service.list_projects()


@router.post(
    "/test-projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project(payload: ProjectWrite, service: ServiceDependency):
    return service.create_project(payload.model_dump())


@router.get("/test-projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, service: ServiceDependency):
    return service.get_project(project_id)


@router.put("/test-projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectWrite,
    service: ServiceDependency,
):
    return service.update_project(project_id, payload.model_dump())


@router.delete(
    "/test-projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(project_id: str, service: ServiceDependency) -> Response:
    service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/test-projects/{project_id}/runs",
    response_model=TestRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    project_id: str,
    payload: RunCreate,
    service: ServiceDependency,
):
    return service.create_run(project_id, payload.device_source_id)


@router.get(
    "/test-projects/{project_id}/runs",
    response_model=list[TestRunRead],
)
def list_runs(project_id: str, service: ServiceDependency):
    return service.list_runs(project_id)


@router.get("/test-runs/{run_id}", response_model=TestRunRead)
def get_run(run_id: str, service: ServiceDependency):
    return service.get_run(run_id)


@router.put(
    "/test-runs/{run_id}/results/{result_id}",
    response_model=RunResultRead,
)
def update_result(
    run_id: str,
    result_id: str,
    payload: ResultUpdate,
    service: ServiceDependency,
):
    return service.update_result(
        run_id,
        result_id,
        payload.model_dump(exclude_unset=True),
    )


@router.post(
    "/test-runs/{run_id}/results/{result_id}/lock",
    response_model=RunResultRead,
)
def lock_result(
    run_id: str,
    result_id: str,
    service: ServiceDependency,
):
    return service.lock_result(run_id, result_id)
