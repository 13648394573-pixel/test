from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.test_case import CaseStep, TestCase


class TestCaseRepository:
    __test__ = False

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[TestCase]:
        statement = (
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .order_by(TestCase.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get(self, test_case_id: str) -> TestCase | None:
        statement = (
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .where(TestCase.id == test_case_id)
        )
        return self.session.scalar(statement)

    def get_by_case_code(self, case_code: str) -> TestCase | None:
        statement = (
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .where(TestCase.case_code == case_code)
        )
        return self.session.scalar(statement)

    def create(
        self,
        values: Mapping[str, Any],
        steps: Sequence[Mapping[str, Any]],
    ) -> TestCase:
        test_case = TestCase(**values)
        test_case.steps = [CaseStep(**step) for step in steps]
        self.session.add(test_case)
        return self._commit_and_reload(test_case)

    def update(
        self,
        test_case: TestCase,
        values: Mapping[str, Any],
        steps: Sequence[Mapping[str, Any]],
    ) -> TestCase:
        try:
            for field, value in values.items():
                setattr(test_case, field, value)
            test_case.steps.clear()
            self.session.flush()
            test_case.steps = [CaseStep(**step) for step in steps]
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload(test_case)

    def delete(self, test_case: TestCase) -> None:
        try:
            self.session.delete(test_case)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def _commit_and_reload(self, test_case: TestCase) -> TestCase:
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload(test_case)

    def _reload(self, test_case: TestCase) -> TestCase:
        loaded = self.get(test_case.id)
        if loaded is None:
            raise RuntimeError("Persisted test case could not be reloaded")
        return loaded
