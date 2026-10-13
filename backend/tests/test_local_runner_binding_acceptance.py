"""Real API/service/coordinator/runtime chain; only physical I/O is simulated."""
from hashlib import sha256
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import re

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.main import create_app
from app.core.config import Settings
from app.local_runner.configuration import RunnerConfig
from app.local_runner.runtime import LocalRuntimeFactory, RuntimeResources
from app.local_runner.ma5800.transport import MA5800SSHConnector
from app.local_runner.onu_web.contracts import ONUWebSelectorError
from app.local_runner.pc_probe import PCProbe, InterfaceAddress
from app.models.execution_session import ExecutionSession
from app.models.test_execution import RunResult
from local_runner_binding_fixtures import valid_config, enrolled_resolver
from test_skill_execution_repository import execution_fixture


class Lab:
    def __init__(self, registered=False, failure=None):
        self.registered = registered
        self.ont_id = 12
        self.failure = failure
        self.wans = {}
        self.clients = []
        self.mutations = []
        self.surfaces = []
        self.pc_calls = []
        self.interface_available = True

    def cli(self, text):
        if text == 'display ont autofind all':
            return 'The number of GPON autofind ONT is 0' if self.registered else 'F/S/P : 0/2/9\nOnt SN : AABBCCDDEEFF0011'
        if text.startswith('display ont info by-sn'):
            if not self.registered:
                return 'Failure: The ONT does not exist'
            return (f'F/S/P : 0/2/9\nONT-ID : {self.ont_id}\nSN : AABBCCDDEEFF0011\n'
                    'Run state : online\nConfig state : normal\nMatch state : match\n'
                    'Line profile ID : 10\nService profile ID : 10')
        if re.fullmatch(r'display ont info \d+ all', text):
            return f'0/2/9 {self.ont_id} AABBCCDDEEFF0011 online normal match' if self.registered else 'The number of ONTs is 0'
        if text.startswith('ont delete'):
            self.registered = False
            self.mutations.append('delete')
        if text.startswith('ont add'):
            self.registered = True
            self.ont_id = int(text.split()[3])
            self.mutations.append('register')
        if text.startswith('ont ipconfig'):
            mode = 'PPPOE' if 'pppoe user-account' in text else 'IPOE'
            self.wans[mode] = dict(mode=mode, ip_index=1 if mode == 'PPPOE' else 0,
                vlan=1000, status='CONNECTED', ip_address='10.30.0.3' if mode == 'PPPOE' else '10.30.0.2')
            self.mutations.append(mode)
        if text.startswith('display ont wan-info'):
            if not self.wans:
                return 'The number of WAN entries is 0'
            return '\n'.join(
                f'WAN index : {wan["ip_index"]}\nIPv4 access type : {("PPPoE" if mode == "PPPOE" else "DHCP")}\n'
                f'VLAN : 1000\nIPv4 Connection status : {wan["status"]}\nIPv4 address : {wan["ip_address"]}'
                for mode, wan in self.wans.items())
        if text.startswith('display service-port port '):
            return 'Total : 0'
        return 'Command executed successfully'


class Channel:
    def __init__(self, lab):
        self.lab = lab
        self.output = b'MA5800-X7#'
        self.closed = False
    def send(self, value):
        self.output += (self.lab.cli(value.strip()) + '\nMA5800-X7#').encode()
    def recv_ready(self):
        return bool(self.output)
    def recv(self, size):
        result, self.output = self.output, b''
        return result
    def close(self):
        self.closed = True


class SSHClient:
    def __init__(self, lab):
        self.lab = lab
        self.closed = False
        self.shells = 0
        self.channel = Channel(lab)
        lab.clients.append(self)
    def load_system_host_keys(self):
        pass
    def set_missing_host_key_policy(self, value):
        self.policy = value
    def connect(self, **kwargs):
        self.target = kwargs['hostname']
        kwargs['auth_strategy'].authenticate(self)
    def auth_password(self, username, password):
        pass
    def get_transport(self):
        return self
    def get_remote_server_key(self):
        return SimpleNamespace(asbytes=lambda: b'changed-key' if self.lab.failure == 'key' else b'fixture-host-key')
    def invoke_shell(self):
        self.shells += 1
        return self.channel
    def close(self):
        self.closed = True


