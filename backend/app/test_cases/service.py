from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.models.test_case import TestCase
from app.test_cases.repository import TestCaseRepository


class TestCaseNotFoundError(Exception):
    __test__ = False


class DuplicateCaseCodeError(Exception):
    pass


class EmptyStepsError(ValueError):
    pass


class TestCaseService:
    __test__ = False

    def __init__(self, repository: TestCaseRepository) -> None:
        self.repository = repository

    def list(self) -> list[TestCase]:
        return self.repository.list()

    def get(self, test_case_id: str) -> TestCase:
        test_case = self.repository.get(test_case_id)
        if test_case is None:
            raise TestCaseNotFoundError(test_case_id)
        return test_case

    def create(self, values: Mapping[str, Any]) -> TestCase:
        case_values, steps = self._prepare_aggregate(values)
        case_code = str(case_values["case_code"])
        if self.repository.get_by_case_code(case_code) is not None:
            raise DuplicateCaseCodeError(case_code)
        return self.repository.create(case_values, steps)

    def update(
        self,
        test_case_id: str,
        values: Mapping[str, Any],
    ) -> TestCase:
        test_case = self.get(test_case_id)
        case_values, steps = self._prepare_aggregate(values)
        case_code = str(case_values["case_code"])
        existing = self.repository.get_by_case_code(case_code)
        if existing is not None and existing.id != test_case.id:
            raise DuplicateCaseCodeError(case_code)
        return self.repository.update(test_case, case_values, steps)

    def delete(self, test_case_id: str) -> None:
        self.repository.delete(self.get(test_case_id))

    def _prepare_aggregate(
        self,
        values: Mapping[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        case_values = dict(values)
        raw_steps = case_values.pop("steps")
        if not isinstance(raw_steps, Sequence) or not raw_steps:
            raise EmptyStepsError
        steps = [
            {
                **dict(step),
                "step_number": index,
            }
            for index, step in enumerate(raw_steps, start=1)
        ]
        return case_values, steps
