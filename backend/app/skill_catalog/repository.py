from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.runner_registry import RunnerPlugin
from app.models.test_intelligence import TestSkill
from app.models.test_standard import StandardProfile


class SkillCatalogRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_skill(self, skill_code: str, version: str) -> TestSkill | None:
        return self.session.scalar(
            select(TestSkill).where(
                TestSkill.skill_code == skill_code,
                TestSkill.version == version,
            )
        )

    def get_skill(self, skill_id: str) -> TestSkill | None:
        return self.session.get(TestSkill, skill_id)

    def list_skills(self) -> list[TestSkill]:
        return list(
            self.session.scalars(
                select(TestSkill).order_by(TestSkill.skill_code, TestSkill.version)
            )
        )

    def get_profile(self, profile_code: str) -> StandardProfile | None:
        return self.session.scalar(
            select(StandardProfile).where(StandardProfile.profile_code == profile_code)
        )

    def get_runner_plugin(self, plugin_code: str, version: str) -> RunnerPlugin | None:
        return self.session.scalar(
            select(RunnerPlugin).where(
                RunnerPlugin.plugin_code == plugin_code,
                RunnerPlugin.version == version,
            )
        )

    def add(self, value: object) -> None:
        self.session.add(value)

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

