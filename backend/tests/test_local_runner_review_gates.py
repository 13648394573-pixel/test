"""Regression gates from the independent review; physical I/O remains offline."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
import paramiko

from app.local_runner.contracts import ActionContext, Observation
from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.actions import MA5800Actions
from app.local_runner.ma5800.transport import CommandTranscript, HostKeyFingerprintMismatchError, MA5800SSHConnector, host_key_fingerprint
from test_local_runner_runtime import parameters, runtime, execute
from app.local_runner.runtime import RuntimeResources
from app.local_runner.pc_probe import InterfaceAddress, PCProbe
from test_local_runner_facts import epoch, event, olt_wan, web_wan
from test_verified_onu_adaptation import surface
from app.local_runner.onu_web.neutral import NeutralONUWebAdapter


def registration(ont_id=12):
    return (f'F/S/P : 0/2/9\nONT-ID : {ont_id}\nSN : AABBCCDDEEFF0011\n'
            'Run state : online\nConfig state : normal\nMatch state : match\n'
            'Line profile ID : 10\nService profile ID : 10')


class Executor:
    def __init__(self, outputs):
        self.outputs, self.commands = outputs, []
    def run(self, command):
        self.commands.append(command.action_code)
        text = self.outputs.get(command.action_code, 'Command executed successfully') + '\nMA5800-X7#'
        return CommandTranscript(command.action_code, text, text, 'MA5800-X7#', 'a' * 64)


def approved(actions, action):
    ctx = ActionContext('review', action, parameters())
    preview = next(o.value for o in getattr(actions, action)(ctx).observations
                   if o.fact_key == 'mutation.preview')
    return getattr(actions, action)(replace(ctx, parameters={**ctx.parameters,
        'mutation_approval': dict(approved=True, preview_hash=preview['preview_hash'])}))


def test_snapshot_rejects_sn_at_different_id_before_querying_other_onu():
    executor = Executor({'display_ont_by_sn': registration(20)})
    outcome = MA5800Actions(executor).snapshot_ont(ActionContext('review', 'snapshot_ont', parameters()))
    assert outcome.status == 'BLOCKED'
    assert executor.commands == ['display_ont_by_sn']


def test_approved_delete_rechecks_live_identity_before_mutation():
    executor = Executor({'display_ont_by_sn': registration(20)})
    assert approved(MA5800Actions(executor), 'delete_ont').status == 'BLOCKED'
    assert 'delete_ont' not in executor.commands


def test_approved_registration_rechecks_requested_id_is_free():
    executor = Executor({'display_ont_by_sn': 'Failure: The ONT does not exist',
                         'display_ont_port': '0/2/9 12 0011223344556677 online normal match'})
    assert approved(MA5800Actions(executor), 'register_ont').status == 'BLOCKED'
    assert 'register_ont' not in executor.commands


@pytest.mark.parametrize('action,code', [('discover_onts', 'display_autofind'),
                                       ('read_wan_info', 'display_wan_info')])
@pytest.mark.parametrize('text', ['Failure: permission denied', 'unsupported firmware format'])
def test_unrecognized_olt_read_blocks_without_negative_facts(action, code, text):
    outcome = getattr(MA5800Actions(Executor({code: text})), action)(
        ActionContext('review', action, parameters()))
    assert outcome.status == 'BLOCKED'
    assert not outcome.observations


@pytest.mark.parametrize('matching_pin', [False, True])
def test_known_host_pin_checked_before_authentication_on_real_paramiko_flow(monkeypatch, matching_pin):
    key = paramiko.RSAKey.generate(1024)
    expected = key if matching_pin else paramiko.RSAKey.generate(1024)
    authenticated = []
    class Socket:
        def settimeout(self, value): pass
        def connect(self, value): pass
        def close(self): pass
    class Transport:
        gss_kex_used = False
        def __init__(self, *args, **kwargs): pass
        def use_compression(self, **kwargs): pass
        def set_gss_host(self, **kwargs):
            assert kwargs['gssapi_requested'] is False
        def get_security_options(self): return SimpleNamespace(key_types=('rsa-sha2-512',))
        def start_client(self, **kwargs): pass
        def get_remote_server_key(self): return key
        def auth_password(self, username, password, **kwargs):
            authenticated.append((username, password))
        def close(self): pass
    monkeypatch.setattr(paramiko.client.socket, 'socket', lambda *args: Socket())
    monkeypatch.setattr(paramiko.client, 'Transport', Transport)
    client = paramiko.SSHClient()
    client.load_system_host_keys = lambda: None
    client._system_host_keys.add('10.20.0.2', key.get_name(), key)
    def connect():
        MA5800SSHConnector(client_factory=lambda: client).connect(
            hostname='10.20.0.2', port=22, username='fixture-user', password='fixture-password',
            expected_fingerprint=host_key_fingerprint(expected), formal_mode=False)
    if matching_pin:
        connect()
        assert authenticated == [('fixture-user', 'fixture-password')]
    else:
        with pytest.raises(HostKeyFingerprintMismatchError):
            connect()
        assert authenticated == []


def test_real_rendered_page_masks_body_and_readonly_credentials_before_png(surface):
    surface.page.set_content("""
        <p>Welcome fixture-user-sensitive</p>
        <input readonly name="username" value="fixture-user-sensitive">
        <iframe srcdoc='<p>PPPoE fixture-password-sensitive</p>'></iframe>
    """)
    surface.surface = surface.page
    original = surface.screenshot
    def checked_screenshot():
        for frame in surface.page.frames:
            rendered = frame.locator('body').inner_text()
            values = frame.locator('input').evaluate_all('xs => xs.map(x => x.value).join(" ")')
            assert 'fixture-user-sensitive' not in rendered + values
            assert 'fixture-password-sensitive' not in rendered + values
        return original()
    surface.screenshot = checked_screenshot
    ctx = ActionContext('review', 'capture_onu_wan', {}, {
        'onu_web_username': SecretValue('fixture-user-sensitive'),
        'onu_web_password': SecretValue('fixture-password-sensitive')})
    artifacts = NeutralONUWebAdapter()._capture_artifacts(surface, ctx, 'review')
    assert artifacts[0].content.startswith(b'\x89PNG')


def test_web_redaction_receives_pppoe_pair_without_persisting_it(tmp_path):
    _, bound, _ = runtime(tmp_path)
    secrets = bound.secrets_for(parameters(), 'capture_onu_wan')
    assert secrets['pppoe_username'].reveal() == 'fixture-user-sensitive'
    assert secrets['pppoe_password'].reveal() == 'fixture-password-sensitive'


@pytest.mark.parametrize('wiring_wait', [False, True])
def test_active_wan_and_source_ping_do_not_prove_current_egress(tmp_path, wiring_wait):
    history = [epoch(), event('IPOE_ADDRESS_OLT', [olt_wan()]),
               event('IPOE_ADDRESS_WEB', [*web_wan(), Observation('ipoe.address.valid', True, 'ONU_WEB')]),
               event('IPOE_PING_ONU', [Observation('ipoe.ping.packets_sent', 4, 'ONU_WEB'),
                     Observation('ipoe.ping.packets_received', 4, 'ONU_WEB'),
                     Observation('ipoe.ping.loss_percent', 0, 'ONU_WEB')])]
    if wiring_wait:
        history.append(event('IPOE_PING_PC', event_type='WAITING_OPERATOR'))
    addresses = lambda: [InterfaceAddress('Fixture Ethernet', '10.20.1.5', True, 24)]
    def probe(writer, provider):
        return PCProbe(interface_provider=provider, evidence_writer=writer,
            subprocess_runner=lambda *args, **kwargs: SimpleNamespace(
                stdout='Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)', stderr=''))
    _, bound, _ = runtime(tmp_path, RuntimeResources(interface_provider=addresses, pc_probe_factory=probe), history)
    outcome = execute(bound, tmp_path, 'pc_connectivity_probe', wan_mode='IPOE')
    assert not any(o.fact_key in {'pc.wan.attributed', 'ipoe.internet.pass'} and o.value is True
                   for o in outcome.observations)
    assert outcome.status == 'PASS'  # Ping collection only; missing standard facts force final BLOCKED.
