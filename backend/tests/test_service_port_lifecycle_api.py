"""Read-only resource summaries and explicit reconciliation through actual local API routes."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.local_runner.ma5800.service_port_contracts import ServicePortMapping
from app.skill_execution.coordinator import SkillCoordinator
from app.skill_execution.router import get_service
from app.skill_execution.service import SkillExecutionService
from test_service_port_creation import lab, prepared
from test_service_port_recovery import interrupt_create, engine_for
from test_skill_execution_api import api, create, Runtime
from test_skill_execution_repository import execution_fixture


@pytest.fixture
def port_api(lab, tmp_path):
    values = lab()
    lifecycle, repo, sid, _, _, state = values
    settings = Settings(_env_file=None, allow_metadata_create_all=True,
        database_url=str(repo.session.get_bind().url), log_file=str(tmp_path / 'api.log'),
        evidence_root=str(tmp_path / 'evidence'), local_runner_evidence_root=str(tmp_path / 'runner'))
    engine = SkillCoordinator(repo, execute=lambda context: lifecycle.inspect_device(sid,
        ServicePortMapping.model_validate(context.parameters['service_port_mapping'])),
        storage=lifecycle.storage, workspace=tmp_path / 'runner')
    service = SkillExecutionService(repo, credential_available=lambda _: True, coordinator=engine)
    app = create_app(settings)
    app.state.skill_execution_runtime = Runtime()  # Normal offline runtime protocol, no SSH implementation.
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app, base_url='http://127.0.0.1') as client:
        yield client, values, engine


def test_old_execution_returns_empty_resource_summary(api):
    client, *_ = api
    view = create(api)
    assert view.get('service_port_resources') == []
    assert client.get('/api/skill-executions/' + view['session_id']).json()['service_port_resources'] == []


def test_resource_summary_comes_from_current_session_events_only(port_api):
    client, values, _ = port_api
    lifecycle, repo, sid, _, _, state = values
    operation, preview = prepared(values)
    assert lifecycle.execute_approved(operation, preview.preview_hash).status == 'PASS'
    before = len(repo.events(sid))
    reads = state['reads']
    response = client.get('/api/skill-executions/' + sid)
    assert response.status_code == 200
    resource = response.json().get('service_port_resources')
    assert resource is not None, 'Missing API resource summary'
    assert len(resource) == 1 and resource[0]['port_id'] == 53
    assert resource[0]['origin'] == 'CREATED' and resource[0]['state'] == 'ACTIVE'
    assert resource[0]['consumers'] == ['IPOE', 'PPPOE'] and resource[0]['creation_event_id']
    assert resource[0]['evidence_ids']
    assert resource[0]['mapping']['vlan'] == 1000 and resource[0]['mapping']['fsp'] == '0/2/9'
    assert 'storage_path' not in response.text and 'password' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert len(repo.events(sid)) == before and state['reads'] == reads


@pytest.mark.parametrize('field,value', [('owned', True), ('service_ports', [53]), ('command', 'undo service-port 53')])
def test_recovery_request_cannot_supply_ownership_or_port_ids(port_api, field, value):
    client, values, _ = port_api
    sid = values[2]
    response = client.post('/api/skill-executions/' + sid + '/reconcile-service-ports', json={field: value})
    assert response.status_code == 422
    assert values[-1]['reads'] == 0 and values[-1]['writes'] == []


def test_explicit_api_reconcile_reads_but_does_not_own_or_resume(port_api):
    client, values, engine = port_api
    _, repo, sid, _, _, state = values
    interrupt_create(values)
    assert engine.recover_interrupted() == 1
    before = state['reads']
    response = client.post('/api/skill-executions/' + sid + '/reconcile-service-ports', json={})
    assert response.status_code == 200
    assert response.json()['status'] == 'RECOVERY_REQUIRED'
    resources = response.json()['service_port_resources']
    assert resources[0]['state'] == 'CREATE_UNCERTAIN' and resources[0]['creation_event_id'] is None
    assert resources[0]['reconciliation']['status'] == 'FOUND'
    assert resources[0]['reconciliation']['evidence_ids']
    assert resources[0]['reconciliation']['automatic_write_authorized'] is False
    assert state['reads'] > before and state['writes'] == [53]
    reads = state['reads']
    for _ in range(2):
        assert client.post('/api/skill-executions/' + sid + '/advance').status_code == 200
    assert state['reads'] == reads and state['writes'] == [53]


def test_recovered_pending_approval_cannot_be_responded_twice(port_api):
    client, values, engine = port_api
    _, repo, sid, _, _, state = values
    _, preview = interrupt_create(values)
    interaction = engine._interaction(repo.get(sid),
        dict(ref='SERVICE_1_CREATE', action='create_service_port', step='REGISTER'),
        ['CONFIRM', 'CANCEL'], preview.to_payload())
    repo.session.commit()
    engine.recover_interrupted()
    reads = state['reads']
    for _ in range(2):
        response = client.post('/api/skill-executions/' + sid + '/interactions/' + interaction.id + '/respond',
            json=dict(choice='CONFIRM', approved=True, preview_hash=preview.preview_hash))
        assert response.status_code == 409
    assert state['reads'] == reads and state['writes'] == [53]


def test_bad_ledger_is_rejected_without_raw_payload_or_device_io(port_api):
    client, values, _ = port_api
    _, repo, sid, _, _, state = values
    repo.append_event(sid, 'PORT_REUSED', {'version': 999, 'secret': 'fixture-do-not-echo'}, 'bad-ledger')
    repo.session.commit()
    response = client.get('/api/skill-executions/' + sid)
    assert response.status_code == 409
    assert 'fixture-do-not-echo' not in response.text
    assert state['reads'] == 0 and state['writes'] == []
