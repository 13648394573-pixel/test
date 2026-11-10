"""Operator approval contracts through the actual local HTTP response."""
import pytest
from copy import deepcopy
from hashlib import sha256

from app.local_runner.ma5800.service_port_contracts import PortOperation
from app.local_runner.contracts import ActionOutcome, Observation
from app.models.test_execution import RunResult, TestRun

from test_service_port_creation import lab, prepared, attach_runtime
from test_service_port_lifecycle_api import port_api
from test_skill_execution_repository import execution_fixture
from app.skill_execution.service_port_lifecycle import cleanup_batch_payload
from test_report_api import create_run, lock_run


def advance_to_port_chain(client, values, engine, monkeypatch, tmp_path):
    """Resume after a captured baseline; only physical SSH transport is an offline double."""
    _, repo, sid, _, _, _ = values
    commands, ports, run = attach_runtime(values, monkeypatch, tmp_path)
    def execute(context):
        operation = context.parameters.get('port_operation')
        return run(context.action_code, PortOperation.model_validate(operation) if operation else None,
                   context.parameters.get('port_approval'))
    engine.execute = execute
    plan = repo.session.get(TestRun, repo.get(sid).test_run_id).execution_plan_snapshot['steps']
    for step in plan:
        if step.get('action') == 'inspect_service_mapping':
            break
        repo.append_event(sid, 'STEP_COMPLETED', {'ref': step['ref']}, step['ref'] + ':done')
    repo.session.commit()
    base = '/api/skill-executions/' + sid
    assert client.post(base + '/advance').status_code == 200
    response = client.post(base + '/advance')
    assert response.status_code == 200
    pending = response.json()['pending_interaction']
    assert pending and pending['service_port_preview']['operations'][0]['port_id'] == 53
    assert 'create_service_port' not in commands
    before = list(commands)
    response = client.post(base + '/interactions/' + pending['id'] + '/respond',
        json=dict(choice='CONFIRM', approved=True, preview_hash=pending['preview_hash']))
    assert response.status_code == 200 and commands == before
    return commands, ports, base


def test_api_coordinator_runner_shared_mapping_creates_once_without_auto_lock(port_api, monkeypatch, tmp_path):
    client, values, engine = port_api
    _, repo, sid, _, _, _ = values
    result = repo.session.get(RunResult, repo.get(sid).run_result_id)
    frozen = deepcopy((result.parameter_snapshot, result.run.device_snapshot,
        result.run.execution_plan_snapshot, result.run.environment_snapshot.profile_snapshot))
    commands, _, base = advance_to_port_chain(client, values, engine, monkeypatch, tmp_path)
    for _ in range(2):  # Approved CREATE, then independent mapping verification.
        response = client.post(base + '/advance')
        assert response.status_code == 200, response.text
    assert commands.count('create_service_port') == 1
    resources = response.json()['service_port_resources']
    assert len(resources) == 1 and resources[0]['consumers'] == ['IPOE', 'PPPOE']
    assert resources[0]['state'] == 'ACTIVE'
    assert response.json()['integrity_status'] == 'DRAFT'
    result = repo.session.get(RunResult, repo.get(sid).run_result_id)
    assert result.locked_at is None and result.result is None
    assert (result.parameter_snapshot, result.run.device_snapshot, result.run.execution_plan_snapshot,
        result.run.environment_snapshot.profile_snapshot) == frozen
    evidence = client.get(base + '/evidence').json()
    assert evidence
    for item in evidence:
        downloaded = client.get(item['download_url'])
        assert downloaded.status_code == 200
        assert sha256(downloaded.content).hexdigest() == item['sha256']
    assert client.post('/api/test-runs/' + result.run_id + '/reports', json={}).status_code == 409


def test_device_write_timeout_is_uncertain_not_pass_and_never_retried(port_api, monkeypatch, tmp_path):
    client, values, engine = port_api
    commands, _, base = advance_to_port_chain(client, values, engine, monkeypatch, tmp_path)
    execute = engine.execute
    def timeout(context):
        outcome = execute(context)
        if context.action_code == 'create_service_port':
            raise TimeoutError('fixture transport loss after physical write')
        return outcome
    engine.execute = timeout
    response = client.post(base + '/advance')
    assert response.status_code == 200
    assert response.json()['status'] == 'RECOVERY_REQUIRED'
    assert response.json()['result'] != 'PASS' and response.json()['integrity_status'] == 'DRAFT'
    resource = response.json()['service_port_resources'][0]
    assert resource['state'] == 'CREATE_UNCERTAIN' and resource['creation_event_id'] is None
    count = len(commands)
    for _ in range(2):
        assert client.post(base + '/advance').status_code == 200
    assert len(commands) == count and commands.count('create_service_port') == 1


