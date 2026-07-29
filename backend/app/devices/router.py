from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.devices.repository import DeviceRepository
from app.devices.schemas import DeviceRead, DeviceWrite
from app.devices.service import DeviceService


router = APIRouter(prefix="/devices", tags=["devices"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> DeviceService:
    return DeviceService(DeviceRepository(session))


ServiceDependency = Annotated[DeviceService, Depends(get_service)]


@router.get("", response_model=list[DeviceRead])
def list_devices(service: ServiceDependency):
    return service.list()


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceWrite, service: ServiceDependency):
    return service.create(payload.model_dump())


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: str, service: ServiceDependency):
    return service.get(device_id)


@router.put("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: str,
    payload: DeviceWrite,
    service: ServiceDependency,
):
    return service.update(device_id, payload.model_dump())


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: str, service: ServiceDependency) -> Response:
    service.delete(device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