class Surface:
    def __init__(self, lab):
        self.lab = lab
        self.mode = None
        self.closed = False
        self.masked = False
        lab.surfaces.append(self)
    def authenticate(self, username, password):
        assert username.reveal() == 'fixture-user-sensitive'
        assert password.reveal() == 'fixture-password-sensitive'
    def open_wan_page(self):
        if self.lab.failure == 'selector':
            raise ONUWebSelectorError('WAN_NAVIGATION', 'fixture-password-sensitive')
    def select_wan(self, mode):
        self.mode = mode
    def read_wan_fields(self):
        wan = self.lab.wans[self.mode]
        return dict(protocol=self.mode, status='Connected', vlan='1000', ip_address=wan['ip_address'])
    def open_ping_page(self):
        pass
    def run_ping(self, target, count):
        failed = self.lab.failure == self.mode
        return f'sent=4 received={3 if failed else 4} loss={25 if failed else 0}% min=1.0ms avg=1.5ms max=2.0ms'
    def mask_sensitive_controls(self, redaction_values=()):
        self.masked = True
    def page_text(self):
        return 'Password: fixture-password-sensitive'
    def screenshot(self):
        assert self.masked
        image = BytesIO()
        Image.new('RGB', (16, 16)).save(image, format='PNG')
        return image.getvalue()
    def close(self):
        self.closed = True


@pytest.fixture
def lab_api(execution_fixture, tmp_path):
    _, repo, command = execution_fixture
    command.parameters.update(olt_access_ref='lab.olt.access', onu_web_access_ref='lab.onu.access',
                              pppoe_access_ref='lab.ppp.access', end_policy='KEEP')
    settings = Settings(_env_file=None, allow_metadata_create_all=True,
        database_url=str(repo.session.get_bind().url), evidence_root=str(tmp_path / 'evidence'),
        local_runner_evidence_root=str(tmp_path / 'runner'), log_file=str(tmp_path / 'app.log'),
        report_root=str(tmp_path / 'reports'))
    lab = Lab()
    resolver = enrolled_resolver()
    addresses = lambda: ([InterfaceAddress('Fixture Ethernet', '10.20.1.5', True, 24)]
                         if lab.interface_available else [])
    def probe_factory(writer, provider):
        def network(args, **kwargs):
            lab.pc_calls.append(args)
            return SimpleNamespace(stdout='Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)', stderr='')
        return PCProbe(subprocess_runner=network, interface_provider=provider, evidence_writer=writer)
    resources = RuntimeResources(
        ssh_connector_factory=lambda: MA5800SSHConnector(client_factory=lambda: SSHClient(lab)),
        web_surface_factory=lambda context: Surface(lab), interface_provider=addresses,
        pc_probe_factory=probe_factory)
    factory = LocalRuntimeFactory(RunnerConfig.model_validate(valid_config()), resolver, resources)
    app = create_app(settings, credential_resolver=resolver, skill_execution_runtime=factory)
    payload = dict(project_id=command.project_id, device_id=command.device_id,
        environment_id=command.environment_id, skill_id=command.skill_id, parameters=command.parameters)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        yield client, payload, repo, lab, settings, resolver, factory


def drain(client, lab, view, *, end='KEEP'):
    base = '/api/skill-executions/' + view['session_id']
    for _ in range(80):
        if view['status'] in {'COMPLETED', 'BLOCKED', 'ERROR', 'RECOVERY_REQUIRED', 'CANCELLED'}:
            return view
        pending = view['pending_interaction']
        if pending:
            choice = end if pending['ref'] == 'END_POLICY' else pending['options'][0]
            before = list(lab.mutations)
            invalid = client.post(base + '/interactions/' + pending['id'] + '/respond',
                json=dict(choice=choice, approved=True, preview_hash='0' * 64))
            assert invalid.status_code == 409
            assert lab.mutations == before
            if pending['ref'] == 'ISOLATE_IPOE' and 'IPOE' in lab.wans:
                lab.wans['IPOE']['status'] = 'DISCONNECTED'  # Operator's external isolation, not runner guessing.
            response = client.post(base + '/interactions/' + pending['id'] + '/respond',
                json=dict(choice=choice, approved=True, preview_hash=pending['preview_hash']))
            assert lab.mutations == before  # Respond itself never sends a mutation.
        else:
            response = client.post(base + '/advance')
        assert response.status_code == 200, response.text
        assert 'fixture-password-sensitive' not in response.text
        view = response.json()
    pytest.fail('Bound runtime did not finish')


