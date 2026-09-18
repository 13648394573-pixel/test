from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from app.local_runner.credentials import SecretValue


@dataclass(frozen=True)
class ActionContext:
    session_id: str
    action_code: str
    parameters: Mapping[str, Any]
    secrets: Mapping[str, SecretValue] = field(default_factory=dict)
    workspace: Path | None = None


@dataclass(frozen=True)
class Observation:
    fact_key: str
    value: Any
    source: str
    detail: str | None = None


@dataclass(frozen=True)
class ArtifactPayload:
    original_name: str
    media_type: str
    storage_path: str | None = None
    content: bytes | None = None
    file_size: int | None = None
    sha256: str | None = None
    redacted: bool = False


@dataclass(frozen=True)
class ActionOutcome:
    status: Literal["PASS", "FAIL", "BLOCKED", "ERROR", "WAITING_OPERATOR"]
    observations: tuple[Observation, ...]
    artifacts: tuple[ArtifactPayload, ...]
    error_code: str | None = None
    detail: str | None = None


class ActionHandler(Protocol):
    def execute(self, context: ActionContext) -> ActionOutcome: ...

