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
from app.skill_execution.service_port_ledger import replay_port_ledger


def olt_binding_hash(binding: RuntimeBinding) -> str:
    return sha256(json.dumps(binding.olt.model_dump(mode='json'), sort_keys=True,
                             separators=(',', ':')).encode()).hexdigest()


class ServicePortLifecycle:
    def __init__(self, repository, *, inspect_device, create_device, persist_evidence, storage):
        self.repository = repository
        self.inspect_device, self.create_device = inspect_device, create_device
        self.persist_evidence, self.storage = persist_evidence, storage

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

    def _capture(self, sid, mapping):
        self._scope(sid, mapping)
        self.repository.session.commit()  # Release the DB boundary before device I/O.
        outcome = self.inspect_device(sid, mapping)
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
