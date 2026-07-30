from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.reports.repository import ReportRepository
from app.reports.schemas import ArchiveRead, ReportGenerate, ReportRead
from app.reports.service import ReportService
from app.reports.storage import ReportStorage


router = APIRouter(tags=["reports"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(
    request: Request,
    session: SessionDependency,
) -> ReportService:
    settings = request.app.state.settings
    return ReportService(
        ReportRepository(session),
        ReportStorage(settings.report_root, settings.evidence_root),
    )


ServiceDependency = Annotated[ReportService, Depends(get_service)]


@router.post(
    "/test-runs/{run_id}/reports",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_report(
    run_id: str,
    payload: ReportGenerate,
    service: ServiceDependency,
):
    return service.generate_report(run_id, payload.title)


@router.get(
    "/test-runs/{run_id}/reports",
    response_model=list[ReportRead],
)
def list_run_reports(run_id: str, service: ServiceDependency):
    return service.list_for_run(run_id)


@router.get(
    "/test-projects/{project_id}/reports",
    response_model=list[ReportRead],
)
def list_project_reports(project_id: str, service: ServiceDependency):
    return service.list_for_project(project_id)


@router.get("/reports/{report_id}", response_model=ReportRead)
def get_report(report_id: str, service: ServiceDependency):
    return service.get_report(report_id)


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    service: ServiceDependency,
) -> FileResponse:
    report = service.get_report(report_id)
    path = service.download_report(report_id)
    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        filename=f"{report.report_no}.html",
    )


@router.post(
    "/reports/{report_id}/archive",
    response_model=ArchiveRead,
    status_code=status.HTTP_201_CREATED,
)
def create_archive(report_id: str, service: ServiceDependency):
    return service.create_archive(report_id)


@router.get("/reports/{report_id}/archive", response_model=ArchiveRead)
def get_report_archive(report_id: str, service: ServiceDependency):
    return service.get_archive_for_report(report_id)


@router.get("/archives/{archive_id}", response_model=ArchiveRead)
def get_archive(archive_id: str, service: ServiceDependency):
    return service.get_archive(archive_id)


@router.get("/archives/{archive_id}/download")
def download_archive(
    archive_id: str,
    service: ServiceDependency,
) -> FileResponse:
    archive = service.get_archive(archive_id)
    path = service.download_archive(archive_id)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{archive.archive_no}.zip",
    )
