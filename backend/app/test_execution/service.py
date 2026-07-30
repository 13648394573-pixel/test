from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.devices.repository import DeviceRepository
from app.environments.service import EnvironmentService
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


class InvalidResultIntegrityError(Exception):
    pass


class LockedResultError(Exception):
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
        environment_service: EnvironmentService | None = None,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.device_repository = device_repository
        self.case_repository = case_repository
        self.environment_service = environment_service
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

    def create_run(
        self,
        project_id: str,
        device_source_id: str,
        environment_profile_id: str,
    ) -> TestRun:
        project = self.get_project(project_id)
        device = self.device_repository.get(device_source_id)
        if device is None:
            raise InvalidDeviceSourceError(device_source_id)
        if self.environment_service is None:
            raise RuntimeError("Environment service is required for run creation")
        environment_profile = self.environment_service.get_enabled_profile(
            environment_profile_id
        )
        captured_at = self.clock()

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
            environment_profile_source_id=environment_profile.id,
            environment_snapshot=self.environment_service.build_snapshot(
                environment_profile,
                captured_at,
            ),
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
        values: Mapping[str, Any],
    ) -> RunResult:
        run, run_result = self._get_result(run_id, result_id)
        if run_result.integrity_status == "LOCKED":
            raise LockedResultError(result_id)
        result = values.get("result", run_result.result)
        if result is not None and result not in {"PASS", "FAIL", "BLOCKED"}:
            raise InvalidResultValueError(str(result))
        updates = {
            name: self._clean_optional_text(value)
            for name, value in values.items()
            if name in {
                "result",
                "actual_result",
                "blocked_reason",
                "test_notes",
            }
        }
        if "result" in values:
            updates["result"] = result
        return self.repository.update_result_draft(run_result, updates)

    def lock_result(self, run_id: str, result_id: str) -> RunResult:
        run, run_result = self._get_result(run_id, result_id)
        if run_result.integrity_status == "LOCKED":
            raise LockedResultError(result_id)
        if run_result.result is None:
            raise InvalidResultIntegrityError("result is required")
        if run_result.result == "FAIL" and not self._has_text(
            run_result.actual_result
        ):
            raise InvalidResultIntegrityError(
                "actual_result is required for FAIL"
            )
        if run_result.result == "BLOCKED" and not self._has_text(
            run_result.blocked_reason
        ):
            raise InvalidResultIntegrityError(
                "blocked_reason is required for BLOCKED"
            )
        if run_result.result == "PASS" and self._has_text(
            run_result.blocked_reason
        ):
            raise InvalidResultIntegrityError(
                "blocked_reason must be empty for PASS"
            )
        complete_run = all(
            item.id == run_result.id or item.integrity_status == "LOCKED"
            for item in run.results
        )
        return self.repository.lock_result(
            run_result,
            self.clock(),
            complete_run=complete_run,
        )

    def _get_result(
        self,
        run_id: str,
        result_id: str,
    ) -> tuple[TestRun, RunResult]:
        run = self.get_run(run_id)
        run_result = next(
            (item for item in run.results if item.id == result_id),
            None,
        )
        if run_result is None:
            raise RunResultNotFoundError(result_id)
        return run, run_result

    @staticmethod
    def _clean_optional_text(value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @staticmethod
    def _has_text(value: str | None) -> bool:
        return bool(value and value.strip())

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
