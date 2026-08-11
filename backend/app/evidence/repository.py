from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.defect import Defect
from app.models.evidence import Evidence
from app.models.evidence_link import EvidenceRunResultLink
from app.models.test_execution import RunResult


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_result(self, result_id: str) -> RunResult | None:
        return self.session.get(RunResult, result_id)

    def get_run_results(self, result_ids: list[str]) -> list[RunResult]:
        if not result_ids:
            return []
        statement = select(RunResult).where(RunResult.id.in_(result_ids))
        by_id = {item.id: item for item in self.session.scalars(statement)}
        return [by_id[item] for item in result_ids if item in by_id]

    def get_defect(self, defect_id: str) -> Defect | None:
        return self.session.get(Defect, defect_id)

    def get(self, evidence_id: str) -> Evidence | None:
        statement = (
            select(Evidence)
            .options(
                selectinload(Evidence.result_links).selectinload(
                    EvidenceRunResultLink.run_result
                )
            )
            .where(Evidence.id == evidence_id)
        )
        return self.session.scalar(statement)

    def list_for_run_result(self, result_id: str) -> list[Evidence]:
        statement = (
            select(Evidence)
            .join(EvidenceRunResultLink)
            .options(selectinload(Evidence.result_links))
            .where(EvidenceRunResultLink.run_result_id == result_id)
            .order_by(Evidence.created_at, Evidence.id)
        )
        return list(self.session.scalars(statement).unique())

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
            self.session.flush()
            if evidence.run_result_id:
                evidence.result_links.append(
                    EvidenceRunResultLink(
                        run_result_id=evidence.run_result_id
                    )
                )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(evidence)
        loaded = self.get(evidence.id)
        if loaded is None:
            raise RuntimeError("Persisted evidence could not be reloaded")
        return loaded

    def create_batch(
        self,
        values_list: list[Mapping[str, Any]],
        result_ids: list[str],
    ) -> list[Evidence]:
        evidences = [Evidence(**dict(values)) for values in values_list]
        try:
            self.session.add_all(evidences)
            self.session.flush()
            for evidence in evidences:
                evidence.result_links = [
                    EvidenceRunResultLink(run_result_id=result_id)
                    for result_id in result_ids
                ]
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        loaded = [self.get(evidence.id) for evidence in evidences]
        if any(item is None for item in loaded):
            raise RuntimeError("Persisted evidence batch could not be reloaded")
        return [item for item in loaded if item is not None]

    def delete(self, evidence: Evidence) -> None:
        try:
            self.session.delete(evidence)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
