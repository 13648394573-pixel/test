from app.core.config import Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "Test Workbench"
    assert settings.database_url == "sqlite:///./data/test_workbench.db"
    assert settings.log_file == "./logs/test-workbench.log"


def test_settings_read_prefixed_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("TEST_WORKBENCH_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
