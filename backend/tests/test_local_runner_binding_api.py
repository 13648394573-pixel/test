from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.local_runner.configuration import RunnerConfig
from app.local_runner.runtime import LocalRuntimeFactory, RuntimeResources
from app.models.execution_session import ExecutionSession
from app.models.test_execution import RunResult, TestRun
from local_runner_binding_fixtures import valid_config, enrolled_resolver
from test_local_runner_runtime import Connector
from test_skill_execution_repository import execution_fixture


@pytest.fixture
def bound_api(execution_fixture, tmp_path):
    legacy, repo, command = execution_fixture
    command.parameters.update(olt_access_ref='lab.olt.access', onu_web_access_ref='lab.onu.access',
                              pppoe_access_ref='lab.ppp.access')
    settings = Settings(_env_file=None, allow_metadata_create_all=True,
        database_url=str(repo.session.get_bind().url), log_file=str(tmp_path / 'app.log'),
        evidence_root=str(tmp_path / 'evidence'), local_runner_evidence_root=str(tmp_path / 'runner'))
    resolver = enrolled_resolver()
    connector = Connector()
    resources = RuntimeResources(ssh_connector_factory=lambda: connector, interface_provider=lambda: [])
    factory = LocalRuntimeFactory(RunnerConfig.model_validate(valid_config()), resolver, resources)
    payload = dict(project_id=command.project_id, device_id=command.device_id,
        environment_id=command.environment_id, skill_id=command.skill_id, parameters=command.parameters)
    app = create_app(settings, credential_resolver=resolver, skill_execution_runtime=factory)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        yield client, payload, repo, settings, resolver, connector, resources, legacy, command


def create(bound_api):
    client, payload, *_ = bound_api
    response = client.post('/api/skill-executions', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_persists_binding_without_network(bound_api):
    client, _, repo, _, _, connector, *_ = bound_api
    view = create(bound_api)
    assert connector.calls == []
    binding = repo.get(view['session_id']).plugin_snapshot['runtime_binding']
    assert binding['olt']['host'] == '10.20.0.2'
    assert 'runtime_binding' not in json.dumps(view)
    assert 'fixture.olt' not in json.dumps(view)


def test_unconfigured_create_rejects_before_run(bound_api):
    client, payload, repo, *_ = bound_api
    client.app.state.skill_execution_runtime = None
    response = client.post('/api/skill-executions', json=payload)
    assert response.status_code == 422
    assert repo.session.scalars(select(TestRun)).all() == []


def test_legacy_session_readable_but_cannot_advance_or_respond(bound_api):
    client, _, repo, _, _, connector, _, legacy, command = bound_api
    execution = legacy.create_execution(command)
    before = deepcopy(execution.plugin_snapshot)
    base = '/api/skill-executions/' + execution.id
    assert client.get(base).status_code == 200
    for path, payload in [('/advance', None),
            ('/interactions/legacy/respond', dict(choice='CONFIRM', approved=True, preview_hash='a' * 64))]:
        response = client.post(base + path, json=payload)
        assert response.status_code == 409
        assert response.json()['detail'] == 'RUNTIME_BINDING_REQUIRED'
    assert repo.get(execution.id).status == 'CREATED'
    assert repo.get(execution.id).plugin_snapshot == before
    assert len(repo.events(execution.id)) == 1
    assert connector.calls == []


def test_restart_uses_old_binding_after_config_change(bound_api):
    client, _, repo, settings, resolver, connector, resources, *_ = bound_api
    view = create(bound_api)
    changed = valid_config()
    changed['targets']['lab.olt']['host'] = '10.20.0.3'
    changed['access_bindings']['lab.olt.access']['password_ref'] = 'changed.olt.pass'
    resolver.enroll('changed.olt.pass', 'new-password-sensitive')
    new_factory = LocalRuntimeFactory(RunnerConfig.model_validate(changed), resolver, resources)
    with TestClient(create_app(settings, credential_resolver=resolver, skill_execution_runtime=new_factory),
                    base_url='http://127.0.0.1') as restarted:
        base = '/api/skill-executions/' + view['session_id']
        assert restarted.post(base + '/advance').status_code == 200  # preflight, no network
        assert restarted.post(base + '/advance').status_code == 200  # discovery
        assert connector.calls[0]['hostname'] == '10.20.0.2'
        assert connector.calls[0]['password'] == 'fixture-password-sensitive'
        assert 'sensitive' not in restarted.get(base).text
    assert repo.get(view['session_id']).plugin_snapshot['runtime_binding']['olt']['host'] == '10.20.0.2'


def test_missing_old_leaf_blocks_without_fallback(bound_api):
    client, _, repo, _, resolver, connector, *_ = bound_api
    view = create(bound_api)
    resolver.delete('fixture.olt.pass')
    response = client.post('/api/skill-executions/' + view['session_id'] + '/advance')
    assert response.status_code == 200
    outcomes = [e for e in repo.events(view['session_id']) if e.event_type == 'ACTION_OUTCOME']
    assert outcomes[-1].payload_json['status'] == 'BLOCKED'
    assert connector.calls == []
    assert 'sensitive' not in response.text


def test_configuration_loading_at_app_creation_is_network_free(bound_api, tmp_path):
    _, _, _, settings, resolver, connector, *_ = bound_api
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(valid_config()), encoding='utf-8')
    settings.local_runner_config_path = str(path)
    app = create_app(settings, credential_resolver=resolver)
    assert isinstance(app.state.skill_execution_runtime, LocalRuntimeFactory)
    assert connector.calls == []


def test_startup_interrupts_running_without_device_actions(bound_api):
    _, _, repo, settings, resolver, connector, resources, *_ = bound_api
    view = create(bound_api)
    execution = repo.get(view['session_id'])
    execution.status = 'RUNNING'
    repo.session.commit()
    factory = LocalRuntimeFactory(RunnerConfig.model_validate(valid_config()), resolver, resources)
    with TestClient(create_app(settings, credential_resolver=resolver, skill_execution_runtime=factory)):
        pass
    assert repo.get(execution.id).status == 'RECOVERY_REQUIRED'
    assert connector.calls == []
