from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[Device]:
        statement = select(Device).order_by(Device.created_at.desc())
        return list(self.session.scalars(statement))

    def get(self, device_id: str) -> Device | None:
        return self.session.get(Device, device_id)

    def get_by_serial_number(self, serial_number: str) -> Device | None:
        statement = select(Device).where(Device.serial_number == serial_number)
        return self.session.scalar(statement)

    def create(self, values: Mapping[str, Any]) -> Device:
        device = Device(**values)
        self.session.add(device)
        self.session.commit()
        self.session.refresh(device)
        return device

    def update(self, device: Device, values: Mapping[str, Any]) -> Device:
        for field, value in values.items():
            setattr(device, field, value)
        self.session.commit()
        self.session.refresh(device)
        return device

    def delete(self, device: Device) -> None:
        self.session.delete(device)
        self.session.commit()
