from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.defects.repository import DefectRepository
from app.models.defect import Defect, Regression


class DefectNotFoundError(Exception):
    pass


class RunResultEvidenceNotFoundError(Exception):
    pass


class InvalidDefectSourceError(Exception):
    pass


class DuplicateDefectSourceError(Exception):
    pass


class InvalidDefectTransitionError(Exception):
    pass


class ClosedDefectError(Exception):
    pass


class InvalidRegressionEvidenceError(Exception):
    pass


class DuplicateRegressionError(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DefectService:
    def __init__(
        self,
        repository: DefectRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.clock = clock

    def list_defects(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[Defect]:
        return self.repository.list_defects(status=status, severity=severity)

    def get_defect(self, defect_id: str) -> Defect:
        defect = self.repository.get_defect(defect_id)
        if defect is None:
            raise DefectNotFoundError(defect_id)
        return defect

    def create_defect(self, values: Mapping[str, Any]) -> Defect:
        defect_values = dict(values)
        source_id = str(defect_values["source_run_result_id"])
        source = self.repository.get_run_result(source_id)
        if source is None:
            raise RunResultEvidenceNotFoundError(source_id)
        if source.result not in {"FAIL", "BLOCKED"} or source.executed_at is None:
            raise InvalidDefectSourceError(source_id)
        if self.repository.source_has_defect(source_id):
            raise DuplicateDefectSourceError(source_id)

        defect_values.update(
            defect_code=self.repository.next_defect_code(),
            status="OPEN",
        )
        return self.repository.create_defect(defect_values)

    def update_defect(
        self,
        defect_id: str,
        values: Mapping[str, Any],
    ) -> Defect:
        defect = self.get_defect(defect_id)
        if defect.status == "CLOSED":
            raise ClosedDefectError(defect_id)
        return self.repository.update_defect(defect, values)

    def transition(
        self,
        defect_id: str,
        target_status: str,
        resolution_notes: str | None = None,
    ) -> Defect:
        defect = self.get_defect(defect_id)
        allowed = {
            "OPEN": "IN_PROGRESS",
            "IN_PROGRESS": "RESOLVED",
            "REOPENED": "IN_PROGRESS",
        }
        if allowed.get(defect.status) != target_status:
            raise InvalidDefectTransitionError(
                f"{defect.status}->{target_status}"
            )

        updates: dict[str, Any] = {"status": target_status}
        if target_status == "RESOLVED":
            notes = (resolution_notes or "").strip()
            if not notes:
                raise InvalidDefectTransitionError("resolution notes required")
            updates.update(
                resolution_notes=notes,
                resolved_at=self.clock(),
                closed_at=None,
            )
        elif defect.status == "REOPENED":
            updates.update(
                resolution_notes=None,
                resolved_at=None,
                closed_at=None,
            )
        return self.repository.update_defect(defect, updates)

    def list_regressions(self, defect_id: str) -> list[Regression]:
        return list(self.get_defect(defect_id).regressions)

    def create_regression(
        self,
        defect_id: str,
        verification_run_result_id: str,
        notes: str | None,
    ) -> Regression:
        defect = self.get_defect(defect_id)
        if defect.status != "RESOLVED":
            raise InvalidDefectTransitionError(
                f"{defect.status}->REGRESSION"
            )
        verification = self.repository.get_run_result(
            verification_run_result_id
        )
        if verification is None:
            raise RunResultEvidenceNotFoundError(
                verification_run_result_id
            )
        if (
            verification.executed_at is None
            or verification.result not in {"PASS", "FAIL", "BLOCKED"}
            or verification.case_source_id
            != defect.source_run_result.case_source_id
            or verification.id == defect.source_run_result_id
        ):
            raise InvalidRegressionEvidenceError(
                verification_run_result_id
            )
        if self.repository.regression_exists(
            defect.id,
            verification_run_result_id,
        ):
            raise DuplicateRegressionError(verification_run_result_id)

        defect_updates: dict[str, Any] = {}
        if verification.result == "PASS":
            defect_updates = {
                "status": "CLOSED",
                "closed_at": self.clock(),
            }
        elif verification.result == "FAIL":
            defect_updates = {
                "status": "REOPENED",
                "resolved_at": None,
                "closed_at": None,
            }

        return self.repository.create_regression(
            defect,
            {
                "verification_run_result_id": verification.id,
                "result": verification.result,
                "notes": notes.strip() if notes and notes.strip() else None,
                "executed_at": verification.executed_at,
            },
            defect_updates,
        )
