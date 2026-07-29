import pytest
from sqlalchemy.orm import Session

from app.test_cases.repository import TestCaseRepository as CaseRepository
from app.test_cases.service import (
    DuplicateCaseCodeError,
    EmptyStepsError,
    TestCaseNotFoundError,
    TestCaseService as CaseService,
)


CASE_INPUT = {
    "case_code": "OLT-PON-001",
    "title": "Verify PON registration",
    "device_type": "OLT",
    "category": "PON",
    "priority": "P0",
    "preconditions": None,
    "description": None,
    "enabled": True,
    "steps": [
        {
            "action": "Connect the ONU to the PON port",
            "expected_result": "ONU reaches O5 state",
        },
        {
            "action": "Query registered ONTs",
            "expected_result": "ONU serial number is listed",
        },
    ],
}


def test_service_assigns_continuous_step_numbers_on_create_and_update(
    db_session: Session,
) -> None:
    service = CaseService(CaseRepository(db_session))
    created = service.create(CASE_INPUT)

    assert [step.step_number for step in created.steps] == [1, 2]

    updated = service.update(
        created.id,
        {
            **CASE_INPUT,
            "steps": [
                CASE_INPUT["steps"][1],
                {
                    "action": "Save the registration result",
                    "expected_result": "Result is recorded",
                },
                CASE_INPUT["steps"][0],
            ],
        },
    )

    assert [step.step_number for step in updated.steps] == [1, 2, 3]
    assert [step.action for step in updated.steps] == [
        "Query registered ONTs",
        "Save the registration result",
        "Connect the ONU to the PON port",
    ]


def test_service_rejects_duplicate_case_code_on_create_and_update(
    db_session: Session,
) -> None:
    service = CaseService(CaseRepository(db_session))
    first = service.create(CASE_INPUT)
    second = service.create({**CASE_INPUT, "case_code": "OLT-PON-002"})

    with pytest.raises(DuplicateCaseCodeError):
        service.create({**CASE_INPUT, "title": "Duplicate"})
    with pytest.raises(DuplicateCaseCodeError):
        service.update(second.id, {**CASE_INPUT, "case_code": first.case_code})


def test_service_rejects_empty_steps(db_session: Session) -> None:
    service = CaseService(CaseRepository(db_session))

    with pytest.raises(EmptyStepsError):
        service.create({**CASE_INPUT, "steps": []})


def test_service_reports_missing_case_for_read_update_and_delete(
    db_session: Session,
) -> None:
    service = CaseService(CaseRepository(db_session))

    with pytest.raises(TestCaseNotFoundError):
        service.get("missing")
    with pytest.raises(TestCaseNotFoundError):
        service.update("missing", CASE_INPUT)
    with pytest.raises(TestCaseNotFoundError):
        service.delete("missing")