@pytest.mark.parametrize('registered,failure', [(False, None), (True, None), (False, 'PPPOE')])
def test_api_to_runtime_to_evidence_chain(lab_api, registered, failure):
    client, payload, repo, lab, settings, *_ = lab_api
    lab.registered, lab.failure = registered, failure
    response = client.post('/api/skill-executions', json=payload)
    assert response.status_code == 201, response.text
    initial = response.json()
    original_result = repo.session.get(RunResult, initial['run_result_id'])
    original = deepcopy((original_result.parameter_snapshot, original_result.run.device_snapshot,
                         original_result.run.standard_snapshot, original_result.run.environment_snapshot.profile_snapshot))
    view = drain(client, lab, response.json())
    assert view['status'] == ('COMPLETED' if registered else 'BLOCKED')
    assert view['result'] == ('FAIL' if registered else 'BLOCKED')
    assert view['functional_verdict'] == ('FAIL' if failure or registered else 'BLOCKED')
    assert view['integrity_status'] == 'DRAFT'
    assert view['evidence_complete'] is (not bool(failure))
    result = repo.session.get(RunResult, view['run_result_id'])
    assert result.parameter_snapshot['ont_id'] == 12  # Original parameter snapshot unchanged.
    assert (result.parameter_snapshot, result.run.device_snapshot,
            result.run.standard_snapshot, result.run.environment_snapshot.profile_snapshot) == original
    base = '/api/skill-executions/' + view['session_id'] + '/evidence'
    artifacts = client.get(base).json()
    assert {item['rule_code'] for item in artifacts if item['rule_code']} == {
        'E1_OLT_AUTOFIND', 'E2_REGISTRATION', 'E3_IPOE_ADDRESS',
        'E4_IPOE_PING', 'E5_PPPOE_ADDRESS', 'E6_PPPOE_PING'}
    for item in artifacts:
        downloaded = client.get(item['download_url'])
        assert downloaded.status_code == 200
        assert sha256(downloaded.content).hexdigest() == item['sha256']
        assert b'fixture-password-sensitive' not in downloaded.content
        assert b'fixture-user-sensitive' not in downloaded.content
    assert all(c.closed and c.channel.closed for c in lab.clients)
    assert all(s.closed for s in lab.surfaces)
    assert lab.pc_calls and all('-S' in call for call in lab.pc_calls)


def test_selector_failure_captures_available_evidence():
    from app.local_runner.onu_web.neutral import NeutralONUWebAdapter
    from app.local_runner.contracts import ActionContext
    from app.local_runner.credentials import SecretValue
    lab = Lab(failure='selector')
    surface = Surface(lab)
    outcome = NeutralONUWebAdapter(lambda context: surface).capture_wan(
        ActionContext('selector', 'capture_onu_wan', {},
            dict(onu_web_username=SecretValue('fixture-user-sensitive'),
                 onu_web_password=SecretValue('fixture-password-sensitive'))), 'IPOE')
    assert outcome.status == 'BLOCKED' and surface.closed
    assert {a.media_type for a in outcome.artifacts} == {'text/plain', 'image/png'}


def test_repeated_connection_wait_does_not_enter_recovery(lab_api):
    client, payload, repo, lab, *_ = lab_api
    lab.interface_available = False
    view = client.post('/api/skill-executions', json=payload).json()
    base = '/api/skill-executions/' + view['session_id']
    for _ in range(30):
        pending = view['pending_interaction']
        if pending and pending['ref'] == 'IPOE_PING_PC':
            break
        if pending:
            view = client.post(base + '/interactions/' + pending['id'] + '/respond',
                json=dict(choice=pending['options'][0], approved=True,
                          preview_hash=pending['preview_hash'])).json()
        else:
            view = client.post(base + '/advance').json()
    assert pending['ref'] == 'IPOE_PING_PC'
    old_hash = pending['preview_hash']
    assert '非配置修改授权' in pending['instructions']
    client.post(base + '/interactions/' + pending['id'] + '/respond',
                json=dict(choice='CONFIRM', approved=True, preview_hash=old_hash))
    waiting = client.post(base + '/advance').json()
    assert waiting['status'] == 'WAITING_OPERATOR'
    assert waiting['pending_interaction']['preview_hash'] != old_hash
    lab.interface_available = True
    finished = drain(client, lab, waiting)
    assert finished['result'] == 'BLOCKED'  # Wiring confirmation alone does not prove WAN egress.
    assert finished['integrity_status'] == 'DRAFT'


