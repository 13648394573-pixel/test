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
    database_url: str = "sqlite:///./data/test_workbench.db"
    log_level: str = "INFO"
    log_file: str = "./logs/test-workbench.log"


@lru_cache
def get_settings() -> Settings:
    return Settings()