def test_created_mapping_replaced_under_another_id_stops_verification(port_api, monkeypatch, tmp_path):
    client, values, engine = port_api
    commands, ports, base = advance_to_port_chain(client, values, engine, monkeypatch, tmp_path)
    assert client.post(base + '/advance').status_code == 200
    ports.pop(53)
    ports[55] = 12  # Same mapping, different globally observable resource identity.
    response = client.post(base + '/advance')
    assert response.status_code == 200
    assert response.json()['status'] == 'RECOVERY_REQUIRED'
    assert response.json()['result'] != 'PASS'
    assert response.json()['service_port_resources'][0]['port_id'] == 53
    assert commands.count('create_service_port') == 1
    assert not any(e.event_type == 'ACTION_STARTED' and e.payload_json['ref'] == 'PROVISION_IPOE'
                   for e in values[1].events(values[2]))


def test_cancel_wan_approval_after_port_creation_requires_manual_recovery(port_api, monkeypatch, tmp_path):
    client, values, engine = port_api
    commands, _, base = advance_to_port_chain(client, values, engine, monkeypatch, tmp_path)
    for _ in range(2):
        assert client.post(base + '/advance').status_code == 200
    execute = engine.execute
    def wan_approval(context):
        if context.action_code == 'provision_ipoe':
            return ActionOutcome('WAITING_OPERATOR', (Observation('mutation.preview',
                dict(preview_hash='f' * 64, target_fsp='0/2/9', ont_id=12,
                     serial_number='AABBCCDDEEFF0011'), 'MA5800'),), ())
        return execute(context)
    engine.execute = wan_approval
    response = client.post(base + '/advance')
    pending = response.json()['pending_interaction']
    assert pending['ref'] == 'PROVISION_IPOE'
    before = list(commands)
    response = client.post(base + '/interactions/' + pending['id'] + '/respond',
        json=dict(choice='CANCEL', approved=False, preview_hash=pending['preview_hash']))
    assert response.status_code == 200
    assert response.json()['status'] == 'RECOVERY_REQUIRED'
    assert response.json()['recovery_tasks']
    result = values[1].session.get(RunResult, response.json()['run_result_id'])
    assert result.recovery_status == 'MANUAL_REQUIRED' and result.integrity_status == 'DRAFT'
    assert commands == before and response.json()['service_port_resources'][0]['state'] == 'ACTIVE'


def test_existing_locked_run_snapshot_report_archive_remain_byte_identical(port_api, monkeypatch, tmp_path):
    client, values, engine = port_api
    client.app.state.settings.report_root = str(tmp_path / 'reports')
    _, old_run = create_run(client)
    lock_run(client, old_run)
    report_response = client.post('/api/test-runs/' + old_run['id'] + '/reports', json={'title': 'Before lifecycle'})
    assert report_response.status_code == 201
    report = report_response.json()
    archive_response = client.post('/api/reports/' + report['id'] + '/archive')
    assert archive_response.status_code == 201
    archive = archive_response.json()
    report = client.get('/api/reports/' + report['id']).json()
    old_view = client.get('/api/test-runs/' + old_run['id']).json()
    html_path = '/api/reports/' + report['id'] + '/download'
    zip_path = '/api/archives/' + archive['id'] + '/download'
    before_html, before_zip = client.get(html_path).content, client.get(zip_path).content
    commands, _, base = advance_to_port_chain(client, values, engine, monkeypatch, tmp_path)
    assert client.post(base + '/advance').status_code == 200
    assert commands.count('create_service_port') == 1
    assert client.get('/api/test-runs/' + old_run['id']).json() == old_view
    assert client.get('/api/reports/' + report['id']).json() == report
    assert client.get('/api/archives/' + archive['id']).json() == archive
    assert client.get(html_path).content == before_html
    assert client.get(zip_path).content == before_zip


