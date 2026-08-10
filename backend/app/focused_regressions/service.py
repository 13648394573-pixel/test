from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime

from app.defects.repository import DefectRepository
from app.devices.repository import DeviceRepository
from app.environments.service import EnvironmentService
from app.focused_regressions.repository import FocusedRegressionRepository
from app.focused_regressions.snapshots import build_defect_snapshot
from app.models.focused_regression import FocusedRegressionRun
from app.models.test_execution import RunResult
from app.test_execution.service import InvalidDeviceSourceError
from app.test_execution.snapshots import build_device_snapshot


class FocusedDefectNotFoundError(Exception):
    pass


class FocusedRegressionNotFoundError(Exception):
    pass


class InvalidFocusedRegressionStateError(Exception):
    pass


class InvalidFocusedRegressionSourceError(Exception):
    pass


class ActiveFocusedRegressionExistsError(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FocusedRegressionService:
    def __init__(
        self,
        repository: FocusedRegressionRepository,
        defect_repository: DefectRepository,
        device_repository: DeviceRepository,
        environment_service: EnvironmentService,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.defect_repository = defect_repository
        self.device_repository = device_repository
        self.environment_service = environment_service
        self.clock = clock

    def create_run(
        self,
        defect_id: str,
        device_source_id: str,
        environment_profile_id: str,
        source_run_result_id: str | None = None,
    ) -> FocusedRegressionRun:
        defect = self.defect_repository.get_defect(defect_id)
        if defect is None:
            raise FocusedDefectNotFoundError(defect_id)
        if defect.status != "RESOLVED":
            raise InvalidFocusedRegressionStateError(defect.status)
        if self.repository.get_active_for_defect(defect.id) is not None:
            raise ActiveFocusedRegressionExistsError(defect.id)

        selected_source_id = source_run_result_id or defect.source_run_result_id
        source = self._resolve_source(defect, selected_source_id)
        device = self.device_repository.get(device_source_id)
        if device is None:
            raise InvalidDeviceSourceError(device_source_id)
        profile = self.environment_service.get_enabled_profile(
            environment_profile_id
        )
        captured_at = self.clock()

        return self.repository.create_run(
            project_id=source.run.project_id,
            device_source_id=device.id,
            device_snapshot=build_device_snapshot(device),
            environment_profile_source_id=profile.id,
            environment_snapshot=self.environment_service.build_snapshot(
                profile,
                captured_at,
            ),
            case_source_id=source.case_source_id,
            case_snapshot=deepcopy(source.case_snapshot),
            defect_id=defect.id,
            source_run_result_id=source.id,
            defect_snapshot=build_defect_snapshot(
                defect,
                source.id,
                captured_at,
            ),
        )

    def list_for_defect(
        self,
        defect_id: str,
    ) -> list[FocusedRegressionRun]:
        if self.defect_repository.get_defect(defect_id) is None:
            raise FocusedDefectNotFoundError(defect_id)
        return self.repository.list_for_defect(defect_id)

    def get_run(self, run_id: str) -> FocusedRegressionRun:
        focused = self.repository.get_by_run_id(run_id)
        if focused is None:
            raise FocusedRegressionNotFoundError(run_id)
        return focused

    def _resolve_source(self, defect, source_id: str) -> RunResult:
        allowed_source_ids = {defect.source_run_result_id}
        allowed_source_ids.update(
            regression.verification_run_result_id
            for regression in defect.regressions
            if regression.result in {"FAIL", "BLOCKED"}
        )
        if source_id not in allowed_source_ids:
            raise InvalidFocusedRegressionSourceError(source_id)

        source = self.defect_repository.get_run_result(source_id)
        if (
            source is None
            or source.integrity_status != "LOCKED"
            or source.executed_at is None
            or source.result not in {"FAIL", "BLOCKED"}
        ):
            raise InvalidFocusedRegressionSourceError(source_id)
        return source
