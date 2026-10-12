import base64
from hashlib import sha256

from app.local_runner.credentials import CredentialResolver, FakeCredentialStore


def valid_config():
    fingerprint = 'SHA256:' + base64.b64encode(sha256(b'fixture-host-key').digest()).decode().rstrip('=')
    return dict(schema_version=1, enabled=True,
        targets={
            'lab.olt': dict(kind='MA5800', host='10.20.0.2', port=22,
                expected_fingerprint=fingerprint),
            'lab.onu': dict(kind='ONU_WEB', url='http://10.20.1.1', adapter_key='neutral-v1',
                pc_interface_name='Fixture Ethernet'),
        },
        access_bindings={
            'lab.olt.access': dict(kind='OLT', username_ref='fixture.olt.user', password_ref='fixture.olt.pass'),
            'lab.onu.access': dict(kind='ONU_WEB', username_ref='fixture.onu.user', password_ref='fixture.onu.pass'),
            'lab.ppp.access': dict(kind='PPPOE', username_ref='fixture.ppp.user', password_ref='fixture.ppp.pass'),
        })


def enrolled_resolver(config=None):
    values = config or valid_config()
    store = FakeCredentialStore()
    resolver = CredentialResolver(store)
    for pair in values['access_bindings'].values():
        resolver.enroll(pair['username_ref'], 'fixture-user-sensitive')
        resolver.enroll(pair['password_ref'], 'fixture-password-sensitive')
    return resolver
