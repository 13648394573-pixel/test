from types import SimpleNamespace
import pytest

from app.local_runner.contracts import Observation
from app.local_runner.facts import derive_standard_facts


PARAMETERS = dict(onu_serial_number='AABBCCDDEEFF0011', frame=0, slot=2, pon_port=9,
                  ont_id=12, line_profile_id=10, service_profile_id=10,
                  wan_mode='IPOE', ipoe_vlan=1000, pppoe_vlan=1000, ipoe_ip_index=0, pppoe_ip_index=1)


def event(ref, observations=(), *, status='PASS', action=None, event_type='ACTION_OUTCOME'):
    return SimpleNamespace(event_type=event_type, action_ref=action, step_ref=ref,
        payload_json=dict(ref=ref, status=status,
            observations=[dict(fact_key=o.fact_key, value=o.value, source=o.source) for o in observations]))


def values(action, observations=(), history=(), parameters=None):
    return {o.fact_key: o.value for o in derive_standard_facts(
        action, parameters or PARAMETERS, observations, history)}


def registration():
    return dict(fsp='0/2/9', ont_id=12, serial_number='AABBCCDDEEFF0011',
        line_profile_id=10, service_profile_id=10, run_state='online', match_state='match',
        config_state='normal')


def wan():
    return dict(mode='IPOE', ip_index=0, vlan=1000, status='CONNECTED', ip_address='10.30.0.2')


def epoch():
    return event('PROVISION_IPOE', action='provision_ipoe')


def olt_wan(item=None):
    return Observation('olt.wan.items', [item or wan()], 'MA5800')


def web_wan():
    return tuple(Observation('ipoe.' + key, value, 'ONU_WEB')
                 for key, value in dict(status='Connected', vlan=1000,
                                        ip_address='10.30.0.2', protocol='IPOE').items())


def test_action_success_without_sources_produces_no_standard_pass():
    assert values('snapshot_ont') == {}
    assert values('pc_connectivity_probe') == {}


@pytest.mark.parametrize('change,expected', [({}, True), ({'serial_number': '0000000000000000'}, False),
    ({'fsp': '0/2/8'}, False), ({'ont_id': 13}, False), ({'line_profile_id': 11}, False),
    ({'run_state': 'offline'}, False), ({'match_state': 'initial'}, False)])
def test_registration_identity_and_state(change, expected):
    item = registration()
    item.update(change)
    assert values('snapshot_ont', [Observation('olt.configuration_snapshot',
        dict(registration=item), 'MA5800')])['olt.registration.ready'] is expected


def test_registration_missing_fields_cannot_pass():
    item = registration()
    del item['line_profile_id']
    assert 'olt.registration.ready' not in values('snapshot_ont', [
        Observation('olt.configuration_snapshot', dict(registration=item), 'MA5800')])


def test_autofind_uses_full_identity_and_never_invents_registered_autofind():
    items = [dict(fsp='0/2/9', serial_number='AABBCCDDEEFF0011')]
    assert values('discover_onts', [Observation('olt.autofind.items', items, 'MA5800')]) == {
        'olt.autofind.matched': True}
    assert values('discover_onts', [Observation('olt.autofind.items', [], 'MA5800')]) == {
        'olt.autofind.matched': False}


@pytest.mark.parametrize('change,expected', [({}, True), ({'mode': 'PPPOE'}, False),
    ({'vlan': 99}, False), ({'ip_address': '10.30.0.3'}, False), ({'status': 'DISCONNECTED'}, False)])
def test_address_requires_same_wan_vlan_and_address(change, expected):
    item = wan()
    item.update(change)
    history = [epoch(), event('IPOE_ADDRESS_OLT', [olt_wan(item)])]
    assert values('capture_onu_wan', web_wan(), history)['ipoe.address.valid'] is expected


def test_address_does_not_use_old_attempt_or_missing_web_fields():
    history = [event('IPOE_ADDRESS_OLT', [olt_wan()]), epoch()]
    assert 'ipoe.address.valid' not in values('capture_onu_wan', web_wan(), history)
    assert 'ipoe.address.valid' not in values('capture_onu_wan', web_wan()[:1], [epoch(), event('IPOE_ADDRESS_OLT', [olt_wan()])])


def test_internet_requires_current_ping_and_explicit_path_proof():
    ping = tuple(Observation('ipoe.ping.' + key, value, 'ONU_WEB') for key, value in
        dict(packets_sent=4, packets_received=4, loss_percent='0').items())
    history = [epoch(), event('IPOE_PING_ONU', ping)]
    pc = [Observation('pc.wan.attributed', True, 'PC_PROBE'),
          Observation('pc.ping.packets_sent', 4, 'PC_PROBE'),
          Observation('pc.ping.packets_received', 4, 'PC_PROBE'),
          Observation('pc.ping.loss_percent', 0, 'PC_PROBE')]
    assert values('pc_connectivity_probe', pc, history)['ipoe.internet.pass'] is True
    assert 'ipoe.internet.pass' not in values('pc_connectivity_probe', pc[1:], history)
    assert 'ipoe.internet.pass' not in values('pc_connectivity_probe', pc, [*history, epoch()])
    failed = [*pc[:-1], Observation('pc.ping.loss_percent', 25, 'PC_PROBE')]
    assert values('pc_connectivity_probe', failed, history)['ipoe.internet.pass'] is False


@pytest.mark.parametrize('raw', ['nan', 'inf', None, True])
def test_invalid_numeric_ping_is_not_a_standard_fact(raw):
    assert not values('run_onu_ping', [Observation('ipoe.ping.loss_percent', raw, 'ONU_WEB')])
