"""Ownership projection tests use real event models, never device connections."""
from copy import deepcopy
from datetime import datetime, UTC
from hashlib import sha256
import importlib.util
import json

import pytest

from app.models.execution_session import ExecutionEvent
from test_skill_execution_repository import execution_fixture


SID = 'fixture-session'


def ledger():
    spec = importlib.util.find_spec('app.skill_execution.service_port_ledger')
    assert spec is not None, 'Missing append-only resource ledger'
    return importlib.import_module(spec.name)


def mapping(**changes):
    result = dict(olt_binding_hash='a' * 64, fsp='0/1/2', ont_id=7, vlan=1000,
                  gemport=1, user_vlan=1000, tag_transform='translate',
                  business_type='multi-service', candidate_id=None)
    result.update(changes)
    return result


def key(values):
    # Independently encode the public mapping-key contract, not production helper.
    semantic = {name: value for name, value in values.items() if name != 'candidate_id'}
    return sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def payload(kind, *, operation='create-1', port_id=51, values=None, consumers=None, creation_ref=None):
    values = mapping() if values is None else deepcopy(values)
    origin = 'REUSED' if kind == 'PORT_REUSED' else 'CREATED'
    result = dict(version=1, operation_id=operation, mapping_key=key(values), mapping=values,
        port_id=port_id, origin=origin, consumers=list(consumers or ['IPOE']),
        approval_hash=None if origin == 'REUSED' else 'b' * 64,
        baseline_hash='c' * 64, read_hash='d' * 64, verification_hash=None,
        before_evidence_ids=['proof-before'], after_evidence_ids=[],
        creation_event_id=creation_ref, captured_at='2026-10-13T08:00:00+00:00',
        command_result='PENDING')
    if kind == 'PORT_REUSED':
        result.update(command_result='NOT_EXECUTED', before_evidence_ids=[],
                      after_evidence_ids=['proof-read'], verification_hash='d' * 64)
    elif kind == 'PORT_CREATE_VERIFIED':
        result.update(command_result='SUCCESS', after_evidence_ids=['proof-created'], verification_hash='e' * 64)
    elif kind in {'PORT_CREATE_UNCERTAIN', 'PORT_DELETE_UNCERTAIN'}:
        result.update(command_result='UNKNOWN')
    elif kind == 'PORT_DELETE_VERIFIED':
        result.update(command_result='ABSENT_CONFIRMED', after_evidence_ids=['proof-absent'], verification_hash='f' * 64)
    elif kind == 'PORT_RETAINED':
        result.update(command_result='KEPT', before_evidence_ids=[], after_evidence_ids=[])
    return result


def event(number, kind, data=None, *, sid=SID):
    data = payload(kind) if data is None else deepcopy(data)
    return ExecutionEvent(id=f'00000000-0000-0000-0000-{number:012d}', session_id=sid,
        sequence_no=number, event_type=kind, payload_json=data,
        idempotency_key=f"{data.get('operation_id', 'ordinary')}:{kind}",
        occurred_at=datetime(2026, 10, 13, 8, tzinfo=UTC))


def created(*, consumers=None, sid=SID):
    return [event(1, 'PORT_CREATE_INTENT', payload('PORT_CREATE_INTENT', consumers=consumers), sid=sid),
            event(2, 'PORT_CREATE_VERIFIED', payload('PORT_CREATE_VERIFIED', consumers=consumers), sid=sid)]


def replay(events, sid=SID):
    return ledger().replay_port_ledger(sid, events)


def candidates(resources, active=frozenset()):
    return ledger().cleanup_candidates(resources, active)


def test_only_verified_session_created_resources_are_cleanup_candidates():
    owned = replay(created())
    reused = replay([event(1, 'PORT_REUSED')])
    pending = replay(created()[:1])
    uncertain = replay([created()[0], event(2, 'PORT_CREATE_UNCERTAIN')])
    foreign = replay(created(sid='foreign-session'))
    assert [resource.port_id for resource in candidates(owned)] == [51]
    assert candidates(reused) == candidates(pending) == candidates(uncertain) == ()
    assert foreign == ()
    assert owned[0].creation_event_id == created()[1].id


def test_shared_mapping_retains_active_consumer():
    resources = replay(created(consumers=['IPOE', 'PPPOE']))
    assert candidates(resources, frozenset({'PPPOE'})) == ()
    assert candidates(resources, frozenset({'IPOE'})) == ()
    assert [item.port_id for item in candidates(resources)] == [51]


def test_keep_is_not_delete():
    history = created()
    history.append(event(3, 'PORT_RETAINED', payload('PORT_RETAINED', operation='keep-1', creation_ref=history[1].id)))
    resource = replay(history)[0]
    assert resource.state == 'RETAINED' and resource.origin == 'CREATED'
    assert resource.creation_event_id == history[1].id
    assert candidates((resource,)) == ()


def test_duplicate_operation_does_not_duplicate_resource():
    history = created()
    resource = replay([history[0], deepcopy(history[0]), history[1], deepcopy(history[1])])
    assert len(resource) == 1 and [item.port_id for item in candidates(resource)] == [51]


