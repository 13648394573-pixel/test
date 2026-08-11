from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.evidence.repository import EvidenceRepository
from app.evidence.schemas import EvidenceRead
from app.evidence.service import EvidenceService
from app.evidence.storage import EvidenceStorage


router = APIRouter(tags=["evidence"])
SessionDependency = Annotated[Session, Depends(get_session)]
Category = Literal["SCREENSHOT", "LOG", "CONFIG", "OTHER"]


def get_service(
    request: Request,
    session: SessionDependency,
) -> EvidenceService:
    settings = request.app.state.settings
    return EvidenceService(
        EvidenceRepository(session),
        EvidenceStorage(
            settings.evidence_root,
            max_bytes=settings.evidence_max_size_mb * 1024 * 1024,
        ),
    )


ServiceDependency = Annotated[EvidenceService, Depends(get_service)]


@router.get(
    "/run-results/{result_id}/evidences",
    response_model=list[EvidenceRead],
)
def list_result_evidence(result_id: str, service: ServiceDependency):
    return service.list_for_run_result(result_id)


@router.post(
    "/evidences/batch",
    response_model=list[EvidenceRead],
    status_code=status.HTTP_201_CREATED,
)
def upload_batch_evidence(
    service: ServiceDependency,
    run_result_ids: Annotated[list[str], Form()],
    files: Annotated[list[UploadFile], File()],
    category: Annotated[Category, Form()],
    description: Annotated[str | None, Form()] = None,
):
    return service.create_batch_for_results(
        run_result_ids,
        [
            {
                "original_name": file.filename or "",
                "media_type": file.content_type or "application/octet-stream",
                "stream": file.file,
            }
            for file in files
        ],
        category=category,
        description=description,
    )


@router.post(
    "/run-results/{result_id}/evidences",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_result_evidence(
    result_id: str,
    service: ServiceDependency,
    category: Annotated[Category, Form()],
    file: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form()] = None,
):
    return service.create_for_run_result(
        result_id,
        category=category,
        original_name=file.filename or "",
        media_type=file.content_type or "application/octet-stream",
        description=description,
        stream=file.file,
    )


@router.get(
    "/defects/{defect_id}/evidences",
    response_model=list[EvidenceRead],
)
def list_defect_evidence(defect_id: str, service: ServiceDependency):
    return service.list_for_defect(defect_id)


@router.post(
    "/defects/{defect_id}/evidences",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_defect_evidence(
    defect_id: str,
    service: ServiceDependency,
    category: Annotated[Category, Form()],
    file: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form()] = None,
):
    return service.create_for_defect(
        defect_id,
        category=category,
        original_name=file.filename or "",
        media_type=file.content_type or "application/octet-stream",
        description=description,
        stream=file.file,
    )


@router.get("/evidences/{evidence_id}/download")
def download_evidence(
    evidence_id: str,
    service: ServiceDependency,
) -> FileResponse:
    evidence, path = service.get_download(evidence_id)
    return FileResponse(
        path,
        media_type=evidence.media_type,
        filename=evidence.original_name,
    )


@router.delete(
    "/evidences/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_evidence(
    evidence_id: str,
    service: ServiceDependency,
) -> Response:
    service.delete(evidence_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
