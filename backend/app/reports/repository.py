from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.defect import Defect
from app.models.evidence import Evidence
from app.models.report import Archive, Report
from app.models.test_execution import RunResult, TestRun


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_graph(self, run_id: str) -> TestRun | None:
        statement = (
            select(TestRun)
            .options(
                selectinload(TestRun.project),
                selectinload(TestRun.results),
                selectinload(TestRun.environment_snapshot),
            )
            .where(TestRun.id == run_id)
        )
        return self.session.scalar(statement)

    def list_evidence(
        self,
        result_ids: Sequence[str],
        defect_ids: Sequence[str],
    ) -> list[Evidence]:
        if not result_ids and not defect_ids:
            return []
        predicates = []
        if result_ids:
            predicates.append(Evidence.run_result_id.in_(result_ids))
        if defect_ids:
            predicates.append(Evidence.defect_id.in_(defect_ids))
        statement = (
            select(Evidence)
            .where(or_(*predicates))
            .order_by(Evidence.created_at, Evidence.id)
        )
        return list(self.session.scalars(statement))

    def list_defects(self, result_ids: Sequence[str]) -> list[Defect]:
        if not result_ids:
            return []
        statement = (
            select(Defect)
            .options(selectinload(Defect.regressions))
            .where(Defect.source_run_result_id.in_(result_ids))
            .order_by(Defect.defect_code)
        )
        return list(self.session.scalars(statement).unique())

    def next_report_version(self, run_id: str) -> int:
        statement = select(func.max(Report.report_version)).where(
            Report.test_run_id == run_id
        )
        return int(self.session.scalar(statement) or 0) + 1

    def next_report_no(self) -> str:
        return self._next_code(Report.report_no, "RPT-")

    def next_archive_no(self) -> str:
        return self._next_code(Archive.archive_no, "ARC-")

    def create_report(self, values: Mapping[str, Any]) -> Report:
        report = Report(**dict(values))
        self.session.add(report)
        return self._commit_and_refresh(report)

    def get_report(self, report_id: str) -> Report | None:
        statement = (
            select(Report)
            .options(selectinload(Report.archive))
            .where(Report.id == report_id)
        )
        return self.session.scalar(statement)

    def list_for_run(self, run_id: str) -> list[Report]:
        statement = (
            select(Report)
            .options(selectinload(Report.archive))
            .where(Report.test_run_id == run_id)
            .order_by(Report.report_version.desc())
        )
        return list(self.session.scalars(statement))

    def list_for_project(self, project_id: str) -> list[Report]:
        statement = (
            select(Report)
            .options(selectinload(Report.archive))
            .where(Report.project_id == project_id)
            .order_by(Report.generated_at.desc())
        )
        return list(self.session.scalars(statement))

    def create_archive(self, values: Mapping[str, Any]) -> Archive:
        archive = Archive(**dict(values))
        self.session.add(archive)
        return self._commit_and_refresh(archive)

    def get_archive(self, archive_id: str) -> Archive | None:
        return self.session.get(Archive, archive_id)

    def get_archive_for_report(self, report_id: str) -> Archive | None:
        statement = select(Archive).where(Archive.report_id == report_id)
        return self.session.scalar(statement)

    def _commit_and_refresh(self, entity):
        try:
            self.session.commit()
            self.session.refresh(entity)
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return entity

    def _next_code(self, column, prefix: str) -> str:
        values = self.session.scalars(select(column)).all()
        numbers = [
            int(value.removeprefix(prefix))
            for value in values
            if value.startswith(prefix)
            and value.removeprefix(prefix).isdigit()
        ]
        return f"{prefix}{max(numbers, default=0) + 1:06d}"
