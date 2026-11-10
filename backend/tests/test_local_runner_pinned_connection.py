import pytest

from app.local_runner.ma5800.transport import (
    MA5800SSHConnector, HostKeyFingerprintMismatchError, host_key_fingerprint,
)


class Key:
    def __init__(self, value):
        self.value = value

    def asbytes(self):
        return self.value

    def get_name(self):
        return 'ssh-ed25519'


class Client:
    def __init__(self, key, *, unknown=False, failure=None):
        self.key, self.unknown, self.failure = key, unknown, failure
        self.closed, self.saved, self.shells = False, False, 0
        self._host_keys = self

    def add(self, *args):
        pass

    def load_system_host_keys(self):
        pass

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        if self.failure == 'connect':
            raise RuntimeError('fixture-password-sensitive')
        if self.unknown:
            self.policy.missing_host_key(self, kwargs['hostname'], self.key)

    def get_transport(self):
        return self

    def get_remote_server_key(self):
        if self.failure == 'key':
            raise RuntimeError('fixture-password-sensitive')
        return self.key

    def invoke_shell(self):
        self.shells += 1

    def close(self):
        self.closed = True

    def save_host_keys(self, *args):
        self.saved = True


def connect(client):
    return MA5800SSHConnector(client_factory=lambda: client).connect(
        hostname='10.20.0.2', port=22, username='fixture-user',
        password='fixture-password-sensitive', expected_fingerprint=host_key_fingerprint(Key(b'A')),
        formal_mode=False)


@pytest.mark.parametrize('unknown', [False, True])
def test_known_hosts_cannot_bypass_pin(unknown):
    client = Client(Key(b'B'), unknown=unknown)
    with pytest.raises(HostKeyFingerprintMismatchError):
        connect(client)
    assert client.closed and not client.saved
    assert client.shells == 0


@pytest.mark.parametrize('unknown', [False, True])
def test_matching_actual_key_is_accepted_without_saving_system_keys(unknown):
    client = Client(Key(b'A'), unknown=unknown)
    assert connect(client) is client
    assert not client.closed and not client.saved


@pytest.mark.parametrize('failure', ['connect', 'key'])
def test_authentication_or_verification_failure_closes_client(failure):
    client = Client(Key(b'A'), failure=failure)
    with pytest.raises(Exception):
        connect(client)
    assert client.closed and client.shells == 0
