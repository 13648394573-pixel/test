from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_endpoint_reports_local_application_status(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{(tmp_path / 'health.db').as_posix()}",
        log_file=str(tmp_path / "health.log"),
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Test Workbench"}
