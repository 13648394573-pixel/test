from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.defect import Defect, Regression
from app.models.test_execution import RunResult


class DefectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_defects(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[Defect]:
        statement = self._defect_statement()
        if status is not None:
            statement = statement.where(Defect.status == status)
        if severity is not None:
            statement = statement.where(Defect.severity == severity)
        statement = statement.order_by(Defect.created_at.desc(), Defect.defect_code)
        return list(self.session.scalars(statement).unique())

    def get_defect(self, defect_id: str) -> Defect | None:
        statement = self._defect_statement().where(Defect.id == defect_id)
        return self.session.scalars(statement).unique().one_or_none()

    def get_run_result(self, result_id: str) -> RunResult | None:
        return self.session.get(RunResult, result_id)

    def source_has_defect(self, result_id: str) -> bool:
        statement = select(Defect.id).where(
            Defect.source_run_result_id == result_id
        )
        return self.session.scalar(statement) is not None

    def regression_exists(
        self,
        defect_id: str,
        verification_result_id: str,
    ) -> bool:
        statement = select(Regression.id).where(
            Regression.defect_id == defect_id,
            Regression.verification_run_result_id == verification_result_id,
        )
        return self.session.scalar(statement) is not None

    def next_defect_code(self) -> str:
        codes = self.session.scalars(select(Defect.defect_code)).all()
        numbers = [
            int(code.removeprefix("DEF-"))
            for code in codes
            if code.startswith("DEF-") and code.removeprefix("DEF-").isdigit()
        ]
        return f"DEF-{max(numbers, default=0) + 1:06d}"

    def create_defect(self, values: Mapping[str, Any]) -> Defect:
        defect = Defect(**dict(values))
        self.session.add(defect)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(defect)
        return defect

    def update_defect(
        self,
        defect: Defect,
        values: Mapping[str, Any],
    ) -> Defect:
        for name, value in values.items():
            setattr(defect, name, value)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(defect)
        return defect

    def create_regression(
        self,
        defect: Defect,
        values: Mapping[str, Any],
        defect_updates: Mapping[str, Any],
    ) -> Regression:
        regression = Regression(defect=defect, **dict(values))
        for name, value in defect_updates.items():
            setattr(defect, name, value)
        self.session.add(regression)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(regression)
        return regression

    @staticmethod
    def _defect_statement():
        return select(Defect).options(
            selectinload(Defect.source_run_result).selectinload(RunResult.run),
            selectinload(Defect.regressions).selectinload(
                Regression.verification_run_result
            ),
        )
