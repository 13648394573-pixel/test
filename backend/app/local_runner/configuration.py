from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Mapping
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from .credentials import REFERENCE_PATTERN


class RunnerConfigurationError(ValueError):
    pass


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, hide_input_in_errors=True)


def private_address(value: str) -> str:
    address = ipaddress.ip_address(value)
    networks = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7')
    if not any(address.version == network.version and address in network
               for network in map(ipaddress.ip_network, networks)):
        raise ValueError('PRIVATE_ADDRESS_REQUIRED')
    return str(address)


def reference(value: str) -> str:
    if not REFERENCE_PATTERN.fullmatch(value):
        raise ValueError('INVALID_REFERENCE')
    return value


class OLTTarget(FrozenModel):
    kind: Literal['MA5800']
    host: str
    port: int = Field(default=22, ge=1, le=65535)
    expected_fingerprint: str

    _host = field_validator('host')(private_address)

    @field_validator('expected_fingerprint')
    @classmethod
    def fingerprint(cls, value: str) -> str:
        if not value.startswith('SHA256:'):
            raise ValueError('INVALID_FINGERPRINT')
        encoded = value[7:]
        try:
            decoded = base64.b64decode(encoded + '=', validate=True)
        except ValueError:
            raise ValueError('INVALID_FINGERPRINT') from None
        if len(decoded) != 32 or base64.b64encode(decoded).decode().rstrip('=') != encoded:
            raise ValueError('INVALID_FINGERPRINT')
        return value


class ONUTarget(FrozenModel):
    kind: Literal['ONU_WEB']
    url: str
    adapter_key: Literal['neutral-v1']
    pc_interface_name: str = Field(min_length=1)

    @field_validator('url')
    @classmethod
    def safe_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
            raise ValueError('INVALID_ONU_URL')
        private_address(parsed.hostname)
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError('INVALID_ONU_PORT')
        return value.rstrip('/')


class AccessBinding(FrozenModel):
    kind: Literal['OLT', 'ONU_WEB', 'PPPOE']
    username_ref: str
    password_ref: str

    _references = field_validator('username_ref', 'password_ref')(reference)

    @model_validator(mode='after')
    def distinct(self):
        if self.username_ref == self.password_ref:
            raise ValueError('DISTINCT_REFERENCES_REQUIRED')
        return self


Target = Annotated[OLTTarget | ONUTarget, Field(discriminator='kind')]


class RunnerConfig(FrozenModel):
    schema_version: Literal[1]
    enabled: bool
    targets: Mapping[str, Target]
    access_bindings: Mapping[str, AccessBinding]

    @field_validator('schema_version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError('INVALID_SCHEMA_VERSION')
        return value

    @model_validator(mode='after')
    def immutable_maps(self):
        for key in (*self.targets, *self.access_bindings):
            reference(key)
        if self.enabled and (
            not {'MA5800', 'ONU_WEB'} <= {target.kind for target in self.targets.values()}
            or not {'OLT', 'ONU_WEB', 'PPPOE'} <= {pair.kind for pair in self.access_bindings.values()}
        ):
            raise ValueError('INCOMPLETE_CONFIGURATION')
        object.__setattr__(self, 'targets', MappingProxyType(dict(self.targets)))
        object.__setattr__(self, 'access_bindings', MappingProxyType(dict(self.access_bindings)))
        return self

    @field_serializer('targets', 'access_bindings')
    def serialize_maps(self, value):
        return {key: item.model_dump(mode='json') for key, item in value.items()}

    @property
    def sha256(self) -> str:
        encoded = json.dumps(self.model_dump(mode='json'), sort_keys=True,
                             separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RunnerConfigurationError('DUPLICATE_CONFIGURATION_KEY')
        result[key] = value
    return result


def load_runner_config(path: Path) -> RunnerConfig:
    try:
        value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
        return RunnerConfig.model_validate(value)
    except (OSError, ValueError, UnicodeError):
        raise RunnerConfigurationError('INVALID_RUNNER_CONFIGURATION') from None


class RuntimeBinding(FrozenModel):
    version: Literal[1] = 1
    config_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    olt_target_ref: str
    onu_web_target_ref: str
    olt: OLTTarget
    onu: ONUTarget
    access_bindings: Mapping[str, AccessBinding]

    _target_refs = field_validator('olt_target_ref', 'onu_web_target_ref')(reference)
    _version = field_validator('version', mode='before')(RunnerConfig.strict_version.__func__)

    @model_validator(mode='after')
    def immutable_access(self):
        if set(self.access_bindings) != {'OLT', 'ONU_WEB', 'PPPOE'}:
            raise ValueError('INCOMPLETE_RUNTIME_BINDING')
        if any(key != pair.kind for key, pair in self.access_bindings.items()):
            raise ValueError('INVALID_RUNTIME_BINDING_KIND')
        object.__setattr__(self, 'access_bindings', MappingProxyType(dict(self.access_bindings)))
        return self

    @field_serializer('access_bindings')
    def serialize_access(self, value):
        return {key: pair.model_dump(mode='json') for key, pair in value.items()}


def resolve_runtime_binding(config: RunnerConfig, parameters: Mapping, pairs) -> RuntimeBinding:
    try:
        if not config.enabled or config.sha256 != pairs.config.sha256:
            raise ValueError('RUNNER_DISABLED')
        olt_ref = parameters['olt_target_ref']
        onu_ref = parameters['onu_web_target_ref']
        olt, onu = config.targets[olt_ref], config.targets[onu_ref]
        if not isinstance(olt, OLTTarget) or not isinstance(onu, ONUTarget):
            raise ValueError('TARGET_KIND_MISMATCH')
        access = {}
        for kind, parameter in (('OLT', 'olt_access_ref'), ('ONU_WEB', 'onu_web_access_ref'),
                                ('PPPOE', 'pppoe_access_ref')):
            access_ref = parameters[parameter]
            pair = config.access_bindings[access_ref]
            if pair.kind != kind or not pairs.available(access_ref):
                raise ValueError('ACCESS_BINDING_UNAVAILABLE')
            access[kind] = pair
        return RuntimeBinding(config_sha256=config.sha256, olt_target_ref=olt_ref,
                              onu_web_target_ref=onu_ref, olt=olt, onu=onu, access_bindings=access)
    except (KeyError, TypeError, ValueError):
        raise RunnerConfigurationError('RUNTIME_BINDING_INVALID') from None
