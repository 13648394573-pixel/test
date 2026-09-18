import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{(tmp_path / 'catalog-api.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_skill_catalog_api_installs_and_reads_draft(client: TestClient) -> None:
    assert client.get("/api/skills").json() == []

    response = client.post(
        "/api/skills/catalog/onu-registration-dual-wan/install-draft"
    )
    assert response.status_code == 201
    installed = response.json()
    assert installed["created"] is True
    assert len(installed["definition_hash"]) == 64

    summaries = client.get("/api/skills").json()
    assert len(summaries) == 1
    assert summaries[0]["skill_code"] == "ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY"
    assert summaries[0]["status"] == "DRAFT"
    assert summaries[0]["supported_olts"] == ["Huawei MA5800-X7"]

    detail_response = client.get(f"/api/skills/{installed['skill_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert [item["rule_code"] for item in detail["evidence_rules"]] == [
        "E1_OLT_AUTOFIND",
        "E2_REGISTRATION",
        "E3_IPOE_ADDRESS",
        "E4_IPOE_PING",
        "E5_PPPOE_ADDRESS",
        "E6_PPPOE_PING",
    ]
    assert not any("command" in action for action in detail["actions"])
    assert not any("credential" in action for action in detail["actions"])

    repeated = client.post(
        "/api/skills/catalog/onu-registration-dual-wan/install-draft"
    )
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False


def test_skill_catalog_api_reports_missing_skill(client: TestClient) -> None:
    response = client.get("/api/skills/missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Skill not found"}
