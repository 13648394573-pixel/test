"""Read-only, fail-closed ownership projection from persisted execution events.

Callers must replay the complete session stream. A cleanup candidate is not a
device authorization: approval, fresh identity/scope checks and I/O are separate.
"""
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.local_runner.credentials import REFERENCE_PATTERN
from app.local_runner.ma5800.service_port_contracts import PortContract, ServicePortMapping
from app.models.execution_session import ExecutionEvent


PORT_EVENTS = frozenset({'PORT_REUSED', 'PORT_CREATE_INTENT', 'PORT_CREATE_VERIFIED',
    'PORT_CREATE_UNCERTAIN', 'PORT_DELETE_INTENT', 'PORT_DELETE_VERIFIED',
    'PORT_DELETE_UNCERTAIN', 'PORT_RETAINED'})
CONSUMERS = frozenset({'IPOE', 'PPPOE'})


class _PortPayload(PortContract):
    version: Literal[1]
    operation_id: str = Field(min_length=1, max_length=80)
    mapping_key: str = Field(pattern=r'^[0-9a-f]{64}$')
    mapping: ServicePortMapping
    port_id: int = Field(ge=0, le=65535)
    origin: Literal['REUSED', 'CREATED']
    consumers: list[Literal['IPOE', 'PPPOE']] = Field(min_length=1)
    approval_hash: str | None = Field(pattern=r'^[0-9a-f]{64}$')
    baseline_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    read_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    verification_hash: str | None = Field(pattern=r'^[0-9a-f]{64}$')
    before_evidence_ids: list[str]
    after_evidence_ids: list[str]
    creation_event_id: str | None
    captured_at: str
    command_result: Literal['NOT_EXECUTED', 'PENDING', 'SUCCESS', 'UNKNOWN', 'ABSENT_CONFIRMED', 'KEPT']

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError('Invalid port event version')
        return value

    @field_validator('operation_id', 'creation_event_id')
    @classmethod
    def reference(cls, value):
        if value is not None and not REFERENCE_PATTERN.fullmatch(value):
            raise ValueError('Invalid port event reference')
        return value

    @field_validator('before_evidence_ids', 'after_evidence_ids')
    @classmethod
    def evidence_references(cls, values):
        if len(set(values)) != len(values) or any(not REFERENCE_PATTERN.fullmatch(value) for value in values):
            raise ValueError('Invalid evidence references')
        return values

    @field_validator('captured_at')
    @classmethod
    def aware_time(cls, value):
        captured = datetime.fromisoformat(value)
        if captured.utcoffset() is None:
            raise ValueError('Timezone-aware capture time is required')
        return value

    @model_validator(mode='after')
    def consistent(self):
        if self.mapping_key != self.mapping.mapping_key or len(set(self.consumers)) != len(self.consumers):
            raise ValueError('Conflicting mapping or consumers')
        if self.origin == 'CREATED' and self.mapping.candidate_id not in (None, self.port_id):
            raise ValueError('Candidate does not match resource ID')
        return self


@dataclass(frozen=True)
class PortResource:
    session_id: str
    mapping: ServicePortMapping
    port_id: int
    origin: Literal['REUSED', 'CREATED']
    consumers: frozenset[str]
    creation_event_id: str | None
    state: str
    operation_id: str
    baseline_hash: str
    approval_hash: str | None
    read_hash: str
    verification_hash: str | None
    before_evidence_ids: tuple[str, ...]
    last_evidence_ids: tuple[str, ...]
    last_event_id: str


def _project(event: ExecutionEvent, data: _PortPayload, state: str,
             creation_ref: str | None = None) -> PortResource:
    return PortResource(event.session_id, data.mapping, data.port_id, data.origin,
        frozenset(data.consumers), creation_ref, state, data.operation_id, data.baseline_hash,
        data.approval_hash, data.read_hash, data.verification_hash, tuple(data.before_evidence_ids),
        tuple(data.after_evidence_ids or data.before_evidence_ids), event.id)


def _same_scope(old: PortResource, data: _PortPayload) -> None:
    if (old.origin != data.origin or old.baseline_hash != data.baseline_hash
            or old.mapping.mapping_key != data.mapping_key or old.port_id != data.port_id):
        raise ValueError('Port resource provenance changed')


