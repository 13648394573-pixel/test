from app.environments.repository import EnvironmentRepository


PROFILE = {
    "name": "ONU Lab A",
    "description": "MA5800-X7 access lab",
    "enabled": True,
}
PARAMETERS = [
    {
        "section": "OLT",
        "param_key": "management_ip",
        "param_value": "192.0.2.10",
        "display_order": 1,
    },
    {
        "section": "VLAN",
        "param_key": "internet_vlan",
        "param_value": "100",
        "display_order": 2,
    },
]


def test_repository_creates_and_replaces_profile_parameters_atomically(
    db_session,
) -> None:
    repository = EnvironmentRepository(db_session)
    profile = repository.create(PROFILE, PARAMETERS)

    updated = repository.update(
        profile,
        {**PROFILE, "description": "Updated lab"},
        [
            {
                "section": "WAN",
                "param_key": "wan_mode",
                "param_value": "IPoE",
                "display_order": 1,
            }
        ],
    )

    assert updated.description == "Updated lab"
    assert [
        (item.section, item.param_key, item.param_value, item.display_order)
        for item in updated.parameters
    ] == [("WAN", "wan_mode", "IPoE", 1)]
    assert repository.get_by_name("ONU Lab A").id == profile.id


def test_repository_delete_removes_profile_and_parameters(db_session) -> None:
    repository = EnvironmentRepository(db_session)
    profile = repository.create(PROFILE, PARAMETERS)

    repository.delete(profile)

    assert repository.get(profile.id) is None
    assert repository.list() == []
