import os
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.diagnostics.adapters.huawei import HuaweiPingAdapter, HuaweiWebPingExecutor
from app.diagnostics.registry import AdapterRegistry
from app.diagnostics.repository import DiagnosticRepository
from app.diagnostics.schemas import DiagnosticCreate, DiagnosticSessionRead
from app.diagnostics.service import DiagnosticService
from app.evidence.repository import EvidenceRepository
from app.evidence.service import EvidenceService
from app.evidence.storage import EvidenceStorage


router = APIRouter(tags=["diagnostics"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(request: Request, session: SessionDependency) -> DiagnosticService:
    settings = request.app.state.settings
    executor = getattr(request.app.state, "huawei_ping_executor", None)
    if executor is None:
        executor = HuaweiWebPingExecutor(
            os.getenv("TEST_WORKBENCH_DIAGNOSTIC_HUAWEI_USERNAME", ""),
            os.getenv("TEST_WORKBENCH_DIAGNOSTIC_HUAWEI_PASSWORD", ""),
        )
    evidence_service = EvidenceService(
        EvidenceRepository(session),
        EvidenceStorage(
            settings.evidence_root,
            max_bytes=settings.evidence_max_size_mb * 1024 * 1024,
        ),
    )
    return DiagnosticService(
        DiagnosticRepository(session),
        AdapterRegistry([HuaweiPingAdapter(executor)]),
        evidence_service=evidence_service,
    )


ServiceDependency = Annotated[DiagnosticService, Depends(get_service)]


@router.post(
    "/run-results/{result_id}/diagnostics",
    response_model=DiagnosticSessionRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_diagnostic(
    result_id: str,
    payload: DiagnosticCreate,
    background_tasks: BackgroundTasks,
    service: ServiceDependency,
):
    diagnostic = service.create(result_id, payload.model_dump())
    background_tasks.add_task(service.execute, diagnostic.id)
    return diagnostic


@router.get(
    "/run-results/{result_id}/diagnostics",
    response_model=list[DiagnosticSessionRead],
)
def list_diagnostics(result_id: str, service: ServiceDependency):
    return service.list_for_result(result_id)


@router.get("/diagnostics/{session_id}", response_model=DiagnosticSessionRead)
def get_diagnostic(session_id: str, service: ServiceDependency):
    return service.get(session_id)
