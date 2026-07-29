from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_session
from app.test_cases.repository import TestCaseRepository
from app.test_cases.schemas import TestCaseRead, TestCaseWrite
from app.test_cases.service import TestCaseService


router = APIRouter(prefix="/test-cases", tags=["test-cases"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_service(session: SessionDependency) -> TestCaseService:
    return TestCaseService(TestCaseRepository(session))


ServiceDependency = Annotated[TestCaseService, Depends(get_service)]


@router.get("", response_model=list[TestCaseRead])
def list_test_cases(service: ServiceDependency):
    return service.list()


@router.post(
    "",
    response_model=TestCaseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_test_case(payload: TestCaseWrite, service: ServiceDependency):
    return service.create(payload.model_dump())


@router.get("/{test_case_id}", response_model=TestCaseRead)
def get_test_case(test_case_id: str, service: ServiceDependency):
    return service.get(test_case_id)


@router.put("/{test_case_id}", response_model=TestCaseRead)
def update_test_case(
    test_case_id: str,
    payload: TestCaseWrite,
    service: ServiceDependency,
):
    return service.update(test_case_id, payload.model_dump())


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(
    test_case_id: str,
    service: ServiceDependency,
) -> Response:
    service.delete(test_case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
