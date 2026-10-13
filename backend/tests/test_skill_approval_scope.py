from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app.local_runner.contracts import ActionOutcome, Observation
from app.local_runner.ma5800.actions import MA5800Actions
from app.models.execution_session import ConfigurationSnapshot
from app.models.test_execution import RunResult, TestRun
from test_skill_coordinator import coordinator
from test_skill_execution_repository import execution_fixture


def port(port_id=288, fsp='0/2/9', ont_id=12):
    return dict(service_port_id=port_id, fsp=fsp, ont_id=ont_id, vlan=1000, gemport=1, user_vlan=1000)


class NoDeviceExecutor:
    def run(self, _command):
        raise AssertionError('No device command is permitted in scope-preview tests')


def setup_scope(execution_fixture, tmp_path, ports):
    service, repo, command, _ = coordinator(execution_fixture, tmp_path)
    snapshot = dict(registration=dict(fsp='0/2/9', ont_id=12,
        serial_number='AABBCCDDEEFF0011', line_profile_id=10, service_profile_id=10,
        run_state='online', config_state='normal', match_state='match'), wan=[], service_ports=deepcopy(ports))
    actions = MA5800Actions(NoDeviceExecutor())
    def driver(context):
        if context.action_code == 'snapshot_ont':
            return ActionOutcome('PASS', (Observation('olt.configuration_snapshot', deepcopy(snapshot), 'MA5800'),), ())
        if context.action_code == 'find_free_ont_id':
            return ActionOutcome('PASS', (Observation('olt.free_ont_id', 16, 'MA5800'),), ())
        if context.action_code == 'delete_ont':
            return actions.delete_ont(context)
        if context.action_code == 'register_ont':
            return actions.register_ont(context)
        return ActionOutcome('PASS', (), ())
    service.coordinator.execute = driver
    execution = service.create_execution(command)
    for _ in range(4):
        service.advance(execution.id)
    return service, repo, execution


@pytest.mark.parametrize('ports,expected', [
    ([port()], [288]),
    ([port(289), port(288)], [288, 289]),
    ([port(), port(299, fsp='0/2/90'), port(300, ont_id=13)], [288]),
    ([], []),
])
def test_delete_approval_uses_only_owned_snapshot_ports_without_rewriting_snapshots(execution_fixture, tmp_path, ports, expected):
    service, repo, execution = setup_scope(execution_fixture, tmp_path, ports)
    result = repo.session.get(RunResult, execution.run_result_id)
    before_parameters = deepcopy(result.parameter_snapshot)
    before_snapshot = deepcopy(repo.get(execution.id).configuration_snapshots[0].snapshot_json)
    before_hash = repo.get(execution.id).configuration_snapshots[0].sha256
    service.advance(execution.id)
    current = repo.get(execution.id)
    assert current.status == 'WAITING_OPERATOR'
    preview = current.operator_interactions[0].impact_preview
    assert preview['action_code'] == 'delete_ont' and preview['ont_id'] == 12
    assert preview['affected_service_ports'] == expected
    assert result.parameter_snapshot == before_parameters
    assert current.configuration_snapshots[0].snapshot_json == before_snapshot
    assert current.configuration_snapshots[0].sha256 == before_hash


def test_old_empty_scope_hash_cannot_approve_new_nonempty_preview(execution_fixture, tmp_path):
    service, repo, execution = setup_scope(execution_fixture, tmp_path, [port()])
    service.advance(execution.id)
    current = repo.get(execution.id)
    interaction = current.operator_interactions[0]
    legacy = dict(action_code='delete_ont', target_fsp='0/2/9', ont_id=12,
        serial_number='AABBCCDDEEFF0011', affected_service_ports=[],
        summary='Delete the existing ONU registration and affected service ports.')
    old_hash = sha256(json.dumps(legacy, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with pytest.raises(ValueError, match='Invalid choice or preview hash'):
        service.respond(execution.id, interaction.id, dict(choice='CONFIRM', approved=True, preview_hash=old_hash))
    assert repo.get(execution.id).status == 'WAITING_OPERATOR'
    assert interaction.status == 'PENDING'


def test_new_ont_target_does_not_inherit_old_ont_service_ports(execution_fixture, tmp_path):
    service, repo, execution = setup_scope(execution_fixture, tmp_path, [port()])
    run = repo.session.get(TestRun, execution.test_run_id)
    result = repo.session.get(RunResult, execution.run_result_id)
    step = next(item for item in run.execution_plan_snapshot['steps'] if item['ref'] == 'REGISTER')
    service.coordinator._action(execution, result, step, repo.events(execution.id))
    preview = repo.get(execution.id).operator_interactions[0].impact_preview
    assert preview['ont_id'] == 16
    assert preview['affected_service_ports'] == []


@pytest.mark.parametrize('ports', [None, [{}], [port(True)], [port(-1)],
    [port(fsp='bad')], [port(fsp='00/2/9')], [port(fsp='0/02/9')],
    [port(ont_id=True)], [port(), port()]])
def test_unconfirmed_snapshot_scope_never_creates_approvable_empty_preview(execution_fixture, tmp_path, ports):
    service, repo, execution = setup_scope(execution_fixture, tmp_path, ports)
    before_events = len(repo.events(execution.id))
    with pytest.raises(ValueError):
        service.advance(execution.id)
    assert not repo.get(execution.id).operator_interactions
    assert len(repo.events(execution.id)) == before_events
