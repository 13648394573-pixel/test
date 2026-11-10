import pytest

from app.local_runner.ma5800.transport import SafeMA5800Command


@pytest.mark.parametrize('code,args,expected', [
    ('display_service_port_by_id', (53,), 'display service-port 53'),
    ('read_profile_gem', (10,), 'display ont-lineprofile gpon profile-id 10'),
    ('create_service_port', (53, 1000, '0/1/2', 7, 1, 1000, 'translate', 'multi-service'),
     'service-port 53 vlan 1000 gpon 0/1/2 ont 7 gemport 1 multi-service user-vlan 1000 tag-transform translate'),
])
def test_verified_service_port_commands_render_explicit_scope(code, args, expected):
    assert SafeMA5800Command(code, args).render() == expected


@pytest.mark.parametrize('position,value', [(0, True), (0, -1), (1, 0), (1, 4095),
    (2, '00/1/2'), (2, '0/32/2'), (2, '0/1/2\nundo service-port 99'),
    (3, 128), (4, '1'), (4, 4096), (5, 0), (6, 'transparent'), (7, 'unknown')])
def test_service_port_creation_rejects_unsafe_unverified_or_out_of_scope_arguments(position, value):
    args = [53, 1000, '0/1/2', 7, 1, 1000, 'translate', 'multi-service']
    args[position] = value
    with pytest.raises(ValueError):
        SafeMA5800Command('create_service_port', tuple(args)).render()
