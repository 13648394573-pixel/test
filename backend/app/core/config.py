from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TEST_WORKBENCH_",
        extra="ignore",
    )

    app_name: str = "Test Workbench"
    app_env: str = "development"
    api_prefix: str = "/api"
    api_bind_host: str = "127.0.0.1"
    database_url: str = "sqlite:///./data/test_workbench.db"
    log_level: str = "INFO"
    log_file: str = "./logs/test-workbench.log"
    evidence_root: str = "./data/evidence"
    local_runner_evidence_root: str = "./data/runner-evidence"
    lab_compatibility_root: str = "./data/runner-evidence/lab-compatibility"
    credential_service_name: str = "ONU Test Workbench"
    evidence_max_size_mb: int = 50
    report_root: str = "./data/reports"
    allow_metadata_create_all: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
