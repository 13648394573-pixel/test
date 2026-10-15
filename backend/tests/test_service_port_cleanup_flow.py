"""Real local API, transactions and proof storage; physical I/O is offline only."""
import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.local_runner.ma5800.service_port_contracts import PortOperation, ServicePortMapping
from app.models.test_execution import RunResult
from app.models.evidence import Evidence
from sqlalchemy import select
from app.skill_execution.coordinator import SkillCoordinator
from app.skill_execution.router import get_service
from app.skill_execution.service import SkillExecutionService
from test_service_port_cleanup import cleanup_lab
from test_skill_execution_repository import execution_fixture
from test_skill_execution_api import Runtime
from test_service_port_creation import lab, prepared
from test_service_port_lifecycle_api import port_api
from test_service_port_cleanup import delete_runtime


@pytest.fixture
def cleanup_api(cleanup_lab, tmp_path):
    def build(*, created=True):
        lifecycle, repo, sid, maps, state = cleanup_lab(create=created)
        def execute(context):
            if context.action_code == 'inspect_service_port':
                return lifecycle.inspect_device(sid, ServicePortMapping.model_validate(context.parameters['service_port_mapping']))
            assert context.action_code == 'delete_service_port'
            return lifecycle.delete_device(PortOperation.model_validate(context.parameters['port_operation']), context.parameters['port_approval'])
        engine = SkillCoordinator(repo, execute=execute, storage=lifecycle.storage, workspace=tmp_path / 'runner')
        result = repo.session.get(RunResult, repo.get(sid).run_result_id)
        step = dict(ref='END_POLICY', interaction=['KEEP', 'CANCEL'], step='FINISH')
        engine._interaction(repo.get(sid), step, step['interaction'], engine._preview(result, step))
        repo.session.commit()
        settings = Settings(_env_file=None, allow_metadata_create_all=True,
            database_url=str(repo.session.get_bind().url), log_file=str(tmp_path / 'api.log'),
            evidence_root=str(tmp_path / 'evidence'), local_runner_evidence_root=str(tmp_path / 'runner'))
        app = create_app(settings)
        app.state.skill_execution_runtime = Runtime()
        service = SkillExecutionService(repo, credential_available=lambda _: True, coordinator=engine)
        app.dependency_overrides[get_service] = lambda: service
        return app, repo, sid, state, lifecycle, maps
    return build


def test_operator_previews_and_executes_all_owned_ports_without_resuming_or_locking(cleanup_api):
    app, repo, sid, state, *_ = cleanup_api()
    with TestClient(app, base_url='http://127.0.0.1') as client:
        base = '/api/skill-executions/' + sid
        response = client.post(base + '/cleanup-preview', json={})
        assert response.status_code == 200, response.text
        preview = response.json()['cleanup_preview']
        assert [op['port_id'] for op in preview['operations']] == [53, 54]
        assert all(op['kind'] == 'DELETE' and op['creation_event_id'] for op in preview['operations'])
        assert preview['evidence_ids'] and state['deletes'] == []
        assert response.json()['status'] == 'WAITING_OPERATOR'
        response = client.post(base + '/cleanup-execute', json={'approved': True, 'preview_hash': preview['preview_hash']})
        assert response.status_code == 200, response.text
        assert state['deletes'] == [53, 54]
        assert response.json()['status'] == 'RECOVERY_REQUIRED'
        assert response.json()['cleanup_outcome']['status'] == 'PASS'
        assert [item['state'] for item in response.json()['service_port_resources']] == ['DELETED', 'DELETED']
        assert response.json()['integrity_status'] == 'DRAFT' and response.json()['result'] != 'PASS'
        reads = len(state['reads'])
        assert client.post(base + '/cleanup-execute', json={'approved': True, 'preview_hash': preview['preview_hash']}).status_code == 200
        assert len(state['reads']) == reads and state['deletes'] == [53, 54]
        assert client.post(base + '/advance').json()['status'] == 'RECOVERY_REQUIRED'


