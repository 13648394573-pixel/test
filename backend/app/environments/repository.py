from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.environment import EnvironmentParameter, EnvironmentProfile


class EnvironmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[EnvironmentProfile]:
        statement = (
            select(EnvironmentProfile)
            .options(selectinload(EnvironmentProfile.parameters))
            .order_by(EnvironmentProfile.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get(self, profile_id: str) -> EnvironmentProfile | None:
        statement = (
            select(EnvironmentProfile)
            .options(selectinload(EnvironmentProfile.parameters))
            .where(EnvironmentProfile.id == profile_id)
        )
        return self.session.scalar(statement)

    def get_by_name(self, name: str) -> EnvironmentProfile | None:
        statement = (
            select(EnvironmentProfile)
            .options(selectinload(EnvironmentProfile.parameters))
            .where(EnvironmentProfile.name == name)
        )
        return self.session.scalar(statement)

    def create(
        self,
        values: Mapping[str, Any],
        parameters: Sequence[Mapping[str, Any]],
    ) -> EnvironmentProfile:
        profile = EnvironmentProfile(**values)
        profile.parameters = [
            EnvironmentParameter(**dict(parameter)) for parameter in parameters
        ]
        self.session.add(profile)
        return self._commit_and_reload(profile)

    def update(
        self,
        profile: EnvironmentProfile,
        values: Mapping[str, Any],
        parameters: Sequence[Mapping[str, Any]],
    ) -> EnvironmentProfile:
        try:
            for field, value in values.items():
                setattr(profile, field, value)
            profile.parameters.clear()
            self.session.flush()
            profile.parameters = [
                EnvironmentParameter(**dict(parameter))
                for parameter in parameters
            ]
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload(profile.id)

    def delete(self, profile: EnvironmentProfile) -> None:
        try:
            self.session.delete(profile)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def _commit_and_reload(
        self,
        profile: EnvironmentProfile,
    ) -> EnvironmentProfile:
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return self._reload(profile.id)

    def _reload(self, profile_id: str) -> EnvironmentProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise RuntimeError("Persisted environment profile could not be reloaded")
        return profile