def _matching_intent(old: PortResource, data: _PortPayload) -> None:
    _same_scope(old, data)
    if (old.operation_id != data.operation_id or old.approval_hash != data.approval_hash
            or old.read_hash != data.read_hash or old.consumers != frozenset(data.consumers)
            or old.before_evidence_ids != tuple(data.before_evidence_ids)):
        raise ValueError('Port outcome does not match intent')


def _verified_evidence(data: _PortPayload) -> None:
    if (not data.before_evidence_ids or not data.after_evidence_ids
            or set(data.before_evidence_ids) & set(data.after_evidence_ids)
            or data.verification_hash in (None, data.read_hash)):
        raise ValueError('Port verification evidence is incomplete')


def _transition(old: PortResource | None, event: ExecutionEvent, data: _PortPayload) -> PortResource:
    kind = event.event_type
    if kind == 'PORT_REUSED':
        if (data.origin != 'REUSED' or data.command_result != 'NOT_EXECUTED'
                or data.approval_hash is not None or data.creation_event_id is not None
                or not data.after_evidence_ids or data.before_evidence_ids
                or data.verification_hash != data.read_hash):
            raise ValueError('Invalid reused resource evidence')
        resource = _project(event, data, 'REUSED')
        if old is not None:
            _same_scope(old, data)
            if old.state != 'REUSED':
                raise ValueError('Resource cannot become reused')
            resource = replace(resource, consumers=old.consumers | resource.consumers)
        return resource
    if kind == 'PORT_CREATE_INTENT':
        if (old is not None or data.origin != 'CREATED' or data.creation_event_id is not None
                or data.command_result != 'PENDING' or data.approval_hash is None
                or not data.before_evidence_ids or data.after_evidence_ids or data.verification_hash is not None):
            raise ValueError('Invalid create intent')
        return _project(event, data, 'CREATE_PENDING')
    if old is None:
        raise ValueError('Port lifecycle event has no provenance')
    _same_scope(old, data)
    if kind in {'PORT_CREATE_VERIFIED', 'PORT_CREATE_UNCERTAIN'}:
        if old.state != 'CREATE_PENDING' or data.origin != 'CREATED' or data.creation_event_id is not None:
            raise ValueError('Create outcome has no matching pending intent')
        _matching_intent(old, data)
        if kind == 'PORT_CREATE_VERIFIED':
            if data.command_result != 'SUCCESS':
                raise ValueError('Creation command was not successful')
            _verified_evidence(data)
            return _project(event, data, 'ACTIVE', event.id)
        if data.command_result != 'UNKNOWN':
            raise ValueError('Invalid uncertain creation outcome')
        return _project(event, data, 'CREATE_UNCERTAIN')
    if kind == 'PORT_RETAINED':
        if (old.state not in {'ACTIVE', 'REUSED'} or data.command_result != 'KEPT'
                or data.creation_event_id != old.creation_event_id
                or frozenset(data.consumers) != old.consumers):
            raise ValueError('Invalid retention of resource')
        return replace(_project(event, data, 'RETAINED', old.creation_event_id),
                       last_evidence_ids=old.last_evidence_ids, verification_hash=old.verification_hash)
    if data.origin != 'CREATED' or data.creation_event_id != old.creation_event_id or old.creation_event_id is None:
        raise ValueError('Deletion requires verified creation provenance')
    if kind == 'PORT_DELETE_INTENT':
        if (old.state not in {'ACTIVE', 'DELETE_UNCERTAIN'} or data.command_result != 'PENDING' or data.approval_hash is None
                or not data.before_evidence_ids or data.after_evidence_ids or data.verification_hash is not None
                or frozenset(data.consumers) != old.consumers):
            raise ValueError('Invalid delete intent')
        if old.state == 'DELETE_UNCERTAIN' and (
                data.operation_id == old.operation_id or data.approval_hash == old.approval_hash
                or set(data.before_evidence_ids) & set(old.before_evidence_ids)):
            raise ValueError('Retry requires new operation, approval and evidence')
        return _project(event, data, 'DELETE_PENDING', old.creation_event_id)
    if old.state != 'DELETE_PENDING' and not (
            old.state == 'DELETE_UNCERTAIN' and kind == 'PORT_DELETE_VERIFIED'):
        raise ValueError('Delete outcome has no matching pending intent')
    _matching_intent(old, data)
    if kind == 'PORT_DELETE_VERIFIED':
        if data.command_result != 'ABSENT_CONFIRMED':
            raise ValueError('Deletion absence is unconfirmed')
        _verified_evidence(data)
        return _project(event, data, 'DELETED', old.creation_event_id)
    if data.command_result != 'UNKNOWN':
        raise ValueError('Invalid uncertain deletion outcome')
    return _project(event, data, 'DELETE_UNCERTAIN', old.creation_event_id)


