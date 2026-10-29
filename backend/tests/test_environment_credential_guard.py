import pytest

from app.environments.snapshots import build_environment_snapshot
from app.models.environment import EnvironmentParameter, EnvironmentProfile
from datetime import datetime


def _profile(parameters: list[EnvironmentParameter]) -> EnvironmentProfile:
    profile = EnvironmentProfile(
        name="Lab",
        description=None,
        enabled=True,
        parameters=parameters,
        updated_at=datetime(2026, 10, 29, 11, 0, 0),
    )
    return profile


def test_snapshot_redacts_credential_reference() -> None:
    profile = _profile(
        [
            EnvironmentParameter(
                section="OLT",
                param_key="login",
                param_value="credential:olt-lab-admin",
                display_order=1,
            ),
            EnvironmentParameter(
                section="OLT",
                param_key="fsp",
                param_value="0/2/10",
                display_order=2,
            ),
        ]
    )
    snapshot = build_environment_snapshot(profile, datetime(2026, 10, 29, 12, 0, 0))
    login = snapshot["parameters"][0]
    assert login["param_value"] == "***"
    assert login["credential_ref"] == "olt-lab-admin"
    assert snapshot["parameters"][1]["param_value"] == "0/2/10"
    assert "credential" not in snapshot["parameters"][1]


def test_model_rejects_plaintext_password_parameter(db_session) -> None:
    profile = EnvironmentProfile(name="Guard", description=None, enabled=True)
    db_session.add(profile)
    db_session.commit()
    bad = EnvironmentParameter(
        profile_id=profile.id,
        section="ONU",
        param_key="super_password",
        param_value="YnQtcG9u",
        display_order=1,
    )
    db_session.add(bad)
    with pytest.raises(ValueError):
        db_session.commit()
    db_session.rollback()

    good = EnvironmentParameter(
        profile_id=profile.id,
        section="ONU",
        param_key="super_password",
        param_value="credential:onu-super-admin",
        display_order=1,
    )
    db_session.add(good)
    db_session.commit()
    assert good.param_value.startswith("credential:")


def test_service_maps_plaintext_secret_to_dedicated_error(db_session) -> None:
    """The model guard must surface as 422, not an unhandled 500."""
    from app.environments.repository import EnvironmentRepository
    from app.environments.service import EnvironmentService, PlaintextSecretError

    service = EnvironmentService(EnvironmentRepository(db_session))
    with pytest.raises(PlaintextSecretError):
        service.create_profile(
            {
                "name": "Bad Profile",
                "description": None,
                "enabled": True,
                "parameters": [
                    {
                        "section": "OLT",
                        "param_key": "root_password",
                        "param_value": "plain-text-secret",
                        "display_order": 1,
                    }
                ],
            }
        )
    db_session.rollback()
    assert service.list_profiles() == []
