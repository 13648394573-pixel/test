import pytest
from sqlalchemy.orm import Session

from app.devices.repository import DeviceRepository
from app.devices.service import (
    DeviceNotFoundError,
    DeviceService,
    DuplicateSerialNumberError,
)


DEVICE_DATA = {
    "device_type": "OLT",
    "vendor": "Huawei",
    "model": "MA5800-X7",
    "serial_number": "OLT-001",
    "mac_address": None,
    "hardware_version": "V2",
    "software_version": "V100R023",
}


def test_service_rejects_duplicate_serial_number(db_session: Session) -> None:
    service = DeviceService(DeviceRepository(db_session))
    service.create(DEVICE_DATA)

    with pytest.raises(DuplicateSerialNumberError):
        service.create({**DEVICE_DATA, "model": "MA5800-X15"})


def test_service_rejects_update_to_another_devices_serial_number(
    db_session: Session,
) -> None:
    service = DeviceService(DeviceRepository(db_session))
    first = service.create(DEVICE_DATA)
    second = service.create({**DEVICE_DATA, "serial_number": "OLT-002"})

    with pytest.raises(DuplicateSerialNumberError):
        service.update(second.id, {"serial_number": first.serial_number})


def test_service_reports_missing_device_for_read_update_and_delete(
    db_session: Session,
) -> None:
    service = DeviceService(DeviceRepository(db_session))

    with pytest.raises(DeviceNotFoundError):
        service.get("missing")
    with pytest.raises(DeviceNotFoundError):
        service.update("missing", {"vendor": "ZTE"})
    with pytest.raises(DeviceNotFoundError):
        service.delete("missing")