def replay_port_ledger(session_id: str, events: Sequence[ExecutionEvent]) -> tuple[PortResource, ...]:
    if not isinstance(session_id, str) or not REFERENCE_PATTERN.fullmatch(session_id):
        raise ValueError('Invalid ledger session')
    resources, seen_events, operations = {}, {}, {}
    session_scope = None
    next_sequence = 1
    for event in events:
        if event.session_id != session_id:
            continue
        if not isinstance(event.id, str) or not event.id or not isinstance(event.idempotency_key, str):
            raise ValueError('Persisted event identity is required')
        try:
            signature = json.dumps([event.id, event.sequence_no, event.event_type, event.payload_json],
                                   sort_keys=True, separators=(',', ':'))
        except (TypeError, ValueError):
            raise ValueError('Invalid execution event representation') from None
        if event.idempotency_key in seen_events:
            if seen_events[event.idempotency_key] != signature:
                raise ValueError('Conflicting duplicate execution event')
            continue
        if type(event.sequence_no) is not int or event.sequence_no != next_sequence:
            raise ValueError('Incomplete or unordered session event stream')
        next_sequence += 1
        seen_events[event.idempotency_key] = signature
        if not isinstance(event.event_type, str):
            raise ValueError('Invalid event type')
        if not event.event_type.startswith('PORT_'):
            continue
        if event.event_type not in PORT_EVENTS:
            raise ValueError('Unsupported port event type')
        try:
            data = _PortPayload.model_validate(event.payload_json)
        except ValueError:
            raise ValueError('Invalid port event payload') from None
        scope = (data.mapping.olt_binding_hash, data.mapping.fsp,
                 data.mapping.ont_id, data.baseline_hash)
        if session_scope is None:
            session_scope = scope
        elif session_scope != scope:
            raise ValueError('Port events cannot mix DUT scope or baseline')
        if event.idempotency_key != f'{data.operation_id}:{event.event_type}':
            raise ValueError('Port idempotency key does not match operation')
        resource_key = (data.mapping_key, data.port_id)
        family = ('CREATE' if event.event_type.startswith('PORT_CREATE_') else
                  'DELETE' if event.event_type.startswith('PORT_DELETE_') else event.event_type)
        operation_scope = (resource_key, family)
        if data.operation_id in operations and operations[data.operation_id] != operation_scope:
            raise ValueError('Operation ID reused across resources or actions')
        operations[data.operation_id] = operation_scope
        for resource in resources.values():
            if (resource.mapping.olt_binding_hash == data.mapping.olt_binding_hash
                    and resource.port_id == data.port_id and resource.mapping.mapping_key != data.mapping_key
                    and resource.state != 'DELETED'):
                raise ValueError('Live port ID has conflicting mapping')
            if (resource.mapping.mapping_key == data.mapping_key and resource.port_id != data.port_id
                    and resource.state != 'DELETED'):
                raise ValueError('Mapping has multiple live resource IDs')
        resources[resource_key] = _transition(resources.get(resource_key), event, data)
    return tuple(sorted(resources.values(), key=lambda resource: (resource.port_id, resource.mapping.mapping_key)))


def cleanup_candidates(resources: Sequence[PortResource], retained_consumers: frozenset[str]) -> tuple[PortResource, ...]:
    if not isinstance(retained_consumers, frozenset) or not retained_consumers <= CONSUMERS:
        raise ValueError('Invalid retained WAN consumers')
    if any(not isinstance(resource, PortResource) for resource in resources):
        raise ValueError('Cleanup requires a trusted resource projection')
    if len({resource.session_id for resource in resources}) > 1:
        raise ValueError('Cleanup cannot combine sessions')
    keys = {(resource.session_id, resource.mapping.mapping_key, resource.port_id)
            for resource in resources}
    if len(keys) != len(resources):
        raise ValueError('Cleanup cannot repeat resource projections')
    return tuple(resource for resource in resources
        if resource.origin == 'CREATED' and resource.state == 'ACTIVE'
        and resource.creation_event_id is not None and resource.verification_hash is not None
        and resource.last_evidence_ids and not resource.consumers & retained_consumers)
