from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.test_execution import (
    ProjectCaseSelection,
    RunResult,
    TestProject,
    TestRun,
)


class TestExecutionRepository:
    __test__ = False

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_projects(self) -> list[TestProject]:
        statement = (
            select(TestProject)
            .options(selectinload(TestProject.case_selections))
            .order_by(TestProject.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_project(self, project_id: str) -> TestProject | None:
        statement = (
            select(TestProject)
            .options(selectinload(TestProject.case_selections))
            .where(TestProject.id == project_id)
        )
        return self.session.scalar(statement)

    def create_project(
        self,
        values: Mapping[str, Any],
        case_source_ids: Sequence[str],
    ) -> TestProject:
        project = TestProject(**values)
        project.case_selections = [
            ProjectCaseSelection(case_source_id=case_source_id)
            for case_source_id in sorted(set(case_source_ids))
        ]
        self.session.add(project)
        return self._commit_and_reload_project(project)

    def update_project(
        self,
        project: TestProject,
        values: Mapping[str, Any],
        case_source_ids: Sequence[str],
    ) -> TestProject:
        try:
            for field, value in values.items():
                setattr(project, field, value)
            project.case_selections.clear()
            self.session.flush()
            project.case_selections = [
                ProjectCaseSelection(case_source_id=case_source_id)
                for case_source_id in sorted(set(case_source_ids))
            ]
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload_project(project)

    def delete_project(self, project: TestProject) -> None:
        try:
            self.session.delete(project)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def project_has_runs(self, project_id: str) -> bool:
        statement = (
            select(func.count())
            .select_from(TestRun)
            .where(TestRun.project_id == project_id)
        )
        return bool(self.session.scalar(statement))

    def create_run(
        self,
        project_id: str,
        device_source_id: str,
        device_snapshot: Mapping[str, Any],
        results: Sequence[Mapping[str, Any]],
    ) -> TestRun:
        run = TestRun(
            project_id=project_id,
            device_source_id=device_source_id,
            device_snapshot=dict(device_snapshot),
            snapshot_version=1,
        )
        run.results = [
            RunResult(
                case_source_id=str(result["case_source_id"]),
                case_snapshot=dict(result["case_snapshot"]),
                snapshot_version=1,
            )
            for result in results
        ]
        self.session.add(run)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload_run(run)

    def get_run(self, run_id: str) -> TestRun | None:
        statement = (
            select(TestRun)
            .options(selectinload(TestRun.results))
            .where(TestRun.id == run_id)
        )
        return self.session.scalar(statement)

    def list_runs(self, project_id: str) -> list[TestRun]:
        statement = (
            select(TestRun)
            .options(selectinload(TestRun.results))
            .where(TestRun.project_id == project_id)
            .order_by(TestRun.started_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_result(self, run_id: str, result_id: str) -> RunResult | None:
        statement = select(RunResult).where(
            RunResult.id == result_id,
            RunResult.run_id == run_id,
        )
        return self.session.scalar(statement)

    def update_result_draft(
        self,
        run_result: RunResult,
        values: Mapping[str, Any],
    ) -> RunResult:
        try:
            for field, value in values.items():
                setattr(run_result, field, value)
            self.session.commit()
            self.session.refresh(run_result)
        except (SQLAlchemyError, ValueError):
            self.session.rollback()
            raise
        return run_result

    def lock_result(
        self,
        run_result: RunResult,
        locked_at: datetime,
        *,
        complete_run: bool,
    ) -> RunResult:
        try:
            run_result.executed_at = locked_at
            run_result.locked_at = locked_at
            run_result.integrity_status = "LOCKED"
            if complete_run:
                run_result.run.status = "COMPLETED"
                run_result.run.finished_at = locked_at
            else:
                run_result.run.status = "IN_PROGRESS"
                run_result.run.finished_at = None
            self.session.commit()
            self.session.refresh(run_result)
        except (SQLAlchemyError, ValueError):
            self.session.rollback()
            raise
        return run_result

    def _commit_and_reload_project(self, project: TestProject) -> TestProject:
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload_project(project)

    def _reload_project(self, project: TestProject) -> TestProject:
        loaded = self.get_project(project.id)
        if loaded is None:
            raise RuntimeError("Persisted test project could not be reloaded")
        return loaded

    def _reload_run(self, run: TestRun) -> TestRun:
        loaded = self.get_run(run.id)
        if loaded is None:
            raise RuntimeError("Persisted test run could not be reloaded")
        return loaded