def test_partial_restore_requires_manual_resolution(lab_api):
    client, payload, repo, lab, *_ = lab_api
    response = client.post('/api/skill-executions', json=payload)
    view = drain(client, lab, response.json(), end='RESTORE')
    assert view['status'] == 'RECOVERY_REQUIRED'
    assert repo.session.get(RunResult, view['run_result_id']).recovery_status == 'MANUAL_REQUIRED'
    assert all(t.status != 'VERIFIED' for t in repo.get(view['session_id']).recovery_tasks)


@pytest.mark.parametrize('failure', ['key', 'selector'])
def test_external_failure_is_blocked_and_retains_evidence(lab_api, failure):
    client, payload, repo, lab, *_ = lab_api
    lab.failure = failure
    view = drain(client, lab, client.post('/api/skill-executions', json=payload).json())
    assert view['result'] == 'BLOCKED'
    assert view['integrity_status'] == 'DRAFT'
    artifacts = client.get('/api/skill-executions/' + view['session_id'] + '/evidence').json()
    if failure == 'selector':
        assert any(item['capture_method'] == 'ONU_WEB' for item in artifacts)
    else:
        assert not lab.mutations
        assert all(c.shells == 0 and c.closed for c in lab.clients)


def test_interrupted_mutation_is_not_replayed(lab_api):
    client, payload, repo, lab, settings, resolver, factory = lab_api
    view = client.post('/api/skill-executions', json=payload).json()
    repo.append_event(view['session_id'], 'ACTION_STARTED', dict(ref='REGISTER', attempt=1),
                      'REGISTER:1:start', action_ref='register_ont')
    execution = repo.get(view['session_id'])
    execution.status = 'RUNNING'
    repo.session.commit()
    before = list(lab.mutations)
    with TestClient(create_app(settings, credential_resolver=resolver, skill_execution_runtime=factory)):
        pass
    assert repo.get(execution.id).status == 'RECOVERY_REQUIRED'
    assert lab.mutations == before and not lab.clients


def test_report_archive_require_explicit_lock_and_remain_hash_verifiable(lab_api):
    client, payload, repo, lab, *_ = lab_api
    view = drain(client, lab, client.post('/api/skill-executions', json=payload).json())
    assert view['integrity_status'] == 'DRAFT'
    url = '/api/test-runs/' + view['test_run_id']
    assert client.post(url + '/reports', json={}).status_code == 409
    locked = client.post(url + '/results/' + view['run_result_id'] + '/lock')
    assert locked.status_code == 200, locked.text
    assert locked.json()['integrity_status'] == 'LOCKED'
    report_response = client.post(url + '/reports', json={})
    assert report_response.status_code == 201, report_response.text
    report = report_response.json()
    html = client.get('/api/reports/' + report['id'] + '/download')
    assert sha256(html.content).hexdigest() == report['html_sha256']
    archive_response = client.post('/api/reports/' + report['id'] + '/archive')
    assert archive_response.status_code == 201, archive_response.text
    archive = archive_response.json()
    zip_response = client.get('/api/archives/' + archive['id'] + '/download')
    assert sha256(zip_response.content).hexdigest() == archive['archive_sha256']
    assert 'fixture-password-sensitive' not in report_response.text + archive_response.text
    assert b'fixture-password-sensitive' not in html.content
    before = list(lab.mutations)
    assert client.post('/api/skill-executions/' + view['session_id'] + '/advance').status_code == 200
    assert lab.mutations == before
    assert repo.session.get(RunResult, view['run_result_id']).integrity_status == 'LOCKED'
