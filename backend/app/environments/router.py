from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.environments.repository import EnvironmentRepository
from app.environments.schemas import EnvironmentProfileRead, EnvironmentProfileWrite
from app.environments.service import EnvironmentService


router = APIRouter(prefix="/environment-profiles", tags=["environments"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> EnvironmentService:
    return EnvironmentService(EnvironmentRepository(session))


ServiceDependency = Annotated[EnvironmentService, Depends(get_service)]


@router.get("", response_model=list[EnvironmentProfileRead])
def list_profiles(service: ServiceDependency):
    return service.list_profiles()


@router.post(
    "",
    response_model=EnvironmentProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    payload: EnvironmentProfileWrite,
    service: ServiceDependency,
):
    return service.create_profile(payload.model_dump())


@router.get("/{profile_id}", response_model=EnvironmentProfileRead)
def get_profile(profile_id: str, service: ServiceDependency):
    return service.get_profile(profile_id)


@router.put("/{profile_id}", response_model=EnvironmentProfileRead)
def update_profile(
    profile_id: str,
    payload: EnvironmentProfileWrite,
    service: ServiceDependency,
):
    return service.update_profile(profile_id, payload.model_dump())


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: str, service: ServiceDependency) -> Response:
    service.delete_profile(profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
