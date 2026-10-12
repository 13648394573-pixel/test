import pytest

from app.local_runner.configuration import RunnerConfig
from app.local_runner.access import PairedAccessResolver
from app.local_runner.credentials import CredentialResolver, FakeCredentialStore, UnavailableCredentialError
from local_runner_binding_fixtures import valid_config


def test_pair_requires_both_leaves():
    config = RunnerConfig.model_validate(valid_config())
    resolver = CredentialResolver(FakeCredentialStore())
    pairs = PairedAccessResolver(config, resolver)
    assert pairs.available('lab.olt.access') is False
    resolver.enroll('fixture.olt.user', 'fixture-user-sensitive')
    assert pairs.available('lab.olt.access') is False
    resolver.enroll('fixture.olt.pass', 'fixture-password-sensitive')
    assert pairs.available('lab.olt.access') is True
    user, password = pairs.resolve('lab.olt.access', 'OLT')
    assert user.reveal() == 'fixture-user-sensitive'
    assert password.reveal() == 'fixture-password-sensitive'
    assert 'fixture-password-sensitive' not in repr(password)
    with pytest.raises(UnavailableCredentialError):
        pairs.resolve('lab.olt.access', 'ONU_WEB')
    assert pairs.available('missing') is False
    with pytest.raises(UnavailableCredentialError):
        pairs.resolve('missing', 'OLT')
