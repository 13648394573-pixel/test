from __future__ import annotations

from ipaddress import ip_address
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from app.lab_compatibility.olt_probe import MA5800ReadOnlyProbe
from app.lab_compatibility.schemas import (
    CompatibilityCheckCreate,
    CompatibilityCheckRead,
    CompatibilityEvidenceRead,
    HostKeyPreviewCreate,
    HostKeyPreviewRead,
)
from app.lab_compatibility.service import ActiveCompatibilityCheckExists, LabCompatibilityService
from app.lab_compatibility.store import (
    CompatibilityCheckNotFound,
    CompatibilityReportStore,
    InvalidCompatibilityCheckId,
)
from app.local_runner.evidence import GeneratedEvidenceWriter
from app.local_runner.onu_web.neutral import NeutralONUWebAdapter
from app.local_runner.pc_probe import PCProbe


router = APIRouter(prefix="/lab-compatibility-checks", tags=["lab-compatibility"])


def _is_loopback(value: str) -> bool:
    if value.casefold() == "localhost":
        return True
    try:
        return ip_address(value).is_loopback
    except ValueError:
        return False


def get_service(request: Request) -> LabCompatibilityService:
    settings = request.app.state.settings
    if not _is_loopback(settings.api_bind_host):
        raise HTTPException(
            status_code=403,
            detail="现场检查接口仅允许本机访问",
        )
    service = getattr(request.app.state, "lab_compatibility_service", None)
    if service is None:
        root = Path(settings.lab_compatibility_root)
        service = LabCompatibilityService(
            CompatibilityReportStore(root),
            request.app.state.credential_resolver,
            MA5800ReadOnlyProbe(),
            NeutralONUWebAdapter(),
            PCProbe(evidence_writer=GeneratedEvidenceWriter(root)),
        )
        request.app.state.lab_compatibility_service = service
    return service


ServiceDependency = Annotated[LabCompatibilityService, Depends(get_service)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/host-key-preview", response_model=HostKeyPreviewRead)
def preview_host_key(
    payload: HostKeyPreviewCreate,
    response: Response,
    service: ServiceDependency,
):
    _no_store(response)
    return {"fingerprint": service.preview_host_key(payload.olt_host, payload.olt_port)}


@router.post(
    "",
    response_model=CompatibilityCheckRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_check(
    payload: CompatibilityCheckCreate,
    background_tasks: BackgroundTasks,
    response: Response,
    service: ServiceDependency,
):
    _no_store(response)
    try:
        view = service.create(payload.to_command())
    except ActiveCompatibilityCheckExists as exception:
        raise HTTPException(status_code=409, detail="已有现场检查正在运行") from exception
    background_tasks.add_task(service.execute, view.check_id)
    return view


@router.get("/{check_id}", response_model=CompatibilityCheckRead)
def get_check(check_id: str, response: Response, service: ServiceDependency):
    _no_store(response)
    try:
        return service.get(check_id)
    except (CompatibilityCheckNotFound, InvalidCompatibilityCheckId) as exception:
        raise HTTPException(status_code=404, detail="现场检查记录不存在") from exception


@router.get("/{check_id}/evidence", response_model=list[CompatibilityEvidenceRead])
def list_evidence(check_id: str, response: Response, service: ServiceDependency):
    _no_store(response)
    try:
        return service.list_evidence(check_id)
    except (CompatibilityCheckNotFound, InvalidCompatibilityCheckId) as exception:
        raise HTTPException(status_code=404, detail="现场检查记录不存在") from exception
