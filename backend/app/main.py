from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import create_database_engine, create_session_factory
from app.defects.router import router as defect_router
from app.defects.service import (
    ClosedDefectError,
    DefectNotFoundError,
    DuplicateDefectSourceError,
    DuplicateRegressionError,
    InvalidDefectSourceError,
    InvalidDefectTransitionError,
    InvalidRegressionEvidenceError,
    RunResultEvidenceNotFoundError,
)
from app.devices.router import router as device_router
from app.devices.service import DeviceNotFoundError, DuplicateSerialNumberError
from app.evidence.router import router as evidence_router
from app.evidence.service import (
    EvidenceConflictError,
    EvidenceGoneError,
    EvidenceNotFoundError,
    EvidenceOwnerNotFoundError,
    EvidenceTooLargeError,
    InvalidEvidenceError,
)
from app.test_cases.router import router as test_case_router
from app.test_cases.service import DuplicateCaseCodeError, TestCaseNotFoundError
from app.test_execution.router import router as test_execution_router
from app.test_execution.service import (
    InvalidCaseSourceError,
    InvalidDeviceSourceError,
    InvalidResultValueError,
    InvalidResultIntegrityError,
    LockedResultError,
    ProjectHasRunsError,
    RunResultNotFoundError,
    TestProjectNotFoundError,
    TestRunNotFoundError,
)


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
    application.state.settings = application_settings

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

    @application.exception_handler(TestProjectNotFoundError)
    def project_not_found(
        _request: Request,
        _exception: TestProjectNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Test project not found"},
        )

    @application.exception_handler(TestRunNotFoundError)
    def run_not_found(
        _request: Request,
        _exception: TestRunNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Test run not found"},
        )

    @application.exception_handler(RunResultNotFoundError)
    def run_result_not_found(
        _request: Request,
        _exception: RunResultNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "Run result not found"},
        )

    @application.exception_handler(ProjectHasRunsError)
    def project_has_runs(
        _request: Request,
        _exception: ProjectHasRunsError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Project has run history"},
        )

    @application.exception_handler(InvalidDeviceSourceError)
    def invalid_device_source(
        _request: Request,
        _exception: InvalidDeviceSourceError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Selected device is unavailable"},
        )

    @application.exception_handler(InvalidCaseSourceError)
    def invalid_case_source(
        _request: Request,
        _exception: InvalidCaseSourceError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Selected test case is unavailable"},
        )

    @application.exception_handler(InvalidResultValueError)
    def invalid_result_value(
        _request: Request,
        _exception: InvalidResultValueError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid result value"},
        )

    @application.exception_handler(InvalidResultIntegrityError)
    def invalid_result_integrity(
        _request: Request,
        exception: InvalidResultIntegrityError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exception)})

    @application.exception_handler(LockedResultError)
    def locked_result(
        _request: Request,
        _exception: LockedResultError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Run result is locked"},
        )

    def defect_not_found(
        _request: Request,
        _exception: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Evidence not found"})

    def defect_conflict(
        _request: Request,
        exception: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exception)})

    def invalid_defect_evidence(
        _request: Request,
        exception: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exception)})

    for exception_type in (DefectNotFoundError, RunResultEvidenceNotFoundError):
        application.add_exception_handler(exception_type, defect_not_found)
    for exception_type in (
        ClosedDefectError,
        DuplicateDefectSourceError,
        DuplicateRegressionError,
        InvalidDefectTransitionError,
    ):
        application.add_exception_handler(exception_type, defect_conflict)
    for exception_type in (
        InvalidDefectSourceError,
        InvalidRegressionEvidenceError,
    ):
        application.add_exception_handler(exception_type, invalid_defect_evidence)

    def evidence_not_found(
        _request: Request,
        _exception: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Evidence not found"})

    for exception_type in (
        EvidenceNotFoundError,
        EvidenceOwnerNotFoundError,
    ):
        application.add_exception_handler(exception_type, evidence_not_found)
    application.add_exception_handler(
        EvidenceConflictError,
        lambda _request, exception: JSONResponse(
            status_code=409,
            content={"detail": str(exception)},
        ),
    )
    application.add_exception_handler(
        EvidenceGoneError,
        lambda _request, _exception: JSONResponse(
            status_code=410,
            content={"detail": "Evidence file is missing"},
        ),
    )
    application.add_exception_handler(
        EvidenceTooLargeError,
        lambda _request, _exception: JSONResponse(
            status_code=413,
            content={"detail": "Evidence file is too large"},
        ),
    )
    application.add_exception_handler(
        InvalidEvidenceError,
        lambda _request, exception: JSONResponse(
            status_code=422,
            content={"detail": str(exception)},
        ),
    )

    application.include_router(
        device_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        test_case_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        test_execution_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        defect_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        evidence_router,
        prefix=application_settings.api_prefix,
    )

    return application


app = create_app()
