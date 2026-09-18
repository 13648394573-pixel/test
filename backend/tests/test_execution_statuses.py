from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.execution_engine import (
    ActionPhase,
    ActionRequestDTO,
    ExecutionMode,
    ExecutionPlanDTO,
    ExecutionStatus,
    FunctionalVerdict,
    InvalidExecutionTransition,
    ObservationDTO,
    RecoveryStatus,
    RunnerEventDTO,
    can_finalize,
    validate_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ExecutionStatus.CREATED, ExecutionStatus.PREFLIGHT),
        (ExecutionStatus.PREFLIGHT, ExecutionStatus.RUNNING),
        (ExecutionStatus.RUNNING, ExecutionStatus.WAITING_OPERATOR),
        (ExecutionStatus.WAITING_OPERATOR, ExecutionStatus.RUNNING),
        (ExecutionStatus.RUNNING, ExecutionStatus.EVALUATING),
        (ExecutionStatus.EVALUATING, ExecutionStatus.RESTORING),
        (ExecutionStatus.RESTORING, ExecutionStatus.COMPLETED),
        (ExecutionStatus.RECOVERY_REQUIRED, ExecutionStatus.RESTORING),
    ],
)
def test_valid_execution_transitions(current, target) -> None:
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ExecutionStatus.CREATED, ExecutionStatus.COMPLETED),
        (ExecutionStatus.ERROR, ExecutionStatus.COMPLETED),
        (ExecutionStatus.RECOVERY_REQUIRED, ExecutionStatus.COMPLETED),
        (ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING),
    ],
)
def test_invalid_execution_transitions_are_rejected(current, target) -> None:
    with pytest.raises(InvalidExecutionTransition):
        validate_transition(current, target)


@pytest.mark.parametrize(
    ("status", "recovery_status", "expected"),
    [
        (ExecutionStatus.COMPLETED, RecoveryStatus.NOT_REQUIRED, True),
        (ExecutionStatus.COMPLETED, RecoveryStatus.VERIFIED, True),
        (ExecutionStatus.BLOCKED, RecoveryStatus.VERIFIED, True),
        (ExecutionStatus.BLOCKED, RecoveryStatus.NOT_REQUIRED, True),
        (ExecutionStatus.COMPLETED, RecoveryStatus.PENDING, False),
        (ExecutionStatus.RECOVERY_REQUIRED, RecoveryStatus.VERIFIED, False),
        (ExecutionStatus.ERROR, RecoveryStatus.NOT_REQUIRED, False),
    ],
)
def test_finalization_requires_terminal_business_state_and_safe_recovery(
    status,
    recovery_status,
    expected,
) -> None:
    assert can_finalize(status, recovery_status) is expected


def test_execution_and_functional_outcomes_are_separate_enums() -> None:
    assert ExecutionStatus.ERROR.value == "ERROR"
    assert FunctionalVerdict.FAIL.value == "FAIL"
    assert ExecutionStatus.ERROR.value not in {item.value for item in FunctionalVerdict}
    assert ExecutionMode.FORMAL.value == "FORMAL"
    assert ActionPhase.RESTORE_VERIFY.value == "RESTORE_VERIFY"


def test_execution_contracts_are_frozen_and_contain_only_handles() -> None:
    action = ActionRequestDTO(
        session_id="session-1",
        action_execution_id="action-1",
        idempotency_key="session-1:action-1",
        plugin_code="onu-vlan",
        plugin_version="1.0.0",
        plugin_sha256="a" * 64,
        action_ref="verify-vlan",
        phase=ActionPhase.VERIFY,
        device_context={"model": "ONU"},
        environment_context={"olt": "lab"},
        parameters={"vlan_id": 100},
        credential_handles={"olt": "credential-ref-1"},
        evidence_directory_handle="evidence-session-1",
        timeout_seconds=30,
    )
    plan = ExecutionPlanDTO(
        run_id="run-1",
        result_id="result-1",
        skill_code="ONU-VLAN",
        skill_version="1.0.0",
        standard_snapshot_hash="b" * 64,
        device_snapshot={"model": "ONU"},
        environment_snapshot={"olt": "lab"},
        actions=(action,),
    )
    observation = ObservationDTO(
        key="observed_vlan",
        value=100,
        data_type="INTEGER",
        unit=None,
        observed_at=datetime.now(UTC),
        action_ref="verify-vlan",
    )
    event = RunnerEventDTO(
        session_id="session-1",
        sequence_no=1,
        idempotency_key="session-1:event-1",
        event_type="OBSERVATION",
        action_ref="verify-vlan",
        payload={"key": observation.key, "value": observation.value},
        occurred_at=datetime.now(UTC),
    )

    assert plan.actions == (action,)
    assert event.payload["value"] == 100
    with pytest.raises(FrozenInstanceError):
        action.timeout_seconds = 60