def test_replay_does_not_mutate_events_or_allow_resource_mutation():
    history = created()
    before = deepcopy([record.payload_json for record in history])
    resources = replay(history)
    assert [record.payload_json for record in history] == before
    with pytest.raises((ValueError, AttributeError)):
        resources[0].origin = 'REUSED'
    with pytest.raises(ValueError):
        resources[0].mapping.ont_id = 8


def test_reused_consumers_merge_without_becoming_created():
    history = [event(1, 'PORT_REUSED', payload('PORT_REUSED', operation='reuse-ipoe')),
               event(2, 'PORT_REUSED', payload('PORT_REUSED', operation='reuse-pppoe', consumers=['PPPOE']))]
    resources = replay(history)
    assert len(resources) == 1 and resources[0].consumers == frozenset({'IPOE', 'PPPOE'})
    assert resources[0].origin == 'REUSED' and resources[0].creation_event_id is None
    assert candidates(resources) == ()


@pytest.mark.parametrize('field,value', [('version', 2), ('version', True), ('port_id', True),
    ('mapping_key', '0' * 64), ('origin', 'REUSED'), ('consumers', ['IPOE', 'IPOE']),
    ('approval_hash', None), ('captured_at', '2026-10-13T08:00:00'), ('owned', True)])
def test_invalid_payload_cannot_grant_ownership(field, value):
    history = created()
    history[1].payload_json[field] = value
    with pytest.raises(ValueError):
        replay(history)


@pytest.mark.parametrize('change', ['missing-intent', 'wrong-operation', 'wrong-baseline', 'wrong-read',
    'wrong-consumers', 'missing-after-proof', 'same-proof', 'missing-hash', 'uncertain-then-verified'])
def test_unproven_or_conflicting_creation_never_becomes_owned(change):
    history = created()
    if change == 'missing-intent':
        history = [event(1, 'PORT_CREATE_VERIFIED')]
    elif change == 'uncertain-then-verified':
        history = [history[0], event(2, 'PORT_CREATE_UNCERTAIN'), event(3, 'PORT_CREATE_VERIFIED')]
    else:
        changes = {'wrong-operation': ('operation_id', 'other-create'),
            'wrong-baseline': ('baseline_hash', 'f' * 64), 'wrong-read': ('read_hash', 'f' * 64),
            'wrong-consumers': ('consumers', ['PPPOE']), 'missing-after-proof': ('after_evidence_ids', []),
            'same-proof': ('after_evidence_ids', ['proof-before']), 'missing-hash': ('verification_hash', None)}
        name, value = changes[change]
        history[1].payload_json[name] = value
        if name == 'operation_id':
            history[1].idempotency_key = f'{value}:PORT_CREATE_VERIFIED'
    with pytest.raises(ValueError):
        replay(history)


def test_delete_requires_original_creation_reference_and_verified_absence():
    history = created()
    for index, kind in [(3, 'PORT_DELETE_INTENT'), (4, 'PORT_DELETE_VERIFIED')]:
        history.append(event(index, kind, payload(kind, operation='delete-1', creation_ref=history[1].id)))
    resource = replay(history)[0]
    assert resource.state == 'DELETED' and resource.creation_event_id == history[1].id
    assert resource.last_evidence_ids == ('proof-absent',)
    assert candidates((resource,)) == ()


@pytest.mark.parametrize('bad', ['missing-reference', 'wrong-mapping', 'reused-origin', 'missing-delete-intent'])
def test_invalid_deletion_history_is_rejected(bad):
    history = created() if bad != 'reused-origin' else [event(1, 'PORT_REUSED')]
    data = payload('PORT_DELETE_INTENT', operation='delete-1', creation_ref=history[-1].id)
    if bad == 'missing-reference':
        data['creation_event_id'] = None
    elif bad == 'wrong-mapping':
        data['mapping']['ont_id'] = 8
        data['mapping_key'] = key(data['mapping'])
    if bad == 'missing-delete-intent':
        history.append(event(3, 'PORT_DELETE_VERIFIED', payload('PORT_DELETE_VERIFIED', operation='delete-1', creation_ref=history[1].id)))
    else:
        history.append(event(len(history) + 1, 'PORT_DELETE_INTENT', data))
    with pytest.raises(ValueError):
        replay(history)


def test_delete_uncertainty_never_returns_to_automatic_cleanup():
    history = created()
    history += [event(3, 'PORT_DELETE_INTENT', payload('PORT_DELETE_INTENT', operation='delete-1', creation_ref=history[1].id)),
                event(4, 'PORT_DELETE_UNCERTAIN', payload('PORT_DELETE_UNCERTAIN', operation='delete-1', creation_ref=history[1].id))]
    assert replay(history)[0].state == 'DELETE_UNCERTAIN'
    assert candidates(replay(history)) == ()


