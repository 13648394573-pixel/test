import json

import pytest

from app.local_runner.configuration import RunnerConfig
from app.local_runner.credentials import CredentialResolver, FakeCredentialStore
from app.local_runner import setup
from local_runner_binding_fixtures import valid_config


def test_enrollment_only_stores_values_in_credential_store(capsys):
    config = RunnerConfig.model_validate(valid_config())
    resolver = CredentialResolver(FakeCredentialStore())
    answers = iter(['fixture-user-sensitive', 'fixture-password-sensitive'])
    setup.enroll_access(config, 'lab.olt.access', resolver, lambda prompt: next(answers))
    assert resolver.resolve('fixture.olt.user').reveal() == 'fixture-user-sensitive'
    assert resolver.resolve('fixture.olt.pass').reveal() == 'fixture-password-sensitive'
    assert 'sensitive' not in capsys.readouterr().out
    assert 'sensitive' not in config.model_dump_json()


def test_enrollment_rolls_back_both_previous_values_on_store_failure():
    class Store(FakeCredentialStore):
        def set_password(self, service_name, reference, value):
            if value == 'new-password':
                raise RuntimeError('fixture-password-sensitive')
            super().set_password(service_name, reference, value)
    resolver = CredentialResolver(Store())
    resolver.enroll('fixture.olt.user', 'old-user')
    resolver.enroll('fixture.olt.pass', 'old-password')
    answers = iter(['new-user', 'new-password'])
    with pytest.raises(setup.SetupEnrollmentError) as error:
        setup.enroll_access(RunnerConfig.model_validate(valid_config()), 'lab.olt.access',
            resolver, lambda prompt: next(answers))
    assert 'fixture-password-sensitive' not in str(error.value)
    assert resolver.resolve('fixture.olt.user').reveal() == 'old-user'
    assert resolver.resolve('fixture.olt.pass').reveal() == 'old-password'


def test_setup_rejects_noninteractive_input_without_enrollment(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(valid_config()), encoding='utf-8')
    monkeypatch.setattr(setup.sys.stdin, 'isatty', lambda: False)
    assert setup.main(['--config', str(path), '--access-ref', 'lab.olt.access']) == 2
    assert 'sensitive' not in capsys.readouterr().out


def test_setup_rejects_plaintext_arguments_without_echoing_them(capsys):
    assert setup.main(['--password', 'fixture-password-sensitive']) == 2
    captured = capsys.readouterr()
    assert 'fixture-password-sensitive' not in captured.out + captured.err
