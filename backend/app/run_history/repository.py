from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.test_execution import RunResult, TestProject, TestRun
from app.models.evidence_link import EvidenceRunResultLink
from app.run_history.schemas import RunHistoryFilters


class RunHistoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self, filters: RunHistoryFilters
    ) -> tuple[list[TestRun], int]:
        predicates = self._predicates(filters)
        base = select(TestRun.id).join(TestProject).where(*predicates)
        total = int(
            self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        statement = (
            select(TestRun)
            .join(TestProject)
            .options(
                selectinload(TestRun.project),
                selectinload(TestRun.results),
                selectinload(TestRun.environment_snapshot),
            )
            .where(*predicates)
            .order_by(TestRun.started_at.desc(), TestRun.id.desc())
            .limit(filters.limit)
            .offset(filters.offset)
        )
        return list(self.session.scalars(statement).unique()), total

    def get_runs(self, run_ids: list[str]) -> list[TestRun]:
        statement = (
            select(TestRun)
            .options(
                selectinload(TestRun.project),
                selectinload(TestRun.results),
                selectinload(TestRun.environment_snapshot),
            )
            .where(TestRun.id.in_(run_ids))
        )
        by_id = {run.id: run for run in self.session.scalars(statement).unique()}
        return [by_id[run_id] for run_id in run_ids if run_id in by_id]

    def evidence_counts(self, result_ids: list[str]) -> dict[str, int]:
        if not result_ids:
            return {}
        statement = (
            select(
                EvidenceRunResultLink.run_result_id,
                func.count(EvidenceRunResultLink.evidence_id),
            )
            .where(EvidenceRunResultLink.run_result_id.in_(result_ids))
            .group_by(EvidenceRunResultLink.run_result_id)
        )
        return {
            str(result_id): int(count)
            for result_id, count in self.session.execute(statement)
        }

    @staticmethod
    def _predicates(filters: RunHistoryFilters) -> list:
        predicates = []
        if filters.project_id:
            predicates.append(TestRun.project_id == filters.project_id)
        if filters.run_no:
            predicates.append(
                func.lower(TestRun.run_no).like(
                    f"{filters.run_no.strip().lower()}%"
                )
            )
        if filters.project_version:
            predicates.append(TestProject.version == filters.project_version)
        for field, value in (
            ("device_type", filters.device_type),
            ("vendor", filters.vendor),
            ("model", filters.model),
            ("serial_number", filters.serial_number),
            ("software_version", filters.software_version),
        ):
            if value:
                extracted = func.lower(
                    func.json_extract(
                        TestRun.device_snapshot, f"$.{field}"
                    )
                )
                if field == "device_type":
                    predicates.append(extracted == value.strip().lower())
                else:
                    predicates.append(
                        extracted.like(f"%{value.strip().lower()}%")
                    )
        if filters.status:
            predicates.append(TestRun.status == filters.status)
        if filters.result:
            result_value = None if filters.result == "UNSET" else filters.result
            predicates.append(
                TestRun.results.any(RunResult.result == result_value)
            )
        if filters.started_from:
            predicates.append(TestRun.started_at >= filters.started_from)
        if filters.started_to:
            predicates.append(TestRun.started_at <= filters.started_to)
        return predicates
