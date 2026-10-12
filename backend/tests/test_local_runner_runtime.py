from pathlib import Path
from dataclasses import replace
from hashlib import sha256
import pytest

from app.local_runner.configuration import RunnerConfig
from app.local_runner.runtime import LocalRuntimeFactory, RuntimeResources
from app.local_runner.contracts import ActionContext
from app.local_runner.ma5800.actions import MA5800Actions
from app.local_runner.ma5800.transport import CommandTranscript
from app.local_runner.onu_web.contracts import ONUWebSelectorError
from app.local_runner.pc_probe import InterfaceAddress, PCProbe
from local_runner_binding_fixtures import valid_config, enrolled_resolver
from test_local_runner_facts import PARAMETERS, event


def parameters():
    return dict(PARAMETERS, olt_target_ref='lab.olt', onu_web_target_ref='lab.onu',
                olt_access_ref='lab.olt.access', onu_web_access_ref='lab.onu.access',
                pppoe_access_ref='lab.ppp.access', ping_target='example.com')


class Channel:
    def __init__(self):
        self.output = b'MA5800-X7#'
        self.closed = False
        self.sent = []

    def send(self, command):
        self.sent.append(command.strip())
        text = 'Command executed successfully'
        if command.startswith('display ont autofind'):
            text = 'F/S/P : 0/2/9\nOnt SN : AABBCCDDEEFF0011'
        self.output += (text + '\nMA5800-X7#').encode()

    def recv_ready(self):
        return bool(self.output)

    def recv(self, size):
        result, self.output = self.output, b''
        return result

    def close(self):
        self.closed = True


class Client:
    def __init__(self):
        self.channel = Channel()
        self.closed = False

    def invoke_shell(self):
        return self.channel

    def close(self):
        self.closed = True


class Connector:
    def __init__(self):
        self.calls = []
        self.client = Client()

    def connect(self, **kwargs):
        self.calls.append(kwargs)
        return self.client


def runtime(tmp_path, resources=None, history=()):
    config = RunnerConfig.model_validate(valid_config())
    resolver = enrolled_resolver()
    factory = LocalRuntimeFactory(config, resolver, resources)
    binding = factory.resolve_binding(parameters())
    return factory, factory.for_binding(binding, lambda: history), resolver


def execute(bound, tmp_path, action, **overrides):
    params = dict(parameters(), **overrides)
    return bound.execute(ActionContext('fixture-session', action, params,
        bound.secrets_for(params, action), tmp_path))


def test_runtime_uses_frozen_binding_not_current_config(tmp_path):
    connector = Connector()
    resources = RuntimeResources(ssh_connector_factory=lambda: connector)
    factory, bound, resolver = runtime(tmp_path, resources)
    changed = valid_config()
    changed['targets']['lab.olt']['host'] = '10.20.0.3'
    other = LocalRuntimeFactory(RunnerConfig.model_validate(changed), resolver, resources)
    outcome = execute(bound, tmp_path, 'discover_onts')
    assert outcome.status == 'PASS'
    assert connector.calls[0]['hostname'] == '10.20.0.2'
    assert other.resolve_binding(parameters()).olt.host == '10.20.0.3'
    assert connector.client.closed and connector.client.channel.closed
    assert {a.media_type for a in outcome.artifacts} == {'text/plain', 'image/png'}
    for artifact in outcome.artifacts:
        content = (tmp_path / artifact.storage_path).read_bytes()
        assert sha256(content).hexdigest() == artifact.sha256
        assert b'fixture-password-sensitive' not in content


def test_wrong_or_unknown_action_has_no_external_effect(tmp_path):
    connector = Connector()
    _, bound, _ = runtime(tmp_path, RuntimeResources(ssh_connector_factory=lambda: connector))
    assert execute(bound, tmp_path, 'arbitrary_command').status == 'BLOCKED'
    assert connector.calls == []
    assert bound.secrets_for(parameters(), 'arbitrary_command') == {}


def test_unapproved_mutation_does_not_open_connection(tmp_path):
    connector = Connector()
    _, bound, _ = runtime(tmp_path, RuntimeResources(ssh_connector_factory=lambda: connector))
    outcome = execute(bound, tmp_path, 'register_ont')
    assert outcome.status == 'WAITING_OPERATOR'
    assert connector.calls == []


@pytest.mark.parametrize('addresses', [
    [], [InterfaceAddress('Other Ethernet', '10.20.1.5', True, 24)],
    [InterfaceAddress('Fixture Ethernet', '10.20.1.5', True)],
    [InterfaceAddress('Fixture Ethernet', '10.20.1.5', True, 24),
     InterfaceAddress('Fixture Ethernet', '10.20.1.6', True, 24)],
    [InterfaceAddress('Fixture Ethernet', '10.20.2.5', True, 24)],
])
def test_pc_requires_unique_bound_interface_address(tmp_path, addresses):
    _, bound, _ = runtime(tmp_path, RuntimeResources(interface_provider=lambda: addresses))
    outcome = execute(bound, tmp_path, 'pc_connectivity_probe')
    assert outcome.status == 'WAITING_OPERATOR'
    preview = next(o.value for o in outcome.observations if o.fact_key == 'mutation.preview')
    assert len(preview['preview_hash']) == 64
    assert '非配置修改授权' in preview['summary']
    assert not any(o.value is True for o in outcome.observations)


