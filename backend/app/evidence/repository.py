from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.defect import Defect
from app.models.evidence import Evidence
from app.models.test_execution import RunResult


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_result(self, result_id: str) -> RunResult | None:
        return self.session.get(RunResult, result_id)

    def get_defect(self, defect_id: str) -> Defect | None:
        return self.session.get(Defect, defect_id)

    def get(self, evidence_id: str) -> Evidence | None:
        return self.session.get(Evidence, evidence_id)

    def list_for_run_result(self, result_id: str) -> list[Evidence]:
        statement = (
            select(Evidence)
            .where(Evidence.run_result_id == result_id)
            .order_by(Evidence.created_at, Evidence.id)
        )
        return list(self.session.scalars(statement))

    def list_for_defect(self, defect_id: str) -> list[Evidence]:
        statement = (
            select(Evidence)
            .where(Evidence.defect_id == defect_id)
            .order_by(Evidence.created_at, Evidence.id)
        )
        return list(self.session.scalars(statement))

    def create(self, values: Mapping[str, Any]) -> Evidence:
        evidence = Evidence(**dict(values))
        self.session.add(evidence)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(evidence)
        return evidence

    def delete(self, evidence: Evidence) -> None:
        try:
            self.session.delete(evidence)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
