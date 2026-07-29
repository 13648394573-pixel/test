from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.devices.router import router as device_router
from app.devices.service import DeviceNotFoundError, DuplicateSerialNumberError
from app.test_cases.router import router as test_case_router
from app.test_cases.service import DuplicateCaseCodeError, TestCaseNotFoundError


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

    @application.exception_handler(DeviceNotFoundError)
    def device_not_found(
        _request: Request,
        _exception: DeviceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Device not found"})

    @application.exception_handler(DuplicateSerialNumberError)
    def duplicate_serial_number(
        _request: Request,
        _exception: DuplicateSerialNumberError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Serial number already exists"},
        )

    @application.exception_handler(TestCaseNotFoundError)
    def test_case_not_found(
        _request: Request,
        _exception: TestCaseNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Test case not found"},
        )

    @application.exception_handler(DuplicateCaseCodeError)
    def duplicate_case_code(
        _request: Request,
        _exception: DuplicateCaseCodeError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Case code already exists"},
        )

    application.include_router(
        device_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        test_case_router,
        prefix=application_settings.api_prefix,
    )

    return application


app = create_app()
