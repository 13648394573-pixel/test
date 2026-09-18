import pytest
from sqlalchemy.exc import IntegrityError

from app.models.credential import CredentialReference
from app.models.execution_session import (
    ConfigurationSnapshot,
    ExecutionEvent,
    ExecutionSession,
    OperatorInteraction,
    RecoveryTask,
)
from app.models.evidence import Evidence
from app.models.test_execution import RunResult, TestProject, TestRun


def make_run_result(db_session) -> RunResult:
    project = TestProject(name="Execution", version="V2")
    run = TestRun(
        run_no="RUN-SESSION-001",
        project=project,
        device_source_id="device-1",
        device_snapshot={},
        status="IN_PROGRESS",
    )
    result = RunResult(
        run=run,
        case_source_id="case-1",
        case_snapshot={},
        integrity_status="DRAFT",
    )
    db_session.add(result)
    db_session.flush()
    return result


def test_only_one_active_execution_session_per_result(db_session) -> None:
    result = make_run_result(db_session)
    db_session.add_all(
        [
            ExecutionSession(
                test_run_id=result.run_id,
                run_result_id=result.id,
                mode="FORMAL",
                status="CREATED",
            ),
            ExecutionSession(
                test_run_id=result.run_id,
                run_result_id=result.id,
                mode="FORMAL",
                status="RUNNING",
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_execution_events_are_idempotent_and_append_only(db_session) -> None:
    result = make_run_result(db_session)
    session = ExecutionSession(
        test_run_id=result.run_id,
        run_result_id=result.id,
        mode="DEVELOPMENT",
        status="RUNNING",
    )
    event = ExecutionEvent(
        sequence_no=1,
        idempotency_key="session:event:1",
        event_type="ACTION_STARTED",
        action_ref="verify-vlan",
        payload_json={},
    )
    session.events.append(event)
    db_session.add(session)
    db_session.commit()

    event.payload_json = {"changed": True}
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    db_session.delete(event)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()


def test_execution_event_sequence_and_idempotency_are_unique(db_session) -> None:
    result = make_run_result(db_session)
    session = ExecutionSession(
        test_run_id=result.run_id,
        run_result_id=result.id,
        mode="MANUAL",
        status="CREATED",
    )
    session.events.extend(
        [
            ExecutionEvent(
                sequence_no=1,
                idempotency_key="same-key",
                event_type="CREATED",
                payload_json={},
            ),
            ExecutionEvent(
                sequence_no=2,
                idempotency_key="same-key",
                event_type="PREFLIGHT",
                payload_json={},
            ),
        ]
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_operator_snapshot_and_recovery_constraints(db_session) -> None:
    result = make_run_result(db_session)
    session = ExecutionSession(
        test_run_id=result.run_id,
        run_result_id=result.id,
        mode="FORMAL",
        status="WAITING_OPERATOR",
    )
    session.operator_interactions.append(
        OperatorInteraction(
            interaction_ref="connect-lan",
            title="Connect LAN cable",
            instructions="Connect the test PC to LAN1.",
            completion_condition="LAN link is up.",
            status="UNKNOWN",
            required=True,
        )
    )
    session.configuration_snapshots.append(
        ConfigurationSnapshot(
            device_ref="onu-1",
            scope_json={"fields": ["vlan"]},
            capture_action_ref="snapshot-vlan",
            snapshot_json={"vlan": 100},
            sha256="short",
        )
    )
    session.recovery_tasks.append(
        RecoveryTask(
            required=True,
            status="PENDING",
            restore_action_ref="restore-vlan",
            verify_action_ref="verify-restore-vlan",
            attempt_count=0,
        )
    )
    db_session.add(session)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_operator_interaction_records_structured_risk_and_response(db_session) -> None:
    result = make_run_result(db_session)
    session = ExecutionSession(
        test_run_id=result.run_id,
        run_result_id=result.id,
        mode="FORMAL",
        status="WAITING_OPERATOR",
    )
    interaction = OperatorInteraction(
        interaction_ref="confirm-delete-registration",
        interaction_type="CONFIRMATION",
        risk_level="HIGH",
        title="Confirm registration replacement",
        instructions="Review the existing ONU before replacement.",
        completion_condition="Operator selects continue or cancel.",
        options_json=["CONTINUE", "CANCEL"],
        impact_preview={"registration": "will be replaced"},
        response_json={"selected": "CONTINUE"},
        status="COMPLETED",
        required=True,
    )
    session.operator_interactions.append(interaction)
    db_session.add(session)
    db_session.commit()

    assert interaction.risk_level == "HIGH"
    assert interaction.response_json == {"selected": "CONTINUE"}


def test_generated_evidence_records_step_and_redaction(db_session) -> None:
    result = make_run_result(db_session)
    session = ExecutionSession(
        test_run_id=result.run_id,
        run_result_id=result.id,
        mode="DEVELOPMENT",
        status="RUNNING",
    )
    db_session.add(session)
    db_session.flush()
    evidence = Evidence(
        run_result_id=result.id,
        execution_session_id=session.id,
        step_ref="IPOE_ADDRESS",
        evidence_rule_code="E3_IPOE_ADDRESS",
        capture_method="OLT_RENDER",
        redacted=True,
        category="SCREENSHOT",
        original_name="ipoe.png",
        storage_path="runs/run-1/ipoe.png",
        media_type="image/png",
        file_size=10,
        sha256="a" * 64,
    )
    db_session.add(evidence)
    db_session.commit()

    assert evidence.step_ref == "IPOE_ADDRESS"
    assert evidence.redacted is True


@pytest.mark.parametrize(
    "credential_target_ref",
    ["https://user:password@olt.local", "line1\nline2", "user:secret@olt"],
)
def test_credential_reference_rejects_secret_like_values(
    db_session,
    credential_target_ref,
) -> None:
    db_session.add(
        CredentialReference(
            purpose="OLT access",
            target_type="OLT",
            credential_target_ref=credential_target_ref,
            masked_display_name="OLT lab account",
        )
    )
    with pytest.raises(ValueError, match="credential reference"):
        db_session.commit()
