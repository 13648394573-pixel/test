from collections.abc import Mapping
from typing import Any

from app.devices.repository import DeviceRepository
from app.models.device import Device


class DeviceNotFoundError(Exception):
    pass


class DuplicateSerialNumberError(Exception):
    pass


class DeviceService:
    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    def list(self) -> list[Device]:
        return self.repository.list()

    def get(self, device_id: str) -> Device:
        device = self.repository.get(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        return device

    def create(self, values: Mapping[str, Any]) -> Device:
        serial_number = str(values["serial_number"])
        if self.repository.get_by_serial_number(serial_number) is not None:
            raise DuplicateSerialNumberError(serial_number)
        return self.repository.create(values)

    def update(self, device_id: str, values: Mapping[str, Any]) -> Device:
        device = self.get(device_id)
        serial_number = values.get("serial_number")
        if serial_number is not None:
            existing = self.repository.get_by_serial_number(str(serial_number))
            if existing is not None and existing.id != device.id:
                raise DuplicateSerialNumberError(str(serial_number))
        return self.repository.update(device, values)

    def delete(self, device_id: str) -> None:
        self.repository.delete(self.get(device_id))
