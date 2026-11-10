"""Cleanup uses real SQLite provenance/evidence; only physical OLT I/O is replaced."""
from dataclasses import replace
from hashlib import sha256
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.storage import EvidenceStorage
from app.local_runner.contracts import ActionContext, ActionOutcome, ArtifactPayload, Observation
from app.local_runner.ma5800.actions import MA5800Actions
from app.local_runner.ma5800.service_port_contracts import PortOperation, ServicePortMapping, ServicePortProfile
from app.models.evidence import Evidence
from app.models.execution_session import ConfigurationSnapshot, ExecutionEvent
from app.models.test_execution import RunResult
from app.skill_execution.coordinator import SkillCoordinator
from app.skill_execution.service_port_ledger import replay_port_ledger
from app.skill_execution.service_port_lifecycle import ServicePortLifecycle, olt_binding_hash
from test_service_port_plan import bound, profile_data
from test_skill_execution_repository import execution_fixture
from test_ma5800_actions import FakeExecutor, context
from test_service_port_creation import lab as creation_lab, attach_runtime, prepared
from app.local_runner.ma5800.transport import CommandTranscript


@pytest.fixture
def cleanup_lab(execution_fixture, tmp_path):
    def build(*, shared=False, create=True):
        service, repo, command, _, _ = bound(execution_fixture)
        profiles = profile_data()
        if not shared:
            profiles['pppoe'].update(vlan=2000, user_vlan=2000, candidate_id=54)
            command.parameters['pppoe_vlan'] = 2000
        resolver = service.binding_resolver
        service.binding_resolver = lambda parameters: resolver(parameters).model_copy(
            update={'service_port_profile': ServicePortProfile.model_validate(profiles)})
        execution = service.create_execution(command)
        baseline = {'registration': {'fixture': True}, 'wan': [], 'service_ports': []}
        digest = sha256(json.dumps(baseline, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        repo.session.add(ConfigurationSnapshot(session_id=execution.id, device_ref=command.device_id,
            scope_json={'fixture': True}, capture_action_ref='snapshot_ont', snapshot_json=baseline, sha256=digest))
        repo.session.commit()
        from app.local_runner.configuration import RuntimeBinding
        binding = RuntimeBinding.model_validate(execution.plugin_snapshot['runtime_binding'])
        maps = tuple(ServicePortMapping(**spec, olt_binding_hash=olt_binding_hash(binding),
            fsp='0/2/9', ont_id=12) for spec in ([profiles['ipoe']] if shared else profiles.values()))
        storage = EvidenceStorage(tmp_path / 'evidence', max_bytes=1024 * 1024)
        engine = SkillCoordinator(repo, execute=lambda _: None, storage=storage, workspace=tmp_path / 'runner')
        state = dict(ports={}, deletes=[], reads=[], fail=None, tamper=False)
        def outcome(mapping, *, commanded=False):
            identifier = mapping.candidate_id
            actual = state['ports'].get(identifier)
            read = dict(binding_hash=mapping.olt_binding_hash,
                observation_hash=sha256(json.dumps([identifier, actual], sort_keys=True).encode()).hexdigest(),
                status='FOUND' if actual else 'ABSENT', query_port_id=identifier,
                items=[dict(port_id=identifier, mapping=actual, state='up')] if actual else [])
            return ActionOutcome('PASS', (
                Observation('port.read', read, 'MA5800'),
                Observation('olt.profile_gem.verified', True, 'MA5800'),
                Observation('port.command_succeeded', commanded, 'MA5800')),
                (ArtifactPayload('fixture.txt', 'text/plain', content=json.dumps(read).encode(), redacted=True),))
        def inspect(sid, mapping):
            assert sid == execution.id
            state['reads'].append(mapping.candidate_id)
            return outcome(mapping)
        def create_port(operation, _approval):
            state['ports'][operation.port_id] = operation.mapping.model_dump(mode='json')
            return outcome(operation.mapping, commanded=True)
        def delete_port(operation, approval):
            assert approval['preview_hash']
            with Session(repo.session.get_bind()) as observer:
                intent = observer.scalar(select(ExecutionEvent).where(
                    ExecutionEvent.session_id == execution.id,
                    ExecutionEvent.idempotency_key == operation.operation_id + ':PORT_DELETE_INTENT'))
                assert intent is not None, 'Delete requires committed provenance visible to another connection'
            state['deletes'].append(operation.port_id)
            if state['fail'] == operation.port_id:
                raise TimeoutError('fixture delete timeout')
            state['ports'].pop(operation.port_id)
            return outcome(operation.mapping, commanded=True)
        def persist(sid, result):
            own = repo.get(sid)
            row = repo.session.get(RunResult, own.run_result_id)
            return engine._store_artifacts(own, row, dict(step='FINISH', method='OLT_RENDER'), result.artifacts)
        lifecycle = ServicePortLifecycle(repo, inspect_device=inspect, create_device=create_port,
            persist_evidence=persist, storage=storage)
        # The new dependency is assigned after construction so RED is a behavior assertion, not a setup error.
        lifecycle.delete_device = delete_port
        if create:
            for number, mapping in enumerate(maps):
                read = lifecycle.inspect(execution.id, mapping)
                consumers = ('IPOE', 'PPPOE') if shared else (('IPOE',) if number == 0 else ('PPPOE',))
                operation = PortOperation(operation_id=f'create-fixture-{number}', session_id=execution.id,
                    mapping=mapping, port_id=mapping.candidate_id, kind='CREATE', baseline_hash=digest,
                    read_hash=read.observation_hash, serial_number='AABBCCDDEEFF0011', line_profile_id=10,
                    service_profile_id=10, consumers=consumers)
                preview = lifecycle.preview(operation, read)
                assert lifecycle.execute_approved(operation, preview.preview_hash).status == 'PASS'
        state['reads'].clear()
        return lifecycle, repo, execution.id, maps, state
    return build


def preview(lab, retained=frozenset()):
    lifecycle, repo, sid = lab[:3]
    assert callable(getattr(lifecycle, 'preview_cleanup', None)), 'Missing trusted cleanup preview'
    previews = lifecycle.preview_cleanup(sid, retained)
    saved = next(e for e in reversed(repo.events(sid)) if e.event_type == 'SERVICE_PORT_CLEANUP_PREVIEW')
    return previews, saved.payload_json['preview_hash']


def test_reused_and_cross_session_ports_are_never_deleted(cleanup_lab):
    lab = cleanup_lab(create=False)
    lifecycle, repo, sid, maps, state = lab
    state['ports'][53] = maps[0].model_dump(mode='json')
    lifecycle.inspect(sid, maps[0])
    # A foreign stream is never supplied as ownership; no backfill from snapshot or OLT list.
    previews, digest = preview(lab)
    assert previews == ()
    reads = len(state['reads'])
    assert lifecycle.cleanup(sid, previews, digest).status == 'PASS'
    assert state['deletes'] == [] and len(state['reads']) == reads
    assert replay_port_ledger(sid, repo.events(sid))[0].origin == 'REUSED'


def test_shared_active_port_is_retained(cleanup_lab):
    lab = cleanup_lab(shared=True)
    lifecycle, repo, sid, _, state = lab
    previews, digest = preview(lab, frozenset({'PPPOE'}))
    assert previews == () and state['reads'] == []
    assert lifecycle.cleanup(sid, previews, digest).status == 'PASS'
    assert state['deletes'] == [] and 53 in state['ports']


def test_all_created_ports_are_processed(cleanup_lab):
    lab = cleanup_lab()
    lifecycle, repo, sid, _, state = lab
    previews, digest = preview(lab)
    assert [p.operation.port_id for p in previews] == [53, 54]
    assert all(p.operation.creation_event_id for p in previews)
    assert lifecycle.cleanup(sid, previews, digest).status == 'PASS'
    assert state['deletes'] == [53, 54] and state['ports'] == {}
    assert [r.state for r in replay_port_ledger(sid, repo.events(sid))] == ['DELETED', 'DELETED']
    reads = len(state['reads'])
    assert lifecycle.cleanup(sid, previews, digest).status == 'PASS'
    assert state['deletes'] == [53, 54] and len(state['reads']) == reads


def test_cleanup_preview_displays_delete_not_create(cleanup_lab):
    previews, _ = preview(cleanup_lab(shared=True))
    assert previews[0].to_payload()['action_code'] == 'delete_service_port'


def test_first_delete_failure_marks_remaining_port_not_processed(cleanup_lab):
    lab = cleanup_lab()
    lifecycle, repo, sid, _, state = lab
    previews, digest = preview(lab)
    state['fail'] = 53
    result = lifecycle.cleanup(sid, previews, digest)
    assert result.status == 'BLOCKED' and state['deletes'] == [53]
    assert next(o.value for o in result.observations if o.fact_key == 'port.cleanup.items') == [
        {'port_id': 53, 'status': 'UNCERTAIN'}, {'port_id': 54, 'status': 'NOT_PROCESSED'}]
    assert [r.state for r in replay_port_ledger(sid, repo.events(sid))] == ['DELETE_UNCERTAIN', 'ACTIVE']


def test_second_delete_failure_keeps_partial_outcomes(cleanup_lab):
    lab = cleanup_lab()
    lifecycle, repo, sid, _, state = lab
    previews, digest = preview(lab)
    state['fail'] = 54
    outcome = lifecycle.cleanup(sid, previews, digest)
    assert outcome.status == 'BLOCKED' and state['deletes'] == [53, 54]
    assert [r.state for r in replay_port_ledger(sid, repo.events(sid))] == ['DELETED', 'DELETE_UNCERTAIN']
    assert lifecycle.cleanup(sid, previews, digest).status == 'BLOCKED'
    assert state['deletes'] == [53, 54]


@pytest.mark.parametrize('drift', ['mapping', 'ont', 'id-reuse'])
def test_mapping_drift_or_id_reuse_stops_cleanup(cleanup_lab, drift):
    lab = cleanup_lab()
    lifecycle, _, sid, maps, state = lab
    previews, digest = preview(lab)
    state['ports'][53] = {**state['ports'][53], ('gemport' if drift == 'mapping' else 'ont_id'): 13}
    assert lifecycle.cleanup(sid, previews, digest).status == 'BLOCKED'
    assert state['deletes'] == [] and 54 in state['ports']


def test_already_absent_records_observation_without_delete(cleanup_lab):
    lab = cleanup_lab()
    lifecycle, repo, sid, _, state = lab
    state['ports'].pop(53)
    previews, digest = preview(lab)
    assert previews[0].read.status == 'ABSENT'
    assert lifecycle.cleanup(sid, previews, digest).status == 'PASS'
    assert state['deletes'] == [54]
    assert replay_port_ledger(sid, repo.events(sid))[0].state == 'DELETED'


def test_keep_retains_all_created_ports(cleanup_lab):
    lab = cleanup_lab()
    lifecycle, repo, sid, _, state = lab
    assert callable(getattr(lifecycle, 'retain', None)), 'Missing KEEP ledger transition'
    lifecycle.retain(sid)
    lifecycle.retain(sid)
    assert [r.state for r in replay_port_ledger(sid, repo.events(sid))] == ['RETAINED', 'RETAINED']
    assert state['deletes'] == state['reads'] == []
    previews, _ = preview(lab)
    assert previews == ()


@pytest.mark.parametrize('tamper', ['hash', 'order', 'subset', 'session', 'creation-reference'])
def test_batch_approval_covers_complete_ordered_scope(cleanup_lab, tamper):
    lab = cleanup_lab()
    lifecycle, _, sid, _, state = lab
    previews, digest = preview(lab)
    if tamper == 'hash':
        digest = 'f' * 64
    elif tamper == 'order':
        previews = tuple(reversed(previews))
    elif tamper == 'subset':
        previews = previews[:1]
    else:
        operation = previews[0].operation.model_copy(update={
            'session_id' if tamper == 'session' else 'creation_event_id': 'foreign-fixture'})
        previews = (replace(previews[0], operation=operation), *previews[1:])
    reads = len(state['reads'])
    assert lifecycle.cleanup(sid, previews, digest).status == 'BLOCKED'
    assert state['deletes'] == [] and len(state['reads']) == reads


def test_legacy_snapshot_list_is_not_delete_authority():
    executor = FakeExecutor()
    actions = MA5800Actions(executor)
    first = actions.remove_test_services(context('remove_test_services', affected_service_ports=[21, 22]))
    approval = next((o.value for o in first.observations if o.fact_key == 'mutation.preview'), {})
    result = actions.remove_test_services(context('remove_test_services', affected_service_ports=[21, 22],
        mutation_approval={'approved': True, 'preview_hash': approval.get('preview_hash')}))
    assert result.status == 'BLOCKED' and executor.commands == []


def delete_runtime(lab, monkeypatch, tmp_path):
    commands, ports, run = attach_runtime(lab, monkeypatch, tmp_path)
    from app.local_runner import runtime as runtime_module
    original = runtime_module._OLTExecutor
    class Executor(original):
        def run(self, command):
            if command.action_code != 'remove_service_port':
                return super().run(command)
            assert command.render() == 'undo service-port 53'
            commands.append(command.action_code)
            ports.pop(53)
            text = 'Command executed successfully\nMA5800-X7(config)#'
            transcript = CommandTranscript(command.action_code, text, text, 'MA5800-X7(config)#', sha256(text.encode()).hexdigest())
            self.transcripts.append(transcript)
            return transcript
    monkeypatch.setattr(runtime_module, '_OLTExecutor', Executor)
    return commands, ports, run


def test_runner_delete_requires_durable_batch_and_intent_before_any_io(creation_lab, monkeypatch, tmp_path):
    lab = creation_lab()
    lifecycle, repo, sid = lab[:3]
    commands, _, run = delete_runtime(lab, monkeypatch, tmp_path)
    operation, approved = prepared(lab)
    assert lifecycle.execute_approved(operation, approved.preview_hash).status == 'PASS'
    lifecycle.inspect_cleanup_device = lambda _sid, _mapping: run('inspect_service_port')
    previews, digest = preview(lab)
    batch = next(e.payload_json for e in reversed(repo.events(sid)) if e.event_type == 'SERVICE_PORT_CLEANUP_PREVIEW')
    commands.clear()
    assert run('delete_service_port', previews[0].operation, batch).status == 'BLOCKED'
    assert commands == []


def test_real_runner_verifies_global_absence_after_single_typed_delete(creation_lab, monkeypatch, tmp_path):
    lab = creation_lab()
    lifecycle, repo, sid = lab[:3]
    commands, ports, run = delete_runtime(lab, monkeypatch, tmp_path)
    operation, approved = prepared(lab)
    assert lifecycle.execute_approved(operation, approved.preview_hash).status == 'PASS'
    lifecycle.inspect_cleanup_device = lambda _sid, _mapping: run('inspect_service_port')
    lifecycle.delete_device = lambda op, approval: run('delete_service_port', op, approval)
    previews, digest = preview(lab)
    assert lifecycle.cleanup(sid, previews, digest).status == 'PASS'
    assert commands.count('remove_service_port') == 1 and ports == {}
    assert replay_port_ledger(sid, repo.events(sid))[0].state == 'DELETED'


def test_keep_response_records_retention_without_device_io(cleanup_lab, tmp_path):
    lifecycle, repo, sid, _, state = cleanup_lab()
    engine = SkillCoordinator(repo, execute=lambda _: pytest.fail('KEEP must not call a device'),
        storage=lifecycle.storage, workspace=tmp_path / 'runner')
    step = dict(ref='END_POLICY', interaction=['KEEP', 'CANCEL'], step='FINISH')
    row = repo.session.get(RunResult, repo.get(sid).run_result_id)
    interaction = engine._interaction(repo.get(sid), step, step['interaction'], engine._preview(row, step))
    repo.session.commit()
    engine.respond(sid, interaction.id, {'choice': 'KEEP', 'approved': True,
                   'preview_hash': interaction.impact_preview['preview_hash']})
    assert [r.state for r in replay_port_ledger(sid, repo.events(sid))] == ['RETAINED', 'RETAINED']
    assert state['deletes'] == state['reads'] == []


def test_foreign_session_batch_cannot_claim_ownership(cleanup_lab):
    foreign = cleanup_lab()
    previews, digest = preview(foreign)
    foreign[1].get(foreign[2]).status = 'CANCELLED'
    foreign[1].session.commit()
    own = cleanup_lab(create=False)
    lifecycle, repo, sid, _, state = own
    batch = next(e.payload_json for e in reversed(repo.events(foreign[2])) if e.event_type == 'SERVICE_PORT_CLEANUP_PREVIEW')
    repo.append_event(sid, 'SERVICE_PORT_CLEANUP_PREVIEW', batch, 'fixture-foreign-batch')
    repo.session.commit()
    assert lifecycle.cleanup(sid, previews, digest).status == 'BLOCKED'
    assert state['deletes'] == state['reads'] == []


@pytest.mark.parametrize('failure', ['intent-commit', 'command-failed', 'post-mismatch', 'proof-tamper', 'cancelled'])
def test_delete_failures_never_become_verified_or_retry(cleanup_lab, monkeypatch, failure):
    lab = cleanup_lab(shared=True)
    lifecycle, repo, sid, _, state = lab
    previews, digest = preview(lab)
    delete = lifecycle.delete_device
    if failure == 'intent-commit':
        commit = repo.session.commit
        def fail_commit():
            if any(isinstance(e, ExecutionEvent) and e.event_type == 'PORT_DELETE_INTENT'
                   for e in repo.session.identity_map.values()):
                raise RuntimeError('fixture failed intent commit')
            commit()
        monkeypatch.setattr(repo.session, 'commit', fail_commit)
    else:
        def broken(op, approval):
            result = delete(op, approval)
            if failure == 'command-failed':
                return replace(result, status='BLOCKED')
            if failure == 'post-mismatch':
                return replace(result, observations=tuple(replace(o, value={**o.value, 'status': 'UNCONFIRMED'})
                    if o.fact_key == 'port.read' else o for o in result.observations))
            if failure == 'proof-tamper':
                item = repo.session.get(Evidence, previews[0].read.evidence_ids[0])
                lifecycle.storage.open_path(item.storage_path).write_bytes(b'fixture corruption')
            if failure == 'cancelled':
                repo.get(sid).status = 'CANCELLED'
                repo.session.commit()
            return result
        lifecycle.delete_device = broken
    assert lifecycle.cleanup(sid, previews, digest).status == 'BLOCKED'
    assert not any(e.event_type == 'PORT_DELETE_VERIFIED' for e in repo.events(sid))
    assert state['deletes'] == ([] if failure == 'intent-commit' else [53])
    assert lifecycle.cleanup(sid, previews, digest).status == 'BLOCKED'
    assert state['deletes'] == ([] if failure == 'intent-commit' else [53])
