from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(
            application_settings.log_file,
            application_settings.log_level,
        )
        engine = create_database_engine(application_settings.database_url)
        Base.metadata.create_all(engine)
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title=application_settings.app_name,
        lifespan=lifespan,
    )

    @application.get(f"{application_settings.api_prefix}/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": application_settings.app_name}

    return application


app = create_app()
