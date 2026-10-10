from hashlib import sha256
import pytest
from sqlalchemy import select
from test_skill_execution_repository import execution_fixture
from app.local_runner.contracts import ActionOutcome, Observation, ArtifactPayload
from app.models.execution_session import RecoveryTask
from app.models.test_execution import RunResult, TestRun
from app.evidence.storage import EvidenceStorage
from app.skill_execution.coordinator import SkillCoordinator, build_plan


class Driver:
    def __init__(self):
        self.calls = []
        self.fail_action = None
        self.crash_action = None

    def __call__(self, context):
        self.calls.append(context.action_code)
        if context.action_code == self.crash_action:
            raise RuntimeError('secret-must-not-persist')
        if context.action_code == self.fail_action:
            return ActionOutcome('FAIL', (), (), 'FIXTURE_FAILURE')
        facts = []
        if context.action_code == 'snapshot_ont':
            facts.append(Observation('olt.configuration_snapshot', {'registration': {}, 'wan': [], 'service_ports': []}, 'MA5800'))
        if context.action_code == 'find_free_ont_id':
            facts.append(Observation('olt.free_ont_id', 12, 'MA5800'))
        for key in ['olt.autofind.matched','olt.registration.ready','ipoe.address.valid',
                    'ipoe.internet.pass','pppoe.address.valid','pppoe.internet.pass']:
            facts.append(Observation(key, True, 'FIXTURE'))
        if context.action_code in {'delete_ont','register_ont','provision_ipoe','provision_pppoe','remove_test_services','restore_snapshot'}:
            preview = {'preview_hash': sha256((context.action_code + str(context.parameters['ont_id'])).encode()).hexdigest()}
            if context.parameters.get('mutation_approval', {}).get('preview_hash') != preview['preview_hash']:
                return ActionOutcome('WAITING_OPERATOR', (Observation('mutation.preview', preview, 'MA5800'),), ())
        png = b'fixture-png-content'
        return ActionOutcome('PASS', tuple(facts), (ArtifactPayload('fixture.png','image/png',content=png,redacted=True),))


def coordinator(execution_fixture, tmp_path):
    service, repo, command = execution_fixture
    driver = Driver()
    engine = SkillCoordinator(repo, execute=driver,
        storage=EvidenceStorage(tmp_path / 'ev', max_bytes=1024 * 1024), workspace=tmp_path / 'runner')
    service.coordinator = engine
    return service, repo, command, driver


def drain(service, repo, session_id, end='KEEP'):
    for _ in range(150):
        execution = repo.get(session_id)
        if execution.status in {'COMPLETED','BLOCKED','ERROR','CANCELLED','RECOVERY_REQUIRED'}:
            return execution
        if execution.status == 'WAITING_OPERATOR':
            interaction = next(i for i in execution.operator_interactions if i.status == 'PENDING')
            choice = end if 'KEEP' in interaction.options_json else interaction.options_json[0]
            service.respond(session_id, interaction.id, {'choice':choice, 'approved':True,
                'preview_hash': interaction.impact_preview['preview_hash']})
        else:
            before = len(repo.events(session_id))
            service.advance(session_id)
            assert len(repo.events(session_id)) > before
    pytest.fail('Coordinator did not terminate')


