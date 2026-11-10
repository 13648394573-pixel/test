import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.local_runner.configuration import load_runner_config, RunnerConfigurationError
from local_runner_binding_fixtures import valid_config


def load(tmp_path, value):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    return load_runner_config(path)


def test_configuration_resolves_typed_targets_and_is_immutable(tmp_path):
    config = load(tmp_path, valid_config())
    assert config.targets['lab.olt'].host == '10.20.0.2'
    assert config.targets['lab.onu'].pc_interface_name == 'Fixture Ethernet'
    assert len(config.sha256) == 64
    with pytest.raises(TypeError):
        config.targets['other'] = config.targets['lab.olt']
    with pytest.raises(ValueError):
        config.targets['lab.olt'].host = '10.20.0.3'


def test_disabled_example_and_default_do_not_enable_runner(tmp_path):
    assert Settings(_env_file=None).local_runner_config_path is None
    disabled = load(tmp_path, dict(schema_version=1, enabled=False, targets={}, access_bindings={}))
    assert disabled.enabled is False


@pytest.mark.parametrize('host', ['8.8.8.8', '127.0.0.1', '0.0.0.0', '224.0.0.1', 'hostname', '169.254.1.1'])
def test_invalid_olt_host_is_rejected(tmp_path, host):
    value = valid_config()
    value['targets']['lab.olt']['host'] = host
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, value)


@pytest.mark.parametrize('url', [
    'http://fixture-user:fixture-password-sensitive@10.20.1.1',
    'http://8.8.8.8', 'http://127.0.0.1', 'file:///config',
    'http://10.20.1.1?password=fixture-password-sensitive', 'http://10.20.1.1#fragment',
    'http://10.20.1.1:99999', 'http://['])
def test_unsafe_onu_url_is_rejected_without_echoing_input(tmp_path, url):
    value = valid_config()
    value['targets']['lab.onu']['url'] = url
    with pytest.raises(RunnerConfigurationError) as error:
        load(tmp_path, value)
    assert 'fixture-password-sensitive' not in str(error.value)


@pytest.mark.parametrize('change', [
    ('port', 0), ('port', 65536), ('port', True),
    ('expected_fingerprint', 'not-a-fingerprint'), ('password', 'fixture-password-sensitive'),
])
def test_invalid_target_fields_are_rejected(tmp_path, change):
    value = valid_config()
    value['targets']['lab.olt'][change[0]] = change[1]
    with pytest.raises(RunnerConfigurationError) as error:
        load(tmp_path, value)
    assert 'fixture-password-sensitive' not in str(error.value)


def test_unknown_adapter_or_ambiguous_pair_is_rejected(tmp_path):
    value = valid_config()
    value['targets']['lab.onu']['adapter_key'] = 'unknown'
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, value)
    value = valid_config()
    pair = value['access_bindings']['lab.olt.access']
    pair['password_ref'] = pair['username_ref']
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, value)
    pair['password_ref'] = 'http://fixture-password-sensitive'
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, value)


def test_extra_and_duplicate_target_keys_are_rejected(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{"schema_version":1,"schema_version":2,"enabled":false,"targets":{},"access_bindings":{}}')
    with pytest.raises(RunnerConfigurationError):
        load_runner_config(path)
    path.write_text('{"schema_version":1,"enabled":false,"targets":{"lab.olt":{},"lab.olt":{}},"access_bindings":{}}')
    with pytest.raises(RunnerConfigurationError):
        load_runner_config(path)
    value = valid_config()
    value['unexpected'] = 'fixture-password-sensitive'
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, value)


def test_missing_invalid_or_unreadable_config_is_controlled(tmp_path):
    with pytest.raises(RunnerConfigurationError):
        load_runner_config(tmp_path / 'missing.json')
    with pytest.raises(RunnerConfigurationError):
        load_runner_config(tmp_path)
    path = tmp_path / 'config.json'
    for content in [b'not json', b'\xff']:
        path.write_bytes(content)
        with pytest.raises(RunnerConfigurationError):
            load_runner_config(path)


def test_enabled_configuration_requires_targets_and_pairs(tmp_path):
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, dict(schema_version=1, enabled=True, targets={}, access_bindings={}))


@pytest.mark.parametrize('field,value', [('schema_version', True), ('enabled', 'true')])
def test_configuration_flags_are_not_coerced(tmp_path, field, value):
    config = valid_config()
    config[field] = value
    with pytest.raises(RunnerConfigurationError):
        load(tmp_path, config)
