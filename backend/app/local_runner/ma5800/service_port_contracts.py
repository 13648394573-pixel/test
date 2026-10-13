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
    evidence_ids: tuple[str, ...] = field(default=(), init=False)
    query_port_id: int | None = None
