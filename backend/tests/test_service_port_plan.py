"""Versioned retained-registration plans; all device I/O is an offline double."""
from copy import deepcopy
from pathlib import Path
from dataclasses import replace
import pytest

from app.local_runner.access import PairedAccessResolver
from app.local_runner.configuration import RunnerConfig, resolve_runtime_binding
from app.local_runner.contracts import ActionContext
from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.service_port_contracts import ServicePortProfile
from app.local_runner.ma5800.transport import CommandTranscript
from app.local_runner.runtime import BoundExecutionRuntime, RuntimeResources
from app.models.test_execution import TestRun
from app.evidence.storage import EvidenceStorage
from app.skill_execution import coordinator as plans
from app.skill_execution.service import SkillExecutionService
from local_runner_binding_fixtures import valid_config, enrolled_resolver
from test_skill_execution_repository import execution_fixture
from test_skill_coordinator import coordinator
from test_ma5800_actions import FakeExecutor, valid_registration_parameters


def profile_data(**changes):
    spec = dict(vlan=1000, gemport=1, user_vlan=1000,
                tag_transform='translate', business_type='multi-service', candidate_id=53)
    value = dict(ipoe=deepcopy(spec), pppoe=deepcopy(spec))
    value.update(changes)
    return value


def profile(**changes):
    return ServicePortProfile.model_validate(profile_data(**changes))


def build(parameters=None, selected=None):
    builder = getattr(plans, 'build_service_port_plan', None)
    assert callable(builder), 'Missing retained-registration plan builder'
    values = dict(ipoe_vlan=1000, pppoe_vlan=1000, execution_mode='SEQUENTIAL_ISOLATED', end_policy='KEEP')
    values.update(parameters or {})
    return builder(values, selected or profile())


def bound(execution_fixture):
    _, repo, command = execution_fixture
    command.parameters.update(olt_access_ref='lab.olt.access', onu_web_access_ref='lab.onu.access',
                              pppoe_access_ref='lab.ppp.access', end_policy='KEEP')
    values = valid_config()
    values['service_port_profiles'] = {'lab.olt': profile_data()}
    config = RunnerConfig.model_validate(values)
    resolver = enrolled_resolver()
    pairs = PairedAccessResolver(config, resolver)
    service = SkillExecutionService(repo, credential_available=pairs.available,
        binding_resolver=lambda parameters: resolve_runtime_binding(config, parameters, pairs))
    return service, repo, command, config, resolver


def test_v2_reuses_registration_without_delete_or_register():
    plan = build()
    assert plan['version'] == 2
    actions = [step.get('action') for step in plan['steps']]
    assert 'verify_existing_registration' in actions
    assert not {'delete_ont', 'register_ont', 'find_free_ont_id', 'discover_onts'} & set(actions)
    assert not {'FREE_ID', 'DELETE_EXISTING', 'REGISTER'} & {step['ref'] for step in plan['steps']}
    assert actions.index('verify_existing_registration') < actions.index('snapshot_ont') < actions.index('inspect_service_mapping')


def test_shared_mapping_does_not_delete_for_wan_switch():
    steps = build()['steps']
    assert not {'remove_test_services', 'restore_snapshot'} & {step.get('action') for step in steps}
    shared = [step for step in steps if step.get('action') == 'inspect_service_mapping']
    assert len(shared) == 1 and shared[0]['consumers'] == ['IPOE', 'PPPOE']
    assert 'ISOLATE_IPOE' in {step['ref'] for step in steps}
    assert next(step for step in steps if step['ref'] == 'END_POLICY')['interaction'] == ['KEEP', 'CANCEL']


def test_different_mappings_have_separate_consumers():
    second = profile_data()['pppoe']
    second.update(vlan=200, user_vlan=200, candidate_id=54)
    steps = build({'pppoe_vlan': 200}, profile(pppoe=second))['steps']
    reads = [step for step in steps if step.get('action') == 'inspect_service_mapping']
    assert [step['consumers'] for step in reads] == [['IPOE'], ['PPPOE']]


def test_concurrent_retains_both_manual_wan_confirmations():
    steps = build({'execution_mode': 'CONCURRENT_DUAL_WAN'})['steps']
    refs = [step['ref'] for step in steps]
    assert 'SWITCH_IPOE' in refs and 'SWITCH_PPPOE' in refs
    assert refs.index('PROVISION_PPPOE') < refs.index('IPOE_ADDRESS_OLT')


@pytest.mark.parametrize('change', [{'ipoe_vlan': 99}, {'pppoe_vlan': 99}])
def test_profile_vlan_mismatch_is_rejected(change):
    with pytest.raises(ValueError):
        build(change)


def test_partial_dual_wan_profile_is_not_filled_with_defaults():
    with pytest.raises(ValueError):
        build(selected=profile(pppoe=None))


def test_frozen_binding_selects_v2_plan(execution_fixture):
    service, repo, command, _, _ = bound(execution_fixture)
    execution = service.create_execution(command)
    plan = repo.session.get(TestRun, execution.test_run_id).execution_plan_snapshot
    assert plan['version'] == 2
    assert next(step for step in plan['steps'] if step.get('action') == 'inspect_service_mapping')['mapping']['candidate_id'] == 53
    command.parameters['ipoe_vlan'] = 99
    assert next(step for step in plan['steps'] if step.get('action') == 'inspect_service_mapping')['mapping']['vlan'] == 1000