def test_sequential_mode_requires_isolation_before_pppoe(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    drain(service, repo, execution.id)
    assert driver.calls.index('provision_ipoe') < driver.calls.index('remove_test_services')
    assert driver.calls.index('remove_test_services') < driver.calls.index('provision_pppoe')
    isolation = [i for i in repo.get(execution.id).operator_interactions if i.interaction_ref == 'ISOLATE_IPOE']
    assert len(isolation) == 1 and isolation[0].status == 'COMPLETED'


def test_concurrent_plan_requires_two_active_wan_confirmations():
    plan = build_plan({'execution_mode':'CONCURRENT_DUAL_WAN'})
    refs = [s['ref'] for s in plan]
    assert refs.index('PROVISION_PPPOE') < refs.index('IPOE_ADDRESS_OLT')
    assert 'SWITCH_IPOE' in refs and 'SWITCH_PPPOE' in refs


def test_each_advance_executes_at_most_one_action_and_waiting_is_stable(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    for _ in range(30):
        previous = len(driver.calls)
        service.advance(execution.id)
        assert len(driver.calls) - previous <= 1
        if repo.get(execution.id).status == 'WAITING_OPERATOR':
            count = len(repo.events(execution.id))
            service.advance(execution.id)
            assert len(repo.events(execution.id)) == count
            break
    else:
        pytest.fail('No guarded interaction')


def test_stale_or_wrong_approval_does_not_execute_mutation(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    while repo.get(execution.id).status != 'WAITING_OPERATOR':
        service.advance(execution.id)
    interaction = next(i for i in repo.get(execution.id).operator_interactions if i.status == 'PENDING')
    with pytest.raises(ValueError):
        service.respond(execution.id, interaction.id, {'choice':'CONFIRM','approved':True,'preview_hash':'wrong'})
    assert interaction.status == 'PENDING'


def test_restart_marks_inflight_action_for_recovery_without_replay(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    execution.status = 'RUNNING'
    repo.append_event(execution.id,'ACTION_STARTED',{'ref':'PREFLIGHT','attempt':1},'PREFLIGHT:1:start')
    repo.session.commit()
    assert service.coordinator.recover_interrupted() == 1
    service.advance(execution.id)
    assert driver.calls == []
    assert repo.get(execution.id).status == 'RECOVERY_REQUIRED'
    assert repo.session.scalar(select(RecoveryTask)).status == 'MANUAL_REQUIRED'


def test_fail_does_not_skip_end_policy_and_locked_result_stays_immutable(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    driver.fail_action = 'run_onu_ping'
    execution = service.create_execution(command)
    drain(service, repo, execution.id)
    result = repo.session.get(RunResult, execution.run_result_id)
    assert result.functional_verdict == 'FAIL'
    assert result.result != 'PASS'
    assert result.integrity_status == 'LOCKED'
    with pytest.raises(ValueError):
        result.result = 'PASS'


def test_clean_fake_execution_locks_complete_evidence(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    final = drain(service, repo, execution.id)
    result = repo.session.get(RunResult, execution.run_result_id)
    assert final.status == 'COMPLETED'
    assert result.result == 'PASS'
    assert result.integrity_status == 'LOCKED'
    assert repo.session.get(TestRun, execution.test_run_id).status == 'COMPLETED'


def test_runner_exception_does_not_store_raw_exception(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    driver.crash_action = 'preflight'
    execution = service.create_execution(command)
    service.advance(execution.id)
    assert repo.get(execution.id).status == 'RECOVERY_REQUIRED'
    assert 'secret-must-not-persist' not in str(service.get_view(execution.id))


def test_restart_leaves_unrelated_sessions_and_waiting_interactions_alone(execution_fixture, tmp_path):
    from app.models.execution_session import ExecutionSession
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    while repo.get(execution.id).status != 'WAITING_OPERATOR':
        service.advance(execution.id)
    unrelated = ExecutionSession(test_run_id=execution.test_run_id, mode='DEVELOPMENT', status='RUNNING')
    repo.session.add(unrelated)
    repo.session.commit()
    service.coordinator.recover_interrupted()
    assert repo.get(execution.id).status == 'WAITING_OPERATOR'
    assert repo.session.get(ExecutionSession, unrelated.id).status == 'RUNNING'


def test_action_claim_is_never_replayed_after_missing_outcome(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    repo.append_event(execution.id,'ACTION_STARTED',{'ref':'PREFLIGHT','attempt':1},'PREFLIGHT:1:start')
    repo.session.commit()
    service.advance(execution.id)
    assert driver.calls == []
    assert repo.get(execution.id).status == 'RECOVERY_REQUIRED'


def test_approved_retry_claim_cannot_be_hidden_by_previous_waiting_outcome(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    while repo.get(execution.id).status != 'WAITING_OPERATOR':
        service.advance(execution.id)
    interaction = next(i for i in repo.get(execution.id).operator_interactions if i.status == 'PENDING')
    service.respond(execution.id, interaction.id, dict(choice='CONFIRM', approved=True,
        preview_hash=interaction.impact_preview['preview_hash']))
    started = [e for e in repo.events(execution.id) if e.event_type == 'ACTION_STARTED'][-1]
    ref = started.payload_json['ref']
    repo.append_event(execution.id, 'ACTION_STARTED', dict(ref=ref, attempt=2), ref + ':2:start')
    repo.session.commit()
    previous_calls = list(driver.calls)
    service.advance(execution.id)
    assert driver.calls == previous_calls
    assert repo.get(execution.id).status == 'RECOVERY_REQUIRED'


def test_restore_full_snapshot_mismatch_never_claims_completion(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    original = driver.__call__
    snapshots = []
    def changed(context):
        outcome = original(context)
        if context.action_code == 'snapshot_ont':
            snapshots.append(1)
            if len(snapshots) >= 3:
                return ActionOutcome('PASS', (Observation('olt.configuration_snapshot',
                    {'registration':{},'wan':[{'mode':'PPPOE'}],'service_ports':[]},'MA5800'),),())
        return outcome
    service.coordinator.execute = changed
    execution = service.create_execution(command)
    final = drain(service, repo, execution.id, end='RESTORE')
    assert final.status == 'RECOVERY_REQUIRED'
    result = repo.session.get(RunResult, execution.run_result_id)
    assert result.integrity_status == 'DRAFT'
    assert result.recovery_status == 'MANUAL_REQUIRED'


def test_hash_tampering_prevents_pass_at_finalization(execution_fixture, tmp_path):
    from app.models.evidence import Evidence
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    for _ in range(100):
        current = repo.get(execution.id)
        if current.status == 'WAITING_OPERATOR':
            interaction = next(i for i in current.operator_interactions if i.status == 'PENDING')
            choice = 'KEEP' if 'KEEP' in interaction.options_json else interaction.options_json[0]
            service.respond(execution.id,interaction.id,dict(choice=choice,approved=True,
                preview_hash=interaction.impact_preview['preview_hash']))
            if choice == 'KEEP':
                break
        else:
            service.advance(execution.id)
    artifact = repo.session.scalar(select(Evidence).where(Evidence.execution_session_id == execution.id))
    path = service.coordinator.storage.open_path(artifact.storage_path)
    path.write_bytes(b'changed-by-fixture')
    service.advance(execution.id)
    assert repo.session.get(RunResult,execution.run_result_id).result == 'BLOCKED'
