from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.environments.repository import EnvironmentRepository
from app.environments.snapshots import build_environment_snapshot
from app.models.environment import EnvironmentProfile


class EnvironmentProfileNotFoundError(Exception):
    pass


class DuplicateEnvironmentProfileError(Exception):
    pass


class DuplicateEnvironmentParameterError(Exception):
    pass


class InvalidEnvironmentProfileError(Exception):
    pass


class EnvironmentService:
    def __init__(self, repository: EnvironmentRepository) -> None:
        self.repository = repository

    def list_profiles(self) -> list[EnvironmentProfile]:
        return self.repository.list()

    def get_profile(self, profile_id: str) -> EnvironmentProfile:
        profile = self.repository.get(profile_id)
        if profile is None:
            raise EnvironmentProfileNotFoundError(profile_id)
        return profile

    def create_profile(self, values: Mapping[str, Any]) -> EnvironmentProfile:
        profile_values, parameters = self._prepare(values)
        if self.repository.get_by_name(profile_values["name"]) is not None:
            raise DuplicateEnvironmentProfileError(profile_values["name"])
        return self.repository.create(profile_values, parameters)

    def update_profile(
        self,
        profile_id: str,
        values: Mapping[str, Any],
    ) -> EnvironmentProfile:
        profile = self.get_profile(profile_id)
        profile_values, parameters = self._prepare(values)
        duplicate = self.repository.get_by_name(profile_values["name"])
        if duplicate is not None and duplicate.id != profile.id:
            raise DuplicateEnvironmentProfileError(profile_values["name"])
        return self.repository.update(profile, profile_values, parameters)

    def delete_profile(self, profile_id: str) -> None:
        self.repository.delete(self.get_profile(profile_id))

    def get_enabled_profile(self, profile_id: str) -> EnvironmentProfile:
        profile = self.repository.get(profile_id)
        if profile is None or not profile.enabled:
            raise InvalidEnvironmentProfileError(profile_id)
        return profile

    def build_snapshot(
        self,
        profile: EnvironmentProfile,
        captured_at: datetime,
    ) -> dict[str, Any]:
        return build_environment_snapshot(profile, captured_at)

    @staticmethod
    def _prepare(
        values: Mapping[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        profile_values = dict(values)
        parameters = [dict(item) for item in profile_values.pop("parameters")]
        keys = [item["param_key"] for item in parameters]
        if len(set(keys)) != len(keys):
            raise DuplicateEnvironmentParameterError()
        return profile_values, parameters
