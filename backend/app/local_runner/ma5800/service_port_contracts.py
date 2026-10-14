"""Immutable contracts for the verified MA5800 VLAN/translate mapping subset."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PortContract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, hide_input_in_errors=True)


class MappingSpec(PortContract):
    vlan: int = Field(ge=1, le=4094)
    gemport: int = Field(ge=0, le=4095)
    user_vlan: int = Field(ge=1, le=4094)
    tag_transform: Literal['translate']
    business_type: Literal['multi-service']
    candidate_id: int | None = Field(default=None, ge=0, le=65535)


class ServicePortMapping(MappingSpec):
    olt_binding_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    fsp: str
    ont_id: int = Field(ge=0, le=127)

    @field_validator('fsp')
    @classmethod
    def canonical_fsp(cls, value):
        if re.fullmatch(r'(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)/(?:0|[1-9][0-9]*)', value) is None:
            raise ValueError('Noncanonical F/S/P')
        frame, slot, port = map(int, value.split('/'))
        if frame > 15 or slot > 31 or port > 255:
            raise ValueError('F/S/P exceeds MA5800 command scope')
        return value

    @property
    def mapping_key(self):
        encoded = json.dumps(self.model_dump(mode='json', exclude={'candidate_id'}),
                             sort_keys=True, separators=(',', ':')).encode()
        return sha256(encoded).hexdigest()


class ServicePortProfile(PortContract):
    ipoe: MappingSpec | None = None
    pppoe: MappingSpec | None = None

    @model_validator(mode='after')
    def nonempty(self):
        if self.ipoe is None and self.pppoe is None:
            raise ValueError('At least one explicit WAN mapping is required')
        return self


@dataclass(frozen=True)
class ServicePortDetail:
    port_id: int
    mapping: ServicePortMapping
    state: Literal['up', 'down']


@dataclass(frozen=True)
class GemVlanMapping:
    profile_id: int
    gemport: int
    vlan: int


@dataclass(frozen=True)
class PortRead:
    binding_hash: str
    observation_hash: str
    status: Literal['UNCONFIRMED', 'FOUND', 'ABSENT'] = 'UNCONFIRMED'
    items: tuple[ServicePortDetail, ...] = ()
    evidence_ids: tuple[str, ...] = field(default=(), kw_only=True)
    query_port_id: int | None = None


class PortOperation(PortContract):
    operation_id: str = Field(pattern=r'^[A-Za-z0-9._:-]{1,80}$')
    session_id: str = Field(pattern=r'^[A-Za-z0-9._:-]{1,200}$')
    mapping: ServicePortMapping
    port_id: int = Field(ge=0, le=65535)
    kind: Literal['CREATE', 'DELETE']
    serial_number: str = Field(pattern=r'^[0-9A-F]{16}$')
    line_profile_id: int = Field(ge=0, le=4095)
    service_profile_id: int = Field(ge=0, le=4095)
    consumers: tuple[Literal['IPOE', 'PPPOE'], ...]
    baseline_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    read_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    creation_event_id: str | None = None

    @field_validator('consumers', mode='before')
    @classmethod
    def consumer_roles(cls, value):
        if isinstance(value, list):
            value = tuple(value)
        if not isinstance(value, tuple) or not value or len(set(value)) != len(value):
            raise ValueError('Explicit unique consumers are required')
        return value

    @model_validator(mode='after')
    def scope(self):
        if self.kind == 'CREATE' and (self.creation_event_id is not None or self.mapping.candidate_id != self.port_id):
            raise ValueError('Creation requires the explicit frozen candidate')
        if self.kind == 'DELETE' and not self.creation_event_id:
            raise ValueError('Deletion requires verified creation provenance')
        return self


def port_read_payload(read: PortRead) -> dict:
    return dict(binding_hash=read.binding_hash, observation_hash=read.observation_hash,
        status=read.status, query_port_id=read.query_port_id, evidence_ids=list(read.evidence_ids),
        items=[dict(port_id=item.port_id, mapping=item.mapping.model_dump(mode='json'), state=item.state)
               for item in read.items])


class _DetailPayload(PortContract):
    port_id: int = Field(ge=0, le=65535)
    mapping: ServicePortMapping
    state: Literal['up', 'down']


class _ReadPayload(PortContract):
    binding_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    observation_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    status: Literal['FOUND', 'ABSENT', 'UNCONFIRMED']
    query_port_id: int | None = Field(default=None, ge=0, le=65535)
    evidence_ids: list[str] = Field(default_factory=list)
    items: list[_DetailPayload]


def read_port_payload(payload: dict) -> PortRead:
    value = _ReadPayload.model_validate(payload)
    return PortRead(value.binding_hash, value.observation_hash, value.status,
        tuple(ServicePortDetail(item.port_id, item.mapping, item.state) for item in value.items),
        query_port_id=value.query_port_id, evidence_ids=tuple(value.evidence_ids))


@dataclass(frozen=True)
class PortPreview:
    operation: PortOperation
    read: PortRead

    @property
    def preview_hash(self) -> str:
        payload = dict(operation=self.operation.model_dump(mode='json'), read=port_read_payload(self.read))
        return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def to_payload(self) -> dict:
        return dict(action_code='create_service_port' if self.operation.kind == 'CREATE' else 'delete_service_port',
                    operation=self.operation.model_dump(mode='json'),
                    target=dict(serial_number=self.operation.serial_number, fsp=self.operation.mapping.fsp,
                        ont_id=self.operation.mapping.ont_id, line_profile_id=self.operation.line_profile_id,
                        service_profile_id=self.operation.service_profile_id), consumers=list(self.operation.consumers),
                    read=port_read_payload(self.read), preview_hash=self.preview_hash)