@pytest.mark.parametrize('change', ['unknown-kind', 'gap', 'unordered', 'conflicting-duplicate', 'wrong-key'])
def test_ambiguous_or_incomplete_event_stream_is_rejected(change):
    history = created()
    if change == 'unknown-kind':
        history[1].event_type = 'PORT_AUTO_CLAIM'
    elif change == 'gap':
        history[1].sequence_no = 3
    elif change == 'unordered':
        history.reverse()
    elif change == 'wrong-key':
        history[1].idempotency_key = 'wrong:PORT_CREATE_VERIFIED'
    else:
        duplicate = deepcopy(history[1])
        duplicate.payload_json['port_id'] = 99
        history.append(duplicate)
    with pytest.raises(ValueError):
        replay(history)


def test_cleanup_rejects_mixed_session_projections():
    own = replay(created())
    other = replay(created(sid='foreign-session'), 'foreign-session')
    with pytest.raises(ValueError):
        candidates(own + other)


def test_ordinary_events_are_preserved_and_not_interpreted_as_port_ownership():
    history = [event(1, 'SESSION_CREATED', {'normal': True})]
    history += [event(2, 'PORT_CREATE_INTENT'), event(3, 'PORT_CREATE_VERIFIED')]
    assert [item.port_id for item in candidates(replay(history))] == [51]


def test_repository_persists_idempotent_events_and_projection_is_readonly(execution_fixture):
    service, repo, command = execution_fixture
    execution = service.create_execution(command)
    for kind in ('PORT_CREATE_INTENT', 'PORT_CREATE_VERIFIED'):
        data = payload(kind)
        record = repo.append_event(execution.id, kind, data, f"create-1:{kind}")
        assert repo.append_event(execution.id, kind, data, f"create-1:{kind}").id == record.id
    repo.session.commit()
    before = deepcopy([entry.payload_json for entry in repo.events(execution.id)])
    resources = replay(repo.events(execution.id), execution.id)
    assert [item.port_id for item in candidates(resources)] == [51]
    assert [entry.payload_json for entry in repo.events(execution.id)] == before


def test_second_live_resource_for_same_mapping_is_ambiguous():
    history = created()
    history.append(event(3, 'PORT_CREATE_INTENT', payload('PORT_CREATE_INTENT', operation='create-2', port_id=52)))
    with pytest.raises(ValueError):
        replay(history)


@pytest.mark.parametrize('change', ['binding', 'ont', 'baseline'])
def test_one_session_cannot_mix_dut_scope_or_baseline(change):
    history = created()
    values = mapping(vlan=1001, user_vlan=1001)
    if change == 'binding':
        values['olt_binding_hash'] = 'f' * 64
    elif change == 'ont':
        values['ont_id'] = 8
    data = payload('PORT_CREATE_INTENT', operation='create-2', port_id=52, values=values)
    if change == 'baseline':
        data['baseline_hash'] = 'f' * 64
    history.append(event(3, 'PORT_CREATE_INTENT', data))
    with pytest.raises(ValueError):
        replay(history)


def test_cleanup_rejects_duplicate_resource_projection():
    resources = replay(created())
    with pytest.raises(ValueError):
        candidates(resources + resources)


def uncertain_delete():
    history = created()
    history += [event(3, 'PORT_DELETE_INTENT', payload('PORT_DELETE_INTENT', operation='delete-1', creation_ref=history[1].id)),
                event(4, 'PORT_DELETE_UNCERTAIN', payload('PORT_DELETE_UNCERTAIN', operation='delete-1', creation_ref=history[1].id))]
    return history


def test_uncertain_deletion_can_be_confirmed_absent_without_new_delete_intent():
    history = uncertain_delete()
    history.append(event(5, 'PORT_DELETE_VERIFIED', payload('PORT_DELETE_VERIFIED', operation='delete-1', creation_ref=history[1].id)))
    assert replay(history)[0].state == 'DELETED'
    assert candidates(replay(history)) == ()


def test_uncertain_deletion_requires_fresh_operation_and_approval_before_retry_intent():
    history = uncertain_delete()
    data = payload('PORT_DELETE_INTENT', operation='delete-retry', creation_ref=history[1].id)
    data.update(approval_hash='1' * 64, before_evidence_ids=['fresh-proof-before'])
    history.append(event(5, 'PORT_DELETE_INTENT', data))
    resource = replay(history)[0]
    assert resource.state == 'DELETE_PENDING' and resource.operation_id == 'delete-retry'
    assert candidates((resource,)) == ()


@pytest.mark.parametrize('old_approval,old_proof', [(True, False), (False, True)])
def test_uncertain_deletion_cannot_reuse_old_approval_or_before_proof(old_approval, old_proof):
    history = uncertain_delete()
    data = payload('PORT_DELETE_INTENT', operation='delete-retry', creation_ref=history[1].id)
    data.update(approval_hash='b' * 64 if old_approval else '1' * 64,
                before_evidence_ids=['proof-before'] if old_proof else ['fresh-proof-before'])
    history.append(event(5, 'PORT_DELETE_INTENT', data))
    with pytest.raises(ValueError):
        replay(history)
