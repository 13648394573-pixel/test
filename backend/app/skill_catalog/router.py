from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.skill_catalog.repository import SkillCatalogRepository
from app.skill_catalog.schemas import (
    CatalogInstallRead,
    SkillDetailRead,
    SkillSummaryRead,
)
from app.skill_catalog.service import SkillCatalogService


router = APIRouter(prefix="/skills", tags=["skills"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> SkillCatalogService:
    return SkillCatalogService(SkillCatalogRepository(session))


ServiceDependency = Annotated[SkillCatalogService, Depends(get_service)]


@router.post(
    "/catalog/onu-registration-dual-wan/install-draft",
    response_model=CatalogInstallRead,
)
def install_draft(service: ServiceDependency, response: Response):
    result = service.install_onu_registration_dual_wan_draft()
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return result


@router.get("", response_model=list[SkillSummaryRead])
def list_skills(service: ServiceDependency):
    return service.list()


@router.get("/{skill_id}", response_model=SkillDetailRead)
def get_skill(skill_id: str, service: ServiceDependency):
    return service.get(skill_id)
