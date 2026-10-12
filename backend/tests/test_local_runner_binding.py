from copy import deepcopy
import json

import pytest
from sqlalchemy import select

from app.local_runner.access import PairedAccessResolver
from app.local_runner.configuration import RunnerConfig, resolve_runtime_binding
from app.models.execution_session import ExecutionSession
from app.models.test_execution import TestRun, RunResult
from app.skill_execution.service import SkillExecutionService
from local_runner_binding_fixtures import valid_config, enrolled_resolver
from test_skill_execution_repository import execution_fixture


def bound_service(execution_fixture):
    _, repo, command = execution_fixture
    command.parameters.update(olt_access_ref='lab.olt.access',
                              onu_web_access_ref='lab.onu.access', pppoe_access_ref='lab.ppp.access')
    config = RunnerConfig.model_validate(valid_config())
    resolver = enrolled_resolver()
    pairs = PairedAccessResolver(config, resolver)
    service = SkillExecutionService(repo, credential_available=pairs.available,
        binding_resolver=lambda parameters: resolve_runtime_binding(config, parameters, pairs))
    return service, command, config, resolver


def test_binding_is_saved_in_creation_transaction(db_session, execution_fixture):
    service, command, _, _ = bound_service(execution_fixture)
    execution = service.create_execution(command)
    binding = execution.plugin_snapshot['runtime_binding']
    assert binding['version'] == 1
    assert binding['olt']['host'] == '10.20.0.2'
    assert binding['access_bindings']['OLT']['username_ref'] == 'fixture.olt.user'
    assert 'sensitive' not in json.dumps(binding)


@pytest.mark.parametrize('changes,missing', [
    ({'olt_target_ref': 'unknown'}, None),
    ({'olt_target_ref': 'lab.onu'}, None),
    ({'olt_access_ref': 'lab.onu.access'}, None),
    ({}, 'fixture.olt.pass'),
])
def test_invalid_binding_creates_no_run(db_session, execution_fixture, changes, missing):
    service, command, _, resolver = bound_service(execution_fixture)
    command.parameters.update(changes)
    if missing:
        resolver.delete(missing)
    with pytest.raises(ValueError):
        service.create_execution(command)
    for model in (TestRun, RunResult, ExecutionSession):
        assert db_session.scalars(select(model)).all() == []


def test_config_change_does_not_change_persisted_binding(db_session, execution_fixture):
    service, command, config, resolver = bound_service(execution_fixture)
    execution = service.create_execution(command)
    run = db_session.get(TestRun, execution.test_run_id)
    result = db_session.get(RunResult, execution.run_result_id)
    original = deepcopy((result.parameter_snapshot, run.standard_snapshot,
                         run.environment_snapshot.profile_snapshot, execution.plugin_snapshot))
    changed = valid_config()
    changed['targets']['lab.olt']['host'] = '10.20.0.3'
    new_config = RunnerConfig.model_validate(changed)
    new_pairs = PairedAccessResolver(new_config, resolver)
    new = resolve_runtime_binding(new_config, result.parameter_snapshot, new_pairs)
    assert new.olt.host == '10.20.0.3'
    assert new.config_sha256 != config.sha256
    db_session.expire_all()
    assert execution.plugin_snapshot['runtime_binding']['olt']['host'] == '10.20.0.2'
    assert (result.parameter_snapshot, run.standard_snapshot,
            run.environment_snapshot.profile_snapshot, execution.plugin_snapshot) == original
    with pytest.raises(TypeError):
        new.access_bindings['OLT'] = new.access_bindings['ONU_WEB']
