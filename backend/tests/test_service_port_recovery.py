"""Restart and explicit reconciliation never replay a device mutation."""
import pytest

from app.models.test_execution import RunResult
from app.skill_execution.coordinator import SkillCoordinator
from app.skill_execution.service_port_ledger import replay_port_ledger, cleanup_candidates
from test_service_port_creation import lab, prepared
from test_skill_execution_repository import execution_fixture


def engine_for(lab, tmp_path):
    lifecycle, repo, *_ = lab
    return SkillCoordinator(repo, execute=lambda _: pytest.fail('Startup must not perform device I/O'),
        storage=lifecycle.storage, workspace=tmp_path / 'runner')


def interrupt_create(lab):
    lifecycle, _, _, _, _, state = lab
    operation, preview = prepared(lab)
    create = lifecycle.create_device
    def crash(op, approval):
        create(op, approval)
        state['read'] = 'FOUND'
        raise SystemExit('fixture process terminated after device write')
    lifecycle.create_device = crash
    with pytest.raises(SystemExit):
        lifecycle.execute_approved(operation, preview.preview_hash)
    return operation, preview


def interrupt_delete(lab):
    lifecycle, repo, sid, _, _, state = lab
    operation, preview = prepared(lab)
    assert lifecycle.execute_approved(operation, preview.preview_hash).status == 'PASS'
    state['read'] = 'FOUND'
    previews = lifecycle.preview_cleanup(sid, frozenset())
    batch = next(e.payload_json for e in reversed(repo.events(sid)) if e.event_type == 'SERVICE_PORT_CLEANUP_PREVIEW')
    def crash(*_):
        raise SystemExit('fixture process terminated after delete intent')
    lifecycle.delete_device = crash
    with pytest.raises(SystemExit):
        lifecycle.cleanup(sid, previews, batch['preview_hash'])
    return previews, batch


def test_restart_after_create_intent_never_reissues_command(lab, tmp_path):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    operation, preview = interrupt_create(lab)
    before = state['reads']
    engine = engine_for(lab, tmp_path)
    assert engine.recover_interrupted() == 1
    assert repo.get(sid).status == 'RECOVERY_REQUIRED'
    resource = replay_port_ledger(sid, repo.events(sid))[0]
    assert resource.state == 'CREATE_UNCERTAIN' and resource.creation_event_id is None
    assert repo.get(sid).error_code == 'PROCESS_RESTARTED'
    assert cleanup_candidates((resource,), frozenset()) == ()
    assert engine.recover_interrupted() == 0
    engine.advance(sid)
    engine.advance(sid)
    assert state['writes'] == [53] and state['reads'] == before
    assert lifecycle.execute_approved(operation, preview.preview_hash).status == 'BLOCKED'


def test_matching_resource_without_verified_event_is_not_owned(lab, tmp_path):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    interrupt_create(lab)
    engine_for(lab, tmp_path).recover_interrupted()
    assert callable(getattr(lifecycle, 'reconcile_interrupted', None)), 'Missing explicit read-only reconciliation'
    resources = lifecycle.reconcile_interrupted(sid)
    assert resources[0].state == 'CREATE_UNCERTAIN' and resources[0].creation_event_id is None
    assert cleanup_candidates(resources, frozenset()) == () and state['writes'] == [53]
    proof = next(e for e in reversed(repo.events(sid)) if e.event_type == 'SERVICE_PORT_RECONCILED')
    assert proof.payload_json['status'] == 'FOUND' and proof.payload_json['automatic_write_authorized'] is False
    assert repo.get(sid).status == 'RECOVERY_REQUIRED'


@pytest.mark.parametrize('present', [True, False])
def test_restart_after_delete_reads_before_new_approval(lab, tmp_path, present):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    interrupt_delete(lab)
    before = state['reads']
    engine_for(lab, tmp_path).recover_interrupted()
    assert state['reads'] == before
    assert replay_port_ledger(sid, repo.events(sid))[0].state == 'DELETE_UNCERTAIN'
    state['read'] = 'FOUND' if present else 'ABSENT'
    assert callable(getattr(lifecycle, 'reconcile_interrupted', None)), 'Missing explicit read-only reconciliation'
    resources = lifecycle.reconcile_interrupted(sid)
    assert state['reads'] > before and state['writes'] == [53]
    assert resources[0].state == ('DELETE_UNCERTAIN' if present else 'DELETED')
    assert repo.get(sid).status == 'RECOVERY_REQUIRED'
    assert cleanup_candidates(resources, frozenset()) == ()


def test_pending_intent_in_waiting_session_cannot_resume_stale_approval(lab, tmp_path):
    lab = lab()
    _, repo, sid, _, _, state = lab
    interrupt_create(lab)
    repo.get(sid).status = 'WAITING_OPERATOR'
    repo.session.commit()
    assert engine_for(lab, tmp_path).recover_interrupted() == 1
    assert repo.get(sid).status == 'RECOVERY_REQUIRED' and state['writes'] == [53]


def test_reconciliation_requires_recovery_and_never_changes_baseline(lab, tmp_path):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    baseline = repo.get(sid).configuration_snapshots[0].snapshot_json
    assert callable(getattr(lifecycle, 'reconcile_interrupted', None)), 'Missing explicit read-only reconciliation'
    with pytest.raises(ValueError):
        lifecycle.reconcile_interrupted(sid)
    assert state['reads'] == 0
    interrupt_create(lab)
    engine_for(lab, tmp_path).recover_interrupted()
    lifecycle.reconcile_interrupted(sid)
    assert repo.get(sid).configuration_snapshots[0].snapshot_json == baseline
    result = repo.session.get(RunResult, repo.get(sid).run_result_id)
    assert result.integrity_status == 'DRAFT' and result.recovery_status == 'MANUAL_REQUIRED'


@pytest.mark.parametrize('protected', ['LOCKED', 'CANCELLED', 'COMPLETED'])
def test_local_marking_cannot_mutate_protected_history(lab, protected):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    interrupt_create(lab)
    execution = repo.get(sid)
    if protected == 'LOCKED':
        repo.session.get(RunResult, execution.run_result_id).integrity_status = 'LOCKED'
    else:
        execution.status = protected
    repo.session.commit()
    count = len(repo.events(sid))
    with pytest.raises(ValueError):
        lifecycle.mark_interrupted(sid)
    assert len(repo.events(sid)) == count and state['writes'] == [53]
