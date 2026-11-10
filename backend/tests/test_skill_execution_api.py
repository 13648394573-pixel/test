from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.local_runner.contracts import ActionOutcome, Observation
from app.local_runner.credentials import CredentialResolver, FakeCredentialStore
from app.models.evidence import Evidence
from app.models.execution_session import ExecutionSession, OperatorInteraction, RecoveryTask
from app.models.test_execution import RunResult, TestRun
from app.skill_execution.coordinator import SkillCoordinator
from test_skill_execution_repository import execution_fixture


class Runtime:
    def resolve_binding(self, parameters):
        from app.local_runner.configuration import RuntimeBinding, RunnerConfig
        from local_runner_binding_fixtures import valid_config
        config = RunnerConfig.model_validate(valid_config())
        return RuntimeBinding(config_sha256=config.sha256,
            olt_target_ref=parameters['olt_target_ref'], onu_web_target_ref=parameters['onu_web_target_ref'],
            olt=config.targets['lab.olt'], onu=config.targets['lab.onu'],
            access_bindings={pair.kind: pair for pair in config.access_bindings.values()})

    def for_binding(self, binding, history_reader):
        return self

    def available(self, reference):
        return True

    def secrets_for(self, parameters, action):
        return {}

    def execute(self, context):
        return ActionOutcome('WAITING_OPERATOR',
            (Observation('mutation.preview', dict(preview_hash='a' * 64,
                target_fsp='0/2/9', ont_id=12, serial_number='AABBCCDDEEFF0011',
                affected_service_ports=[100, 101], summary='password=must-not-echo',
                command='must-not-echo'), 'MA5800'),), ())


@pytest.fixture
def api(execution_fixture, tmp_path):
    service, repo, command = execution_fixture
    settings = Settings(_env_file=None, allow_metadata_create_all=True,
        database_url=str(repo.session.get_bind().url), log_file=str(tmp_path / 'api.log'),
        evidence_root=str(tmp_path / 'evidence'), local_runner_evidence_root=str(tmp_path / 'runner'))
    resolver = CredentialResolver(FakeCredentialStore())
    for ref in ['olt.access', 'onu.access', 'ppp.access']:
        resolver.enroll(ref, 'must-not-echo')
    app = create_app(settings, credential_resolver=resolver)
    app.state.skill_execution_runtime = Runtime()
    payload = dict(project_id=command.project_id, device_id=command.device_id,
        environment_id=command.environment_id, skill_id=command.skill_id, parameters=command.parameters)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        yield client, payload, repo, settings, resolver


