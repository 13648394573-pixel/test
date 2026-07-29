import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.test_case import CaseStep, TestCase as TestCaseModel
from app.test_cases.repository import TestCaseRepository as CaseRepository


CASE_DATA = {
    "case_code": "ONU-LOGIN-001",
    "title": "ONU Web login",
    "device_type": "ONU",
    "category": "Management",
    "priority": "P1",
    "preconditions": "ONU is reachable",
    "description": "Verify local Web login",
    "enabled": True,
}
STEP_DATA = [
    {
        "step_number": 1,
        "action": "Open the management address",
        "expected_result": "Login page is displayed",
    },
    {
        "step_number": 2,
        "action": "Enter valid credentials",
        "expected_result": "Home page is displayed",
    },
]


def test_repository_creates_lists_and_gets_test_case_with_steps(
    db_session: Session,
) -> None:
    repository = CaseRepository(db_session)

    created = repository.create(CASE_DATA, STEP_DATA)

    assert created.id
    assert [step.step_number for step in created.steps] == [1, 2]
    assert [step.action for step in created.steps] == [
        "Open the management address",
        "Enter valid credentials",
    ]
    assert repository.list() == [created]
    assert repository.get(created.id) is created
    assert repository.get_by_case_code("ONU-LOGIN-001") is created


def test_repository_replaces_all_steps_on_update(db_session: Session) -> None:
    repository = CaseRepository(db_session)
    test_case = repository.create(CASE_DATA, STEP_DATA)
    original_step_ids = {step.id for step in test_case.steps}

    updated = repository.update(
        test_case,
        {"title": "Updated login case"},
        [
            {
                "step_number": 1,
                "action": "Log in with valid credentials",
                "expected_result": "Overview page is displayed",
            }
        ],
    )

    assert updated.title == "Updated login case"
    assert len(updated.steps) == 1
    assert updated.steps[0].action == "Log in with valid credentials"
    assert updated.steps[0].id not in original_step_ids
    assert db_session.scalar(select(func.count()).select_from(CaseStep)) == 1


def test_repository_rolls_back_entire_aggregate_when_steps_are_invalid(
    db_session: Session,
) -> None:
    repository = CaseRepository(db_session)
    duplicate_numbers = [
        {**STEP_DATA[0], "step_number": 1},
        {**STEP_DATA[1], "step_number": 1},
    ]

    with pytest.raises(IntegrityError):
        repository.create(CASE_DATA, duplicate_numbers)

    assert db_session.scalar(select(func.count()).select_from(TestCaseModel)) == 0
    assert db_session.scalar(select(func.count()).select_from(CaseStep)) == 0


def test_repository_deletes_test_case_and_cascades_steps(
    db_session: Session,
) -> None:
    repository = CaseRepository(db_session)
    test_case = repository.create(CASE_DATA, STEP_DATA)

    repository.delete(test_case)

    assert repository.get(test_case.id) is None
    assert db_session.scalar(select(func.count()).select_from(CaseStep)) == 0
