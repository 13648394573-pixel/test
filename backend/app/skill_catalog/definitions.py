from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParameterDefinition:
    key: str
    label: str
    data_type: str
    source: str
    required: bool
    default: Any | None
    constraints: dict[str, Any]
    sensitive: bool = False
    description: str | None = None


@dataclass(frozen=True)
class StepDefinition:
    code: str
    title: str
    action: str
    expected_observation: str
    execution_mode: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequirementDefinition:
    code: str
    title: str
    description: str
    fact_key: str
    data_type: str = "BOOLEAN"
    operator: str = "EQ"
    expected: Any = True


@dataclass(frozen=True)
class EvidenceDefinition:
    code: str
    title: str
    description: str
    sensitive_content: str
    capture_methods: tuple[str, ...]
    required_for: tuple[str, ...] = ("PASS", "FAIL", "BLOCKED")
    min_count: int = 1
    max_count: int | None = None


@dataclass(frozen=True)
class ActionDefinition:
    code: str
    phase: str
    step_code: str | None
    timeout_seconds: int
    idempotent: bool
    recovery_capability: str
    observation_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogDefinition:
    skill_code: str
    version: str
    status: str
    name: str
    objective: str
    description: str
    standard_code: str
    standard_version: str
    standard_profile_code: str
    test_case_code: str
    template_code: str
    supported_olts: tuple[str, ...]
    parameters: tuple[ParameterDefinition, ...]
    steps: tuple[StepDefinition, ...]
    requirements: tuple[RequirementDefinition, ...]
    evidence: tuple[EvidenceDefinition, ...]
    actions: tuple[ActionDefinition, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