def create(api):
    client, payload, *_ = api
    response = client.post('/api/skill-executions', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_read_snapshotted_execution(api):
    client, _, repo, *_ = api
    view = create(api)
    assert view['skill_code'] == 'ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY'
    assert view['wan_mode'] == 'SEQUENTIAL_ISOLATED'
    assert view['status'] == 'CREATED'
    assert view['integrity_status'] == 'DRAFT'
    assert view['pending_interaction'] is None
    response = client.get('/api/skill-executions/' + view['session_id'])
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert len(response.json()['events']) == 1
    assert 'must-not-echo' not in response.text
    assert len(repo.session.scalars(select(TestRun)).all()) == 1


def test_active_conflict_has_no_partial_second_run(api):
    client, payload, repo, *_ = api
    create(api)
    assert client.post('/api/skill-executions', json=payload).status_code == 409
    assert len(repo.session.scalars(select(TestRun)).all()) == 1


@pytest.mark.parametrize('parameters', [
    {'execution_mode': 'invalid'}, {'olt_vendor': 'other'}, {'password': 'must-not-echo'},
    {'olt_access_ref': 'http://name:must-not-echo@device'},
    {'mutation_approval': {'approved': True}}, {'frame': 100},
])
def test_invalid_parameters_do_not_create_or_echo_secrets(api, parameters):
    client, payload, repo, *_ = api
    payload['parameters'].update(parameters)
    response = client.post('/api/skill-executions', json=payload)
    assert response.status_code == 422
    assert 'must-not-echo' not in response.text
    assert repo.session.scalars(select(TestRun)).all() == []


def test_request_schema_rejects_unknown_fields_and_bad_identifiers(api):
    client, payload, *_ = api
    payload['command'] = 'must-not-echo'
    response = client.post('/api/skill-executions', json=payload)
    assert response.status_code == 422
    assert 'must-not-echo' not in response.text
    del payload['command']
    payload['project_id'] = 'bad'
    assert client.post('/api/skill-executions', json=payload).status_code == 422


@pytest.mark.parametrize('path,method', [
    ('', 'get'), ('/advance', 'post'), ('/evidence', 'get'),
    ('/interactions/' + str(uuid4()) + '/respond', 'post'),
])
def test_unknown_session_is_404(api, path, method):
    client, *_ = api
    kwargs = {'json': dict(choice='CONFIRM', approved=True, preview_hash='a' * 64)} if 'respond' in path else {}
    assert getattr(client, method)('/api/skill-executions/' + str(uuid4()) + path, **kwargs).status_code == 404


def test_advance_and_approval_do_not_execute_another_action(api):
    client, _, repo, *_ = api
    view = create(api)
    base = '/api/skill-executions/' + view['session_id']
    response = client.post(base + '/advance')
    assert response.status_code == 200
    pending = response.json()['pending_interaction']
    assert response.json()['status'] == 'WAITING_OPERATOR'
    assert pending['preview_hash'] == 'a' * 64
    assert pending['target']['ont_id'] == 12
    assert pending['affected_service_ports'] == [100, 101]
    assert pending['action_code'] == 'preflight'
    assert 'must-not-echo' not in response.text
    assert 'command' not in response.text
    assert client.post(base + '/advance').json()['status'] == 'WAITING_OPERATOR'
    url = base + '/interactions/' + pending['id'] + '/respond'
    assert client.post(url, json=dict(choice='CONFIRM', approved=True, preview_hash='b' * 64)).status_code == 409
    assert repo.session.get(OperatorInteraction, pending['id']).status == 'PENDING'
    response = client.post(url, json=dict(choice='CONFIRM', approved=True, preview_hash='a' * 64))
    assert response.status_code == 200
    assert response.json()['status'] == 'RUNNING'
    assert client.post(url, json=dict(choice='CONFIRM', approved=True, preview_hash='a' * 64)).status_code == 409


def test_unconfigured_runtime_cannot_start_or_change_existing_execution(api):
    client, _, repo, *_ = api
    view = create(api)
    client.app.state.skill_execution_runtime = None
    base = '/api/skill-executions/' + view['session_id']
    assert client.post(base + '/advance').status_code == 409
    assert repo.get(view['session_id']).status == 'CREATED'
    assert len(repo.events(view['session_id'])) == 1
    assert client.get(base).status_code == 200


def test_other_execution_session_is_not_exposed_or_advanced(api):
    client, _, repo, *_ = api
    view = create(api)
    other = ExecutionSession(test_run_id=view['test_run_id'], mode='MANUAL', status='RUNNING')
    repo.session.add(other)
    repo.session.commit()
    base = '/api/skill-executions/' + other.id
    assert client.get(base).status_code == 404
    assert client.post(base + '/advance').status_code == 404
    assert repo.session.get(ExecutionSession, other.id).status == 'RUNNING'


def test_public_view_uses_safe_observations_not_raw_event_payloads(api):
    client, _, repo, *_ = api
    view = create(api)
    repo.append_event(view['session_id'], 'ACTION_OUTCOME', dict(ref='fixture', status='PASS',
        observations=[dict(fact_key='olt.autofind.matched', value=True, source='MA5800'),
            dict(fact_key='raw_output', value='must-not-echo', source='MA5800'),
            dict(fact_key='olt.registration.ready', value='must-not-echo', source='MA5800')]), 'fixture:outcome')
    repo.session.commit()
    response = client.get('/api/skill-executions/' + view['session_id'])
    assert response.status_code == 200
    assert response.json()['observations'] == [
        dict(fact_key='olt.autofind.matched', value=True, source='MA5800')]
    assert 'must-not-echo' not in response.text
    assert 'payload' not in response.text


def test_evidence_list_checks_hash_and_never_exposes_storage_path(api):
    from app.evidence.storage import EvidenceStorage
    client, _, repo, settings, _ = api
    view = create(api)
    storage = EvidenceStorage(settings.evidence_root, max_bytes=1024)
    content = b'test-only-evidence'
    stored = storage.store('run-results', view['run_result_id'], 'fixture.txt', BytesIO(content))
    artifact = Evidence(run_result_id=view['run_result_id'], execution_session_id=view['session_id'],
        category='LOG', original_name='must-not-echo', media_type='text/plain',
        storage_path=stored.storage_path, file_size=stored.file_size, sha256=stored.sha256,
        step_ref='PREFLIGHT', capture_method='OLT_RENDER', redacted=True)
    repo.session.add(artifact)
    repo.session.commit()
    url = '/api/skill-executions/' + view['session_id'] + '/evidence'
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()[0]['sha256'] == sha256(content).hexdigest()
    download = url + '/' + artifact.id + '/download'
    assert response.json()[0]['download_url'] == download
    downloaded = client.get(download)
    assert downloaded.status_code == 200 and downloaded.content == content
    assert downloaded.headers['cache-control'] == 'no-store'
    assert 'must-not-echo' not in downloaded.headers['content-disposition']
    alias = '/api/evidences/' + artifact.id + '/download'
    assert 'must-not-echo' not in client.get(alias).headers['content-disposition']
    assert client.get(url + '/' + str(uuid4()) + '/download').status_code == 404
    assert client.get('/api/skill-executions/' + str(uuid4()) + '/evidence/' + artifact.id + '/download').status_code == 404
    assert 'storage_path' not in response.text and 'must-not-echo' not in response.text
    storage.open_path(stored.storage_path).write_bytes(b'tampered')
    assert client.get(url).status_code == 409
    assert client.get(download).status_code == 409
    assert client.get(alias).status_code == 409
    storage.open_path(stored.storage_path).unlink()
    assert client.get(url).status_code == 410
    assert client.get(download).status_code == 410


def test_startup_recovers_running_and_preserves_waiting(api):
    client, _, repo, settings, resolver = api
    first = create(api)
    running = repo.get(first['session_id'])
    running.status = 'RUNNING'
    waiting = ExecutionSession(test_run_id=first['test_run_id'], mode='DEVELOPMENT',
        status='WAITING_OPERATOR', plugin_snapshot={'code': 'ONU_LOCAL_RUNNER'})
    repo.session.add(waiting)
    repo.session.commit()
    with TestClient(create_app(settings, credential_resolver=resolver)):
        pass
    assert repo.get(first['session_id']).status == 'RECOVERY_REQUIRED'
    assert repo.session.get(RunResult, first['run_result_id']).recovery_status == 'MANUAL_REQUIRED'
    assert repo.session.scalar(select(RecoveryTask)).status == 'MANUAL_REQUIRED'
    assert repo.get(waiting.id).status == 'WAITING_OPERATOR'


def test_cross_origin_requests_are_rejected_without_creating_runs(api):
    client, payload, repo, *_ = api
    response = client.post('/api/skill-executions', json=payload,
        headers={'Origin': 'https://malicious.example'})
    assert response.status_code == 403
    assert repo.session.scalars(select(TestRun)).all() == []


@pytest.mark.parametrize('bind', ['0.0.0.0', 'invalid-host'])
def test_non_loopback_binding_is_rejected(api, bind):
    client, payload, repo, *_ = api
    client.app.state.settings.api_bind_host = bind
    assert client.post('/api/skill-executions', json=payload).status_code == 403
    assert repo.session.scalars(select(TestRun)).all() == []


def test_execution_errors_are_not_cached(api):
    client, *_ = api
    response = client.get('/api/skill-executions/' + str(uuid4()))
    assert response.status_code == 404
    assert response.headers['cache-control'] == 'no-store'


def test_rebound_host_is_rejected_even_when_origin_matches(api):
    client, payload, repo, *_ = api
    response = client.post('/api/skill-executions', json=payload,
        headers={'Host': 'malicious.example', 'Origin': 'http://malicious.example'})
    assert response.status_code == 403
    assert repo.session.scalars(select(TestRun)).all() == []


@pytest.mark.parametrize('origin', ['http://[', 'https://127.0.0.1'])
def test_invalid_or_different_scheme_origin_is_rejected_without_mutation(api, origin):
    client, payload, repo, *_ = api
    response = client.post('/api/skill-executions', json=payload, headers={'Origin': origin})
    assert response.status_code == 403
    assert response.headers['cache-control'] == 'no-store'
    assert repo.session.scalars(select(TestRun)).all() == []


def test_same_origin_request_remains_allowed(api):
    client, payload, *_ = api
    assert client.post('/api/skill-executions', json=payload,
        headers={'Origin': 'http://127.0.0.1'}).status_code == 201


@pytest.mark.parametrize('storage_path,status', [('missing.txt', 410), ('../outside.txt', 409)])
def test_legacy_skill_download_redirects_before_file_resolution(api, storage_path, status):
    client, _, repo, *_ = api
    view = create(api)
    artifact = Evidence(run_result_id=view['run_result_id'], execution_session_id=view['session_id'],
        category='LOG', original_name='fixture.txt', media_type='text/plain',
        storage_path=storage_path, file_size=1, sha256=sha256(b'x').hexdigest(), redacted=True)
    repo.session.add(artifact)
    repo.session.commit()
    alias = '/api/evidences/' + artifact.id + '/download'
    response = client.get(alias, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['location'] == ('/api/skill-executions/' + view['session_id'] +
        '/evidence/' + artifact.id + '/download')
    checked = client.get(alias)
    assert checked.status_code == status
    assert checked.headers['cache-control'] == 'no-store'
    rejected = client.get(alias, headers={'Origin': 'https://malicious.example'})
    assert rejected.status_code == 403
    assert rejected.headers['cache-control'] == 'no-store'
