from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from ipaddress import ip_address, ip_interface
import json
import re
from typing import Callable
from uuid import uuid4
from urllib.parse import urlsplit

from .access import PairedAccessResolver
from .configuration import RunnerConfig, RuntimeBinding, resolve_runtime_binding
from .contracts import ActionContext, ActionOutcome, Observation
from .credentials import CredentialResolver, UnavailableCredentialError
from .evidence import GeneratedEvidenceWriter
from .facts import derive_standard_facts, historical_observations, recent_history
from .ma5800.actions import MA5800Actions, register_default_ma5800_actions
from .ma5800.actions import _validated_target
from .ma5800.parsers import PROMPT_LINE, normalize_cli_output, parse_ont_state, parse_profile_gem
from .ma5800.transport import MA5800SSHConnector, MA5800Transport, SafeMA5800Command, HostKeyFingerprintMismatchError
from .onu_web.neutral import NeutralONUWebAdapter
from .pc_probe import PCProbe, ProbeRequest
from .registry import LocalActionRegistry


OLT_ACTIONS = frozenset({'preflight', 'discover_onts', 'snapshot_ont', 'find_free_ont_id',
    'delete_ont', 'register_ont', 'provision_ipoe', 'provision_pppoe', 'read_wan_info',
    'remove_test_services', 'restore_snapshot', 'verify_restore', 'verify_existing_registration'})
WEB_ACTIONS = frozenset({'capture_onu_wan', 'run_onu_ping'})
ALLOWED_ACTIONS = OLT_ACTIONS | WEB_ACTIONS | {'pc_connectivity_probe'}
_GPON_COMMANDS = frozenset({'display_ont_port', 'display_wan_info', 'delete_ont',
                          'register_ont', 'provision_ipoe', 'provision_pppoe'})


def _pc_probe(writer, provider):
    return PCProbe(evidence_writer=writer, interface_provider=provider)


@dataclass(frozen=True)
class RuntimeResources:
    ssh_connector_factory: Callable = MA5800SSHConnector
    web_surface_factory: Callable | None = None
    interface_provider: Callable = PCProbe._local_interfaces
    pc_probe_factory: Callable = _pc_probe
    clock: Callable = lambda: datetime.now(UTC)


class LocalRuntimeFactory:
    def __init__(self, config: RunnerConfig, resolver: CredentialResolver,
                 resources: RuntimeResources | None = None):
        self.config, self.resolver = config, resolver
        self.resources = resources or RuntimeResources()
        self.pairs = PairedAccessResolver(config, resolver)

    def available(self, reference: str) -> bool:
        return self.config.enabled and self.pairs.available(reference)

    def resolve_binding(self, parameters) -> RuntimeBinding:
        return resolve_runtime_binding(self.config, parameters, self.pairs)

    def for_binding(self, binding: RuntimeBinding, history_reader) -> BoundExecutionRuntime:
        return BoundExecutionRuntime(binding, self.resolver, self.resources, history_reader)


class _OLTExecutor:
    """Lazy SSH connection: an unapproved preview never opens a device connection."""
    def __init__(self, binding, resources, context):
        self.binding, self.resources, self.context = binding, resources, context
        self.client = self.channel = self.transport = None
        self.gpon = False
        self.transcripts = []

    def run(self, command):
        if self.client is None:
            target = self.binding.olt
            self.client = self.resources.ssh_connector_factory().connect(
                hostname=target.host, port=target.port,
                username=self.context.secrets['olt_username'].reveal(),
                password=self.context.secrets['olt_password'].reveal(),
                expected_fingerprint=target.expected_fingerprint, formal_mode=False)
            self.channel = self.client.invoke_shell()
            self.transport = MA5800Transport(self.channel)
            self.transport.synchronize()
            self.transport.run(SafeMA5800Command('enable', ()))
            self.transport.run(SafeMA5800Command('disable_paging', ()))
            self.transport.run(SafeMA5800Command('enter_config', ()))
        requires_gpon = command.action_code in _GPON_COMMANDS
        if self.gpon and not requires_gpon:
            self.transport.run(SafeMA5800Command('leave_gpon_interface', ()))
            self.gpon = False
        if requires_gpon and not self.gpon:
            self.transport.run(SafeMA5800Command('enter_gpon_interface',
                (self.context.parameters['frame'], self.context.parameters['slot'])))
            self.gpon = True
        transcript = self.transport.run(command)
        self.transcripts.append(transcript)
        return transcript

    def close(self):
        closed = True
        for resource in (self.channel, self.client):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    closed = False
        return closed