@pytest.mark.parametrize('field,expected', [
    ('fsp', '0/2/9'),
    ('line_profile_id', 10),
    ('service_profile_id', 10),
])
def test_port_approval_preserves_frozen_target_for_operator(port_api, field, expected):
    client, values, engine = port_api
    _, repo, sid, _, _, state = values
    _, preview = prepared(values)
    engine._interaction(repo.get(sid),
        dict(ref='SERVICE_1_CREATE', action='create_service_port', step='REGISTER'),
        ['CONFIRM', 'CANCEL'], preview.to_payload())
    repo.session.commit()
    reads = state['reads']

    response = client.get('/api/skill-executions/' + sid)

    assert response.status_code == 200, response.text
    pending = response.json()['pending_interaction']
    assert pending['preview_hash'] == preview.preview_hash
    assert pending['target'].get(field) == expected, 'Approval omits frozen target context'
    assert state['writes'] == [] and state['reads'] == reads


def test_creation_approval_exposes_complete_mapping_hashes_and_consumers(port_api):
    client, values, engine = port_api
    _, repo, sid, _, _, _ = values
    _, preview = prepared(values)
    payload = preview.to_payload()
    payload['password'] = 'fixture-never-echo'
    engine._interaction(repo.get(sid),
        dict(ref='SERVICE_1_CREATE', action='create_service_port', step='REGISTER'),
        ['CONFIRM', 'CANCEL'], payload)
    repo.session.commit()
    response = client.get('/api/skill-executions/' + sid)
    assert response.status_code == 200
    pending = response.json()['pending_interaction']
    assert pending['action_code'] == 'create_service_port'
    detail = pending.get('service_port_preview')
    assert detail is not None, 'Operator needs a complete typed impact preview'
    operation = detail['operations'][0]
    assert operation['kind'] == 'CREATE' and operation['port_id'] == 53
    assert operation['mapping']['vlan'] == 1000
    assert operation['mapping']['gemport'] == 1
    assert operation['mapping']['user_vlan'] == 1000
    assert operation['mapping']['tag_transform'] == 'translate'
    assert operation['mapping']['business_type'] == 'multi-service'
    assert operation['consumers'] == ['IPOE', 'PPPOE']
    assert operation['baseline_hash'] == values[4]
    assert operation['read_hash'] == 'd' * 64
    assert detail['evidence_ids'] and detail['retained_consumers'] == []
    assert 'fixture-never-echo' not in response.text and 'storage_path' not in response.text


def test_cleanup_approval_displays_all_provenance_and_retained_consumers(port_api):
    client, values, engine = port_api
    lifecycle, repo, sid, _, _, state = values
    operation, preview = prepared(values)
    assert lifecycle.execute_approved(operation, preview.preview_hash).status == 'PASS'
    state['read'] = 'FOUND'
    previews = lifecycle.preview_cleanup(sid, frozenset())
    payload = cleanup_batch_payload(previews, frozenset())
    engine._interaction(repo.get(sid),
        dict(ref='CLEANUP', action='cleanup_service_ports', step='FINISH'),
        ['CONFIRM', 'CANCEL'], payload)
    repo.session.commit()
    response = client.get('/api/skill-executions/' + sid)
    assert response.status_code == 200
    pending = response.json()['pending_interaction']
    detail = pending.get('service_port_preview')
    assert detail is not None
    assert pending['action_code'] == 'cleanup_service_ports'
    assert pending['affected_service_ports'] == [53]
    assert detail['operations'][0]['kind'] == 'DELETE'
    assert detail['operations'][0]['creation_event_id']
    assert detail['retained_consumers'] == []


def test_tampered_stored_port_preview_is_not_presented_as_approvable(port_api):
    client, values, engine = port_api
    _, repo, sid, _, _, state = values
    _, preview = prepared(values)
    payload = preview.to_payload()
    payload['operation']['mapping']['gemport'] = 2
    engine._interaction(repo.get(sid),
        dict(ref='SERVICE_1_CREATE', action='create_service_port', step='REGISTER'),
        ['CONFIRM', 'CANCEL'], payload)
    repo.session.commit()
    response = client.get('/api/skill-executions/' + sid)
    assert response.status_code == 409
    assert state['writes'] == []