def test_old_plan_snapshot_is_unchanged(execution_fixture, tmp_path):
    service, repo, command, driver = coordinator(execution_fixture, tmp_path)
    execution = service.create_execution(command)
    run = repo.session.get(TestRun, execution.test_run_id)
    original = deepcopy(run.execution_plan_snapshot)
    assert original['version'] == 1
    service.binding_resolver = lambda _: None
    service.advance(execution.id)
    assert run.execution_plan_snapshot == original


def test_required_restore_blocks_before_any_write(execution_fixture, tmp_path):
    service, repo, command, _, _ = bound(execution_fixture)
    _, _, _, driver = coordinator(execution_fixture, tmp_path)
    service.coordinator = plans.SkillCoordinator(repo, execute=driver,
        storage=EvidenceStorage(tmp_path / 'ev', max_bytes=100000),
        workspace=tmp_path / 'runner')
    command.parameters['end_policy'] = 'RESTORE'
    execution = service.create_execution(command)
    service.advance(execution.id)
    assert repo.get(execution.id).status == 'BLOCKED'
    assert driver.calls == []
    assert repo.get(execution.id).error_code == 'COMPLETE_WAN_RESTORE_UNSUPPORTED'


@pytest.mark.parametrize('override', ['service_port_profile', 'owned', 'mapping'])
def test_request_cannot_override_frozen_mapping(execution_fixture, override):
    service, repo, command, _, _ = bound(execution_fixture)
    command.parameters[override] = profile_data()
    with pytest.raises(ValueError):
        service.create_execution(command)
    assert repo.session.query(TestRun).count() == 0


@pytest.mark.parametrize('problem', ['valid', 'none', 'serial', 'fsp', 'ont', 'profile', 'offline', 'gem',
                                    'duplicate-profile', 'read-failure', 'truncated'])
def test_registration_or_profile_mismatch_blocks_with_zero_writes(execution_fixture, tmp_path, monkeypatch, problem):
    _, _, command, config, resolver = bound(execution_fixture)
    parameters = {**command.parameters, **valid_registration_parameters()}
    pairs = PairedAccessResolver(config, resolver)
    binding = resolve_runtime_binding(config, parameters, pairs)
    commands = []
    class Executor(FakeExecutor):
        def __init__(self, *_):
            self.commands = commands
            self.transcripts = []
        def run(self, cmd):
            if cmd.action_code == 'read_profile_gem':
                self.commands.append(cmd)
                text = (Path(__file__).parent / 'fixtures/ma5800/profile_gem.txt').read_text(encoding='utf-8')
                if problem == 'gem':
                    text = text.replace('<Gem Index 1>', '<Gem Index 2>')
                return CommandTranscript(cmd.action_code, text, text, 'MA5800-X7(config)#', 'a' * 64)
            result = super().run(cmd)
            if cmd.action_code == 'display_ont_by_sn':
                text = result.normalized_output
                replacements = {'serial': ('48575443DD91BBBB', '4857544311223344'),
                    'fsp': ('0/2/10', '0/2/11'), 'ont': (': 36', ': 37'),
                    'profile': ('Line profile ID     : 10', 'Line profile ID     : 11'),
                    'offline': ('online', 'offline')}
                if problem == 'none':
                    text = 'Failure: ONT does not exist\nMA5800-X7#'
                elif problem in replacements:
                    text = text.replace(*replacements[problem])
                elif problem == 'duplicate-profile':
                    text = text.replace('Line profile ID     : 10', 'Line profile ID     : 11\nLine profile ID     : 10')
                elif problem == 'read-failure':
                    text = 'Failure: uncertain read\n' + text
                elif problem == 'truncated':
                    text = text.replace('MA5800-X7#', '')
                result = replace(result, normalized_output=text)
            return result
        def close(self):
            return True
    monkeypatch.setattr('app.local_runner.runtime._OLTExecutor', Executor)
    runtime = BoundExecutionRuntime(binding, resolver, RuntimeResources(), lambda: [])
    context = ActionContext('fixture-session', 'verify_existing_registration', parameters,
        {'olt_username': SecretValue('fixture-user'), 'olt_password': SecretValue('fixture-password')}, tmp_path)
    outcome = runtime.execute(context)
    assert outcome.status == ('PASS' if problem == 'valid' else 'BLOCKED')
    if problem == 'valid':
        facts = {item.fact_key: item.value for item in outcome.observations}
        assert facts['olt.registration.ready'] is True
        assert facts['olt.profile_gem.verified'] is True
    assert commands, 'Must attempt read-only registration verification, not merely reject unknown action'
    assert {cmd.action_code for cmd in commands} <= {'display_ont_by_sn', 'read_profile_gem'}


def test_keep_does_not_let_unproven_registration_reach_mutation(execution_fixture, tmp_path):
    service, repo, command, _, _ = bound(execution_fixture)
    legacy_service, _, _, driver = coordinator(execution_fixture, tmp_path)
    service.coordinator = legacy_service.coordinator
    execution = service.create_execution(command)
    for _ in range(6):
        service.advance(execution.id)
        if repo.get(execution.id).status == 'BLOCKED':
            break
    assert repo.get(execution.id).status == 'BLOCKED'
    assert not set(driver.calls) & {'delete_ont', 'register_ont', 'provision_ipoe', 'provision_pppoe'}
