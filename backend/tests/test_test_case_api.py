import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.main import create_app
from app.models.test_case import CaseStep


CASE_PAYLOAD = {
    "case_code": "ONU-WAN-001",
    "title": "Verify IPoE WAN connectivity",
    "device_type": "ONU",
    "category": "WAN",
    "priority": "P1",
    "preconditions": "ONU is registered",
    "description": "Verify an IPoE WAN can reach the Internet",
    "enabled": True,
    "steps": [
        {
            "action": "Create an IPoE WAN",
            "expected_result": "WAN obtains an address",
        },
        {
            "action": "Ping the gateway",
            "expected_result": "Ping succeeds",
        },
    ],
}


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_test_case_api_supports_aggregate_crud_lifecycle(
    client: TestClient,
) -> None:
    create_response = client.post("/api/test-cases", json=CASE_PAYLOAD)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["case_code"] == "ONU-WAN-001"
    assert [step["step_number"] for step in created["steps"]] == [1, 2]
    assert all(step["id"] for step in created["steps"])
    assert all(step["created_at"] for step in created["steps"])

    assert client.get("/api/test-cases").json() == [created]
    assert client.get(f"/api/test-cases/{created['id']}").json() == created

    update_response = client.put(
        f"/api/test-cases/{created['id']}",
        json={
            **CASE_PAYLOAD,
            "title": "Updated WAN connectivity",
            "steps": [
                {
                    "action": "Ping a public resolver",
                    "expected_result": "Ping succeeds",
                }
            ],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Updated WAN connectivity"
    assert len(updated["steps"]) == 1
    assert updated["steps"][0]["step_number"] == 1
    assert updated["steps"][0]["id"] not in {
        step["id"] for step in created["steps"]
    }

    delete_response = client.delete(f"/api/test-cases/{created['id']}")
    assert delete_response.status_code == 204
    assert client.get("/api/test-cases").json() == []
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CaseStep)) == 0


def test_test_case_api_reports_duplicate_case_code(client: TestClient) -> None:
    assert client.post("/api/test-cases", json=CASE_PAYLOAD).status_code == 201

    response = client.post(
        "/api/test-cases",
        json={**CASE_PAYLOAD, "title": "Duplicate code"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Case code already exists"}


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_test_case_api_reports_missing_case(
    client: TestClient,
    method: str,
) -> None:
    if method == "put":
        response = client.put("/api/test-cases/missing", json=CASE_PAYLOAD)
    else:
        response = getattr(client, method)("/api/test-cases/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Test case not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {**CASE_PAYLOAD, "priority": "P4"},
        {**CASE_PAYLOAD, "steps": []},
        {
            **CASE_PAYLOAD,
            "steps": [{"action": "", "expected_result": "Result"}],
        },
        {
            **CASE_PAYLOAD,
            "steps": [{"action": "Action", "expected_result": "  "}],
        },
    ],
)
def test_test_case_api_rejects_invalid_payload(
    client: TestClient,
    payload: dict,
) -> None:
    response = client.post("/api/test-cases", json=payload)

    assert response.status_code == 422