class BoundExecutionRuntime:
    def __init__(self, binding, resolver, resources, history_reader):
        self.binding, self.resolver = binding, resolver
        self.resources, self.history_reader = resources, history_reader

    def secrets_for(self, parameters, action):
        if action not in ALLOWED_ACTIONS or action == 'pc_connectivity_probe':
            return {}
        # ONU pages may render the PPPoE account outside labelled controls.
        # Load its frozen pair for redaction only; never persist/cache it.
        kinds = ['ONU_WEB', 'PPPOE'] if action in WEB_ACTIONS else ['OLT']
        if action == 'provision_pppoe':
            kinds.append('PPPOE')
        secrets = {}
        try:
            for kind in kinds:
                pair = self.binding.access_bindings[kind]
                prefix = {'OLT': 'olt', 'ONU_WEB': 'onu_web', 'PPPOE': 'pppoe'}[kind]
                secrets[prefix + '_username'] = self.resolver.resolve(pair.username_ref)
                secrets[prefix + '_password'] = self.resolver.resolve(pair.password_ref)
        except Exception:
            return {}  # No partial credential pair and no fallback to current configuration.
        return secrets

    def execute(self, context: ActionContext) -> ActionOutcome:
        action = context.action_code
        if action not in ALLOWED_ACTIONS:
            return ActionOutcome('BLOCKED', (), (), 'ACTION_NOT_ALLOWED')
        required = ({'onu_web_username', 'onu_web_password'} if action in WEB_ACTIONS
                    else {'olt_username', 'olt_password'} if action in OLT_ACTIONS else set())
        if action == 'provision_pppoe':
            required |= {'pppoe_username', 'pppoe_password'}
        if not required <= set(context.secrets):
            return self._blocked(context, 'CREDENTIAL_UNAVAILABLE')
        history = list(self.history_reader())
        latest = next((e.payload_json.get('ref') for e in reversed(history)
                       if e.event_type == 'ACTION_STARTED'), None)
        if action in {'restore_snapshot', 'verify_restore'} or (
                action == 'snapshot_ont' and latest == 'RESTORE_VERIFY'):
            return ActionOutcome('BLOCKED', (), (), 'COMPLETE_WAN_RESTORE_UNSUPPORTED',
                                 'Registration-only restoration cannot verify the complete WAN snapshot; manual recovery required.')
        executor = None
        try:
            if action in OLT_ACTIONS:
                executor = _OLTExecutor(self.binding, self.resources, context)
                if action == 'verify_existing_registration':
                    outcome = self._verify_existing_registration(executor, context)
                else:
                    registry = LocalActionRegistry()
                    register_default_ma5800_actions(registry, MA5800Actions(executor))
                    outcome = registry.resolve('ma5800', action).execute(context)
                if executor.transcripts:
                    writer = GeneratedEvidenceWriter(context.workspace, clock=self.resources.clock)
                    artifacts = writer.write_text_and_png(uuid4().hex, title='OLT parsed transcript',
                        text='\n\n'.join(t.normalized_output for t in executor.transcripts),
                        redaction_values=tuple(secret.reveal() for secret in context.secrets.values()))
                    outcome = replace(outcome, artifacts=outcome.artifacts + artifacts)
            elif action in WEB_ACTIONS:
                bound_context = replace(context, parameters={**context.parameters,
                    'onu_web_url': self.binding.onu.url})
                adapter = NeutralONUWebAdapter(self.resources.web_surface_factory)
                mode = context.parameters.get('wan_mode')
                if mode not in {'IPOE', 'PPPOE'}:
                    return ActionOutcome('BLOCKED', (), (), 'WAN_MODE_REQUIRED')
                outcome = (adapter.capture_wan(bound_context, mode) if action == 'capture_onu_wan'
                           else adapter.run_ping(bound_context, mode, context.parameters['ping_target'], 4))
            else:
                outcome = self._pc(context, history)
            facts = derive_standard_facts(action, context.parameters, outcome.observations, history)
            return replace(outcome, observations=outcome.observations + facts + (
                Observation('runner.captured_at', self.resources.clock().isoformat(), 'LOCAL_RUNNER'),))
        except HostKeyFingerprintMismatchError:
            return self._blocked(context, 'OLT_HOST_KEY_PIN_MISMATCH')
        except UnavailableCredentialError:
            return self._blocked(context, 'CREDENTIAL_UNAVAILABLE')
        except Exception:
            return self._blocked(context, 'RUNNER_IO_UNAVAILABLE')
        finally:
            if executor is not None and not executor.close():
                return self._blocked(context, 'RUNNER_RESOURCE_CLOSE_FAILED')

    def _verify_existing_registration(self, executor, context):
        profile = self.binding.service_port_profile
        if profile is None or profile.ipoe is None or profile.pppoe is None:
            return ActionOutcome('BLOCKED', (), (), 'SERVICE_PORT_PROFILE_REQUIRED')
        target = _validated_target(context.parameters)
        transcript = executor.run(SafeMA5800Command('display_ont_by_sn', (target['serial'],)))
        text = normalize_cli_output(transcript.normalized_output)
        lines = text.splitlines()
        keys = [match[1].strip().casefold().replace('-', ' ') for line in lines
                if (match := re.fullmatch(r'([^:]+?)\s*:\s*(.*?)', line))]
        if (not lines or not PROMPT_LINE.fullmatch(lines[-1]) or len(keys) != len(set(keys))
                or re.search(r'(?im)^(?:Failure:|Error:|%)', text)):
            return ActionOutcome('BLOCKED', (), (), 'OLT_REGISTRATION_UNCONFIRMED')
        try:
            registration = parse_ont_state(text)
        except (ValueError, TypeError):
            return ActionOutcome('BLOCKED', (), (), 'OLT_REGISTRATION_UNCONFIRMED')
        fsp = '/'.join(str(target[key]) for key in ('frame', 'slot', 'pon_port'))
        if (registration.fsp != fsp or registration.ont_id != target['ont_id']
                or registration.serial_number != target['serial']
                or registration.line_profile_id != context.parameters.get('line_profile_id')
                or registration.service_profile_id != context.parameters.get('service_profile_id')
                or registration.run_state != 'online' or registration.match_state != 'match'):
            return ActionOutcome('BLOCKED', (), (), 'OLT_REGISTRATION_PROFILE_MISMATCH')
        transcript = executor.run(SafeMA5800Command('read_profile_gem', (registration.line_profile_id,)))
        try:
            mappings = parse_profile_gem(transcript.normalized_output, expected_profile_id=registration.line_profile_id)
        except (ValueError, TypeError):
            return ActionOutcome('BLOCKED', (), (), 'OLT_PROFILE_GEM_UNCONFIRMED')
        for spec in (profile.ipoe, profile.pppoe):
            if not any(item.gemport == spec.gemport and item.vlan == spec.user_vlan for item in mappings):
                return ActionOutcome('BLOCKED', (), (), 'OLT_PROFILE_GEM_MISMATCH')
        return ActionOutcome('PASS', (
            Observation('olt.retained_registration', asdict(registration), 'MA5800'),
            Observation('olt.registration.ready', True, 'MA5800'),
            Observation('olt.profile_gem.verified', True, 'MA5800'),
            Observation('olt.autofind.matched', True, 'MA5800',
                        'Existing registration proves the target is reported; no autofind observation was fabricated.'),
        ), ())

    def _blocked(self, context, code):
        artifacts = ()
        if context.workspace is not None:
            artifacts = GeneratedEvidenceWriter(context.workspace, clock=self.resources.clock).write_text_and_png(
                uuid4().hex, title='Local runner blocked', text=code)
        return ActionOutcome('BLOCKED', (), artifacts, code)

    def _pc(self, context, history):
        candidates = []
        target = ip_address(urlsplit(self.binding.onu.url).hostname)
        for item in self.resources.interface_provider():
            if (not item.is_up or item.interface_name.casefold() != self.binding.onu.pc_interface_name.casefold()
                    or type(item.prefix_length) is not int):
                continue
            try:
                interface = ip_interface(f'{item.address}/{item.prefix_length}')
                if target.version == interface.version and target in interface.network and (
                        not interface.ip.is_unspecified and not interface.ip.is_loopback
                        and not interface.ip.is_link_local and not interface.ip.is_multicast):
                    candidates.append(item.address)
            except ValueError:
                continue
        if len(set(candidates)) != 1:
            return self._wait_pc(context, 'PC_SOURCE_ADDRESS_UNCERTAIN')
        source = candidates[0]
        writer = GeneratedEvidenceWriter(context.workspace, clock=self.resources.clock)
        probe = self.resources.pc_probe_factory(writer, self.resources.interface_provider)
        result = probe.run(ProbeRequest(self.binding.onu.pc_interface_name, source,
            context.parameters['ping_target'], evidence_base=uuid4().hex))
        if result.status == 'WAITING_OPERATOR':
            # The provider may have changed between selection and probe validation.
            return self._wait_pc(context, 'PC_SOURCE_ADDRESS_CHANGED')
        observations = [Observation('pc.interface_name', self.binding.onu.pc_interface_name, 'PC_PROBE'),
                        Observation('pc.source_address', source, 'PC_PROBE')]
        if result.ping is not None:
            for key in ('sent', 'received', 'loss_percent'):
                name = {'sent': 'packets_sent', 'received': 'packets_received'}.get(key, key)
                observations.append(Observation('pc.ping.' + name, getattr(result.ping, key), 'PC_PROBE'))
        # A source-bound ping and historical ONU WAN are not current egress proof.
        # Retain diagnostic metrics/evidence, never credit another router to this WAN.
        return ActionOutcome(result.status, tuple(observations), result.artifacts,
                             result.error_code, 'PC_WAN_PATH_UNVERIFIED: diagnostic collection is not WAN success proof.')

    def _wait_pc(self, context, code):
        preview = dict(action_code=context.action_code, interface_name=self.binding.onu.pc_interface_name,
                       check_id=uuid4().hex,
                       summary='请连接绑定网卡并确认唯一源地址；接线确认，非配置修改授权。',
                       target_fsp='/'.join(str(context.parameters.get(key)) for key in ('frame', 'slot', 'pon_port')),
                       ont_id=context.parameters.get('ont_id'), serial_number=context.parameters.get('onu_serial_number'),
                       affected_service_ports=[])
        preview['preview_hash'] = sha256(json.dumps(preview, sort_keys=True).encode()).hexdigest()
        return ActionOutcome('WAITING_OPERATOR', (Observation('mutation.preview', preview, 'PC_PROBE'),), (), code)