def test_partial_restore_never_becomes_verified(tmp_path):
    connector = Connector()
    history = [event('RESTORE_VERIFY', event_type='ACTION_STARTED', action='snapshot_ont')]
    _, bound, _ = runtime(tmp_path, RuntimeResources(ssh_connector_factory=lambda: connector), history)
    snapshot = dict(registration={}, wan=[], service_ports=[])
    for action in ('restore_snapshot', 'snapshot_ont'):
        assert execute(bound, tmp_path, action, configuration_snapshot=snapshot).status == 'BLOCKED'
    assert connector.calls == []


def test_resources_close_on_selector_failure(tmp_path):
    class Surface:
        closed = False
        def authenticate(self, *args):
            pass
        def open_wan_page(self):
            raise ONUWebSelectorError('WAN', 'fixture-password-sensitive')
        def close(self):
            self.closed = True
    surface = Surface()
    _, bound, _ = runtime(tmp_path, RuntimeResources(web_surface_factory=lambda context: surface))
    outcome = execute(bound, tmp_path, 'capture_onu_wan', wan_mode='IPOE')
    assert outcome.status == 'BLOCKED' and surface.closed
    assert outcome.error_code == 'ONU_WEB_SELECTOR_UNSUPPORTED'
    assert 'sensitive' not in repr(outcome)


def test_connection_timeout_is_safe_and_resources_close(tmp_path):
    connector = Connector()
    def failing_send(command):
        raise TimeoutError('fixture-password-sensitive')
    connector.client.channel.send = failing_send
    _, bound, _ = runtime(tmp_path, RuntimeResources(ssh_connector_factory=lambda: connector))
    outcome = execute(bound, tmp_path, 'discover_onts')
    assert outcome.status == 'BLOCKED'
    assert connector.client.closed and connector.client.channel.closed
    assert 'fixture-password-sensitive' not in repr(outcome)


def test_confirmed_missing_registration_can_be_snapshotted_before_new_registration():
    class Executor:
        calls = []
        def run(self, command):
            self.calls.append(command.action_code)
            raw = 'Failure: The ONT does not exist\nMA5800-X7#'
            return CommandTranscript(command.action_code, raw, raw, 'MA5800-X7#', sha256(raw.encode()).hexdigest())
    executor = Executor()
    outcome = MA5800Actions(executor).snapshot_ont(ActionContext('new', 'snapshot_ont', parameters()))
    assert outcome.status == 'PASS'
    assert outcome.observations[0].value == dict(registration=None, wan=[], service_ports=[])
    assert executor.calls == ['display_ont_by_sn']


def test_pc_uses_real_prefix_not_assumed_24_and_never_system_dns(tmp_path):
    from types import SimpleNamespace
    addresses = [InterfaceAddress('Fixture Ethernet', '10.20.0.8', True, 23)]
    calls = []
    def network(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout='Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)',
                               stderr='')
    def probe_factory(writer, provider):
        return PCProbe(subprocess_runner=network, interface_provider=provider, evidence_writer=writer,
            dns_resolver=lambda name: (_ for _ in ()).throw(AssertionError('Unbound DNS must not run')))
    _, bound, _ = runtime(tmp_path, RuntimeResources(interface_provider=lambda: addresses,
                                                    pc_probe_factory=probe_factory))
    outcome = execute(bound, tmp_path, 'pc_connectivity_probe')
    assert outcome.status == 'PASS'
    assert calls[0][-2:] == ['10.20.0.8', 'example.com']
    assert '-S' in calls[0]
    assert not any(o.fact_key == 'ipoe.internet.pass' and o.value is True for o in outcome.observations)


def test_interface_enumeration_preserves_prefix_length(monkeypatch):
    from types import SimpleNamespace
    import app.local_runner.pc_probe as module
    def network(args, **kwargs):
        assert 'PrefixLength' in args[-1]
        return SimpleNamespace(returncode=0, stdout='[{"InterfaceAlias":"Fixture Ethernet","IPAddress":"10.20.1.5","IsUp":true,"PrefixLength":23}]')
    monkeypatch.setattr(module.subprocess, 'run', network)
    assert PCProbe._local_interfaces()[0].prefix_length == 23


def test_address_disappearing_during_probe_stays_waiting_not_exception_recovery(tmp_path):
    calls = iter([[InterfaceAddress('Fixture Ethernet', '10.20.1.5', True, 24)], []])
    _, bound, _ = runtime(tmp_path, RuntimeResources(interface_provider=lambda: next(calls)))
    outcome = execute(bound, tmp_path, 'pc_connectivity_probe')
    assert outcome.status == 'WAITING_OPERATOR'
    assert any(o.fact_key == 'mutation.preview' for o in outcome.observations)


def test_resource_close_failure_is_safe_and_attempts_both_closes(tmp_path):
    connector = Connector()
    def fail():
        raise RuntimeError('fixture-password-sensitive')
    connector.client.channel.close = fail
    _, bound, _ = runtime(tmp_path, RuntimeResources(ssh_connector_factory=lambda: connector))
    outcome = execute(bound, tmp_path, 'discover_onts')
    assert outcome.status == 'BLOCKED'
    assert connector.client.closed
    assert 'fixture-password-sensitive' not in repr(outcome)
