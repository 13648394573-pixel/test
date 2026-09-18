import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


PROFILE_PAYLOAD = {
    "name": "ONU Access Lab",
    "description": "MA5800-X7 and VLAN 100",
    "enabled": True,
    "parameters": [
        {
            "section": "OLT",
            "param_key": "model",
            "param_value": "MA5800-X7",
            "display_order": 1,
        },
        {
            "section": "VLAN",
            "param_key": "internet_vlan",
            "param_value": "100",
            "display_order": 2,
        },
    ],
}


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_environment_profile_api_supports_crud(client: TestClient) -> None:
    created_response = client.post(
        "/api/environment-profiles",
        json=PROFILE_PAYLOAD,
    )
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["name"] == "ONU Access Lab"
    assert created["parameters"][0]["param_key"] == "model"
    assert client.get("/api/environment-profiles").json() == [created]
    assert client.get(
        f"/api/environment-profiles/{created['id']}"
    ).json() == created

    updated_response = client.put(
        f"/api/environment-profiles/{created['id']}",
        json={
            **PROFILE_PAYLOAD,
            "description": "Updated",
            "parameters": [PROFILE_PAYLOAD["parameters"][1]],
        },
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["description"] == "Updated"
    assert len(updated_response.json()["parameters"]) == 1

    delete_response = client.delete(
        f"/api/environment-profiles/{created['id']}"
    )
    assert delete_response.status_code == 204
    assert client.get("/api/environment-profiles").json() == []


def test_environment_profile_api_validates_conflicts_and_parameters(
    client: TestClient,
) -> None:
    assert client.post(
        "/api/environment-profiles",
        json=PROFILE_PAYLOAD,
    ).status_code == 201
    duplicate = client.post(
        "/api/environment-profiles",
        json=PROFILE_PAYLOAD,
    )
    assert duplicate.status_code == 409
    invalid = client.post(
        "/api/environment-profiles",
        json={
            **PROFILE_PAYLOAD,
            "name": "Invalid",
            "parameters": [
                PROFILE_PAYLOAD["parameters"][0],
                {
                    **PROFILE_PAYLOAD["parameters"][1],
                    "param_key": "model",
                },
            ],
        },
    )
    assert invalid.status_code == 422
    assert client.get("/api/environment-profiles/missing").status_code == 404
