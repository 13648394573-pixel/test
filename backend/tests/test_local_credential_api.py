import logging
import sqlite3

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.local_runner.credentials import CredentialResolver, FakeCredentialStore
from app.main import create_app


def test_local_credential_api_never_echoes_or_persists_secret(tmp_path, caplog) -> None:
    database_path = tmp_path / "credential-api.db"
    store = FakeCredentialStore()
    resolver = CredentialResolver(store)
    settings = Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{database_path.as_posix()}",
        log_file=str(tmp_path / "api.log"),
        api_bind_host="127.0.0.1",
    )
    secret = "never-log-this-value"
    caplog.set_level(logging.DEBUG)

    with TestClient(create_app(settings, credential_resolver=resolver)) as client:
        put_response = client.put(
            "/api/local-credentials/olt.lab.primary", json={"secret": secret}
        )
        assert put_response.status_code == 200
        assert put_response.json() == {
            "reference": "olt.lab.primary",
            "available": True,
        }
        assert put_response.headers["cache-control"] == "no-store"
        assert client.get(
            "/api/local-credentials/olt.lab.primary/status"
        ).json() == {"reference": "olt.lab.primary", "available": True}
        delete_response = client.delete(
            "/api/local-credentials/olt.lab.primary"
        )
        assert delete_response.json() == {
            "reference": "olt.lab.primary",
            "available": False,
        }

    assert secret not in caplog.text
    assert secret not in (tmp_path / "api.log").read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM credential_references"
        ).fetchone()[0] == 0


def test_local_credential_routes_require_loopback_configuration(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        allow_metadata_create_all=True,
        database_url=f"sqlite:///{(tmp_path / 'remote.db').as_posix()}",
        log_file=str(tmp_path / "api.log"),
        api_bind_host="0.0.0.0",
    )
    with TestClient(
        create_app(settings, credential_resolver=CredentialResolver(FakeCredentialStore()))
    ) as client:
        response = client.get("/api/local-credentials/olt.lab/status")
        assert response.status_code == 403

