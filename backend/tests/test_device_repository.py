from sqlalchemy.orm import Session

from app.devices.repository import DeviceRepository


DEVICE_DATA = {
    "device_type": "ONU",
    "vendor": "Huawei",
    "model": "HN8546X6",
    "serial_number": "ONU-001",
    "mac_address": "00:11:22:33:44:55",
    "hardware_version": "V1",
    "software_version": "V5R020",
}


def test_repository_creates_lists_and_gets_device(db_session: Session) -> None:
    repository = DeviceRepository(db_session)

    created = repository.create(DEVICE_DATA)

    assert created.id
    assert created.serial_number == "ONU-001"
    assert repository.list() == [created]
    assert repository.get(created.id) is created


def test_repository_updates_and_deletes_device(db_session: Session) -> None:
    repository = DeviceRepository(db_session)
    device = repository.create(DEVICE_DATA)

    updated = repository.update(
        device,
        {"software_version": "V5R021", "vendor": "Huawei Technologies"},
    )

    assert updated.software_version == "V5R021"
    assert updated.vendor == "Huawei Technologies"

    repository.delete(updated)

    assert repository.get(device.id) is None
    assert repository.list() == []