@pytest.mark.parametrize('status,locked', [('RUNNING', False), ('CREATED', False), ('COMPLETED', False),
    ('CANCELLED', False), ('WAITING_OPERATOR', True)])
def test_cleanup_rejects_active_or_historical_scope_before_io(cleanup_api, status, locked):
    app, repo, sid, state, *_ = cleanup_api()
    repo.get(sid).status = status
    if locked:
        repo.session.get(RunResult, repo.get(sid).run_result_id).integrity_status = 'LOCKED'
    repo.session.commit()
    # Do not run startup recovery: the request boundary itself must reject the current scope.
    client = TestClient(app, base_url='http://127.0.0.1')
    response = client.post('/api/skill-executions/' + sid + '/cleanup-preview', json={})
    assert response.status_code == 409
    assert state['reads'] == [] and state['deletes'] == []


@pytest.mark.parametrize('extra', [{'owned': True}, {'ports': [53]}, {'retained_consumers': []}, {'command': 'fixture'}])
def test_client_cannot_supply_cleanup_scope(cleanup_api, extra):
    app, _, sid, state, *_ = cleanup_api()
    response = TestClient(app, base_url='http://127.0.0.1').post('/api/skill-executions/' + sid + '/cleanup-preview', json=extra)
    assert response.status_code == 422
    assert state['reads'] == state['deletes'] == []


def test_stale_preview_or_missing_approval_does_not_delete(cleanup_api):
    app, _, sid, state, *_ = cleanup_api()
    client = TestClient(app, base_url='http://127.0.0.1')
    base = '/api/skill-executions/' + sid
    first = client.post(base + '/cleanup-preview', json={})
    assert first.status_code == 200
    old = first.json()['cleanup_preview']['preview_hash']
    assert client.post(base + '/cleanup-preview', json={}).status_code == 200
    for body in [{'approved': True, 'preview_hash': old}, {'approved': False, 'preview_hash': old}]:
        assert client.post(base + '/cleanup-execute', json=body).status_code == 409
    assert state['deletes'] == []


def test_partial_cleanup_is_audited_and_never_retried(cleanup_api):
    app, _, sid, state, *_ = cleanup_api()
    state['fail'] = 53
    client = TestClient(app, base_url='http://127.0.0.1')
    base = '/api/skill-executions/' + sid
    response = client.post(base + '/cleanup-preview', json={})
    assert response.status_code == 200
    body = {'approved': True, 'preview_hash': response.json()['cleanup_preview']['preview_hash']}
    response = client.post(base + '/cleanup-execute', json=body)
    assert response.status_code == 200
    assert response.json()['cleanup_outcome']['status'] == 'BLOCKED'
    assert response.json()['cleanup_outcome']['items'] == [{'port_id': 53, 'status': 'UNCERTAIN'}, {'port_id': 54, 'status': 'NOT_PROCESSED'}]
    assert response.json()['status'] == 'RECOVERY_REQUIRED'
    reads = len(state['reads'])
    assert client.post(base + '/cleanup-execute', json=body).status_code == 200
    assert state['deletes'] == [53] and len(state['reads']) == reads


def test_reused_resources_are_excluded_from_platform_cleanup(cleanup_api):
    app, _, sid, state, lifecycle, maps = cleanup_api(created=False)
    # Capture an existing resource before entering the end confirmation.
    repo = lifecycle.repository
    repo.get(sid).status = 'RUNNING'
    repo.session.commit()
    state['ports'][53] = maps[0].model_dump(mode='json')
    lifecycle.inspect(sid, maps[0])
    repo.get(sid).status = 'WAITING_OPERATOR'
    repo.session.commit()
    state['reads'].clear()
    response = TestClient(app, base_url='http://127.0.0.1').post('/api/skill-executions/' + sid + '/cleanup-preview', json={})
    assert response.status_code == 200
    assert response.json()['cleanup_preview']['operations'] == []
    assert state['ports'][53] and state['reads'] == state['deletes'] == []


