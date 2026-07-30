from datetime import datetime

import pytest

from app.environments.repository import EnvironmentRepository
from app.environments.service import (
    DuplicateEnvironmentParameterError,
    DuplicateEnvironmentProfileError,
    EnvironmentProfileNotFoundError,
    EnvironmentService,
    InvalidEnvironmentProfileError,
)


def payload(name: str = "ONU Lab A") -> dict:
    return {
        "name": name,
        "description": "MA5800-X7 lab",
        "enabled": True,
        "parameters": [
            {
                "section": "OLT",
                "param_key": "management_ip",
                "param_value": "192.0.2.10",
                "display_order": 2,
            },
            {
                "section": "VLAN",
                "param_key": "internet_vlan",
                "param_value": "100",
                "display_order": 1,
            },
        ],
    }


def test_service_rejects_duplicate_profile_names_and_parameter_keys(
    db_session,
) -> None:
    service = EnvironmentService(EnvironmentRepository(db_session))
    service.create_profile(payload())

    with pytest.raises(DuplicateEnvironmentProfileError):
        service.create_profile(payload())
    duplicate_key = payload("Lab B")
    duplicate_key["parameters"][1]["param_key"] = "management_ip"
    with pytest.raises(DuplicateEnvironmentParameterError):
        service.create_profile(duplicate_key)


def test_service_resolves_only_enabled_profile_for_run(db_session) -> None:
    service = EnvironmentService(EnvironmentRepository(db_session))
    profile = service.create_profile({**payload(), "enabled": False})

    with pytest.raises(InvalidEnvironmentProfileError):
        service.get_enabled_profile(profile.id)
    with pytest.raises(InvalidEnvironmentProfileError):
        service.get_enabled_profile("missing")


def test_snapshot_builder_captures_sorted_history_and_timestamp(db_session) -> None:
    captured_at = datetime(2026, 7, 30, 15, 30, 0)
    service = EnvironmentService(EnvironmentRepository(db_session))
    profile = service.create_profile(payload())

    snapshot = service.build_snapshot(profile, captured_at)

    assert snapshot == {
        "profile_name": "ONU Lab A",
        "description": "MA5800-X7 lab",
        "profile_updated_at": profile.updated_at.isoformat(),
        "captured_at": "2026-07-30T15:30:00",
        "parameters": [
            {
                "section": "VLAN",
                "param_key": "internet_vlan",
                "param_value": "100",
                "display_order": 1,
            },
            {
                "section": "OLT",
                "param_key": "management_ip",
                "param_value": "192.0.2.10",
                "display_order": 2,
            },
        ],
    }


def test_service_reports_missing_profile(db_session) -> None:
    service = EnvironmentService(EnvironmentRepository(db_session))

    with pytest.raises(EnvironmentProfileNotFoundError):
        service.get_profile("missing")
