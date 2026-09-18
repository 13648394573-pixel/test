from typing import Any

from pydantic import BaseModel


class CatalogInstallRead(BaseModel):
    skill_id: str
    created: bool
    definition_hash: str
    evidence_codes: tuple[str, ...]


class SkillSummaryRead(BaseModel):
    id: str
    skill_code: str
    version: str
    name: str
    status: str
    supported_olts: list[str]
    definition_hash: str


class SkillDetailRead(SkillSummaryRead):
    objective: str
    description: str | None
    parameters: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    evidence_rules: list[dict[str, Any]]
    standard: dict[str, Any] | None
    standard_profile: dict[str, Any] | None
    actions: list[dict[str, Any]]
    runner_statuses: list[str]

