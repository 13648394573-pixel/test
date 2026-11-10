from copy import deepcopy
from hashlib import sha256
import json

import pytest

from app.local_runner.ma5800 import service_port_contracts as contracts
from app.local_runner.configuration import RunnerConfig, RuntimeBinding, resolve_runtime_binding
from app.local_runner.access import PairedAccessResolver
from local_runner_binding_fixtures import valid_config, enrolled_resolver


def mapping_values(**changes):
    return dict(vlan=1000, gemport=1, user_vlan=1000, tag_transform='translate',
                business_type='multi-service', candidate_id=53, **changes)


def model(name, **values):
    cls = getattr(contracts, name, None)
    assert callable(cls), 'Missing strict service-port contract ' + name
    return cls(**values)


@pytest.mark.parametrize('field,value', [('vlan', True), ('vlan', 0), ('vlan', 4095),
    ('gemport', -1), ('gemport', 4096), ('gemport', '1'), ('user_vlan', False),
    ('candidate_id', -1), ('candidate_id', 65536), ('candidate_id', True),
    ('tag_transform', 'transparent'), ('business_type', 'unknown'), ('password', 'secret')])
def test_mapping_contract_rejects_unsafe_or_unverified_values(field, value):
    values = mapping_values()
    values[field] = value
    with pytest.raises(ValueError):
        model('MappingSpec', **values)


def test_mapping_contract_is_frozen_and_candidate_is_optional():
    spec = model('MappingSpec', **mapping_values())
    with pytest.raises(ValueError):
        spec.gemport = 2
    values = mapping_values()
    values.pop('candidate_id')
    assert model('MappingSpec', **values).candidate_id is None


@pytest.mark.parametrize('fsp', ['00/1/2', '0/01/2', '0/1 /2', '16/1/2', '0/32/2', '0/1/256', 'bad'])
def test_complete_mapping_rejects_noncanonical_or_platform_invalid_fsp(fsp):
    with pytest.raises(ValueError):
        model('ServicePortMapping', **mapping_values(), olt_binding_hash='a' * 64, fsp=fsp, ont_id=7)


def test_mapping_key_binds_target_but_not_candidate_allocation():
    values = dict(mapping_values(), olt_binding_hash='a' * 64, fsp='0/1/2', ont_id=7)
    first = model('ServicePortMapping', **values)
    values['candidate_id'] = 54
    assert model('ServicePortMapping', **values).mapping_key == first.mapping_key
    values['ont_id'] = 8
    assert model('ServicePortMapping', **values).mapping_key != first.mapping_key


def configured_profile():
    values = valid_config()
    values['service_port_profiles'] = {'lab.olt': dict(ipoe=mapping_values(), pppoe=mapping_values())}
    return values


def test_new_profile_is_frozen_in_binding_and_later_config_change_cannot_drift():
    values = configured_profile()
    config = RunnerConfig.model_validate(values)
    resolver = enrolled_resolver()
    params = dict(olt_target_ref='lab.olt', onu_web_target_ref='lab.onu', olt_access_ref='lab.olt.access',
                  onu_web_access_ref='lab.onu.access', pppoe_access_ref='lab.ppp.access')
    binding = resolve_runtime_binding(config, params, PairedAccessResolver(config, resolver))
    stored = deepcopy(binding.model_dump(mode='json'))
    assert binding.service_port_profile.ipoe.gemport == 1
    with pytest.raises(TypeError):
        config.service_port_profiles['lab.olt'] = None
    with pytest.raises(ValueError):
        binding.service_port_profile.ipoe.gemport = 2
    values['service_port_profiles']['lab.olt']['ipoe']['gemport'] = 2
    changed = RunnerConfig.model_validate(values)
    assert changed.sha256 != binding.config_sha256
    assert RuntimeBinding.model_validate(stored).service_port_profile.ipoe.gemport == 1


@pytest.mark.parametrize('target', ['unknown', 'lab.onu'])
def test_profile_can_only_bind_an_existing_olt_target(target):
    values = configured_profile()
    values['service_port_profiles'] = {target: values['service_port_profiles']['lab.olt']}
    with pytest.raises(ValueError):
        RunnerConfig.model_validate(values)


def test_old_config_keeps_serialization_hash_and_no_invented_profile():
    config = RunnerConfig.model_validate(valid_config())
    assert dict(config.service_port_profiles) == {}
    assert 'service_port_profiles' not in config.model_dump(mode='json')
    legacy_bytes = json.dumps(valid_config(), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    assert config.sha256 == sha256(legacy_bytes).hexdigest()
