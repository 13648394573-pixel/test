"""Creation gates use real SQLite events/evidence and an offline device boundary."""
from dataclasses import replace
from pathlib import Path
from hashlib import sha256
import importlib.util
import json
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.storage import EvidenceStorage
from app.local_runner.contracts import ActionContext, ActionOutcome, ArtifactPayload, Observation
from app.local_runner.configuration import RuntimeBinding
from app.local_runner.credentials import SecretValue
from app.local_runner.runtime import BoundExecutionRuntime, RuntimeResources
from app.local_runner.ma5800.transport import CommandTranscript
from app.local_runner.ma5800 import service_port_contracts as contracts
from app.models.execution_session import ConfigurationSnapshot, ExecutionEvent
from app.models.evidence import Evidence
from app.models.test_execution import RunResult
from app.skill_execution.coordinator import SkillCoordinator
from app.skill_execution.service_port_ledger import replay_port_ledger, cleanup_candidates
from test_service_port_plan import bound
from test_skill_execution_repository import execution_fixture


def module():
    spec = importlib.util.find_spec('app.skill_execution.service_port_lifecycle')
    assert spec is not None, 'Missing safe service-port lifecycle'
    return importlib.import_module(spec.name)


@pytest.fixture
def lab(execution_fixture, tmp_path):
    service, repo, command, _, _ = bound(execution_fixture)
    execution = service.create_execution(command)
    baseline = {'registration': {'fixture': True}, 'wan': [], 'service_ports': []}
    baseline_hash = sha256(json.dumps(baseline, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    repo.session.add(ConfigurationSnapshot(session_id=execution.id, device_ref=command.device_id,
        scope_json={'fixture': True}, capture_action_ref='snapshot_ont', snapshot_json=baseline, sha256=baseline_hash))
    repo.session.commit()
    identity = execution.plugin_snapshot['runtime_binding']['olt']
    binding_hash = sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    mapping = contracts.ServicePortMapping(olt_binding_hash=binding_hash, fsp='0/2/9', ont_id=12,
        vlan=1000, gemport=1, user_vlan=1000, tag_transform='translate', business_type='multi-service', candidate_id=53)
    storage = EvidenceStorage(tmp_path / 'ev', max_bytes=1024 * 1024)
    engine = SkillCoordinator(repo, execute=lambda _: None, storage=storage, workspace=tmp_path / 'runner')
    state = {'read': 'ABSENT', 'post': 'FOUND', 'writes': [], 'reads': 0, 'timeout': False, 'missing_profile': False}
    def outcome(status, post=False):
        items = ([dict(port_id=53, mapping=mapping.model_dump(mode='json'), state='up')]
                 if status in {'FOUND', 'DUPLICATE'} else [])
        if status == 'DUPLICATE':
            items.append({**items[0], 'port_id': 54})
        if status == 'OCCUPIED':
            items = [dict(port_id=53, mapping={**mapping.model_dump(mode='json'), 'ont_id': 13}, state='up')]
        read = dict(binding_hash=binding_hash, observation_hash=('e' if post else 'd') * 64,
                    status='FOUND' if items else status, items=items, query_port_id=53)
        return ActionOutcome('PASS', (
            Observation('port.read', read, 'MA5800'),
            Observation('port.command_succeeded', post and not state.get('command_failed', False), 'MA5800'),
            Observation('olt.profile_gem.verified', not state['missing_profile'], 'MA5800')),
            (ArtifactPayload('proof.txt', 'text/plain', content=b'fixture redacted protocol proof', redacted=True),))
    def read_device(_sid, _mapping):
        state['reads'] += 1
        return outcome(state['read'])
    def create_device(operation, approval):
        with Session(repo.session.get_bind()) as observer:
            intents = observer.scalars(select(ExecutionEvent).where(ExecutionEvent.session_id == execution.id,
                ExecutionEvent.event_type == 'PORT_CREATE_INTENT')).all()
            assert len(intents) == 1, 'Device write requires a committed intent visible on another connection'
        assert approval['preview_hash']
        state['writes'].append(operation.port_id)
        if state['timeout']:
            raise TimeoutError('fixture timeout')
        return outcome(state['post'], True)
    def persist(sid, result):
        own = repo.get(sid)
        row = repo.session.get(RunResult, own.run_result_id)
        return engine._store_artifacts(own, row, dict(step='REGISTER', method='OLT_RENDER'), result.artifacts)
    def construct():
        lifecycle = module().ServicePortLifecycle(repo, inspect_device=read_device,
            create_device=create_device, persist_evidence=persist, storage=storage)
        return lifecycle, repo, execution.id, mapping, baseline_hash, state
    return construct


def operation(lab, read):
    _, _, sid, mapping, baseline, _ = lab
    model = getattr(contracts, 'PortOperation', None)
    assert model is not None, 'Missing immutable port operation'
    return model(operation_id='fixture-create', session_id=sid, mapping=mapping, port_id=53,
                 serial_number='AABBCCDDEEFF0011', line_profile_id=10, service_profile_id=10, consumers=('IPOE', 'PPPOE'),
                 kind='CREATE', baseline_hash=baseline, read_hash=read.observation_hash)


def prepared(lab):
    lifecycle, _, sid, mapping, _, _ = lab
    read = lifecycle.inspect(sid, mapping)
    op = operation(lab, read)
    return op, lifecycle.preview(op, read)


def test_exact_match_reuses_without_write(lab):
    lab = lab()
    lifecycle, repo, sid, mapping, _, state = lab
    state['read'] = 'FOUND'
    assert lifecycle.inspect(sid, mapping).status == 'FOUND'
    resources = replay_port_ledger(sid, repo.events(sid))
    assert len(resources) == 1 and resources[0].origin == 'REUSED'
    assert cleanup_candidates(resources, frozenset()) == () and state['writes'] == []


@pytest.mark.parametrize('case', ['DUPLICATE', 'OCCUPIED', 'missing-profile'])
def test_duplicate_global_occupation_or_incomplete_profile_blocks(lab, case):
    lab = lab()
    lifecycle, repo, sid, mapping, _, state = lab
    if case == 'missing-profile':
        state['missing_profile'] = True
    else:
        state['read'] = case
    read = lifecycle.inspect(sid, mapping)
    assert read.status == 'UNCONFIRMED'
    with pytest.raises(ValueError):
        lifecycle.preview(operation(lab, read), read)
    assert state['writes'] == [] and cleanup_candidates(replay_port_ledger(sid, repo.events(sid)), frozenset()) == ()


def test_intent_is_committed_before_device_write_and_outcome_is_owned(lab):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    op, preview = prepared(lab)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'PASS'
    resources = replay_port_ledger(sid, repo.events(sid))
    assert resources[0].state == 'ACTIVE' and resources[0].consumers == frozenset({'IPOE', 'PPPOE'})
    assert state['writes'] == [53]


def test_state_changed_after_approval_has_zero_writes(lab):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    op, preview = prepared(lab)
    state['read'] = 'FOUND'
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'BLOCKED'
    assert state['writes'] == []
    assert not any(e.event_type == 'PORT_CREATE_INTENT' for e in repo.events(sid))


def test_preview_hash_covers_full_operation_scope(lab):
    lab = lab()
    lifecycle, _, _, _, _, state = lab
    op, preview = prepared(lab)
    altered = op.model_copy(update={'port_id': 54})
    assert lifecycle.execute_approved(altered, preview.preview_hash).status == 'BLOCKED'
    assert lifecycle.execute_approved(op, 'f' * 64).status == 'BLOCKED'
    assert state['writes'] == []


def test_preview_explicitly_shows_dut_profiles_and_shared_consumers(lab):
    lab = lab()
    _, preview = prepared(lab)
    values = preview.to_payload()
    assert values.get('target', {}).get('serial_number') == 'AABBCCDDEEFF0011'
    assert values.get('target', {}).get('line_profile_id') == 10
    assert values.get('target', {}).get('service_profile_id') == 10
    assert values.get('consumers') == ['IPOE', 'PPPOE']


def test_intent_commit_failure_prevents_io(lab, monkeypatch):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    op, preview = prepared(lab)
    commit = repo.session.commit
    def fail_intent():
        if any(isinstance(e, ExecutionEvent) and e.event_type == 'PORT_CREATE_INTENT'
               for e in repo.session.identity_map.values()):
            raise RuntimeError('fixture intent commit failure')
        commit()
    monkeypatch.setattr(repo.session, 'commit', fail_intent)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'BLOCKED'
    assert state['writes'] == []
    monkeypatch.setattr(repo.session, 'commit', commit)
    assert not any(e.event_type == 'PORT_CREATE_INTENT' for e in repo.events(sid))


@pytest.mark.parametrize('case', ['timeout', 'mismatch', 'evidence', 'result-commit', 'command-failed', 'before-proof-tamper', 'cancelled-session'])
def test_uncertain_creation_never_claims_resource_or_reissues_write(lab, monkeypatch, case):
    lab = lab()
    lifecycle, repo, sid, _, _, state = lab
    op, preview = prepared(lab)
    if case == 'timeout':
        state['timeout'] = True
    elif case == 'command-failed':
        state['command_failed'] = True
    elif case == 'before-proof-tamper':
        create = lifecycle.create_device
        def tamper_before(op, approval):
            intent = next(e for e in repo.events(sid) if e.event_type == 'PORT_CREATE_INTENT')
            proof = repo.session.get(Evidence, intent.payload_json['before_evidence_ids'][0])
            lifecycle.storage.open_path(proof.storage_path).write_bytes(b'fixture tampered evidence')
            return create(op, approval)
        monkeypatch.setattr(lifecycle, 'create_device', tamper_before)
    elif case == 'cancelled-session':
        create = lifecycle.create_device
        def cancel_during_write(op, approval):
            result = create(op, approval)
            repo.get(sid).status = 'CANCELLED'
            repo.session.commit()
            return result
        monkeypatch.setattr(lifecycle, 'create_device', cancel_during_write)
    elif case == 'mismatch':
        state['post'] = 'OCCUPIED'
    elif case == 'evidence':
        persist = lifecycle.persist_evidence
        def fail_post(sid, result):
            if state['writes']:
                raise OSError('fixture evidence failure')
            return persist(sid, result)
        monkeypatch.setattr(lifecycle, 'persist_evidence', fail_post)
    else:
        commit = repo.session.commit
        def fail_result():
            if any(isinstance(e, ExecutionEvent) and e.event_type == 'PORT_CREATE_VERIFIED'
                   for e in repo.session.identity_map.values()):
                raise RuntimeError('fixture result commit failure')
            commit()
        monkeypatch.setattr(repo.session, 'commit', fail_result)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'BLOCKED'
    assert state['writes'] == [53]
    assert any(e.event_type == 'PORT_CREATE_INTENT' for e in repo.events(sid))
    assert cleanup_candidates(replay_port_ledger(sid, repo.events(sid)), frozenset()) == ()
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'BLOCKED'
    assert state['writes'] == [53]


def test_verified_operation_is_idempotent_without_more_reads_or_writes(lab):
    lab = lab()
    lifecycle, _, _, _, _, state = lab
    op, preview = prepared(lab)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'PASS'
    reads = state['reads']
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'PASS'
    assert state['writes'] == [53] and state['reads'] == reads


def attach_runtime(lab, monkeypatch, tmp_path, *, protocol=None):
    lifecycle, repo, sid, mapping, _, _ = lab
    binding = RuntimeBinding.model_validate(repo.get(sid).plugin_snapshot['runtime_binding'])
    commands, ports = [], {}
    protocol = {} if protocol is None else protocol
    class Executor:
        def __init__(self, *_):
            self.transcripts = []
        def run(self, command):
            commands.append(command.action_code)
            fixtures = Path(__file__).parent / 'fixtures/ma5800'
            if command.action_code == 'display_ont_by_sn':
                text = (fixtures / 'ont_online.txt').read_text(encoding='utf-8').replace('48575443DD91BBBB', 'AABBCCDDEEFF0011').replace('0/2/10', '0/2/9').replace(': 36', ': 12')
            elif command.action_code == 'read_profile_gem':
                text = (fixtures / 'profile_gem.txt').read_text(encoding='utf-8')
            elif command.action_code == 'display_service_ports':
                text = ''.join(f'{identifier} 1000 0/2/9 {ont} {2 if identifier == 54 else 1} 1000\n' for identifier, ont in ports.items() if ont == 12) + 'Total : ' + str(sum(ont == 12 for ont in ports.values())) + '\nMA5800-X7#'
                if protocol.get('empty_failure') and not any(ont == 12 for ont in ports.values()):
                    query = 'display service-port port 0/2/9 ont 12'
                    text = (query + '\n{ <cr>|e2e<K>|gemport<K>|sort-by<K>||<K> }:\nCommand:\n'
                            + query + '\nFailure: No service virtual port can be operated\nMA5800-X7(config)#')
            elif command.action_code == 'display_service_port_by_id':
                identifier = command.arguments[0]
                if identifier in ports:
                    text = (fixtures / 'service_port_detail.txt').read_text(encoding='utf-8').replace('51', str(identifier)).replace('0/1/2', '0/2/9').replace('ONT ID              : 7', f'ONT ID              : {ports[identifier]}')
                    if identifier == 54:
                        text = text.replace('GEM port index      : 1', 'GEM port index      : 2')
                    for before, after in protocol.get('detail_changes', {}).items():
                        text = text.replace(before, after)
                else:
                    text = f'display service-port {identifier}\nFailure: Service virtual port does not exist\nMA5800-X7(config)#'
            elif command.action_code == 'create_service_port':
                assert command.render() == 'service-port 53 vlan 1000 gpon 0/2/9 ont 12 gemport 1 multi-service user-vlan 1000 tag-transform translate'
                if protocol.get('timeout'):
                    raise TimeoutError('fixture write outcome unknown')
                if protocol.get('apply', True):
                    ports[53] = protocol.get('created_ont', 12)
                text = protocol.get('create_reply', 'Command executed successfully\nMA5800-X7(config)#')
            else:
                pytest.fail('Unexpected offline command: ' + command.action_code)
            transcript = CommandTranscript(command.action_code, text, text, 'MA5800-X7(config)#', sha256(text.encode()).hexdigest())
            self.transcripts.append(transcript)
            return transcript
        def close(self):
            return True
    monkeypatch.setattr('app.local_runner.runtime._OLTExecutor', Executor)
    runtime = BoundExecutionRuntime(binding, None, RuntimeResources(), lambda: repo.events(sid))
    def run(action, operation=None, approval=None):
        execution = repo.get(sid)
        values = dict(repo.session.get(RunResult, execution.run_result_id).parameter_snapshot,
            service_port_mapping=mapping.model_dump(mode='json'))
        if operation is not None:
            values.update(port_operation=operation.model_dump(mode='json'), port_approval=approval)
        return runtime.execute(ActionContext(sid, action, values,
            {'olt_username': SecretValue('fixture-user'), 'olt_password': SecretValue('fixture-password')}, tmp_path / 'runner' / sid))
    lifecycle.inspect_device = lambda _sid, _mapping: run('inspect_service_mapping')
    lifecycle.create_device = lambda op, approval: run('create_service_port', op, approval)
    return commands, ports, run


def test_real_runner_reads_global_candidate_before_approved_creation(lab, monkeypatch, tmp_path):
    lab = lab()
    lifecycle, repo, sid, _, _, _ = lab
    commands, _, _ = attach_runtime(lab, monkeypatch, tmp_path)
    op, preview = prepared(lab)
    assert 'display_service_port_by_id' in commands
    assert 'create_service_port' not in commands
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'PASS'
    assert commands.count('create_service_port') == 1
    assert replay_port_ledger(sid, repo.events(sid))[0].state == 'ACTIVE'


def test_runner_global_candidate_owned_elsewhere_blocks(lab, monkeypatch, tmp_path):
    lab = lab()
    lifecycle, _, sid, mapping, _, _ = lab
    commands, ports, _ = attach_runtime(lab, monkeypatch, tmp_path)
    ports[53] = 13
    assert lifecycle.inspect(sid, mapping).status == 'UNCONFIRMED'
    assert 'display_service_port_by_id' in commands and 'create_service_port' not in commands


def test_runner_requires_durable_intent_before_any_device_io(lab, monkeypatch, tmp_path):
    lab = lab()
    _, _, _, _, _, _ = lab
    commands, _, run = attach_runtime(lab, monkeypatch, tmp_path)
    op, preview = prepared(lab)
    commands.clear()
    assert run('create_service_port', op, preview.to_payload()).status == 'BLOCKED'
    assert commands == []


def test_runner_conflicting_vlan_mapping_blocks_instead_of_creating_another(lab, monkeypatch, tmp_path):
    lab = lab()
    lifecycle, _, sid, mapping, _, _ = lab
    commands, ports, _ = attach_runtime(lab, monkeypatch, tmp_path)
    ports[54] = 12
    assert lifecycle.inspect(sid, mapping).status == 'UNCONFIRMED'
    assert 'create_service_port' not in commands


def test_coordinator_waits_for_exact_mapping_approval_before_creation(lab, monkeypatch, tmp_path):
    lab = lab()
    lifecycle, repo, sid, mapping, _, _ = lab
    commands, _, run = attach_runtime(lab, monkeypatch, tmp_path)
    def execute(context):
        op = contracts.PortOperation.model_validate(context.parameters['port_operation']) if 'port_operation' in context.parameters else None
        return run(context.action_code, op, context.parameters.get('port_approval'))
    engine = SkillCoordinator(repo, execute=execute, storage=lifecycle.storage, workspace=tmp_path / 'runner')
    for ref in ('PREFLIGHT', 'VERIFY_REGISTRATION', 'SNAPSHOT'):
        repo.append_event(sid, 'STEP_COMPLETED', {'ref': ref}, ref + ':done')
    repo.session.commit()
    original = json.dumps(repo.get(sid).configuration_snapshots[0].snapshot_json, sort_keys=True)
    engine.advance(sid)
    engine.advance(sid)
    execution = repo.get(sid)
    assert execution.status == 'WAITING_OPERATOR'
    assert 'create_service_port' not in commands
    pending = next(item for item in execution.operator_interactions if item.status == 'PENDING')
    assert pending.interaction_ref == 'SERVICE_1_CREATE'
    assert pending.impact_preview['operation']['mapping']['gemport'] == 1
    with pytest.raises(ValueError):
        engine.respond(sid, pending.id, {'choice': 'CONFIRM', 'approved': True, 'preview_hash': 'f' * 64})
    engine.respond(sid, pending.id, {'choice': 'CONFIRM', 'approved': True,
                                    'preview_hash': pending.impact_preview['preview_hash']})
    engine.advance(sid)
    engine.advance(sid)
    assert commands.count('create_service_port') == 1
    resources = replay_port_ledger(sid, repo.events(sid))
    assert len(resources) == 1 and resources[0].state == 'ACTIVE'
    assert json.dumps(repo.get(sid).configuration_snapshots[0].snapshot_json, sort_keys=True) == original


SILENT_CREATE = (
    'service-port 53 vlan 1000 gpon 0/2/9 ont 12 gemport 1 multi-s ervice user-vlan 1000 tag-transform translate\n'
    '{ <cr>|bundle<K>|inbound<K>|rx-cttr<K> }:\nCommand:\n'
    'service-port 53 vlan 1000 gpon 0/2/9 ont 12 gemport 1 multi-service\n'
    'user-vlan 1000 tag-transform translate\nMA5800-X7(config)#'
)


@pytest.mark.parametrize('empty_failure', [False, True])
def test_silent_create_requires_matching_readback_then_commits_once(lab, monkeypatch, tmp_path, empty_failure):
    current = lab()
    lifecycle, repo, sid, _, _, _ = current
    commands, _, _ = attach_runtime(current, monkeypatch, tmp_path,
        protocol={'create_reply': SILENT_CREATE, 'empty_failure': empty_failure})
    baseline = json.dumps(repo.get(sid).configuration_snapshots[0].snapshot_json, sort_keys=True)
    op, preview = prepared(current)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'PASS'
    resources = replay_port_ledger(sid, repo.events(sid))
    assert len(resources) == 1 and resources[0].origin == 'CREATED' and resources[0].state == 'ACTIVE'
    assert commands.count('create_service_port') == 1
    assert 'display_service_port_by_id' in commands[commands.index('create_service_port') + 1:]
    event = next(e for e in repo.events(sid) if e.event_type == 'PORT_CREATE_VERIFIED')
    assert event.payload_json['after_evidence_ids']
    before_repeat = list(commands)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'PASS'
    assert commands == before_repeat
    assert json.dumps(repo.get(sid).configuration_snapshots[0].snapshot_json, sort_keys=True) == baseline


@pytest.mark.parametrize('case', ['no-port', 'wrong-ont', 'wrong-gem', 'wrong-vlan', 'error',
    'unknown-payload', 'only-prompt', 'wrong-command', 'truncated', 'timeout'])
def test_silent_or_uncertain_create_never_claims_or_retries_without_full_proof(lab, monkeypatch, tmp_path, case):
    current = lab()
    lifecycle, repo, sid, _, _, _ = current
    protocol = {'create_reply': SILENT_CREATE}
    if case == 'no-port':
        protocol['apply'] = False
    elif case == 'wrong-ont':
        protocol['created_ont'] = 13
    elif case == 'wrong-gem':
        protocol['detail_changes'] = {'GEM port index      : 1': 'GEM port index      : 2'}
    elif case == 'wrong-vlan':
        protocol['detail_changes'] = {'VLAN ID             : 1000': 'VLAN ID             : 2000'}
    elif case == 'error':
        protocol['create_reply'] = SILENT_CREATE.replace('MA5800-X7(config)#', 'Failure: Permission denied\nMA5800-X7(config)#')
    elif case == 'unknown-payload':
        protocol['create_reply'] = SILENT_CREATE.replace('MA5800-X7(config)#', 'Unexpected status: pending\nMA5800-X7(config)#')
    elif case == 'only-prompt':
        protocol['create_reply'] = 'MA5800-X7(config)#'
    elif case == 'wrong-command':
        protocol['create_reply'] = SILENT_CREATE.replace('ont 12', 'ont 13')
    elif case == 'truncated':
        protocol['create_reply'] = SILENT_CREATE.replace('MA5800-X7(config)#', '')
    else:
        protocol['timeout'] = True
    commands, _, _ = attach_runtime(current, monkeypatch, tmp_path, protocol=protocol)
    op, preview = prepared(current)
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'BLOCKED'
    assert commands.count('create_service_port') == 1
    assert not any(e.event_type == 'PORT_CREATE_VERIFIED' for e in repo.events(sid))
    assert cleanup_candidates(replay_port_ledger(sid, repo.events(sid)), frozenset()) == ()
    assert lifecycle.execute_approved(op, preview.preview_hash).status == 'BLOCKED'
    assert commands.count('create_service_port') == 1
