from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.devices.repository import DeviceRepository
from app.models.test_execution import RunResult, TestProject, TestRun
from app.test_cases.repository import TestCaseRepository
from app.test_execution.repository import TestExecutionRepository
from app.test_execution.snapshots import (
    build_case_snapshot,
    build_device_snapshot,
)


class TestProjectNotFoundError(Exception):
    __test__ = False


class TestRunNotFoundError(Exception):
    __test__ = False


class RunResultNotFoundError(Exception):
    pass


class InvalidDeviceSourceError(Exception):
    pass


class InvalidCaseSourceError(Exception):
    pass


class InvalidResultValueError(Exception):
    pass


class ProjectHasRunsError(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TestExecutionService:
    __test__ = False

    def __init__(
        self,
        repository: TestExecutionRepository,
        device_repository: DeviceRepository,
        case_repository: TestCaseRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.device_repository = device_repository
        self.case_repository = case_repository
        self.clock = clock

    def list_projects(self) -> list[TestProject]:
        return self.repository.list_projects()

    def get_project(self, project_id: str) -> TestProject:
        project = self.repository.get_project(project_id)
        if project is None:
            raise TestProjectNotFoundError(project_id)
        return project

    def create_project(self, values: Mapping[str, Any]) -> TestProject:
        project_values, case_source_ids = self._prepare_project(values)
        return self.repository.create_project(project_values, case_source_ids)

    def update_project(
        self,
        project_id: str,
        values: Mapping[str, Any],
    ) -> TestProject:
        project = self.get_project(project_id)
        project_values, case_source_ids = self._prepare_project(values)
        return self.repository.update_project(
            project,
            project_values,
            case_source_ids,
        )

    def delete_project(self, project_id: str) -> None:
        project = self.get_project(project_id)
        if self.repository.project_has_runs(project.id):
            raise ProjectHasRunsError(project.id)
        self.repository.delete_project(project)

    def create_run(self, project_id: str, device_source_id: str) -> TestRun:
        project = self.get_project(project_id)
        device = self.device_repository.get(device_source_id)
        if device is None:
            raise InvalidDeviceSourceError(device_source_id)

        results: list[dict[str, Any]] = []
        for selection in project.case_selections:
            test_case = self.case_repository.get(selection.case_source_id)
            if test_case is None or not test_case.enabled:
                raise InvalidCaseSourceError(selection.case_source_id)
            results.append(
                {
                    "case_source_id": test_case.id,
                    "case_snapshot": build_case_snapshot(test_case),
                }
            )

        return self.repository.create_run(
            project.id,
            device.id,
            build_device_snapshot(device),
            results,
        )

    def get_run(self, run_id: str) -> TestRun:
        run = self.repository.get_run(run_id)
        if run is None:
            raise TestRunNotFoundError(run_id)
        return run

    def list_runs(self, project_id: str) -> list[TestRun]:
        self.get_project(project_id)
        return self.repository.list_runs(project_id)

    def update_result(
        self,
        run_id: str,
        result_id: str,
        result: str,
    ) -> RunResult:
        if result not in {"PASS", "FAIL", "BLOCKED"}:
            raise InvalidResultValueError(result)
        run = self.get_run(run_id)
        run_result = next(
            (item for item in run.results if item.id == result_id),
            None,
        )
        if run_result is None:
            raise RunResultNotFoundError(result_id)
        complete_run = all(
            item.id == run_result.id or item.result is not None
            for item in run.results
        )
        return self.repository.update_result(
            run_result,
            result,
            self.clock(),
            complete_run=complete_run,
        )

    def _prepare_project(
        self,
        values: Mapping[str, Any],
    ) -> tuple[dict[str, Any], Sequence[str]]:
        project_values = dict(values)
        case_source_ids = list(dict.fromkeys(project_values.pop("case_source_ids")))
        if not case_source_ids:
            raise InvalidCaseSourceError("")
        for case_source_id in case_source_ids:
            test_case = self.case_repository.get(str(case_source_id))
            if test_case is None or not test_case.enabled:
                raise InvalidCaseSourceError(str(case_source_id))
        return project_values, case_source_ids
