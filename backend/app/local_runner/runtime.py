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
from .ma5800.parsers import PROMPT_LINE, normalize_cli_output, parse_ont_state, parse_profile_gem, parse_service_port_detail
from .ma5800.service_port_contracts import PortOperation, PortPreview, PortRead, ServicePortMapping, port_read_payload, read_port_payload
from .ma5800.transport import MA5800SSHConnector, MA5800Transport, SafeMA5800Command, HostKeyFingerprintMismatchError
from .onu_web.neutral import NeutralONUWebAdapter
from .pc_probe import PCProbe, ProbeRequest
from .registry import LocalActionRegistry


OLT_ACTIONS = frozenset({'preflight', 'discover_onts', 'snapshot_ont', 'find_free_ont_id',
    'delete_ont', 'register_ont', 'provision_ipoe', 'provision_pppoe', 'read_wan_info',
    'remove_test_services', 'restore_snapshot', 'verify_restore', 'verify_existing_registration',
    'inspect_service_mapping', 'create_service_port', 'verify_service_port',
    'inspect_service_port', 'delete_service_port'})
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
            if action == 'create_service_port' and not self._port_create_guard(context, history):
                return self._blocked(context, 'PORT_DURABLE_APPROVAL_REQUIRED')
            if action == 'delete_service_port' and not self._port_delete_guard(context, history):
                return self._blocked(context, 'PORT_DURABLE_APPROVAL_REQUIRED')
            if action in OLT_ACTIONS:
                executor = _OLTExecutor(self.binding, self.resources, context)
                if action == 'verify_existing_registration':
                    outcome = self._verify_existing_registration(executor, context)
                elif action in {'inspect_service_mapping', 'verify_service_port'}:
                    outcome = self._inspect_service_mapping(executor, context)
                elif action == 'create_service_port':
                    outcome = self._create_service_port(executor, context)
                elif action == 'inspect_service_port':
                    outcome = self._inspect_service_port(executor, context)
                elif action == 'delete_service_port':
                    outcome = self._delete_service_port(executor, context)
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
            Observation('olt.profile_gem.mappings', [asdict(item) for item in mappings], 'MA5800'),
            Observation('olt.autofind.matched', True, 'MA5800',
                        'Existing registration proves the target is reported; no autofind observation was fabricated.'),
        ), ())

    def _port_mapping(self, context):
        mapping = ServicePortMapping.model_validate(context.parameters['service_port_mapping'])
        binding_hash = sha256(json.dumps(self.binding.olt.model_dump(mode='json'), sort_keys=True,
                                        separators=(',', ':')).encode()).hexdigest()
        target = _validated_target(context.parameters)
        spec = mapping.model_dump(mode='json', exclude={'olt_binding_hash', 'fsp', 'ont_id'})
        profile = self.binding.service_port_profile
        if (mapping.olt_binding_hash != binding_hash or mapping.ont_id != target['ont_id']
                or mapping.fsp != '/'.join(str(target[key]) for key in ('frame', 'slot', 'pon_port'))
                or profile is None or not any(item is not None and item.model_dump(mode='json') == spec
                                              for item in (profile.ipoe, profile.pppoe))):
            raise ValueError('Mapping differs from frozen binding')
        return mapping, target

    def _inspect_service_mapping(self, executor, context):
        mapping, target = self._port_mapping(context)
        verification = self._verify_existing_registration(executor, context)
        if verification.status != 'PASS':
            return verification
        facts = {item.fact_key: item.value for item in verification.observations}
        transcript = executor.run(SafeMA5800Command('display_service_ports', (mapping.fsp, mapping.ont_id)))
        ports = MA5800Actions._target_service_ports(transcript, target)
        details, ambiguous = [], False
        for port in ports:
            raw = executor.run(SafeMA5800Command('display_service_port_by_id', (port.service_port_id,)))
            read = parse_service_port_detail(raw.normalized_output, binding_hash=mapping.olt_binding_hash)
            if read.status != 'FOUND' or len(read.items) != 1 or read.items[0].port_id != port.service_port_id:
                ambiguous = True
            elif read.items[0].mapping.fsp != mapping.fsp or read.items[0].mapping.ont_id != mapping.ont_id:
                ambiguous = True
            else:
                details.append(read.items[0])
        ambiguous |= any(item.mapping.vlan == mapping.vlan and item.mapping.mapping_key != mapping.mapping_key
                         for item in details)
        matches = [item for item in details if item.mapping.mapping_key == mapping.mapping_key]
        status, items = 'UNCONFIRMED', ()
        if not ambiguous and len(matches) == 1:
            status, items = 'FOUND', (matches[0],)
        elif not ambiguous and not matches and mapping.candidate_id is not None:
            raw = executor.run(SafeMA5800Command('display_service_port_by_id', (mapping.candidate_id,)))
            candidate = parse_service_port_detail(raw.normalized_output, binding_hash=mapping.olt_binding_hash)
            if candidate.status == 'ABSENT' and candidate.query_port_id == mapping.candidate_id:
                status = 'ABSENT'
        semantic = dict(binding_hash=mapping.olt_binding_hash, mapping=mapping.model_dump(mode='json'),
            registration=facts['olt.retained_registration'], profile=facts['olt.profile_gem.mappings'],
            ports=[dict(port_id=item.port_id, mapping=item.mapping.model_dump(mode='json'), state=item.state)
                   for item in sorted(details, key=lambda item: item.port_id)], status=status)
        digest = sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        read = PortRead(mapping.olt_binding_hash, digest, status, items, query_port_id=mapping.candidate_id)
        return ActionOutcome('PASS' if status != 'UNCONFIRMED' else 'BLOCKED',
            (Observation('port.read', port_read_payload(read), 'MA5800'),
             Observation('olt.profile_gem.verified', True, 'MA5800')), (),
            None if status != 'UNCONFIRMED' else 'PORT_MAPPING_UNCONFIRMED')

    def _port_create_guard(self, context, history):
        try:
            operation = PortOperation.model_validate(context.parameters['port_operation'])
            approval = context.parameters['port_approval']
            mapping, _ = self._port_mapping(context)
            if operation.session_id != context.session_id or operation.kind != 'CREATE' or operation.mapping != mapping:
                return False
            if (operation.serial_number != context.parameters['onu_serial_number'].upper()
                    or operation.line_profile_id != context.parameters['line_profile_id']
                    or operation.service_profile_id != context.parameters['service_profile_id']):
                return False
            if context.parameters.get('end_policy') != 'KEEP' or approval['operation'] != operation.model_dump(mode='json'):
                return False
            if PortPreview(operation, read_port_payload(approval['read'])).preview_hash != approval['preview_hash']:
                return False
            own = [event for event in history if event.session_id == context.session_id]
            if any(event.event_type in {'PORT_CREATE_VERIFIED', 'PORT_CREATE_UNCERTAIN'}
                   and event.payload_json.get('operation_id') == operation.operation_id for event in own):
                return False
            saved = next((event for event in own if event.idempotency_key == operation.operation_id + ':preview'), None)
            intent = next((event for event in own if event.idempotency_key == operation.operation_id + ':PORT_CREATE_INTENT'), None)
            if saved is None or saved.payload_json != approval or intent is None:
                return False
            payload = intent.payload_json
            return (payload.get('approval_hash') == approval['preview_hash']
                    and payload.get('mapping') == mapping.model_dump(mode='json')
                    and payload.get('port_id') == operation.port_id and payload.get('baseline_hash') == operation.baseline_hash
                    and payload.get('read_hash') == operation.read_hash and payload.get('command_result') == 'PENDING')
        except (ValueError, KeyError, TypeError):
            return False

    def _create_service_port(self, executor, context):
        operation = PortOperation.model_validate(context.parameters['port_operation'])
        fresh = self._inspect_service_mapping(executor, context)
        values = {item.fact_key: item.value for item in fresh.observations}
        read = read_port_payload(values['port.read'])
        if fresh.status != 'PASS' or read.status != 'ABSENT' or read.observation_hash != operation.read_hash:
            return ActionOutcome('BLOCKED', fresh.observations, (), 'PORT_APPROVAL_STALE')
        command = MA5800Actions(executor).create_service_port(operation)
        if command.status != 'PASS':
            return command
        after = self._inspect_service_mapping(executor, context)
        result = read_port_payload(next(item.value for item in after.observations if item.fact_key == 'port.read'))
        verified = after.status == 'PASS' and result.status == 'FOUND' and result.items[0].port_id == operation.port_id
        return ActionOutcome('PASS' if verified else 'BLOCKED', command.observations + after.observations, (),
                             None if verified else 'PORT_POSTCONDITION_UNCONFIRMED')

    def _inspect_service_port(self, executor, context):
        """Global ID proof with a per-resource hash, independent of other batch deletions."""
        mapping, _ = self._port_mapping(context)
        verification = self._verify_existing_registration(executor, context)
        if verification.status != 'PASS':
            return verification
        operation = (PortOperation.model_validate(context.parameters['port_operation'])
                     if 'port_operation' in context.parameters else None)
        identifier = operation.port_id if operation else mapping.candidate_id
        if identifier is None:
            return ActionOutcome('BLOCKED', (), (), 'PORT_ID_REQUIRED')
        transcript = executor.run(SafeMA5800Command('display_service_port_by_id', (identifier,)))
        read = parse_service_port_detail(transcript.normalized_output, binding_hash=mapping.olt_binding_hash)
        if (read.status == 'FOUND' and (len(read.items) != 1 or read.items[0].port_id != identifier
                or read.items[0].mapping.mapping_key != mapping.mapping_key)):
            read = replace(read, status='UNCONFIRMED')
        if read.status == 'ABSENT' and read.query_port_id != identifier:
            read = replace(read, status='UNCONFIRMED')
        facts = {o.fact_key: o.value for o in verification.observations}
        semantic = dict(mapping=mapping.model_dump(mode='json'), port_id=identifier,
            registration=facts['olt.retained_registration'], profile=facts['olt.profile_gem.mappings'],
            status=read.status, items=[dict(port_id=item.port_id, mapping=item.mapping.model_dump(mode='json'),
                state=item.state) for item in read.items])
        digest = sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        read = replace(read, observation_hash=digest, query_port_id=identifier)
        return ActionOutcome('PASS' if read.status != 'UNCONFIRMED' else 'BLOCKED',
            (Observation('port.read', port_read_payload(read), 'MA5800'),
             Observation('olt.profile_gem.verified', True, 'MA5800')), (),
            None if read.status != 'UNCONFIRMED' else 'PORT_MAPPING_UNCONFIRMED')

    def _port_delete_guard(self, context, history):
        try:
            from app.skill_execution.service_port_ledger import replay_port_ledger
            from app.skill_execution.service_port_lifecycle import cleanup_batch_payload
            operation = PortOperation.model_validate(context.parameters['port_operation'])
            approval = context.parameters['port_approval']
            mapping, _ = self._port_mapping(context)
            if (operation.session_id != context.session_id or operation.kind != 'DELETE'
                    or operation.mapping != mapping or context.parameters.get('end_policy') != 'KEEP'
                    or operation.serial_number != context.parameters['onu_serial_number'].upper()
                    or operation.line_profile_id != context.parameters['line_profile_id']
                    or operation.service_profile_id != context.parameters['service_profile_id']):
                return False
            previews = tuple(PortPreview(PortOperation.model_validate(p['operation']), read_port_payload(p['read']))
                             for p in approval['previews'])
            if cleanup_batch_payload(previews, frozenset(approval['retained_consumers'])) != approval:
                return False
            if not any(p.operation == operation and p.read.observation_hash == operation.read_hash for p in previews):
                return False
            own = [e for e in history if e.session_id == context.session_id]
            if not any(e.event_type == 'SERVICE_PORT_CLEANUP_PREVIEW' and e.payload_json == approval for e in own):
                return False
            resource = next((r for r in replay_port_ledger(context.session_id, own)
                if r.mapping.mapping_key == mapping.mapping_key and r.port_id == operation.port_id), None)
            return (resource is not None and resource.state == 'DELETE_PENDING' and resource.origin == 'CREATED'
                    and resource.operation_id == operation.operation_id and resource.creation_event_id == operation.creation_event_id
                    and resource.baseline_hash == operation.baseline_hash and resource.read_hash == operation.read_hash
                    and resource.approval_hash == approval['preview_hash']
                    and resource.consumers == frozenset(operation.consumers)
                    and not resource.consumers & frozenset(approval['retained_consumers']))
        except (ValueError, KeyError, TypeError):
            return False

    def _delete_service_port(self, executor, context):
        operation = PortOperation.model_validate(context.parameters['port_operation'])
        fresh = self._inspect_service_port(executor, context)
        values = {o.fact_key: o.value for o in fresh.observations}
        read = read_port_payload(values['port.read'])
        if (fresh.status != 'PASS' or read.status != 'FOUND' or read.items[0].port_id != operation.port_id
                or read.observation_hash != operation.read_hash):
            return ActionOutcome('BLOCKED', fresh.observations, (), 'PORT_APPROVAL_STALE')
        command = MA5800Actions(executor).delete_service_port(operation)
        if command.status != 'PASS':
            return command
        after = self._inspect_service_port(executor, context)
        result = read_port_payload(next(o.value for o in after.observations if o.fact_key == 'port.read'))
        verified = after.status == 'PASS' and result.status == 'ABSENT' and result.query_port_id == operation.port_id
        return ActionOutcome('PASS' if verified else 'BLOCKED', command.observations + after.observations, (),
                             None if verified else 'PORT_DELETE_ABSENCE_UNCONFIRMED')

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
