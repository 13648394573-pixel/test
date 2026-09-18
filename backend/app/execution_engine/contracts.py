from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from app.execution_engine.statuses import ActionPhase


type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(frozen=True)
class ObservationDTO:
    key: str
    value: JsonValue
    data_type: str
    unit: str | None
    observed_at: datetime
    action_ref: str


@dataclass(frozen=True)
class ActionRequestDTO:
    session_id: str
    action_execution_id: str
    idempotency_key: str
    plugin_code: str
    plugin_version: str
    plugin_sha256: str
    action_ref: str
    phase: ActionPhase
    device_context: Mapping[str, JsonValue]
    environment_context: Mapping[str, JsonValue]
    parameters: Mapping[str, JsonValue]
    credential_handles: Mapping[str, str]
    evidence_directory_handle: str
    timeout_seconds: int


@dataclass(frozen=True)
class ExecutionPlanDTO:
    run_id: str
    result_id: str
    skill_code: str
    skill_version: str
    standard_snapshot_hash: str
    device_snapshot: Mapping[str, JsonValue]
    environment_snapshot: Mapping[str, JsonValue]
    actions: tuple[ActionRequestDTO, ...]


@dataclass(frozen=True)
class RunnerEventDTO:
    session_id: str
    sequence_no: int
    idempotency_key: str
    event_type: str
    action_ref: str | None
    payload: Mapping[str, JsonValue]
    occurred_at: datetime
