from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.schema_guard import require_database_health, resolve_expected_revision
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
from app.diagnostics.router import router as diagnostic_router
from app.diagnostics.repository import DiagnosticRepository
from app.diagnostics.service import (
    ActiveDiagnosticConflictError,
    DiagnosticNotFoundError,
    DiagnosticResultNotFoundError,
    InvalidDiagnosticPolicyError,
    LockedDiagnosticResultError,
    UnsupportedDiagnosticAdapterError,
)
from app.evidence.router import router as evidence_router
from app.evidence.service import (
    EvidenceConflictError,
    EvidenceGoneError,
    EvidenceNotFoundError,
    EvidenceOwnerNotFoundError,
    EvidenceTooLargeError,
    InvalidEvidenceError,
)
from app.focused_regressions.router import router as focused_regression_router
from app.focused_regressions.service import (
    ActiveFocusedRegressionExistsError,
    FocusedDefectNotFoundError,
    FocusedRegressionNotFoundError,
    InvalidFocusedRegressionSourceError,
    InvalidFocusedRegressionStateError,
)
from app.reports.router import router as report_router
from app.run_history.router import router as run_history_router
from app.run_history.service import RunComparisonConflictError
from app.reports.service import (
    ArchiveAlreadyExistsError,
    ArchiveNotFoundError,
    ReportArtifactConflictError,
    ReportModeError,
    ReportNotFoundError,
    ReportNotReadyError,
    ReportSourceNotFoundError,
)
from app.environments.router import router as environment_router
from app.environments.service import (
    DuplicateEnvironmentParameterError,
    DuplicateEnvironmentProfileError,
    EnvironmentProfileNotFoundError,
    InvalidEnvironmentProfileError,
    PlaintextSecretError,
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
from app.test_execution.run_numbers import RunNumberConflictError
from app.skill_catalog.router import router as skill_catalog_router
from app.skill_catalog.service import (
    CatalogVersionConflictError,
    SkillCatalogNotFoundError,
)
from app.local_runner.credential_router import router as local_credential_router
from app.local_runner.credentials import (
    CredentialResolver,
    InvalidCredentialReferenceError,
    KeyringCredentialStore,
    UnavailableCredentialError,
)
from app.lab_compatibility.router import router as lab_compatibility_router
from app.lab_compatibility.service import LabCompatibilityService


def create_app(
    settings: Settings | None = None,
    *,
    credential_resolver: CredentialResolver | None = None,
    lab_compatibility_service: LabCompatibilityService | None = None,
) -> FastAPI:
    application_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(
            application_settings.log_file,
            application_settings.log_level,
        )
        engine = create_database_engine(application_settings.database_url)
        if application_settings.allow_metadata_create_all:
            Base.metadata.create_all(engine)
        else:
            require_database_health(engine, resolve_expected_revision())
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
        with application.state.session_factory() as session:
            DiagnosticRepository(session).interrupt_running(
                datetime.now(UTC).replace(tzinfo=None)
            )
        yield
        engine.dispose()

    application = FastAPI(
        title=application_settings.app_name,
        lifespan=lifespan,
    )
    application.state.settings = application_settings
    application.state.credential_resolver = credential_resolver or CredentialResolver(
        KeyringCredentialStore(), application_settings.credential_service_name
    )
    application.state.lab_compatibility_service = lab_compatibility_service

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

    application.add_exception_handler(
        RunComparisonConflictError,
        lambda _request, exception: JSONResponse(
            status_code=409,
            content={"detail": str(exception)},
        ),
    )
    application.add_exception_handler(
        RunNumberConflictError,
        lambda _request, exception: JSONResponse(
            status_code=409,
            content={"detail": str(exception)},
        ),
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

    def report_not_found(
        _request: Request,
        _exception: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Report resource not found"})

    for exception_type in (
        ReportSourceNotFoundError,
        ReportNotFoundError,
        ArchiveNotFoundError,
    ):
        application.add_exception_handler(exception_type, report_not_found)
    for exception_type in (
        ReportNotReadyError,
        ArchiveAlreadyExistsError,
        ReportArtifactConflictError,
    ):
        application.add_exception_handler(
            exception_type,
            lambda _request, exception: JSONResponse(
                status_code=409,
                content={"detail": str(exception) or "Report conflict"},
            ),
        )

    application.add_exception_handler(
        ReportModeError,
        lambda _request, exception: JSONResponse(
            status_code=422,
            content={"detail": str(exception)},
        ),
    )
    application.add_exception_handler(
        SkillCatalogNotFoundError,
        lambda _request, _exception: JSONResponse(
            status_code=404, content={"detail": "Skill not found"}
        ),
    )
    application.add_exception_handler(
        CatalogVersionConflictError,
        lambda _request, exception: JSONResponse(
            status_code=409, content={"detail": str(exception)}
        ),
    )
    application.add_exception_handler(
        InvalidCredentialReferenceError,
        lambda _request, _exception: JSONResponse(
            status_code=422, content={"detail": "Invalid credential reference"}
        ),
    )
    application.add_exception_handler(
        UnavailableCredentialError,
        lambda _request, _exception: JSONResponse(
            status_code=404, content={"detail": "Credential is unavailable"}
        ),
    )

    application.add_exception_handler(
        EnvironmentProfileNotFoundError,
        lambda _request, _exception: JSONResponse(
            status_code=404,
            content={"detail": "Environment profile not found"},
        ),
    )
    application.add_exception_handler(
        DuplicateEnvironmentProfileError,
        lambda _request, _exception: JSONResponse(
            status_code=409,
            content={"detail": "Environment profile name already exists"},
        ),
    )
    for exception_type in (
        DuplicateEnvironmentParameterError,
        InvalidEnvironmentProfileError,
        PlaintextSecretError,
    ):
        application.add_exception_handler(
            exception_type,
            lambda _request, exception: JSONResponse(
                status_code=422,
                content={"detail": str(exception) or "Invalid environment profile"},
            ),
        )

    for exception_type in (DiagnosticNotFoundError, DiagnosticResultNotFoundError):
        application.add_exception_handler(
            exception_type,
            lambda _request, _exception: JSONResponse(
                status_code=404, content={"detail": "Diagnostic resource not found"}
            ),
        )
    for exception_type in (LockedDiagnosticResultError, ActiveDiagnosticConflictError):
        application.add_exception_handler(
            exception_type,
            lambda _request, exception: JSONResponse(
                status_code=409, content={"detail": str(exception) or "Diagnostic conflict"}
            ),
        )
    for exception_type in (InvalidDiagnosticPolicyError, UnsupportedDiagnosticAdapterError):
        application.add_exception_handler(
            exception_type,
            lambda _request, exception: JSONResponse(
                status_code=422, content={"detail": str(exception) or "Invalid diagnostic request"}
            ),
        )

    for exception_type in (
        FocusedDefectNotFoundError,
        FocusedRegressionNotFoundError,
    ):
        application.add_exception_handler(
            exception_type,
            lambda _request, _exception: JSONResponse(
                status_code=404,
                content={"detail": "Focused regression resource not found"},
            ),
        )
    for exception_type in (
        ActiveFocusedRegressionExistsError,
        InvalidFocusedRegressionSourceError,
        InvalidFocusedRegressionStateError,
    ):
        application.add_exception_handler(
            exception_type,
            lambda _request, exception: JSONResponse(
                status_code=409,
                content={"detail": str(exception) or "Focused regression conflict"},
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
        run_history_router,
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
    application.include_router(
        environment_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        report_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        diagnostic_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        focused_regression_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        skill_catalog_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        local_credential_router,
        prefix=application_settings.api_prefix,
    )
    application.include_router(
        lab_compatibility_router,
        prefix=application_settings.api_prefix,
    )

    return application


app = create_app()
