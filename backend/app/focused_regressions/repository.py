from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.environment import RunEnvironmentSnapshot
from app.models.focused_regression import FocusedRegressionRun
from app.models.test_execution import RunResult, TestRun
from app.test_execution.run_numbers import (
    RunNumberConflictError,
    is_run_number_conflict,
    next_run_no,
)


class FocusedRegressionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        *,
        project_id: str,
        device_source_id: str,
        device_snapshot: Mapping[str, Any],
        environment_profile_source_id: str,
        environment_snapshot: Mapping[str, Any],
        case_source_id: str,
        case_snapshot: Mapping[str, Any],
        defect_id: str,
        source_run_result_id: str,
        defect_snapshot: Mapping[str, Any],
    ) -> FocusedRegressionRun:
        run = TestRun(
            run_no=next_run_no(self.session),
            project_id=project_id,
            device_source_id=device_source_id,
            device_snapshot=dict(device_snapshot),
            snapshot_version=1,
        )
        run.results = [
            RunResult(
                case_source_id=case_source_id,
                case_snapshot=dict(case_snapshot),
                snapshot_version=1,
            )
        ]
        run.environment_snapshot = RunEnvironmentSnapshot(
            environment_profile_source_id=environment_profile_source_id,
            profile_snapshot=dict(environment_snapshot),
            snapshot_version=1,
        )
        focused = FocusedRegressionRun(
            defect_id=defect_id,
            source_run_result_id=source_run_result_id,
            defect_snapshot=dict(defect_snapshot),
            snapshot_version=1,
        )
        focused.test_run = run
        self.session.add(focused)
        try:
            self.session.commit()
        except IntegrityError as exception:
            self.session.rollback()
            if is_run_number_conflict(exception):
                raise RunNumberConflictError(
                    "Run number allocation conflict"
                ) from exception
            raise
        except (SQLAlchemyError, ValueError):
            self.session.rollback()
            raise
        return self._reload(focused)

    def get_by_run_id(self, run_id: str) -> FocusedRegressionRun | None:
        statement = self._statement().where(
            FocusedRegressionRun.test_run_id == run_id
        )
        return self.session.scalar(statement)

    def list_for_defect(self, defect_id: str) -> list[FocusedRegressionRun]:
        statement = (
            self._statement()
            .where(FocusedRegressionRun.defect_id == defect_id)
            .order_by(FocusedRegressionRun.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_active_for_defect(
        self,
        defect_id: str,
    ) -> FocusedRegressionRun | None:
        statement = (
            self._statement()
            .join(FocusedRegressionRun.test_run)
            .where(
                FocusedRegressionRun.defect_id == defect_id,
                TestRun.status == "IN_PROGRESS",
            )
            .order_by(FocusedRegressionRun.created_at.desc())
        )
        return self.session.scalar(statement)

    @staticmethod
    def _statement():
        return select(FocusedRegressionRun).options(
            selectinload(FocusedRegressionRun.test_run).selectinload(
                TestRun.results
            ),
            selectinload(FocusedRegressionRun.test_run).selectinload(
                TestRun.environment_snapshot
            ),
            selectinload(FocusedRegressionRun.source_run_result),
        )

    def _reload(self, focused: FocusedRegressionRun) -> FocusedRegressionRun:
        loaded = self.get_by_run_id(focused.test_run_id)
        if loaded is None:
            raise RuntimeError("Persisted focused regression run could not be reloaded")
        return loaded
