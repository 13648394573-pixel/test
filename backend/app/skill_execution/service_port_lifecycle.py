"""Approved port creation: durable intentions, real evidence, no implicit retries."""
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from uuid import uuid4

from app.local_runner.configuration import RuntimeBinding
from app.local_runner.contracts import ActionOutcome, Observation
from app.local_runner.ma5800.service_port_contracts import (
    PortOperation, PortPreview, PortRead, ServicePortMapping, port_read_payload, read_port_payload)
from app.models.evidence import Evidence
from app.models.test_execution import RunResult, TestRun
from app.skill_execution.service_port_ledger import replay_port_ledger, cleanup_candidates


def cleanup_batch_payload(previews, retained_consumers):
    body = dict(action_code='cleanup_service_ports', previews=[p.to_payload() for p in previews],
                retained_consumers=sorted(retained_consumers))
    return {**body, 'preview_hash': sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def olt_binding_hash(binding: RuntimeBinding) -> str:
    return sha256(json.dumps(binding.olt.model_dump(mode='json'), sort_keys=True,
                             separators=(',', ':')).encode()).hexdigest()


class ServicePortLifecycle:
    def __init__(self, repository, *, inspect_device, create_device, persist_evidence, storage,
                 delete_device=None, inspect_cleanup_device=None):
        self.repository = repository
        self.inspect_device, self.create_device = inspect_device, create_device
        self.persist_evidence, self.storage = persist_evidence, storage
        self.delete_device, self.inspect_cleanup_device = delete_device, inspect_cleanup_device

    def _scope(self, sid, mapping):
        repo = self.repository
        execution = repo.get(sid)
        result = repo.session.get(RunResult, execution.run_result_id)
        run = repo.session.get(TestRun, execution.test_run_id)
        binding = RuntimeBinding.model_validate(execution.plugin_snapshot['runtime_binding'])
        parameters = result.parameter_snapshot
        fsp = '/'.join(str(parameters[key]) for key in ('frame', 'slot', 'pon_port'))
        if (execution.status not in {'CREATED', 'RUNNING'}
                or run.execution_plan_snapshot.get('version') != 2 or result.integrity_status == 'LOCKED'
                or parameters.get('end_policy') != 'KEEP' or mapping.olt_binding_hash != olt_binding_hash(binding)
                or mapping.fsp != fsp or mapping.ont_id != parameters['ont_id']
                or len(execution.configuration_snapshots) != 1):
            raise ValueError('Unconfirmed service-port session scope')
        baseline = execution.configuration_snapshots[0]
        actual = sha256(json.dumps(baseline.snapshot_json, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if actual != baseline.sha256:
            raise ValueError('Baseline integrity mismatch')
        spec = mapping.model_dump(mode='json', exclude={'olt_binding_hash', 'fsp', 'ont_id'})
        consumers = tuple(wan for wan in ('IPOE', 'PPPOE')
            if binding.service_port_profile is not None and getattr(binding.service_port_profile, wan.lower()) is not None
            and getattr(binding.service_port_profile, wan.lower()).model_dump(mode='json') == spec)
        if not consumers:
            raise ValueError('Mapping does not belong to the frozen profile')
        return baseline.sha256, consumers

    def _proofs(self, sid, ids):
        execution = self.repository.get(sid)
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('Evidence is required')
        for identifier in ids:
            item = self.repository.session.get(Evidence, identifier)
            if (item is None or item.execution_session_id != sid or item.run_result_id != execution.run_result_id
                    or item.redacted is not True
                    or sha256(self.storage.open_path(item.storage_path).read_bytes()).hexdigest() != item.sha256):
                raise ValueError('Evidence integrity or ownership mismatch')

    @staticmethod
    def _normalize(read, mapping):
        valid = read.binding_hash == mapping.olt_binding_hash
        if read.status == 'FOUND':
            valid &= len(read.items) == 1 and read.items[0].mapping.mapping_key == mapping.mapping_key
        elif read.status == 'ABSENT':
            valid &= not read.items and mapping.candidate_id is not None and read.query_port_id == mapping.candidate_id
        else:
            valid = False
        return read if valid else replace(read, status='UNCONFIRMED')

    def _capture(self, sid, mapping, *, cleanup=False):
        self._scope(sid, mapping)
        self.repository.session.commit()  # Release the DB boundary before device I/O.
        callback = self.inspect_cleanup_device if cleanup and self.inspect_cleanup_device else self.inspect_device
        outcome = callback(sid, mapping)
        values = {o.fact_key: o.value for o in outcome.observations if o.source == 'MA5800'}
        read = (read_port_payload(values['port.read']) if 'port.read' in values else
                PortRead(mapping.olt_binding_hash, sha256(str(outcome.error_code).encode()).hexdigest()))
        if outcome.status != 'PASS' or values.get('olt.profile_gem.verified') is not True:
            read = replace(read, status='UNCONFIRMED')
        read = self._normalize(read, mapping)
        ids = self.persist_evidence(sid, outcome)
        self._proofs(sid, ids)
        read = replace(read, evidence_ids=tuple(ids))
        self.repository.append_event(sid, 'SERVICE_MAPPING_READ',
            {'mapping_key': mapping.mapping_key, 'read': port_read_payload(read)}, f'read-{uuid4().hex}:capture')
        self.repository.session.commit()
        return read

    def _append(self, sid, kind, payload):
        event = self.repository.append_event(sid, kind, payload, f"{payload['operation_id']}:{kind}")
        replay_port_ledger(sid, self.repository.events(sid))  # Reject invalid persisted transitions before commit.
        self.repository.session.commit()
        return event

    def _payload(self, op, consumers, *, approval, before, after=(), result='PENDING', verification=None):
        return dict(version=1, operation_id=op.operation_id, mapping_key=op.mapping.mapping_key,
            mapping=op.mapping.model_dump(mode='json'), port_id=op.port_id, origin='CREATED',
            consumers=list(consumers), approval_hash=approval, baseline_hash=op.baseline_hash,
            read_hash=op.read_hash, verification_hash=verification, before_evidence_ids=list(before),
            after_evidence_ids=list(after), creation_event_id=None,
            captured_at=datetime.now(UTC).isoformat(), command_result=result)

    def inspect(self, session_id: str, mapping: ServicePortMapping) -> PortRead:
        baseline, consumers = self._scope(session_id, mapping)
        read = self._capture(session_id, mapping)
        existing = replay_port_ledger(session_id, self.repository.events(session_id))
        if read.status == 'FOUND' and not any(item.mapping.mapping_key == mapping.mapping_key for item in existing):
            op = dict(version=1, operation_id='reuse-' + mapping.mapping_key[:24], mapping_key=mapping.mapping_key,
                mapping=mapping.model_dump(mode='json'), port_id=read.items[0].port_id, origin='REUSED',
                consumers=list(consumers), approval_hash=None, baseline_hash=baseline,
                read_hash=read.observation_hash, verification_hash=read.observation_hash,
                before_evidence_ids=[], after_evidence_ids=list(read.evidence_ids), creation_event_id=None,
                captured_at=datetime.now(UTC).isoformat(), command_result='NOT_EXECUTED')
            self._append(session_id, 'PORT_REUSED', op)
        return read

    def preview(self, operation: PortOperation, read: PortRead) -> PortPreview:
        baseline, consumers = self._scope(operation.session_id, operation.mapping)
        self._operation_target(operation, consumers)
        if (operation.kind != 'CREATE' or operation.baseline_hash != baseline or read.status != 'ABSENT'
                or operation.mapping.candidate_id != operation.port_id or operation.read_hash != read.observation_hash):
            raise ValueError('Invalid creation preview scope')
        self._proofs(operation.session_id, read.evidence_ids)
        if not any(e.event_type == 'SERVICE_MAPPING_READ' and e.payload_json.get('read') == port_read_payload(read)
                   for e in self.repository.events(operation.session_id)):
            raise ValueError('Preview requires a persisted read')
        preview = PortPreview(operation, read)
        self.repository.append_event(operation.session_id, 'SERVICE_PORT_PREVIEW', preview.to_payload(),
                                     operation.operation_id + ':preview')
        self.repository.session.commit()
        return preview

    @staticmethod
    def _blocked(code):
        return ActionOutcome('BLOCKED', (), (), code)

    def _operation_target(self, operation, consumers):
        execution = self.repository.get(operation.session_id)
        values = self.repository.session.get(RunResult, execution.run_result_id).parameter_snapshot
        if (operation.serial_number != values['onu_serial_number'].upper()
                or operation.line_profile_id != values['line_profile_id']
                or operation.service_profile_id != values['service_profile_id'] or operation.consumers != consumers):
            raise ValueError('Operation target differs from frozen session')

    def execute_approved(self, operation: PortOperation, preview_hash: str) -> ActionOutcome:
        repo, sid = self.repository, operation.session_id
        try:
            baseline, consumers = self._scope(sid, operation.mapping)
            self._operation_target(operation, consumers)
            if operation.kind != 'CREATE' or operation.baseline_hash != baseline or operation.mapping.candidate_id != operation.port_id:
                return self._blocked('PORT_APPROVAL_SCOPE_MISMATCH')
            events = repo.events(sid)
            saved = next((e.payload_json for e in events if e.idempotency_key == operation.operation_id + ':preview'), None)
            if saved is None or saved['operation'] != operation.model_dump(mode='json') or saved['preview_hash'] != preview_hash:
                return self._blocked('PORT_APPROVAL_SCOPE_MISMATCH')
            original = read_port_payload(saved['read'])
            if PortPreview(operation, original).preview_hash != preview_hash:
                return self._blocked('PORT_APPROVAL_SCOPE_MISMATCH')
            prior = [e for e in events if e.payload_json.get('operation_id') == operation.operation_id and e.event_type.startswith('PORT_CREATE_')]
            if prior:
                if any(e.event_type == 'PORT_CREATE_VERIFIED' for e in prior):
                    return ActionOutcome('PASS', (), ())
                return self._blocked('PORT_RECOVERY_REQUIRED')
            self._proofs(sid, original.evidence_ids)
            fresh = self._capture(sid, operation.mapping)
            if fresh.status != 'ABSENT' or fresh.observation_hash != operation.read_hash:
                return self._blocked('PORT_APPROVAL_STALE')
            before = (*original.evidence_ids, *fresh.evidence_ids)
            payload = self._payload(operation, consumers, approval=preview_hash, before=before)
            self._append(sid, 'PORT_CREATE_INTENT', payload)
        except Exception:
            repo.session.rollback()
            return self._blocked('PORT_INTENT_NOT_COMMITTED')
        try:
            outcome = self.create_device(operation, saved)
            values = {o.fact_key: o.value for o in outcome.observations if o.source == 'MA5800'}
            after = self._normalize(read_port_payload(values['port.read']), operation.mapping)
            ids = self.persist_evidence(sid, outcome)
            self._proofs(sid, ids)
            self._proofs(sid, before)
            current_baseline, current_consumers = self._scope(sid, operation.mapping)
            if current_baseline != operation.baseline_hash or current_consumers != consumers:
                raise ValueError('Session scope changed during creation')
            if (outcome.status != 'PASS' or after.status != 'FOUND' or after.items[0].port_id != operation.port_id
                    or values.get('port.command_succeeded') is not True
                    or values.get('olt.profile_gem.verified') is not True or after.observation_hash == operation.read_hash):
                raise ValueError('Creation postcondition unconfirmed')
            verified = {**payload, 'after_evidence_ids': list(ids), 'verification_hash': after.observation_hash,
                        'command_result': 'SUCCESS', 'captured_at': datetime.now(UTC).isoformat()}
            self._append(sid, 'PORT_CREATE_VERIFIED', verified)
            return ActionOutcome('PASS', (Observation('port.creation.verified', True, 'MA5800'),), ())
        except Exception:
            repo.session.rollback()
            try:
                self._append(sid, 'PORT_CREATE_UNCERTAIN', {**payload, 'command_result': 'UNKNOWN',
                             'captured_at': datetime.now(UTC).isoformat()})
            except Exception:
                repo.session.rollback()  # The committed INTENT remains the durable recovery authority.
            return self._blocked('PORT_CREATION_UNCERTAIN')

    def _resources(self, sid):
        return replay_port_ledger(sid, self.repository.events(sid))

    def _creation_proof(self, sid, resource):
        event = next((e for e in self.repository.events(sid) if e.id == resource.creation_event_id
                      and e.event_type == 'PORT_CREATE_VERIFIED'), None)
        if (event is None or resource.origin != 'CREATED'
                or event.payload_json['mapping'] != resource.mapping.model_dump(mode='json')
                or event.payload_json['port_id'] != resource.port_id):
            raise ValueError('Verified session creation is required')
        self._proofs(sid, (*event.payload_json['before_evidence_ids'], *event.payload_json['after_evidence_ids']))

    def preview_cleanup(self, session_id: str, retained_consumers: frozenset[str]) -> tuple[PortPreview, ...]:
        candidates = cleanup_candidates(self._resources(session_id), retained_consumers)
        previews = []
        for resource in candidates:
            baseline, consumers = self._scope(session_id, resource.mapping)
            self._creation_proof(session_id, resource)
            read = self._capture(session_id, resource.mapping, cleanup=True)
            if read.status == 'UNCONFIRMED' or (read.status == 'FOUND' and read.items[0].port_id != resource.port_id):
                raise ValueError('Cleanup mapping is unconfirmed')
            values = self.repository.session.get(RunResult, self.repository.get(session_id).run_result_id).parameter_snapshot
            operation = PortOperation(operation_id='delete-' + uuid4().hex, session_id=session_id,
                mapping=resource.mapping, port_id=resource.port_id, kind='DELETE', baseline_hash=baseline,
                read_hash=read.observation_hash, creation_event_id=resource.creation_event_id,
                serial_number=values['onu_serial_number'].upper(), line_profile_id=values['line_profile_id'],
                service_profile_id=values['service_profile_id'], consumers=consumers)
            previews.append(PortPreview(operation, read))
        batch = cleanup_batch_payload(tuple(previews), retained_consumers)
        self.repository.append_event(session_id, 'SERVICE_PORT_CLEANUP_PREVIEW', batch, 'cleanup-' + batch['preview_hash'])
        self.repository.session.commit()
        return tuple(previews)

    def retain(self, session_id: str):
        for resource in self._resources(session_id):
            if resource.state not in {'ACTIVE', 'REUSED'}:
                continue
            self._scope(session_id, resource.mapping)
            # KEEP is a ledger decision, never a device call or an ownership upgrade.
            event = next(e for e in self.repository.events(session_id) if e.id == resource.last_event_id)
            payload = {**event.payload_json, 'operation_id': 'keep-' + resource.last_event_id,
                'creation_event_id': resource.creation_event_id, 'command_result': 'KEPT',
                'captured_at': datetime.now(UTC).isoformat()}
            self._append(session_id, 'PORT_RETAINED', payload)

    def cleanup(self, session_id: str, previews: tuple[PortPreview, ...], approval_hash: str) -> ActionOutcome:
        repo, outcomes = self.repository, []
        try:
            saved = next((e.payload_json for e in repo.events(session_id)
                if e.event_type == 'SERVICE_PORT_CLEANUP_PREVIEW' and e.payload_json.get('preview_hash') == approval_hash), None)
            if saved is None or not isinstance(previews, tuple):
                return self._blocked('PORT_CLEANUP_APPROVAL_MISMATCH')
            retained = frozenset(saved['retained_consumers'])
            if cleanup_batch_payload(previews, retained) != saved:
                return self._blocked('PORT_CLEANUP_APPROVAL_MISMATCH')
            resources = self._resources(session_id)
            expected = {(r.mapping.mapping_key, r.port_id) for r in cleanup_candidates(resources, retained)}
            remaining = {(p.operation.mapping.mapping_key, p.operation.port_id) for p in previews
                         if not any(r.creation_event_id == p.operation.creation_event_id and r.state == 'DELETED'
                                    for r in resources)}
            # No caller-supplied subset, no new owned resources added since approval.
            if expected != remaining:
                return self._blocked('PORT_CLEANUP_SCOPE_CHANGED')
            for preview in previews:
                operation = preview.operation
                baseline, consumers = self._scope(session_id, operation.mapping)
                self._operation_target(operation, consumers)
                resource = next(r for r in resources if r.port_id == operation.port_id
                                and r.mapping.mapping_key == operation.mapping.mapping_key)
                if (operation.session_id != session_id or operation.kind != 'DELETE'
                        or baseline != operation.baseline_hash or resource.creation_event_id != operation.creation_event_id
                        or resource.origin != 'CREATED' or resource.consumers & retained):
                    return self._blocked('PORT_CLEANUP_SCOPE_CHANGED')
                if resource.state == 'DELETED':
                    done = next(e for e in repo.events(session_id) if e.id == resource.last_event_id)
                    if done.payload_json['operation_id'] != operation.operation_id:
                        return self._blocked('PORT_CLEANUP_SCOPE_CHANGED')
                elif resource.state != 'ACTIVE':
                    return self._blocked('PORT_RECOVERY_REQUIRED')
                self._creation_proof(session_id, resource)
                self._proofs(session_id, preview.read.evidence_ids)
        except Exception:
            repo.session.rollback()
            return self._blocked('PORT_CLEANUP_SCOPE_CHANGED')
        for index, preview in enumerate(previews):
            operation, payload = preview.operation, None
            if any(r.port_id == operation.port_id and r.state == 'DELETED' for r in self._resources(session_id)):
                outcomes.append(dict(port_id=operation.port_id, status='DELETED'))
                continue
            try:
                fresh = self._capture(session_id, operation.mapping, cleanup=True)
                if fresh.observation_hash != operation.read_hash or fresh.status != preview.read.status:
                    raise ValueError('Cleanup approval stale')
                if fresh.status == 'UNCONFIRMED' or (fresh.status == 'FOUND' and fresh.items[0].port_id != operation.port_id):
                    raise ValueError('Cleanup mapping changed')
                resource = next(r for r in self._resources(session_id) if r.creation_event_id == operation.creation_event_id)
                if resource.state != 'ACTIVE':
                    raise ValueError('Cleanup provenance changed')
                self._creation_proof(session_id, resource)
                self._proofs(session_id, preview.read.evidence_ids)
                baseline, consumers = self._scope(session_id, operation.mapping)
                self._operation_target(operation, consumers)
                if baseline != operation.baseline_hash:
                    raise ValueError('Baseline changed')
                before = (*preview.read.evidence_ids, *fresh.evidence_ids)
                payload = {**self._payload(operation, consumers, approval=approval_hash, before=before),
                           'creation_event_id': operation.creation_event_id}
                self._append(session_id, 'PORT_DELETE_INTENT', payload)
                if fresh.status == 'ABSENT':
                    after = self._capture(session_id, operation.mapping, cleanup=True)
                    ids = after.evidence_ids
                    repo.append_event(session_id, 'SERVICE_PORT_ABSENCE_OBSERVED',
                        {'operation_id': operation.operation_id, 'port_id': operation.port_id, 'command_executed': False},
                        operation.operation_id + ':absence')
                else:
                    if self.delete_device is None:
                        raise ValueError('Delete device boundary unavailable')
                    outcome = self.delete_device(operation, saved)
                    values = {o.fact_key: o.value for o in outcome.observations if o.source == 'MA5800'}
                    ids = self.persist_evidence(session_id, outcome)
                    after = self._normalize(read_port_payload(values['port.read']), operation.mapping)
                    if (outcome.status != 'PASS' or values.get('port.command_succeeded') is not True
                            or values.get('olt.profile_gem.verified') is not True):
                        raise ValueError('Delete command unconfirmed')
                self._proofs(session_id, ids)
                self._proofs(session_id, before)
                self._creation_proof(session_id, resource)
                self._scope(session_id, operation.mapping)
                if after.status != 'ABSENT' or after.query_port_id != operation.port_id:
                    raise ValueError('Delete absence unconfirmed')
                verification = sha256(json.dumps(port_read_payload(replace(after, evidence_ids=tuple(ids))),
                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                self._append(session_id, 'PORT_DELETE_VERIFIED', {**payload, 'command_result': 'ABSENT_CONFIRMED',
                    'after_evidence_ids': list(ids), 'verification_hash': verification,
                    'captured_at': datetime.now(UTC).isoformat()})
                outcomes.append(dict(port_id=operation.port_id, status='DELETED'))
            except Exception:
                repo.session.rollback()
                if payload is not None:
                    try:
                        self._append(session_id, 'PORT_DELETE_UNCERTAIN', {**payload, 'command_result': 'UNKNOWN',
                            'captured_at': datetime.now(UTC).isoformat()})
                    except Exception:
                        repo.session.rollback()
                outcomes.append(dict(port_id=operation.port_id, status='UNCERTAIN' if payload else 'BLOCKED'))
                outcomes.extend(dict(port_id=p.operation.port_id, status='NOT_PROCESSED') for p in previews[index + 1:])
                return ActionOutcome('BLOCKED', (Observation('port.cleanup.items', outcomes, 'MA5800'),), (),
                                     'PORT_CLEANUP_INCOMPLETE')
        return ActionOutcome('PASS', (Observation('port.cleanup.items', outcomes, 'MA5800'),), ())