def test_locked_during_cleanup_preview_stops_before_persisting_new_evidence(cleanup_api):
    app, repo, sid, state, lifecycle, _ = cleanup_api()
    service = app.dependency_overrides[get_service]()
    execute = service.coordinator.execute
    before = len(repo.session.scalars(select(Evidence)).all())
    def lock_during_read(context):
        outcome = execute(context)
        repo.session.get(RunResult, repo.get(sid).run_result_id).integrity_status = 'LOCKED'
        repo.session.commit()
        return outcome
    service.coordinator.execute = lock_during_read
    response = TestClient(app, base_url='http://127.0.0.1').post('/api/skill-executions/' + sid + '/cleanup-preview', json={})
    assert response.status_code == 409
    assert len(repo.session.scalars(select(Evidence)).all()) == before
    assert state['deletes'] == []


@pytest.mark.parametrize('state', ['CANCELLED', 'COMPLETED', 'LOCKED'])
def test_cleanup_never_resurrects_terminal_or_locked_scope_after_device_io(cleanup_api, state):
    app, repo, sid, device, *_ = cleanup_api()
    service = app.dependency_overrides[get_service]()
    client = TestClient(app, base_url='http://127.0.0.1')
    base = '/api/skill-executions/' + sid
    preview = client.post(base + '/cleanup-preview', json={})
    assert preview.status_code == 200
    execute = service.coordinator.execute
    changed = {}
    def change_scope_after_io(context):
        outcome = execute(context)
        if context.action_code == 'delete_service_port':
            execution = repo.get(sid)
            result = repo.session.get(RunResult, execution.run_result_id)
            if state == 'LOCKED':
                result.integrity_status = 'LOCKED'
            else:
                execution.status = state
                result.run.execution_status = state
            repo.session.commit()
            changed['fields'] = (execution.status, result.run.execution_status, result.integrity_status, result.recovery_status)
        return outcome
    service.coordinator.execute = change_scope_after_io
    response = client.post(base + '/cleanup-execute', json={'approved': True,
        'preview_hash': preview.json()['cleanup_preview']['preview_hash']})
    assert response.status_code == 409
    execution = repo.get(sid)
    result = repo.session.get(RunResult, execution.run_result_id)
    assert (execution.status, result.run.execution_status, result.integrity_status, result.recovery_status) == changed['fields']
    assert device['deletes'] == [53]
    assert not any(e.event_type == 'SERVICE_PORT_CLEANUP_OUTCOME' for e in repo.events(sid))


def test_platform_cleanup_calls_guarded_bound_runner_and_verifies_global_absence(port_api, monkeypatch, tmp_path):
    client, values, engine = port_api
    lifecycle, repo, sid, _, _, _ = values
    commands, ports, run = delete_runtime(values, monkeypatch, tmp_path)
    operation, preview = prepared(values)
    assert lifecycle.execute_approved(operation, preview.preview_hash).status == 'PASS'
    result = repo.session.get(RunResult, repo.get(sid).run_result_id)
    step = dict(ref='END_POLICY', interaction=['KEEP', 'CANCEL'], step='FINISH')
    engine._interaction(repo.get(sid), step, step['interaction'], engine._preview(result, step))
    repo.session.commit()
    engine.execute = lambda context: run(context.action_code,
        PortOperation.model_validate(context.parameters['port_operation']) if 'port_operation' in context.parameters else None,
        context.parameters.get('port_approval'))
    base = '/api/skill-executions/' + sid
    response = client.post(base + '/cleanup-preview', json={})
    assert response.status_code == 200, response.text
    assert commands.count('remove_service_port') == 0
    response = client.post(base + '/cleanup-execute', json={'approved': True, 'preview_hash': response.json()['cleanup_preview']['preview_hash']})
    assert response.status_code == 200, response.text
    assert response.json()['cleanup_outcome']['status'] == 'PASS'
    assert commands.count('remove_service_port') == 1 and ports == {}
    assert response.json()['service_port_resources'][0]['state'] == 'DELETED'
