from types import MappingProxyType

from app.execution_engine.statuses import ExecutionStatus, RecoveryStatus


class InvalidExecutionTransition(ValueError):
    pass


VALID_TRANSITIONS = MappingProxyType(
    {
        ExecutionStatus.CREATED: frozenset(
            {ExecutionStatus.PREFLIGHT, ExecutionStatus.CANCELLED}
        ),
        ExecutionStatus.PREFLIGHT: frozenset(
            {
                ExecutionStatus.RUNNING,
                ExecutionStatus.BLOCKED,
                ExecutionStatus.ERROR,
                ExecutionStatus.CANCELLED,
            }
        ),
        ExecutionStatus.RUNNING: frozenset(
            {
                ExecutionStatus.WAITING_OPERATOR,
                ExecutionStatus.EVALUATING,
                ExecutionStatus.RESTORING,
                ExecutionStatus.BLOCKED,
                ExecutionStatus.ERROR,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.RECOVERY_REQUIRED,
            }
        ),
        ExecutionStatus.WAITING_OPERATOR: frozenset(
            {
                ExecutionStatus.RUNNING,
                ExecutionStatus.BLOCKED,
                ExecutionStatus.ERROR,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.RECOVERY_REQUIRED,
            }
        ),
        ExecutionStatus.EVALUATING: frozenset(
            {
                ExecutionStatus.RESTORING,
                ExecutionStatus.COMPLETED,
                ExecutionStatus.BLOCKED,
                ExecutionStatus.ERROR,
                ExecutionStatus.RECOVERY_REQUIRED,
            }
        ),
        ExecutionStatus.RESTORING: frozenset(
            {
                ExecutionStatus.COMPLETED,
                ExecutionStatus.BLOCKED,
                ExecutionStatus.ERROR,
                ExecutionStatus.RECOVERY_REQUIRED,
            }
        ),
        ExecutionStatus.RECOVERY_REQUIRED: frozenset({ExecutionStatus.RESTORING}),
        ExecutionStatus.COMPLETED: frozenset(),
        ExecutionStatus.BLOCKED: frozenset(),
        ExecutionStatus.ERROR: frozenset(),
        ExecutionStatus.CANCELLED: frozenset(),
    }
)


def validate_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    if target not in VALID_TRANSITIONS[current]:
        raise InvalidExecutionTransition(
            f"Execution cannot transition from {current.value} to {target.value}"
        )


def can_finalize(
    status: ExecutionStatus,
    recovery_status: RecoveryStatus,
) -> bool:
    return status in {ExecutionStatus.COMPLETED, ExecutionStatus.BLOCKED} and (
        recovery_status in {RecoveryStatus.NOT_REQUIRED, RecoveryStatus.VERIFIED}
    )
